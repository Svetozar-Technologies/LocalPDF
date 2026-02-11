"""Background worker for OCR operations."""

from PyQt6.QtCore import QThread, pyqtSignal

from core.ocr import OCREngine, OCRResult


class OCRWorker(QThread):
    """Runs OCR in a background thread."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        mode: str,  # "extract_image", "extract_pdf", "searchable_pdf"
        input_path: str,
        output_path: str = "",
        language: str = "eng",
        parent=None,
    ):
        super().__init__(parent)
        self._mode = mode
        self._input_path = input_path
        self._output_path = output_path
        self._language = language
        self._cancelled = False
        self._engine = OCREngine()

    def run(self):
        try:
            if self._mode == "extract_image":
                result = self._engine.extract_text_from_image(
                    self._input_path,
                    language=self._language,
                    on_progress=self._on_progress,
                    is_cancelled=self._is_cancelled,
                )
            elif self._mode == "extract_pdf":
                result = self._engine.extract_text_from_pdf(
                    self._input_path,
                    language=self._language,
                    on_progress=self._on_progress,
                    is_cancelled=self._is_cancelled,
                )
            elif self._mode == "searchable_pdf":
                result = self._engine.make_searchable_pdf(
                    self._input_path,
                    self._output_path,
                    language=self._language,
                    on_progress=self._on_progress,
                    is_cancelled=self._is_cancelled,
                )
            else:
                result = OCRResult(success=False, error_message="Invalid OCR mode.")

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
