"""Background worker for PDF watermarking."""

from PyQt6.QtCore import QThread, pyqtSignal

from core.watermark import (
    PDFWatermarker, TextWatermarkConfig, ImageWatermarkConfig, WatermarkResult,
)


class WatermarkWorker(QThread):
    """Runs PDF watermarking in a background thread."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        mode: str,  # "text" or "image"
        text_config: TextWatermarkConfig = None,
        image_config: ImageWatermarkConfig = None,
        parent=None,
    ):
        super().__init__(parent)
        self._mode = mode
        self._text_config = text_config
        self._image_config = image_config
        self._cancelled = False
        self._watermarker = PDFWatermarker()

    def run(self):
        try:
            if self._mode == "text" and self._text_config:
                result = self._watermarker.add_text_watermark(
                    self._text_config,
                    on_progress=self._on_progress,
                    is_cancelled=self._is_cancelled,
                )
            elif self._mode == "image" and self._image_config:
                result = self._watermarker.add_image_watermark(
                    self._image_config,
                    on_progress=self._on_progress,
                    is_cancelled=self._is_cancelled,
                )
            else:
                result = WatermarkResult(success=False, error_message="Invalid configuration.")

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
