"""Background worker for PDF to Image conversion."""

from PyQt6.QtCore import QThread, pyqtSignal
from typing import List, Optional

from core.pdf_to_image import PDFToImageConverter, PDFToImageResult, ImageFormat


class PDFToImageWorker(QThread):
    """Runs PDF-to-Image conversion in a background thread."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        input_path: str,
        output_dir: str,
        page_numbers: Optional[List[int]] = None,
        image_format: ImageFormat = ImageFormat.PNG,
        dpi: int = 300,
        jpeg_quality: int = 90,
        parent=None,
    ):
        super().__init__(parent)
        self._input_path = input_path
        self._output_dir = output_dir
        self._page_numbers = page_numbers
        self._image_format = image_format
        self._dpi = dpi
        self._jpeg_quality = jpeg_quality
        self._cancelled = False
        self._converter = PDFToImageConverter()

    def run(self):
        try:
            result = self._converter.convert(
                self._input_path,
                self._output_dir,
                page_numbers=self._page_numbers,
                image_format=self._image_format,
                dpi=self._dpi,
                jpeg_quality=self._jpeg_quality,
                on_progress=self._on_progress,
                is_cancelled=self._is_cancelled,
            )
            if not self._cancelled:
                self.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(f"Unexpected error: {str(e)}")

    def cancel(self):
        self._cancelled = True

    def _on_progress(self, step: int, total: int, message: str):
        if not self._cancelled:
            self.progress.emit(step, total, message)

    def _is_cancelled(self) -> bool:
        return self._cancelled
