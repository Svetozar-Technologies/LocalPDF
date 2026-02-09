"""
PDF Compression Engine.

Uses binary search on JPEG quality to compress a PDF to a target file size.
Falls back to DPI reduction if quality alone is insufficient.
"""

import io
import os
import tempfile
import fitz  # PyMuPDF
from PIL import Image
from dataclasses import dataclass
from typing import Callable, Optional, List, Tuple


@dataclass
class CompressionResult:
    success: bool
    output_path: str = ""
    original_size: int = 0
    compressed_size: int = 0
    compression_ratio: float = 0.0
    quality_used: int = 0
    scale_used: float = 1.0
    pages_processed: int = 0
    images_found: int = 0
    error_message: str = ""
    already_small: bool = False
    target_impossible: bool = False
    minimum_achievable_size: int = 0
    text_only: bool = False


@dataclass
class CompressionConfig:
    input_path: str
    output_path: str
    target_size_bytes: int
    min_quality: int = 5
    max_quality: int = 95
    min_scale: float = 0.1
    max_scale: float = 1.0
    binary_search_tolerance_bytes: int = 102400  # 100KB
    max_iterations: int = 12


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


class PDFCompressor:
    """Main PDF compression engine."""

    def compress(
        self,
        config: CompressionConfig,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> CompressionResult:
        """Orchestrate the full compression pipeline."""
        original_size = os.path.getsize(config.input_path)

        # Step 1: Check if already small enough
        if original_size <= config.target_size_bytes:
            return CompressionResult(
                success=True,
                output_path=config.input_path,
                original_size=original_size,
                compressed_size=original_size,
                compression_ratio=0.0,
                already_small=True,
            )

        self._report(on_progress, 1, 100, "Opening PDF...")

        # Step 2: Lossless optimization
        try:
            doc = fitz.open(config.input_path)
        except Exception as e:
            return CompressionResult(success=False, error_message=f"Cannot open PDF: {e}")

        if doc.is_encrypted:
            doc.close()
            return CompressionResult(success=False, error_message="PDF is password-protected.")

        pages = len(doc)
        doc.close()

        self._report(on_progress, 5, 100, "Applying lossless optimizations...")

        if self._check_cancel(is_cancelled):
            return CompressionResult(success=False, error_message="Cancelled.")

        lossless_bytes = self._apply_lossless_optimization(config.input_path)
        lossless_size = len(lossless_bytes)

        self._report(on_progress, 15, 100,
                     f"Lossless: {self._fmt(original_size)} -> {self._fmt(lossless_size)}")

        if lossless_size <= config.target_size_bytes:
            self._write_bytes(config.output_path, lossless_bytes)
            return CompressionResult(
                success=True,
                output_path=config.output_path,
                original_size=original_size,
                compressed_size=lossless_size,
                compression_ratio=self._ratio(original_size, lossless_size),
                quality_used=100,
                scale_used=1.0,
                pages_processed=pages,
            )

        # Step 3: Count images
        image_xrefs = self._get_image_xrefs_from_bytes(lossless_bytes)
        image_count = len(image_xrefs)

        if image_count == 0:
            # Text-only PDF: lossless is the best we can do
            self._write_bytes(config.output_path, lossless_bytes)
            return CompressionResult(
                success=True,
                output_path=config.output_path,
                original_size=original_size,
                compressed_size=lossless_size,
                compression_ratio=self._ratio(original_size, lossless_size),
                pages_processed=pages,
                images_found=0,
                text_only=True,
            )

        self._report(on_progress, 20, 100,
                     f"Found {image_count} images. Starting quality optimization...")

        if self._check_cancel(is_cancelled):
            return CompressionResult(success=False, error_message="Cancelled.")

        # Step 4: Binary search on JPEG quality
        result_bytes, quality = self._binary_search_quality(
            lossless_bytes, config.target_size_bytes,
            config.min_quality, config.max_quality,
            config.binary_search_tolerance_bytes, config.max_iterations,
            on_progress, is_cancelled,
        )

        if self._check_cancel(is_cancelled):
            return CompressionResult(success=False, error_message="Cancelled.")

        if result_bytes is not None:
            compressed_size = len(result_bytes)
            self._write_bytes(config.output_path, result_bytes)
            return CompressionResult(
                success=True,
                output_path=config.output_path,
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=self._ratio(original_size, compressed_size),
                quality_used=quality,
                scale_used=1.0,
                pages_processed=pages,
                images_found=image_count,
            )

        # Step 5: Binary search on scale factor (quality alone insufficient)
        self._report(on_progress, 70, 100, "Reducing image resolution...")

        result_bytes, scale = self._binary_search_scale(
            lossless_bytes, config.target_size_bytes,
            config.min_scale, config.max_scale,
            config.min_quality, config.binary_search_tolerance_bytes,
            min(config.max_iterations, 8),
            on_progress, is_cancelled,
        )

        if self._check_cancel(is_cancelled):
            return CompressionResult(success=False, error_message="Cancelled.")

        if result_bytes is not None:
            compressed_size = len(result_bytes)
            self._write_bytes(config.output_path, result_bytes)
            return CompressionResult(
                success=True,
                output_path=config.output_path,
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=self._ratio(original_size, compressed_size),
                quality_used=config.min_quality,
                scale_used=scale,
                pages_processed=pages,
                images_found=image_count,
            )

        # Step 6: Target impossible — compute minimum achievable
        self._report(on_progress, 95, 100, "Computing minimum achievable size...")
        min_bytes = self._rebuild_pdf_with_quality(
            lossless_bytes, config.min_quality, config.min_scale,
        )
        min_size = len(min_bytes) if min_bytes else lossless_size

        return CompressionResult(
            success=False,
            original_size=original_size,
            compressed_size=min_size,
            pages_processed=pages,
            images_found=image_count,
            target_impossible=True,
            minimum_achievable_size=min_size,
            error_message=(
                f"Cannot compress to target. "
                f"Minimum achievable size is {self._fmt(min_size)}."
            ),
        )

    def _apply_lossless_optimization(self, input_path: str) -> bytes:
        """Apply lossless optimizations: garbage collection, deflation, metadata strip."""
        doc = fitz.open(input_path)
        doc.set_metadata({})
        try:
            doc.del_xml_metadata()
        except Exception:
            pass

        buf = io.BytesIO()
        doc.save(buf, garbage=4, deflate=True, clean=True, no_new_id=True)
        doc.close()
        return buf.getvalue()

    def _get_image_xrefs_from_bytes(self, pdf_bytes: bytes) -> List[int]:
        """Get list of all unique image xref numbers."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        xrefs = set()
        for page_num in range(len(doc)):
            page = doc[page_num]
            for img in page.get_images(full=True):
                xrefs.add(img[0])  # xref number
        doc.close()
        return sorted(xrefs)

    def _rebuild_pdf_with_quality(
        self,
        source_bytes: bytes,
        quality: int,
        scale: float = 1.0,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
        progress_start: int = 0,
        progress_end: int = 100,
    ) -> Optional[bytes]:
        """Re-encode all images at given quality and scale, return PDF bytes."""
        doc = fitz.open(stream=source_bytes, filetype="pdf")
        image_xrefs = set()
        for page in doc:
            for img in page.get_images(full=True):
                image_xrefs.add(img[0])

        total_images = len(image_xrefs)
        processed = 0

        for xref in sorted(image_xrefs):
            if self._check_cancel(is_cancelled):
                doc.close()
                return None

            try:
                img_info = doc.extract_image(xref)
                if img_info is None or not img_info.get("image"):
                    continue

                # Skip very small images (< 4KB) - not worth re-encoding
                if len(img_info["image"]) < 4096:
                    continue

                # Check xref dict for special properties
                xref_dict = doc.xref_object(xref)

                # Skip mask images (1-bit masks used for transparency)
                if "/ImageMask true" in xref_dict:
                    continue

                # Skip SMask images themselves (they are referenced by other images)
                if "/SMask" not in xref_dict:
                    # Check if THIS xref is used as someone else's SMask — skip it
                    pass

                pil_img = Image.open(io.BytesIO(img_info["image"]))
                orig_mode = pil_img.mode

                # Scale if needed
                if scale < 1.0:
                    new_w = max(1, int(pil_img.width * scale))
                    new_h = max(1, int(pil_img.height * scale))
                    pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                else:
                    new_w, new_h = pil_img.width, pil_img.height

                # Handle CMYK images: convert to RGB properly
                if pil_img.mode == "CMYK":
                    # Invert CMYK values first (Pillow uses inverted CMYK)
                    from PIL import ImageChops
                    pil_img = ImageChops.invert(pil_img)
                    pil_img = pil_img.convert("RGB")
                elif pil_img.mode == "RGBA":
                    # Flatten alpha onto white background
                    bg = Image.new("RGB", pil_img.size, (255, 255, 255))
                    bg.paste(pil_img, mask=pil_img.split()[3])
                    pil_img = bg
                elif pil_img.mode not in ("RGB", "L"):
                    pil_img = pil_img.convert("RGB")

                # Encode to JPEG
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=quality, optimize=True)
                jpeg_bytes = buf.getvalue()

                # Replace stream and update xref dict
                # compress=0 is CRITICAL: prevents PyMuPDF from wrapping JPEG
                # data in zlib, which would corrupt it (0x78 0xda instead of 0xFF 0xD8)
                doc.update_stream(xref, jpeg_bytes, compress=0)
                doc.xref_set_key(xref, "Filter", "/DCTDecode")
                doc.xref_set_key(xref, "Width", str(new_w))
                doc.xref_set_key(xref, "Height", str(new_h))
                if pil_img.mode == "L":
                    doc.xref_set_key(xref, "ColorSpace", "/DeviceGray")
                else:
                    doc.xref_set_key(xref, "ColorSpace", "/DeviceRGB")
                doc.xref_set_key(xref, "BitsPerComponent", "8")
                doc.xref_set_key(xref, "DecodeParms", "null")

            except Exception:
                # Skip problematic images rather than crashing
                pass

            processed += 1
            if on_progress and total_images > 0:
                pct = progress_start + int(
                    (progress_end - progress_start) * processed / total_images
                )
                self._report(on_progress, pct, 100, f"Processing image {processed}/{total_images}")

        # Save with garbage collection
        # CRITICAL: deflate=False — do NOT re-compress JPEG streams with zlib.
        # Using deflate=True would wrap JPEG data in FlateDecode without updating
        # the Filter dict, causing "Not a JPEG file: starts with 0x78" errors.
        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=4, deflate=False)
        doc.close()
        return out_buf.getvalue()

    def _binary_search_quality(
        self,
        source_bytes: bytes,
        target_bytes: int,
        min_q: int,
        max_q: int,
        tolerance: int,
        max_iterations: int,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> Tuple[Optional[bytes], int]:
        """Binary search on JPEG quality to hit target size."""
        lo, hi = min_q, max_q
        best_result = None
        best_quality = max_q

        for iteration in range(max_iterations):
            if self._check_cancel(is_cancelled):
                return (None, 0)

            mid = (lo + hi) // 2
            pct = 20 + int(50 * iteration / max_iterations)
            self._report(on_progress, pct, 100,
                         f"Trying quality {mid}% (iteration {iteration + 1}/{max_iterations})...")

            result = self._rebuild_pdf_with_quality(source_bytes, quality=mid)
            if result is None:
                return (None, 0)  # Cancelled

            result_size = len(result)

            if result_size <= target_bytes:
                best_result = result
                best_quality = mid
                lo = mid + 1  # Try higher quality
            else:
                hi = mid - 1  # Need lower quality

            # Close enough?
            if best_result and abs(len(best_result) - target_bytes) <= tolerance:
                break

            if lo > hi:
                break

        return (best_result, best_quality)

    def _binary_search_scale(
        self,
        source_bytes: bytes,
        target_bytes: int,
        min_scale: float,
        max_scale: float,
        quality: int,
        tolerance: int,
        max_iterations: int,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> Tuple[Optional[bytes], float]:
        """Binary search on DPI scale factor with quality fixed at min_quality."""
        lo, hi = min_scale, max_scale
        best_result = None
        best_scale = max_scale

        for iteration in range(max_iterations):
            if self._check_cancel(is_cancelled):
                return (None, 0.0)

            mid = (lo + hi) / 2
            pct = 70 + int(25 * iteration / max_iterations)
            self._report(on_progress, pct, 100,
                         f"Trying scale {mid:.0%} (iteration {iteration + 1}/{max_iterations})...")

            result = self._rebuild_pdf_with_quality(source_bytes, quality=quality, scale=mid)
            if result is None:
                return (None, 0.0)

            result_size = len(result)

            if result_size <= target_bytes:
                best_result = result
                best_scale = mid
                lo = mid + 0.05  # Try higher scale (better quality)
            else:
                hi = mid - 0.05

            if best_result and abs(len(best_result) - target_bytes) <= tolerance:
                break

            if lo > hi:
                break

        return (best_result, best_scale)

    @staticmethod
    def _report(cb: Optional[ProgressCallback], step: int, total: int, msg: str):
        if cb:
            cb(step, total, msg)

    @staticmethod
    def _check_cancel(cb: Optional[CancelCheck]) -> bool:
        return cb() if cb else False

    @staticmethod
    def _write_bytes(path: str, data: bytes):
        with open(path, "wb") as f:
            f.write(data)

    @staticmethod
    def _fmt(size_bytes: int) -> str:
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.0f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"

    @staticmethod
    def _ratio(original: int, compressed: int) -> float:
        if original == 0:
            return 0.0
        return (1 - compressed / original) * 100
