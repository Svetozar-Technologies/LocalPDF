"""Dialog for selecting and inserting pages from another PDF."""

from typing import List, Optional

from PIL import Image
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGridLayout, QWidget, QFrame, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QImage, QPixmap

from core.page_manager import PageSource, PageSourceType, PageManager
from workers.page_manager_worker import ThumbnailWorker


class _InsertThumbnail(QFrame):
    """Thumbnail cell for a page in the source PDF."""

    clicked = pyqtSignal(int, object)  # (page_index, QMouseEvent)

    THUMB_WIDTH = 120

    def __init__(self, page_index: int, parent=None):
        super().__init__(parent)
        self._page_index = page_index
        self._selected = False
        self.setFixedSize(140, 175)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 2)
        layout.setSpacing(2)

        self._image_label = QLabel()
        self._image_label.setFixedSize(self.THUMB_WIDTH, 145)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet("background: #f0f0f0; border: 1px solid #ddd; border-radius: 3px;")
        layout.addWidget(self._image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel(f"Page {self._page_index + 1}")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("font-size: 10px; color: #666;")
        layout.addWidget(self._label)

    def set_thumbnail(self, img: Image.Image):
        img_rgb = img.convert("RGB")
        data = img_rgb.tobytes()
        qimg = QImage(data, img_rgb.width, img_rgb.height, 3 * img_rgb.width, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(
            self.THUMB_WIDTH, 145,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)

    @property
    def page_index(self) -> int:
        return self._page_index

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool):
        self._selected = value
        if value:
            self.setStyleSheet("_InsertThumbnail { border: 2px solid #2196F3; border-radius: 5px; background: #E3F2FD; }")
        else:
            self.setStyleSheet("")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._page_index, event)
        super().mousePressEvent(event)


class InsertPagesDialog(QDialog):
    """Modal dialog for picking pages from another PDF to insert."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insert Pages from PDF")
        self.setMinimumSize(700, 550)
        self.resize(700, 550)
        self.setModal(True)

        self._source_path = ""
        self._cells: List[_InsertThumbnail] = []
        self._selected_indices: List[int] = []
        self._thumbnails: dict = {}
        self._thumbnail_worker: Optional[ThumbnailWorker] = None
        self._result_sources: List[PageSource] = []

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # File picker row
        file_row = QHBoxLayout()
        file_row.setSpacing(8)

        self._file_label = QLabel("No file selected")
        self._file_label.setStyleSheet("color: #666; font-size: 13px;")
        file_row.addWidget(self._file_label, 1)

        self._browse_btn = QPushButton("Browse PDF...")
        self._browse_btn.setProperty("class", "secondaryButton")
        self._browse_btn.clicked.connect(self._on_browse)
        file_row.addWidget(self._browse_btn)

        layout.addLayout(file_row)

        # Info row
        info_row = QHBoxLayout()
        self._info_label = QLabel("")
        self._info_label.setStyleSheet("font-size: 12px; color: #999;")
        info_row.addWidget(self._info_label)

        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.setProperty("class", "secondaryButton")
        self._select_all_btn.clicked.connect(self._on_select_all)
        self._select_all_btn.hide()
        info_row.addWidget(self._select_all_btn)

        layout.addLayout(info_row)

        # Thumbnail grid
        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(True)
        self._grid_scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(8)
        self._grid_layout.setContentsMargins(4, 4, 4, 4)

        self._grid_scroll.setWidget(self._grid_container)
        layout.addWidget(self._grid_scroll, 1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setProperty("class", "secondaryButton")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        self._insert_btn = QPushButton("Insert 0 Pages")
        self._insert_btn.setObjectName("primaryButton")
        self._insert_btn.setEnabled(False)
        self._insert_btn.clicked.connect(self._on_insert)
        btn_row.addWidget(self._insert_btn)

        layout.addLayout(btn_row)

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if not path:
            return

        self._source_path = path
        self._file_label.setText(path.split("/")[-1])
        self._clear_grid()

        # Start rendering thumbnails
        self._thumbnail_worker = ThumbnailWorker(path, thumb_width=_InsertThumbnail.THUMB_WIDTH)
        self._thumbnail_worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._thumbnail_worker.finished.connect(self._on_thumbnails_done)
        self._thumbnail_worker.error.connect(self._on_thumbnail_error)
        self._thumbnail_worker.start()

    def _on_thumbnail_ready(self, index: int, img: Image.Image):
        self._thumbnails[index] = img

        cell = _InsertThumbnail(index)
        cell.set_thumbnail(img)
        cell.clicked.connect(self._on_cell_clicked)
        self._cells.append(cell)

        cols = max(1, (self._grid_scroll.viewport().width() - 12) // 152)
        row, col = divmod(len(self._cells) - 1, cols)
        self._grid_layout.addWidget(cell, row, col, alignment=Qt.AlignmentFlag.AlignTop)

    def _on_thumbnails_done(self):
        self._thumbnail_worker = None
        self._select_all_btn.show()
        self._info_label.setText(f"{len(self._cells)} pages available")

    def _on_thumbnail_error(self, msg: str):
        self._thumbnail_worker = None
        self._info_label.setText(f"Error: {msg}")

    def _on_cell_clicked(self, page_index: int, event):
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        shift = event.modifiers() & Qt.KeyboardModifier.ShiftModifier

        if ctrl:
            if page_index in self._selected_indices:
                self._selected_indices.remove(page_index)
            else:
                self._selected_indices.append(page_index)
        elif shift and self._selected_indices:
            last = self._selected_indices[-1]
            start, end = min(last, page_index), max(last, page_index)
            for j in range(start, end + 1):
                if j not in self._selected_indices:
                    self._selected_indices.append(j)
        else:
            self._selected_indices = [page_index]

        self._update_selection()

    def _on_select_all(self):
        if len(self._selected_indices) == len(self._cells):
            self._selected_indices.clear()
        else:
            self._selected_indices = list(range(len(self._cells)))
        self._update_selection()

    def _update_selection(self):
        for cell in self._cells:
            cell.selected = (cell.page_index in self._selected_indices)

        count = len(self._selected_indices)
        self._insert_btn.setText(f"Insert {count} Page{'s' if count != 1 else ''}")
        self._insert_btn.setEnabled(count > 0)

    def _on_insert(self):
        manager = PageManager()
        self._result_sources = []
        for idx in sorted(self._selected_indices):
            src = PageSource(
                source_type=PageSourceType.EXTERNAL,
                source_path=self._source_path,
                source_page_index=idx,
            )
            # Read actual page dimensions
            import fitz
            doc = fitz.open(self._source_path)
            page = doc[idx]
            src.width = page.rect.width
            src.height = page.rect.height
            doc.close()
            self._result_sources.append(src)
        self.accept()

    def get_selected_sources(self) -> List[PageSource]:
        return self._result_sources

    def get_thumbnails(self) -> dict:
        """Return {source_page_index: PIL.Image} for selected pages."""
        return {idx: self._thumbnails[idx] for idx in sorted(self._selected_indices) if idx in self._thumbnails}

    def _clear_grid(self):
        for cell in self._cells:
            self._grid_layout.removeWidget(cell)
            cell.deleteLater()
        self._cells.clear()
        self._thumbnails.clear()
        self._selected_indices.clear()

    def closeEvent(self, event):
        if self._thumbnail_worker and self._thumbnail_worker.isRunning():
            self._thumbnail_worker.cancel()
            self._thumbnail_worker.wait(3000)
        super().closeEvent(event)
