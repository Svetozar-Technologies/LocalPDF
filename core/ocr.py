"""OCR Engine — Tesseract-based offline text recognition."""

import io
import os
import fitz
from PIL import Image
from dataclasses import dataclass, field
from typing import Callable, Optional, List


@dataclass
class OCRResult:
    success: bool
    text: str = ""
    page_texts: List[str] = field(default_factory=list)
    output_path: str = ""
    pages_processed: int = 0
    error_message: str = ""
    tesseract_missing: bool = False


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


class OCREngine:
    """Offline OCR using Tesseract via pytesseract."""

    def extract_text_from_image(
        self,
        image_path: str,
        language: str = "eng",
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> OCRResult:
        """Extract text from a single image file."""
        try:
            import pytesseract
        except ImportError:
            return OCRResult(
                success=False,
                error_message="pytesseract is not installed. Run: pip install pytesseract",
                tesseract_missing=True,
            )

        if not self._check_tesseract():
            return OCRResult(
                success=False,
                error_message="Tesseract OCR is not installed on this system.",
                tesseract_missing=True,
            )

        self._report(on_progress, 10, 100, "Loading image...")

        try:
            img = Image.open(image_path)
        except Exception as e:
            return OCRResult(success=False, error_message=f"Cannot open image: {e}")

        if is_cancelled and is_cancelled():
            return OCRResult(success=False, error_message="Cancelled.")

        self._report(on_progress, 30, 100, "Running OCR...")

        try:
            text = pytesseract.image_to_string(img, lang=language)
            img.close()
        except Exception as e:
            return OCRResult(success=False, error_message=f"OCR failed: {e}")

        self._report(on_progress, 100, 100, "Done!")

        return OCRResult(
            success=True,
            text=text.strip(),
            page_texts=[text.strip()],
            pages_processed=1,
        )

    def extract_text_from_pdf(
        self,
        pdf_path: str,
        language: str = "eng",
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> OCRResult:
        """Extract text from a PDF by rendering each page and running OCR."""
        try:
            import pytesseract
        except ImportError:
            return OCRResult(
                success=False,
                error_message="pytesseract is not installed.",
                tesseract_missing=True,
            )

        if not self._check_tesseract():
            return OCRResult(
                success=False,
                error_message="Tesseract OCR is not installed on this system.",
                tesseract_missing=True,
            )

        self._report(on_progress, 5, 100, "Opening PDF...")

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            return OCRResult(success=False, error_message=f"Cannot open PDF: {e}")

        if doc.is_encrypted:
            doc.close()
            return OCRResult(success=False, error_message="PDF is password-protected.")

        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            return OCRResult(success=False, error_message="PDF has no pages.")

        page_texts = []
        all_text_parts = []

        try:
            for i in range(total_pages):
                if is_cancelled and is_cancelled():
                    doc.close()
                    return OCRResult(success=False, error_message="Cancelled.")

                self._report(on_progress, 5 + int(90 * i / total_pages), 100,
                             f"OCR page {i + 1}/{total_pages}...")

                # First try to extract embedded text
                page = doc[i]
                embedded_text = page.get_text().strip()

                if embedded_text:
                    # Page already has text
                    page_texts.append(embedded_text)
                    all_text_parts.append(f"--- Page {i + 1} ---\n{embedded_text}")
                else:
                    # Render page as image for OCR
                    zoom = 300 / 72  # 300 DPI
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)
                    pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                    ocr_text = pytesseract.image_to_string(pil_img, lang=language).strip()
                    pil_img.close()

                    page_texts.append(ocr_text)
                    all_text_parts.append(f"--- Page {i + 1} ---\n{ocr_text}")

            doc.close()

        except Exception as e:
            try:
                doc.close()
            except Exception:
                pass
            return OCRResult(success=False, error_message=f"OCR failed: {e}")

        self._report(on_progress, 100, 100, "Done!")

        full_text = "\n\n".join(all_text_parts)
        return OCRResult(
            success=True,
            text=full_text,
            page_texts=page_texts,
            pages_processed=total_pages,
        )

    def make_searchable_pdf(
        self,
        input_path: str,
        output_path: str,
        language: str = "eng",
        on_progress: Optional[ProgressCallback] = None,
        is_cancelled: Optional[CancelCheck] = None,
    ) -> OCRResult:
        """Create a searchable PDF by adding invisible text layer over scanned pages."""
        try:
            import pytesseract
        except ImportError:
            return OCRResult(
                success=False,
                error_message="pytesseract is not installed.",
                tesseract_missing=True,
            )

        if not self._check_tesseract():
            return OCRResult(
                success=False,
                error_message="Tesseract OCR is not installed on this system.",
                tesseract_missing=True,
            )

        self._report(on_progress, 5, 100, "Opening PDF...")

        try:
            doc = fitz.open(input_path)
        except Exception as e:
            return OCRResult(success=False, error_message=f"Cannot open PDF: {e}")

        if doc.is_encrypted:
            doc.close()
            return OCRResult(success=False, error_message="PDF is password-protected.")

        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            return OCRResult(success=False, error_message="PDF has no pages.")

        page_texts = []

        try:
            for i in range(total_pages):
                if is_cancelled and is_cancelled():
                    doc.close()
                    return OCRResult(success=False, error_message="Cancelled.")

                self._report(on_progress, 5 + int(85 * i / total_pages), 100,
                             f"OCR page {i + 1}/{total_pages}...")

                page = doc[i]
                existing_text = page.get_text().strip()

                if existing_text:
                    page_texts.append(existing_text)
                    continue

                # Render page at high DPI for OCR
                zoom = 300 / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # Get word-level OCR data with bounding boxes
                ocr_data = pytesseract.image_to_data(
                    pil_img, lang=language, output_type=pytesseract.Output.DICT
                )
                pil_img.close()

                page_text_parts = []

                # Insert invisible text at each word's position
                for j in range(len(ocr_data["text"])):
                    word = ocr_data["text"][j].strip()
                    if not word:
                        continue

                    conf = int(ocr_data["conf"][j])
                    if conf < 0:
                        continue

                    # Convert from image coordinates to PDF coordinates
                    x = ocr_data["left"][j] / zoom
                    y = ocr_data["top"][j] / zoom
                    w = ocr_data["width"][j] / zoom
                    h = ocr_data["height"][j] / zoom

                    # Calculate appropriate font size based on word height
                    fontsize = max(h * 0.85, 4)

                    # Insert invisible text
                    point = fitz.Point(x, y + h * 0.85)
                    rc = page.insert_text(
                        point,
                        word,
                        fontsize=fontsize,
                        color=(0, 0, 0),
                        render_mode=3,  # invisible text
                    )

                    page_text_parts.append(word)

                page_texts.append(" ".join(page_text_parts))

            self._report(on_progress, 92, 100, "Saving searchable PDF...")

            doc.save(output_path, garbage=4)
            doc.close()

            self._report(on_progress, 100, 100, "Done!")

            full_text = "\n\n".join(
                f"--- Page {i + 1} ---\n{t}" for i, t in enumerate(page_texts)
            )

            return OCRResult(
                success=True,
                text=full_text,
                page_texts=page_texts,
                output_path=output_path,
                pages_processed=total_pages,
            )

        except Exception as e:
            try:
                doc.close()
            except Exception:
                pass
            return OCRResult(success=False, error_message=f"OCR failed: {e}")

    @staticmethod
    def get_available_languages() -> List[str]:
        """Get list of installed Tesseract languages."""
        try:
            import pytesseract
            langs = pytesseract.get_languages()
            # Filter out 'osd' (orientation/script detection)
            return [l for l in langs if l != "osd"]
        except Exception:
            return ["eng"]

    @staticmethod
    def _check_tesseract() -> bool:
        """Check if Tesseract binary is available."""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    @staticmethod
    def _report(cb: Optional[ProgressCallback], step: int, total: int, msg: str):
        if cb:
            cb(step, total, msg)
