"""Background worker for PDF merge operations."""

from PyQt6.QtCore import QThread, pyqtSignal
from typing import List

from core.merger import PDFMerger, MergeResult


class MergeWorker(QThread):
    """Runs PDF merge in a background thread."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, input_paths: List[str], output_path: str, parent=None):
        super().__init__(parent)
        self._input_paths = input_paths
        self._output_path = output_path
        self._cancelled = False
        self._merger = PDFMerger()

    def run(self):
        try:
            result = self._merger.merge(
                self._input_paths,
                self._output_path,
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
