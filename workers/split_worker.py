"""Background worker for PDF split/extract operations."""

from PyQt6.QtCore import QThread, pyqtSignal
from typing import List

from core.splitter import PDFSplitter, SplitResult


class SplitWorker(QThread):
    """Runs PDF split/extract in a background thread."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        input_path: str,
        output_path: str,
        output_dir: str,
        page_numbers: List[int],
        split_individual: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._input_path = input_path
        self._output_path = output_path
        self._output_dir = output_dir
        self._page_numbers = page_numbers
        self._split_individual = split_individual
        self._cancelled = False
        self._splitter = PDFSplitter()

    def run(self):
        try:
            if self._split_individual:
                result = self._splitter.split_individual(
                    self._input_path,
                    self._output_dir,
                    self._page_numbers,
                    on_progress=self._on_progress,
                    is_cancelled=self._is_cancelled,
                )
            else:
                result = self._splitter.extract_pages(
                    self._input_path,
                    self._output_path,
                    self._page_numbers,
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
