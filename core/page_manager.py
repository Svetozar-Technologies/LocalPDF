"""PDF Page Manager engine — reorder, rotate, delete, insert, annotate pages."""

import copy
import io
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class PageSourceType(Enum):
    ORIGINAL = "original"
    EXTERNAL = "external"
    BLANK = "blank"


@dataclass
class TextAnnotation:
    text: str
    x: float  # normalized 0-1
    y: float  # normalized 0-1
    font_size: int = 14
    color: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # RGB 0-1


@dataclass
class ImageAnnotation:
    image_path: str
    x: float  # normalized 0-1
    y: float  # normalized 0-1
    width: float  # normalized 0-1 of page width
    height: float  # normalized 0-1 of page height


@dataclass
class PageSource:
    source_type: PageSourceType
    source_path: str = ""
    source_page_index: int = 0
    rotation: int = 0
    width: float = 595.0   # A4 default
    height: float = 842.0  # A4 default
    text_annotations: List[TextAnnotation] = field(default_factory=list)
    image_annotations: List[ImageAnnotation] = field(default_factory=list)


@dataclass
class PageManagerResult:
    success: bool
    output_path: str = ""
    total_pages: int = 0
    error_message: str = ""


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


class PageManager:
    """Render thumbnails and apply page operations (reorder, rotate, delete, insert, annotate)."""

    def render_thumbnails(
        self,
        pdf_path: str,
        thumb_width: int = 150,
        on_thumbnail: Optional[Callable[[int, Image.Image], None]] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> List[Image.Image]:
        """Render page thumbnails from a PDF.

        Args:
            pdf_path: Path to the PDF file.
            thumb_width: Width of each thumbnail in pixels.
            on_thumbnail: Callback (page_index, image) fired after each page renders.
            is_cancelled: Callable returning True to abort early.

        Returns:
            List of PIL Images (one per page).
        """
        doc = fitz.open(pdf_path)
        thumbnails: List[Image.Image] = []

        try:
            for i in range(len(doc)):
                if is_cancelled and is_cancelled():
                    break

                page = doc[i]
                # Calculate zoom to fit thumb_width
                zoom = thumb_width / page.rect.width
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)

                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                thumbnails.append(img)

                if on_thumbnail:
                    on_thumbnail(i, img)
        finally:
            doc.close()

        return thumbnails

    def apply_operations(
        self,
        pdf_path: str,
        output_path: str,
        page_order: List[int],
        rotations: Dict[int, int],
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> PageManagerResult:
        """Apply reorder, rotate, and delete operations and save.

        Args:
            pdf_path: Input PDF path.
            output_path: Output PDF path.
            page_order: List of original page indices in desired order.
                        Pages not in the list are deleted.
            rotations: Dict mapping original page index to rotation degrees (0/90/180/270).
            on_progress: Progress callback (step, total, message).
            is_cancelled: Callable returning True to abort.

        Returns:
            PageManagerResult with success status.
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(page_order)

            if total_pages == 0:
                doc.close()
                return PageManagerResult(
                    success=False, error_message="No pages selected to save.",
                )

            if on_progress:
                on_progress(0, total_pages + 1, "Preparing pages...")

            # Select pages in order (this reorders and removes unselected pages)
            doc.select(page_order)

            # Apply rotations
            for new_idx, orig_idx in enumerate(page_order):
                if is_cancelled and is_cancelled():
                    doc.close()
                    return PageManagerResult(success=False, error_message="Cancelled.")

                if orig_idx in rotations and rotations[orig_idx] != 0:
                    page = doc[new_idx]
                    page.set_rotation(rotations[orig_idx])

                if on_progress:
                    on_progress(new_idx + 1, total_pages + 1, f"Processing page {new_idx + 1}/{total_pages}")

            if is_cancelled and is_cancelled():
                doc.close()
                return PageManagerResult(success=False, error_message="Cancelled.")

            # Save
            if on_progress:
                on_progress(total_pages, total_pages + 1, "Saving PDF...")

            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            doc.save(output_path, garbage=3, deflate=True)
            doc.close()

            return PageManagerResult(
                success=True,
                output_path=output_path,
                total_pages=total_pages,
            )

        except Exception as e:
            return PageManagerResult(success=False, error_message=str(e))

    # ------------------------------------------------------------------ Enhanced methods

    def render_thumbnail_for_page(
        self, source: PageSource, thumb_width: int = 150,
    ) -> Image.Image:
        """Render a single thumbnail for any PageSource type."""
        if source.source_type == PageSourceType.BLANK:
            # White image at correct aspect ratio
            aspect = source.height / source.width if source.width > 0 else 842 / 595
            h = int(thumb_width * aspect)
            return Image.new("RGB", (thumb_width, h), (255, 255, 255))

        # ORIGINAL or EXTERNAL — render from PDF
        doc = fitz.open(source.source_path)
        try:
            page = doc[source.source_page_index]
            zoom = thumb_width / page.rect.width
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        finally:
            doc.close()

    def render_full_page(
        self, source: PageSource, max_width: int = 800,
    ) -> Image.Image:
        """Render a high-res page image for preview, including annotations."""
        if source.source_type == PageSourceType.BLANK:
            aspect = source.height / source.width if source.width > 0 else 842 / 595
            h = int(max_width * aspect)
            img = Image.new("RGB", (max_width, h), (255, 255, 255))
        else:
            doc = fitz.open(source.source_path)
            try:
                page = doc[source.source_page_index]
                zoom = max_width / page.rect.width
                mat = fitz.Matrix(zoom, zoom)
                if source.rotation:
                    mat = mat.prerotate(source.rotation)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            finally:
                doc.close()

        # Composite annotations onto the rendered image
        if source.text_annotations or source.image_annotations:
            img = self._composite_annotations(img, source)
        return img

    def _composite_annotations(
        self, img: Image.Image, source: PageSource,
    ) -> Image.Image:
        """Overlay text and image annotations onto a rendered page image."""
        from PIL import ImageDraw, ImageFont

        # --- Text annotations ---
        if source.text_annotations:
            draw = ImageDraw.Draw(img)
            # Scale factor: PDF points → pixel coordinates
            scale = img.width / source.width if source.width > 0 else 1.0

            for ann in source.text_annotations:
                font_size_px = max(8, int(ann.font_size * scale))
                font = self._get_font(font_size_px)

                px = int(ann.x * img.width)
                py = int(ann.y * img.height)
                color = tuple(int(c * 255) for c in ann.color)

                draw.text((px, py), ann.text, fill=color, font=font)

        # --- Image annotations (signatures, overlays) ---
        for ann in source.image_annotations:
            if not os.path.exists(ann.image_path):
                continue
            try:
                overlay = Image.open(ann.image_path).convert("RGBA")
                ow = max(1, int(ann.width * img.width))
                oh = max(1, int(ann.height * img.height))
                overlay = overlay.resize((ow, oh), Image.Resampling.LANCZOS)

                px = max(0, min(int(ann.x * img.width), img.width - ow))
                py = max(0, min(int(ann.y * img.height), img.height - oh))

                img_rgba = img.convert("RGBA")
                img_rgba.paste(overlay, (px, py), overlay)
                img = img_rgba.convert("RGB")
            except Exception:
                pass

        return img

    @staticmethod
    def _get_font(size: int):
        """Try system fonts, fall back to PIL default."""
        from PIL import ImageFont

        for path in (
            "/System/Library/Fonts/Helvetica.ttc",        # macOS
            "/System/Library/Fonts/SFNSText.ttf",          # macOS alt
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
            "C:/Windows/Fonts/arial.ttf",                  # Windows
        ):
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    def apply_enhanced_operations(
        self,
        page_sources: List[PageSource],
        output_path: str,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> PageManagerResult:
        """Build a new PDF from a list of PageSource objects with annotations."""
        try:
            total = len(page_sources)
            if total == 0:
                return PageManagerResult(success=False, error_message="No pages to save.")

            if on_progress:
                on_progress(0, total + 1, "Preparing pages...")

            out_doc = fitz.open()  # new empty doc
            doc_cache: Dict[str, fitz.Document] = {}

            try:
                for idx, src in enumerate(page_sources):
                    if is_cancelled and is_cancelled():
                        return PageManagerResult(success=False, error_message="Cancelled.")

                    if src.source_type == PageSourceType.BLANK:
                        out_doc.new_page(width=src.width, height=src.height)
                    else:
                        # Get or open source doc
                        if src.source_path not in doc_cache:
                            doc_cache[src.source_path] = fitz.open(src.source_path)
                        src_doc = doc_cache[src.source_path]
                        out_doc.insert_pdf(
                            src_doc,
                            from_page=src.source_page_index,
                            to_page=src.source_page_index,
                        )

                    page = out_doc[-1]  # last inserted page

                    # Apply rotation
                    if src.rotation:
                        page.set_rotation(src.rotation)

                    # Apply text annotations
                    for ann in src.text_annotations:
                        px = ann.x * page.rect.width
                        py = ann.y * page.rect.height
                        page.insert_text(
                            fitz.Point(px, py),
                            ann.text,
                            fontsize=ann.font_size,
                            color=ann.color,
                        )

                    # Apply image annotations
                    for ann in src.image_annotations:
                        if os.path.exists(ann.image_path):
                            rect = fitz.Rect(
                                ann.x * page.rect.width,
                                ann.y * page.rect.height,
                                (ann.x + ann.width) * page.rect.width,
                                (ann.y + ann.height) * page.rect.height,
                            )
                            page.insert_image(rect, filename=ann.image_path)

                    if on_progress:
                        on_progress(idx + 1, total + 1, f"Processing page {idx + 1}/{total}")

                if is_cancelled and is_cancelled():
                    return PageManagerResult(success=False, error_message="Cancelled.")

                if on_progress:
                    on_progress(total, total + 1, "Saving PDF...")

                os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                out_doc.save(output_path, garbage=3, deflate=True)

                return PageManagerResult(
                    success=True, output_path=output_path, total_pages=total,
                )
            finally:
                out_doc.close()
                for d in doc_cache.values():
                    d.close()

        except Exception as e:
            return PageManagerResult(success=False, error_message=str(e))
