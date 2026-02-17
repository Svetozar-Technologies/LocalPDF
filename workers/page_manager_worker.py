"""Background workers for Page Manager thumbnail rendering and saving."""

from typing import Dict, List

from PIL import Image
from PyQt6.QtCore import QThread, pyqtSignal

from core.page_manager import PageManager, PageSource


class ThumbnailWorker(QThread):
    """Renders PDF page thumbnails in background."""

    thumbnail_ready = pyqtSignal(int, object)  # (page_index, PIL.Image)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, pdf_path: str, thumb_width: int = 150, parent=None):
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._thumb_width = thumb_width
        self._cancelled = False

    def run(self):
        try:
            manager = PageManager()
            manager.render_thumbnails(
                self._pdf_path,
                thumb_width=self._thumb_width,
                on_thumbnail=self._on_thumbnail,
                is_cancelled=self._is_cancelled,
            )
            if not self._cancelled:
                self.finished.emit()
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))

    def _on_thumbnail(self, index: int, img: Image.Image):
        if not self._cancelled:
            self.thumbnail_ready.emit(index, img)

    def cancel(self):
        self._cancelled = True

    def _is_cancelled(self) -> bool:
        return self._cancelled


class SaveWorker(QThread):
    """Applies page operations and saves the PDF."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)  # PageManagerResult
    error = pyqtSignal(str)

    def __init__(
        self,
        pdf_path: str,
        output_path: str,
        page_order: List[int],
        rotations: Dict[int, int],
        parent=None,
    ):
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._output_path = output_path
        self._page_order = page_order
        self._rotations = rotations
        self._cancelled = False

    def run(self):
        try:
            manager = PageManager()
            result = manager.apply_operations(
                self._pdf_path,
                self._output_path,
                self._page_order,
                self._rotations,
                on_progress=self._on_progress,
                is_cancelled=self._is_cancelled,
            )
            if not self._cancelled:
                self.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(f"Save error: {str(e)}")

    def cancel(self):
        self._cancelled = True

    def _on_progress(self, step: int, total: int, message: str):
        if not self._cancelled:
            self.progress.emit(step, total, message)

    def _is_cancelled(self) -> bool:
        return self._cancelled


class EnhancedSaveWorker(QThread):
    """Builds a new PDF from a list of PageSource objects with annotations."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)  # PageManagerResult
    error = pyqtSignal(str)

    def __init__(self, page_sources: List[PageSource], output_path: str, parent=None):
        super().__init__(parent)
        self._page_sources = page_sources
        self._output_path = output_path
        self._cancelled = False

    def run(self):
        try:
            manager = PageManager()
            result = manager.apply_enhanced_operations(
                self._page_sources,
                self._output_path,
                on_progress=self._on_progress,
                is_cancelled=self._is_cancelled,
            )
            if not self._cancelled:
                self.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(f"Save error: {str(e)}")

    def cancel(self):
        self._cancelled = True

    def _on_progress(self, step: int, total: int, message: str):
        if not self._cancelled:
            self.progress.emit(step, total, message)

    def _is_cancelled(self) -> bool:
        return self._cancelled


class FullPageRenderWorker(QThread):
    """Renders a high-resolution page image for preview."""

    finished = pyqtSignal(object)  # PIL.Image
    error = pyqtSignal(str)

    def __init__(self, source: PageSource, max_width: int = 800, parent=None):
        super().__init__(parent)
        self._source = source
        self._max_width = max_width
        self._cancelled = False

    def run(self):
        try:
            manager = PageManager()
            img = manager.render_full_page(self._source, max_width=self._max_width)
            if not self._cancelled:
                self.finished.emit(img)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(f"Render error: {str(e)}")

    def cancel(self):
        self._cancelled = True
