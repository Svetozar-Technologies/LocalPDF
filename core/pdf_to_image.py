"""PDF to Image Converter Engine."""

import os
import fitz
from PIL import Image
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, List


class ImageFormat(Enum):
    PNG = "png"
    JPEG = "jpeg"


@dataclass
class PDFToImageResult:
    success: bool
    output_dir: str = ""
    output_paths: List[str] = field(default_factory=list)
    pages_exported: int = 0
    error_message: str = ""


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


class PDFToImageConverter:
    """Converts PDF pages to images (PNG or JPEG)."""

    def convert(
        self,
        input_path: str,
        output_dir: str,
        page_numbers: Optional[List[int]] = None,
        image_format: ImageFormat = ImageFormat.PNG,
        dpi: int = 300,
        jpeg_quality: int = 90,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> PDFToImageResult:
        """
        Convert PDF pages to images.

        Args:
            input_path: Path to the input PDF.
            output_dir: Directory to save images.
            page_numbers: 0-indexed page numbers to export. None = all pages.
            image_format: PNG or JPEG.
            dpi: Resolution (72, 150, 300, 600).
            jpeg_quality: JPEG quality (1-100), only used for JPEG format.
            on_progress: Progress callback.
            is_cancelled: Cancellation check.
        """
        self._report(on_progress, 0, 100, "Opening PDF...")

        try:
            doc = fitz.open(input_path)
        except Exception as e:
            return PDFToImageResult(success=False, error_message=f"Cannot open PDF: {e}")

        if doc.is_encrypted:
            doc.close()
            return PDFToImageResult(success=False, error_message="PDF is password-protected.")

        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            return PDFToImageResult(success=False, error_message="PDF has no pages.")

        # Determine which pages to export
        if page_numbers is None:
            page_numbers = list(range(total_pages))
        else:
            # Validate page numbers
            for p in page_numbers:
                if p < 0 or p >= total_pages:
                    doc.close()
                    return PDFToImageResult(
                        success=False,
                        error_message=f"Page {p + 1} is out of range (document has {total_pages} pages).",
                    )

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        total = len(page_numbers)
        pad_width = len(str(max(page_numbers) + 1))
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        ext = "png" if image_format == ImageFormat.PNG else "jpg"
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)

        output_paths = []

        try:
            for i, page_num in enumerate(page_numbers):
                if is_cancelled and is_cancelled():
                    doc.close()
                    return PDFToImageResult(success=False, error_message="Cancelled.")

                page_label = str(page_num + 1).zfill(pad_width)
                out_name = f"{base_name}_page_{page_label}.{ext}"
                out_path = os.path.join(output_dir, out_name)

                self._report(on_progress, i, total,
                             f"Exporting page {page_num + 1} ({i + 1}/{total})...")

                page = doc[page_num]
                pix = page.get_pixmap(matrix=mat)

                # Convert to PIL Image for consistent saving
                pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                if image_format == ImageFormat.JPEG:
                    pil_img.save(out_path, format="JPEG", quality=jpeg_quality, optimize=True)
                else:
                    pil_img.save(out_path, format="PNG", optimize=True)

                output_paths.append(out_path)

            doc.close()

            self._report(on_progress, total, total, "Done!")

            return PDFToImageResult(
                success=True,
                output_dir=output_dir,
                output_paths=output_paths,
                pages_exported=len(output_paths),
            )

        except Exception as e:
            doc.close()
            return PDFToImageResult(success=False, error_message=f"Export failed: {e}")

    @staticmethod
    def _report(cb: Optional[ProgressCallback], step: int, total: int, msg: str):
        if cb:
            cb(step, total, msg)
