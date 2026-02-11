"""PDF Watermark Engine."""

import os
import fitz
from dataclasses import dataclass
from typing import Callable, Optional, List


@dataclass
class TextWatermarkConfig:
    input_path: str
    output_path: str
    text: str = "CONFIDENTIAL"
    font_size: int = 60
    color: tuple = (0.5, 0.5, 0.5)  # RGB 0-1
    opacity: float = 0.15
    rotation: float = 45.0  # degrees
    page_numbers: Optional[List[int]] = None  # None = all pages


@dataclass
class ImageWatermarkConfig:
    input_path: str
    output_path: str
    image_path: str = ""
    opacity: float = 0.3
    scale: float = 0.3  # relative to page width
    position: str = "center"  # center, top-left, top-right, bottom-left, bottom-right
    page_numbers: Optional[List[int]] = None  # None = all pages


@dataclass
class WatermarkResult:
    success: bool
    output_path: str = ""
    pages_processed: int = 0
    error_message: str = ""


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


class PDFWatermarker:
    """Adds text or image watermarks to PDF files."""

    def add_text_watermark(
        self,
        config: TextWatermarkConfig,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> WatermarkResult:
        """Add a diagonal text watermark to PDF pages."""
        self._report(on_progress, 5, 100, "Opening PDF...")

        try:
            doc = fitz.open(config.input_path)
        except Exception as e:
            return WatermarkResult(success=False, error_message=f"Cannot open PDF: {e}")

        if doc.is_encrypted:
            doc.close()
            return WatermarkResult(success=False, error_message="PDF is password-protected.")

        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            return WatermarkResult(success=False, error_message="PDF has no pages.")

        # Determine which pages to watermark
        pages = config.page_numbers if config.page_numbers is not None else list(range(total_pages))
        total = len(pages)

        try:
            for i, page_num in enumerate(pages):
                if is_cancelled and is_cancelled():
                    doc.close()
                    return WatermarkResult(success=False, error_message="Cancelled.")

                if page_num < 0 or page_num >= total_pages:
                    continue

                self._report(on_progress, 5 + int(85 * i / total), 100,
                             f"Watermarking page {page_num + 1} ({i + 1}/{total})...")

                page = doc[page_num]
                rect = page.rect
                center_x = rect.width / 2
                center_y = rect.height / 2

                # Create text writer for the watermark
                # Use a shape to draw rotated text
                tw = fitz.TextWriter(page.rect)

                # Calculate font size and text position
                font = fitz.Font("helv")
                fontsize = config.font_size

                # Measure text width
                text_width = font.text_length(config.text, fontsize=fontsize)

                # Insert centered text
                text_point = fitz.Point(
                    center_x - text_width / 2,
                    center_y + fontsize / 3,
                )
                tw.append(text_point, config.text, font=font, fontsize=fontsize)

                # Apply with rotation and opacity
                morph = (fitz.Point(center_x, center_y), fitz.Matrix(1, 0, 0, 1, 0, 0).prerotate(config.rotation))
                r, g, b = config.color
                tw.write_text(page, morph=morph, color=(r, g, b), opacity=config.opacity)

            self._report(on_progress, 92, 100, "Saving watermarked PDF...")

            doc.save(config.output_path, garbage=4)
            doc.close()

            self._report(on_progress, 100, 100, "Done!")

            return WatermarkResult(
                success=True,
                output_path=config.output_path,
                pages_processed=total,
            )

        except Exception as e:
            try:
                doc.close()
            except Exception:
                pass
            return WatermarkResult(success=False, error_message=f"Watermarking failed: {e}")

    def add_image_watermark(
        self,
        config: ImageWatermarkConfig,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> WatermarkResult:
        """Add an image watermark (logo) to PDF pages."""
        if not config.image_path or not os.path.exists(config.image_path):
            return WatermarkResult(success=False, error_message="Watermark image not found.")

        self._report(on_progress, 5, 100, "Opening PDF...")

        try:
            doc = fitz.open(config.input_path)
        except Exception as e:
            return WatermarkResult(success=False, error_message=f"Cannot open PDF: {e}")

        if doc.is_encrypted:
            doc.close()
            return WatermarkResult(success=False, error_message="PDF is password-protected.")

        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            return WatermarkResult(success=False, error_message="PDF has no pages.")

        pages = config.page_numbers if config.page_numbers is not None else list(range(total_pages))
        total = len(pages)

        try:
            for i, page_num in enumerate(pages):
                if is_cancelled and is_cancelled():
                    doc.close()
                    return WatermarkResult(success=False, error_message="Cancelled.")

                if page_num < 0 or page_num >= total_pages:
                    continue

                self._report(on_progress, 5 + int(85 * i / total), 100,
                             f"Watermarking page {page_num + 1} ({i + 1}/{total})...")

                page = doc[page_num]
                rect = page.rect

                # Calculate image dimensions
                img_w = rect.width * config.scale
                # Get image aspect ratio
                from PIL import Image as PILImage
                pil_img = PILImage.open(config.image_path)
                aspect = pil_img.height / pil_img.width
                pil_img.close()
                img_h = img_w * aspect

                # Position the watermark
                x, y = self._get_position(
                    rect.width, rect.height, img_w, img_h, config.position
                )

                img_rect = fitz.Rect(x, y, x + img_w, y + img_h)
                page.insert_image(
                    img_rect,
                    filename=config.image_path,
                    overlay=True,
                    alpha=int(config.opacity * 255),
                )

            self._report(on_progress, 92, 100, "Saving watermarked PDF...")

            doc.save(config.output_path, garbage=4)
            doc.close()

            self._report(on_progress, 100, 100, "Done!")

            return WatermarkResult(
                success=True,
                output_path=config.output_path,
                pages_processed=total,
            )

        except Exception as e:
            try:
                doc.close()
            except Exception:
                pass
            return WatermarkResult(success=False, error_message=f"Watermarking failed: {e}")

    @staticmethod
    def _get_position(
        page_w: float, page_h: float,
        img_w: float, img_h: float,
        position: str,
    ) -> tuple:
        """Calculate (x, y) for the watermark based on position string."""
        margin = 36  # 0.5 inch

        if position == "top-left":
            return (margin, margin)
        elif position == "top-right":
            return (page_w - img_w - margin, margin)
        elif position == "bottom-left":
            return (margin, page_h - img_h - margin)
        elif position == "bottom-right":
            return (page_w - img_w - margin, page_h - img_h - margin)
        else:  # center
            return ((page_w - img_w) / 2, (page_h - img_h) / 2)

    @staticmethod
    def _report(cb: Optional[ProgressCallback], step: int, total: int, msg: str):
        if cb:
            cb(step, total, msg)
