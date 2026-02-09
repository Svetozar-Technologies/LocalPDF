"""Image to PDF Converter Engine."""

import os
import fitz
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, List
from PIL import Image


class PageOrientation(Enum):
    AUTO = "auto"
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


@dataclass
class ImageToPdfResult:
    success: bool
    output_path: str = ""
    page_count: int = 0
    output_size: int = 0
    error_message: str = ""


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


class ImageToPdfConverter:
    """Converts a list of images into a single PDF, one image per page."""

    A4_W = 595.276  # A4 width in points (portrait)
    A4_H = 841.890  # A4 height in points (portrait)
    MARGIN = 18      # 0.25 inch margin

    def convert(
        self,
        image_paths: List[str],
        output_path: str,
        orientation: PageOrientation = PageOrientation.AUTO,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> ImageToPdfResult:
        if not image_paths:
            return ImageToPdfResult(success=False, error_message="No images provided.")

        total = len(image_paths)
        self._report(on_progress, 0, total, "Creating PDF...")

        doc = fitz.open()

        try:
            for i, img_path in enumerate(image_paths):
                if is_cancelled and is_cancelled():
                    doc.close()
                    return ImageToPdfResult(success=False, error_message="Cancelled.")

                name = os.path.basename(img_path)
                self._report(on_progress, i, total, f"Adding {name} ({i + 1}/{total})...")

                try:
                    # Get image dimensions to determine page orientation
                    pil_img = Image.open(img_path)
                    img_w, img_h = pil_img.size
                    pil_img.close()
                except Exception as e:
                    doc.close()
                    return ImageToPdfResult(
                        success=False,
                        error_message=f"Cannot read image '{name}': {e}",
                    )

                # Determine page dimensions
                page_w, page_h = self._get_page_size(img_w, img_h, orientation)

                # Create new page
                page = doc.new_page(width=page_w, height=page_h)

                # Calculate image rect with margins, preserving aspect ratio
                usable_w = page_w - 2 * self.MARGIN
                usable_h = page_h - 2 * self.MARGIN

                scale = min(usable_w / img_w, usable_h / img_h)
                draw_w = img_w * scale
                draw_h = img_h * scale

                # Center on page
                x = self.MARGIN + (usable_w - draw_w) / 2
                y = self.MARGIN + (usable_h - draw_h) / 2

                img_rect = fitz.Rect(x, y, x + draw_w, y + draw_h)
                page.insert_image(img_rect, filename=img_path)

            self._report(on_progress, total, total, "Saving PDF...")
            doc.save(output_path, garbage=4)
            doc.close()

            output_size = os.path.getsize(output_path)
            return ImageToPdfResult(
                success=True,
                output_path=output_path,
                page_count=total,
                output_size=output_size,
            )

        except Exception as e:
            try:
                doc.close()
            except Exception:
                pass
            return ImageToPdfResult(success=False, error_message=f"Conversion failed: {e}")

    def _get_page_size(
        self, img_w: int, img_h: int, orientation: PageOrientation
    ) -> tuple:
        if orientation == PageOrientation.PORTRAIT:
            return (self.A4_W, self.A4_H)
        elif orientation == PageOrientation.LANDSCAPE:
            return (self.A4_H, self.A4_W)
        else:  # AUTO
            if img_w > img_h:
                return (self.A4_H, self.A4_W)  # landscape
            return (self.A4_W, self.A4_H)  # portrait

    @staticmethod
    def _report(cb: Optional[ProgressCallback], step: int, total: int, msg: str):
        if cb:
            cb(step, total, msg)
