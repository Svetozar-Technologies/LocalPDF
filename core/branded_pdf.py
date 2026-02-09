"""
Branded PDF generator for PrepLadder-style slide decks.

Features:
- Cover page with subject name, optional cover image
- 2 slides per page (stacked vertically)
- Diagonal watermark on every content page
- Page numbers
"""

import io
import os
import fitz  # PyMuPDF
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import Color, HexColor
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
from dataclasses import dataclass
from typing import Optional, Callable, List


@dataclass
class BrandingConfig:
    input_pdf_path: str
    output_path: str
    subject_name: str = "Subject"
    subtitle: str = ""
    cover_image_path: Optional[str] = None
    watermark_text: str = "PREPLADDER"
    watermark_opacity: float = 0.06
    watermark_color: str = "#888888"
    watermark_font_size: int = 72
    slides_per_page: int = 2
    page_margin: float = 36.0  # 0.5 inch in points
    slide_spacing: float = 22.0  # ~0.3 inch
    add_page_numbers: bool = True
    include_cover: bool = True


@dataclass
class BrandedResult:
    success: bool
    output_path: str = ""
    total_slides: int = 0
    total_pages: int = 0
    error_message: str = ""


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


class BrandedPDFGenerator:
    """Generates a branded PDF from a plain slide PDF."""

    def generate(
        self,
        config: BrandingConfig,
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> BrandedResult:
        """Main entry point."""
        try:
            src_doc = fitz.open(config.input_pdf_path)
        except Exception as e:
            return BrandedResult(success=False, error_message=f"Cannot open source PDF: {e}")

        total_slides = len(src_doc)
        if total_slides == 0:
            src_doc.close()
            return BrandedResult(success=False, error_message="Source PDF has no pages.")

        if on_progress:
            on_progress(5, 100, "Rendering slides as images...")

        # Render all slides to images
        slide_images = []
        for i in range(total_slides):
            if is_cancelled and is_cancelled():
                src_doc.close()
                return BrandedResult(success=False, error_message="Cancelled.")

            img = self._render_slide_to_image(src_doc[i], dpi=200)
            slide_images.append(img)

            if on_progress:
                pct = 5 + int(50 * (i + 1) / total_slides)
                on_progress(pct, 100, f"Rendering slide {i + 1}/{total_slides}...")

        src_doc.close()

        if on_progress:
            on_progress(60, 100, "Composing branded PDF...")

        # Create output PDF with reportlab
        page_w, page_h = A4
        c = Canvas(config.output_path, pagesize=A4)
        c.setTitle(f"{config.subject_name} - PrepLadder Notes")
        c.setAuthor("PrepLadder")

        total_pages = 0

        # Cover page
        if config.include_cover:
            self._draw_cover_page(c, config)
            c.showPage()
            total_pages += 1

        # Content pages
        margin = config.page_margin
        spacing = config.slide_spacing
        usable_w = page_w - 2 * margin
        usable_h = page_h - 2 * margin
        spp = config.slides_per_page
        slot_h = (usable_h - (spp - 1) * spacing) / spp

        for i in range(0, total_slides, spp):
            if is_cancelled and is_cancelled():
                return BrandedResult(success=False, error_message="Cancelled.")

            batch = slide_images[i: i + spp]

            # Draw watermark first (behind slides)
            self._draw_watermark(c, config)

            for j, pil_img in enumerate(batch):
                # Calculate position: stack from top
                slot_top_y = page_h - margin - j * (slot_h + spacing)

                # Scale image to fit slot
                scale_w = usable_w / pil_img.width
                scale_h = slot_h / pil_img.height
                scale = min(scale_w, scale_h)
                draw_w = pil_img.width * scale
                draw_h = pil_img.height * scale

                # Center horizontally
                x = margin + (usable_w - draw_w) / 2
                # Align to top of slot
                y = slot_top_y - draw_h

                # Convert PIL to reportlab ImageReader
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                buf.seek(0)
                c.drawImage(ImageReader(buf), x, y, draw_w, draw_h)

            # Page number
            if config.add_page_numbers:
                content_page_num = (i // spp) + 1
                self._draw_page_number(c, content_page_num)

            c.showPage()
            total_pages += 1

            if on_progress:
                pct = 60 + int(35 * (i + spp) / total_slides)
                on_progress(min(pct, 95), 100,
                            f"Composing page {total_pages}...")

        c.save()

        if on_progress:
            on_progress(100, 100, "Done!")

        return BrandedResult(
            success=True,
            output_path=config.output_path,
            total_slides=total_slides,
            total_pages=total_pages,
        )

    @staticmethod
    def _render_slide_to_image(page: fitz.Page, dpi: int = 200) -> Image.Image:
        """Render a PDF page to a PIL Image."""
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    @staticmethod
    def _draw_cover_page(c: Canvas, config: BrandingConfig):
        """Draw the branded cover page."""
        w, h = A4

        # Background
        c.setFillColor(HexColor("#1a1a2e"))
        c.rect(0, 0, w, h, fill=1, stroke=0)

        # Accent bar at top
        c.setFillColor(HexColor("#4da6ff"))
        c.rect(0, h - 8, w, 8, fill=1, stroke=0)

        # PrepLadder branding
        c.setFillColor(HexColor("#ffffff"))
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(w / 2, h - 50, "PrepLadder")

        # Subject name (large)
        c.setFont("Helvetica-Bold", 48)
        spaced = "  ".join(config.subject_name.upper())
        c.drawCentredString(w / 2, h - 130, spaced)

        # Subtitle
        if config.subtitle:
            c.setFont("Helvetica", 18)
            c.setFillColor(HexColor("#aaaaaa"))
            c.drawCentredString(w / 2, h - 170, config.subtitle)

        # Cover image
        if config.cover_image_path and os.path.exists(config.cover_image_path):
            try:
                img = Image.open(config.cover_image_path)
                max_w = w * 0.65
                max_h = h * 0.45
                scale = min(max_w / img.width, max_h / img.height)
                draw_w = img.width * scale
                draw_h = img.height * scale
                x = (w - draw_w) / 2
                y = (h - draw_h) / 2 - 30

                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                c.drawImage(ImageReader(buf), x, y, draw_w, draw_h, mask="auto")
            except Exception:
                pass

        # Decorative line
        c.setStrokeColor(HexColor("#4da6ff"))
        c.setLineWidth(2)
        c.line(w * 0.15, 90, w * 0.85, 90)

        # Bottom text
        c.setFillColor(HexColor("#cccccc"))
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(w / 2, 55, "RESOLVE 2026")
        c.setFont("Helvetica", 11)
        c.setFillColor(HexColor("#888888"))
        c.drawCentredString(w / 2, 35, "100% Local Processing")

    @staticmethod
    def _draw_watermark(c: Canvas, config: BrandingConfig):
        """Draw diagonal watermark text across the page."""
        w, h = A4
        c.saveState()

        # Parse color
        try:
            hex_color = config.watermark_color.lstrip("#")
            r = int(hex_color[0:2], 16) / 255
            g = int(hex_color[2:4], 16) / 255
            b = int(hex_color[4:6], 16) / 255
        except Exception:
            r, g, b = 0.53, 0.53, 0.53

        c.setFillColor(Color(r, g, b, alpha=config.watermark_opacity))
        c.setFont("Helvetica-Bold", config.watermark_font_size)
        c.translate(w / 2, h / 2)
        c.rotate(45)
        c.drawCentredString(0, 0, config.watermark_text)
        c.restoreState()

    @staticmethod
    def _draw_page_number(c: Canvas, page_num: int):
        """Draw page number at bottom center."""
        w, _ = A4
        c.setFont("Helvetica", 9)
        c.setFillColor(HexColor("#666666"))
        c.drawCentredString(w / 2, 20, f"Page {page_num}")
