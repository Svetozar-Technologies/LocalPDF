"""QThread worker for PDF compression."""

from PyQt6.QtCore import QThread, pyqtSignal
from core.compressor import PDFCompressor, CompressionConfig, CompressionResult


class CompressWorker(QThread):
    """Worker thread for PDF compression."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, config: CompressionConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._cancelled = False
        self._compressor = PDFCompressor()

    def run(self):
        try:
            result = self._compressor.compress(
                self._config,
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
