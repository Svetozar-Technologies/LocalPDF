"""Page Manager tab widget — reorder, rotate, delete, insert, duplicate, extract, annotate PDF pages."""

import copy
import os
from typing import Dict, List, Optional

from PIL import Image
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QScrollArea, QFrame, QGridLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint
from PyQt6.QtGui import QImage, QPixmap, QDrag

from ui.components.drop_zone import DropZone
from ui.components.progress_widget import ProgressWidget
from ui.components.result_card import ResultCard
from ui.edit_view_widget import EditViewWidget
from workers.page_manager_worker import ThumbnailWorker, EnhancedSaveWorker
from core.page_manager import PageSource, PageSourceType, PageManager
from core.utils import validate_pdf, get_output_path


# ---------------------------------------------------------------------------
# Thumbnail cell widget
# ---------------------------------------------------------------------------

class _PageThumbnail(QFrame):
    """A single page thumbnail cell in the grid."""

    _next_id = 0

    clicked = pyqtSignal(int, object)   # (cell_id, QMouseEvent)
    drag_started = pyqtSignal(int)       # cell_id
    double_clicked = pyqtSignal(int)     # cell_id

    THUMB_WIDTH = 150

    def __init__(self, source: PageSource, parent=None):
        super().__init__(parent)
        self._cell_id = _PageThumbnail._next_id
        _PageThumbnail._next_id += 1
        self._source = source
        self._selected = False
        self._drag_start_pos: Optional[QPoint] = None
        self.setFixedSize(170, 220)
        self.setProperty("class", "pageThumbnail")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 4)
        layout.setSpacing(2)

        # Image container with potential badge overlay
        self._image_label = QLabel()
        self._image_label.setFixedSize(self.THUMB_WIDTH, 170)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet("background: #f0f0f0; border: 1px solid #ddd; border-radius: 4px;")
        layout.addWidget(self._image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        info_row = QHBoxLayout()
        info_row.setSpacing(2)

        # Source badge
        self._badge_label = QLabel("")
        self._badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge_label.setFixedWidth(30)
        self._badge_label.setStyleSheet("font-size: 9px; color: white; background: #2196F3; border-radius: 3px; padding: 1px;")
        self._badge_label.hide()
        info_row.addWidget(self._badge_label)

        self._page_label = QLabel("Page 1")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setStyleSheet("font-size: 11px; color: #666;")
        info_row.addWidget(self._page_label, 1)

        self._rotation_label = QLabel("")
        self._rotation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rotation_label.setStyleSheet("font-size: 10px; color: #999;")
        self._rotation_label.hide()
        info_row.addWidget(self._rotation_label)

        # Annotation indicator
        self._ann_label = QLabel("")
        self._ann_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ann_label.setFixedWidth(16)
        self._ann_label.setStyleSheet("font-size: 10px; color: #FF9800;")
        self._ann_label.hide()
        info_row.addWidget(self._ann_label)

        layout.addLayout(info_row)

        # Show badge based on source type
        self._update_badge()

    def _update_badge(self):
        if self._source.source_type == PageSourceType.EXTERNAL:
            self._badge_label.setText("EXT")
            self._badge_label.setStyleSheet("font-size: 9px; color: white; background: #FF5722; border-radius: 3px; padding: 1px;")
            self._badge_label.show()
        elif self._source.source_type == PageSourceType.BLANK:
            self._badge_label.setText("NEW")
            self._badge_label.setStyleSheet("font-size: 9px; color: white; background: #4CAF50; border-radius: 3px; padding: 1px;")
            self._badge_label.show()
        else:
            self._badge_label.hide()

    def update_annotation_indicator(self):
        has_ann = bool(self._source.text_annotations or self._source.image_annotations)
        if has_ann:
            count = len(self._source.text_annotations) + len(self._source.image_annotations)
            self._ann_label.setText(f"\u270E{count}")
            self._ann_label.show()
        else:
            self._ann_label.hide()

    def set_thumbnail(self, img: Image.Image):
        img_rgb = img.convert("RGB")
        data = img_rgb.tobytes()
        qimg = QImage(data, img_rgb.width, img_rgb.height, 3 * img_rgb.width, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(
            self.THUMB_WIDTH, 170,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)

    @property
    def cell_id(self) -> int:
        return self._cell_id

    @property
    def source(self) -> PageSource:
        return self._source

    @property
    def rotation(self) -> int:
        return self._source.rotation

    @rotation.setter
    def rotation(self, degrees: int):
        self._source.rotation = degrees % 360
        if self._source.rotation != 0:
            self._rotation_label.setText(f"{self._source.rotation}\u00B0")
            self._rotation_label.show()
        else:
            self._rotation_label.hide()

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool):
        self._selected = value
        if value:
            self.setStyleSheet("_PageThumbnail { border: 2px solid #2196F3; border-radius: 6px; background: #E3F2FD; }")
        else:
            self.setStyleSheet("")

    def update_label(self, position: int):
        self._page_label.setText(f"Page {position + 1}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            self.clicked.emit(self._cell_id, event)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self._cell_id)
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            distance = (event.pos() - self._drag_start_pos).manhattanLength()
            if distance > 20:
                self.drag_started.emit(self._cell_id)
                self._drag_start_pos = None
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

class PageManagerWidget(QWidget):
    """Page Manager tab: full page editing suite with thumbnails."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = ""
        self._thumbnail_worker: Optional[ThumbnailWorker] = None
        self._save_worker: Optional[EnhancedSaveWorker] = None
        self._cells: List[_PageThumbnail] = []
        self._cell_thumbnails: Dict[int, Image.Image] = {}  # cell_id -> PIL Image
        self._selected_ids: List[int] = []  # cell_ids of selected cells
        self._drag_source: Optional[int] = None  # position in _cells
        self._current_view = "grid"  # "grid" or "edit"
        self._setup_ui()
        self._connect_signals()

    # ------------------------------------------------------------------ UI

    def _setup_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("PDF Page Editor")
        title.setProperty("class", "sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("Edit, reorder, rotate, annotate, erase, and extract PDF pages. 100% local processing.")
        subtitle.setProperty("class", "sectionSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Drop zone
        self._drop_zone = DropZone(
            accepted_extensions=[".pdf"],
            placeholder_text="Drop a PDF file here or click to browse",
        )
        layout.addWidget(self._drop_zone)

        # --- Toolbar Row 1: basic operations ---
        self._toolbar = QWidget()
        toolbar_v = QVBoxLayout(self._toolbar)
        toolbar_v.setContentsMargins(0, 0, 0, 0)
        toolbar_v.setSpacing(6)

        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self._rotate_left_btn = QPushButton("\u21BA Rotate Left")
        self._rotate_left_btn.setProperty("class", "secondaryButton")
        self._rotate_left_btn.setToolTip("Rotate selected pages 90\u00B0 counter-clockwise")
        row1.addWidget(self._rotate_left_btn)

        self._rotate_right_btn = QPushButton("\u21BB Rotate Right")
        self._rotate_right_btn.setProperty("class", "secondaryButton")
        self._rotate_right_btn.setToolTip("Rotate selected pages 90\u00B0 clockwise")
        row1.addWidget(self._rotate_right_btn)

        self._delete_btn = QPushButton("\u2715 Delete")
        self._delete_btn.setProperty("class", "secondaryButton")
        self._delete_btn.setToolTip("Remove selected pages")
        row1.addWidget(self._delete_btn)

        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.setProperty("class", "secondaryButton")
        row1.addWidget(self._select_all_btn)

        self._view_toggle_btn = QPushButton("\u2630 Edit View")
        self._view_toggle_btn.setProperty("class", "secondaryButton")
        self._view_toggle_btn.setToolTip("Toggle between grid thumbnails and continuous edit view")
        row1.addWidget(self._view_toggle_btn)

        row1.addStretch()

        self._move_left_btn = QPushButton("\u25C0")
        self._move_left_btn.setProperty("class", "secondaryButton")
        self._move_left_btn.setFixedWidth(36)
        self._move_left_btn.setToolTip("Move selected page left")
        row1.addWidget(self._move_left_btn)

        self._move_right_btn = QPushButton("\u25B6")
        self._move_right_btn.setProperty("class", "secondaryButton")
        self._move_right_btn.setFixedWidth(36)
        self._move_right_btn.setToolTip("Move selected page right")
        row1.addWidget(self._move_right_btn)

        toolbar_v.addLayout(row1)

        # --- Toolbar Row 2: enhanced operations ---
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self._insert_pages_btn = QPushButton("\u2795 Insert Pages")
        self._insert_pages_btn.setProperty("class", "secondaryButton")
        self._insert_pages_btn.setToolTip("Insert pages from another PDF")
        row2.addWidget(self._insert_pages_btn)

        self._insert_blank_btn = QPushButton("\u2B1C Insert Blank")
        self._insert_blank_btn.setProperty("class", "secondaryButton")
        self._insert_blank_btn.setToolTip("Insert a blank A4 page")
        row2.addWidget(self._insert_blank_btn)

        self._duplicate_btn = QPushButton("\u2398 Duplicate")
        self._duplicate_btn.setProperty("class", "secondaryButton")
        self._duplicate_btn.setToolTip("Duplicate selected pages")
        row2.addWidget(self._duplicate_btn)

        self._extract_btn = QPushButton("\u2197 Extract")
        self._extract_btn.setProperty("class", "secondaryButton")
        self._extract_btn.setToolTip("Extract selected pages to a new PDF")
        row2.addWidget(self._extract_btn)

        row2.addStretch()

        self._add_text_btn = QPushButton("\U0001D5A0 Add Text")
        self._add_text_btn.setProperty("class", "secondaryButton")
        self._add_text_btn.setToolTip("Add text annotation to selected pages")
        row2.addWidget(self._add_text_btn)

        self._add_image_btn = QPushButton("\U0001F5BC Add Image")
        self._add_image_btn.setProperty("class", "secondaryButton")
        self._add_image_btn.setToolTip("Add image overlay to selected pages")
        row2.addWidget(self._add_image_btn)

        self._sign_btn = QPushButton("\u270D Sign")
        self._sign_btn.setProperty("class", "secondaryButton")
        self._sign_btn.setToolTip("Draw or upload a signature and place it on selected pages")
        row2.addWidget(self._sign_btn)

        self._manage_ann_btn = QPushButton("\u270E Annotations")
        self._manage_ann_btn.setProperty("class", "secondaryButton")
        self._manage_ann_btn.setToolTip("Manage and delete annotations on the selected page")
        row2.addWidget(self._manage_ann_btn)

        self._eraser_btn = QPushButton("\u2702 Eraser")
        self._eraser_btn.setProperty("class", "secondaryButton")
        self._eraser_btn.setToolTip("Erase (white-out) content on the selected page")
        row2.addWidget(self._eraser_btn)

        toolbar_v.addLayout(row2)

        self._toolbar.hide()
        layout.addWidget(self._toolbar)

        # Selection info
        self._selection_label = QLabel("")
        self._selection_label.setProperty("class", "helperText")
        self._selection_label.hide()
        layout.addWidget(self._selection_label)

        # Thumbnail grid
        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(True)
        self._grid_scroll.setMinimumHeight(300)
        self._grid_scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(12)
        self._grid_layout.setContentsMargins(8, 8, 8, 8)

        self._grid_scroll.setWidget(self._grid_container)
        self._grid_scroll.hide()
        layout.addWidget(self._grid_scroll)

        # Edit view (continuous scroll)
        self._edit_view = EditViewWidget()
        self._edit_view.page_selected.connect(self._on_edit_view_page_selected)
        self._edit_view.page_double_clicked.connect(self._on_cell_double_clicked_by_pos)
        self._edit_view.hide()
        layout.addWidget(self._edit_view)

        # Save button
        self._save_btn = QPushButton("Save PDF")
        self._save_btn.setObjectName("primaryButton")
        self._save_btn.setEnabled(False)
        self._save_btn.hide()
        layout.addWidget(self._save_btn)

        # Progress
        self._progress = ProgressWidget()
        layout.addWidget(self._progress)

        # Result card
        self._result_card = ResultCard()
        layout.addWidget(self._result_card)

        layout.addStretch()

        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    # ------------------------------------------------------------------ Signals

    def _connect_signals(self):
        self._drop_zone.file_selected.connect(self._on_file_selected)
        self._drop_zone.file_removed.connect(self._on_file_removed)
        self._rotate_left_btn.clicked.connect(self._on_rotate_left)
        self._rotate_right_btn.clicked.connect(self._on_rotate_right)
        self._delete_btn.clicked.connect(self._on_delete_selected)
        self._select_all_btn.clicked.connect(self._on_select_all)
        self._move_left_btn.clicked.connect(self._on_move_left)
        self._move_right_btn.clicked.connect(self._on_move_right)
        self._insert_pages_btn.clicked.connect(self._on_insert_pages)
        self._insert_blank_btn.clicked.connect(self._on_insert_blank)
        self._duplicate_btn.clicked.connect(self._on_duplicate)
        self._extract_btn.clicked.connect(self._on_extract_pages)
        self._add_text_btn.clicked.connect(self._on_add_text)
        self._add_image_btn.clicked.connect(self._on_add_image)
        self._sign_btn.clicked.connect(self._on_add_signature)
        self._manage_ann_btn.clicked.connect(self._on_manage_annotations)
        self._eraser_btn.clicked.connect(self._on_eraser)
        self._view_toggle_btn.clicked.connect(self._on_toggle_view)
        self._save_btn.clicked.connect(self._on_save_clicked)
        self._progress.cancel_clicked.connect(self._on_cancel_clicked)
        self._result_card.compress_another.connect(self._on_another)

    # ------------------------------------------------------------------ File loading

    def _on_file_selected(self, file_path: str):
        result = validate_pdf(file_path)
        if not result.valid:
            QMessageBox.warning(self, "Invalid File", result.error_message)
            self._drop_zone.reset()
            return

        self._current_file = file_path
        self._result_card.reset()
        self._progress.reset()
        self._clear_grid()
        self._toolbar.show()
        self._grid_scroll.show()
        self._save_btn.show()
        self._save_btn.setEnabled(False)

        self._thumbnail_worker = ThumbnailWorker(file_path, thumb_width=_PageThumbnail.THUMB_WIDTH)
        self._thumbnail_worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._thumbnail_worker.finished.connect(self._on_thumbnails_finished)
        self._thumbnail_worker.error.connect(self._on_thumbnail_error)
        self._thumbnail_worker.start()

    def _on_file_removed(self):
        self._current_file = ""
        self._clear_grid()
        self._toolbar.hide()
        self._grid_scroll.hide()
        self._edit_view.hide()
        self._edit_view.cleanup()
        self._current_view = "grid"
        self._view_toggle_btn.setText("\u2630 Edit View")
        self._save_btn.hide()
        self._save_btn.setEnabled(False)
        self._selection_label.hide()
        self._result_card.reset()
        self._progress.reset()

    def _on_thumbnail_ready(self, index: int, img: Image.Image):
        import fitz
        # Read actual page dimensions
        doc = fitz.open(self._current_file)
        page = doc[index]
        w, h = page.rect.width, page.rect.height
        doc.close()

        source = PageSource(
            source_type=PageSourceType.ORIGINAL,
            source_path=self._current_file,
            source_page_index=index,
            width=w,
            height=h,
        )
        cell = _PageThumbnail(source)
        cell.set_thumbnail(img)
        cell.clicked.connect(self._on_cell_clicked)
        cell.drag_started.connect(self._on_drag_started)
        cell.double_clicked.connect(self._on_cell_double_clicked)
        self._cells.append(cell)
        self._cell_thumbnails[cell.cell_id] = img

        self._relayout_grid()

    def _on_thumbnails_finished(self):
        self._thumbnail_worker = None
        self._save_btn.setEnabled(len(self._cells) > 0)

    def _on_thumbnail_error(self, error_msg: str):
        self._thumbnail_worker = None
        QMessageBox.critical(self, "Error", f"Failed to render thumbnails: {error_msg}")

    # ------------------------------------------------------------------ Grid layout

    def _relayout_grid(self):
        while self._grid_layout.count():
            self._grid_layout.takeAt(0)

        cols = max(1, (self._grid_scroll.viewport().width() - 20) // 182)
        for i, cell in enumerate(self._cells):
            row, col = divmod(i, cols)
            cell.update_label(i)
            self._grid_layout.addWidget(cell, row, col, alignment=Qt.AlignmentFlag.AlignTop)

    def _clear_grid(self):
        for cell in self._cells:
            self._grid_layout.removeWidget(cell)
            cell.deleteLater()
        self._cells.clear()
        self._cell_thumbnails.clear()
        self._selected_ids.clear()

    # ------------------------------------------------------------------ Helpers

    def _pos_of_id(self, cell_id: int) -> Optional[int]:
        for i, cell in enumerate(self._cells):
            if cell.cell_id == cell_id:
                return i
        return None

    def _selected_positions(self) -> List[int]:
        """Return sorted list of positions for selected cell_ids."""
        positions = []
        for cid in self._selected_ids:
            p = self._pos_of_id(cid)
            if p is not None:
                positions.append(p)
        return sorted(positions)

    # ------------------------------------------------------------------ Selection

    def _on_cell_clicked(self, cell_id: int, event):
        pos = self._pos_of_id(cell_id)
        if pos is None:
            return

        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        shift = event.modifiers() & Qt.KeyboardModifier.ShiftModifier

        if ctrl:
            if cell_id in self._selected_ids:
                self._selected_ids.remove(cell_id)
            else:
                self._selected_ids.append(cell_id)
        elif shift and self._selected_ids:
            last_pos = self._pos_of_id(self._selected_ids[-1])
            if last_pos is not None:
                start, end = min(last_pos, pos), max(last_pos, pos)
                for j in range(start, end + 1):
                    cid = self._cells[j].cell_id
                    if cid not in self._selected_ids:
                        self._selected_ids.append(cid)
        else:
            self._selected_ids = [cell_id]

        self._update_selection_display()

    def _on_cell_double_clicked(self, cell_id: int):
        pos = self._pos_of_id(cell_id)
        if pos is None:
            return
        from ui.page_preview_dialog import PagePreviewDialog
        sources = [cell.source for cell in self._cells]
        dlg = PagePreviewDialog(sources, start_index=pos, parent=self)
        dlg.exec()

    def _update_selection_display(self):
        selected_set = set(self._selected_ids)
        for cell in self._cells:
            cell.selected = (cell.cell_id in selected_set)

        count = len(self._selected_ids)
        if count == 0:
            self._selection_label.hide()
        else:
            self._selection_label.setText(f"{count} page{'s' if count != 1 else ''} selected")
            self._selection_label.show()

    def _on_select_all(self):
        if len(self._selected_ids) == len(self._cells):
            self._selected_ids.clear()
        else:
            self._selected_ids = [cell.cell_id for cell in self._cells]
        self._update_selection_display()

    # ------------------------------------------------------------------ Basic operations

    def _on_rotate_left(self):
        if not self._selected_ids:
            return
        for cid in self._selected_ids:
            pos = self._pos_of_id(cid)
            if pos is not None:
                cell = self._cells[pos]
                cell.rotation = (cell.rotation - 90) % 360
        self._save_btn.setEnabled(True)
        self._sync_edit_view()

    def _on_rotate_right(self):
        if not self._selected_ids:
            return
        for cid in self._selected_ids:
            pos = self._pos_of_id(cid)
            if pos is not None:
                cell = self._cells[pos]
                cell.rotation = (cell.rotation + 90) % 360
        self._save_btn.setEnabled(True)
        self._sync_edit_view()

    def _on_delete_selected(self):
        if not self._selected_ids:
            return

        remaining = len(self._cells) - len(self._selected_ids)
        if remaining == 0:
            QMessageBox.warning(self, "Cannot Delete", "You cannot delete all pages. At least one page must remain.")
            return

        positions = sorted(self._selected_positions(), reverse=True)
        for pos in positions:
            cell = self._cells.pop(pos)
            self._grid_layout.removeWidget(cell)
            cell.deleteLater()

        self._selected_ids.clear()
        self._relayout_grid()
        self._update_selection_display()
        self._save_btn.setEnabled(len(self._cells) > 0)
        self._sync_edit_view()

    def _on_move_left(self):
        if not self._selected_ids:
            return
        positions = self._selected_positions()
        if not positions or positions[0] <= 0:
            return
        pos = positions[0]
        self._cells[pos], self._cells[pos - 1] = self._cells[pos - 1], self._cells[pos]
        self._relayout_grid()
        self._update_selection_display()
        self._save_btn.setEnabled(True)
        self._sync_edit_view()

    def _on_move_right(self):
        if not self._selected_ids:
            return
        positions = self._selected_positions()
        if not positions or positions[-1] >= len(self._cells) - 1:
            return
        pos = positions[-1]
        self._cells[pos], self._cells[pos + 1] = self._cells[pos + 1], self._cells[pos]
        self._relayout_grid()
        self._update_selection_display()
        self._save_btn.setEnabled(True)
        self._sync_edit_view()

    # ------------------------------------------------------------------ Enhanced operations

    def _on_insert_blank(self):
        source = PageSource(
            source_type=PageSourceType.BLANK,
            width=595.0,
            height=842.0,
        )
        # White thumbnail
        aspect = source.height / source.width
        thumb_h = int(_PageThumbnail.THUMB_WIDTH * aspect)
        img = Image.new("RGB", (_PageThumbnail.THUMB_WIDTH, thumb_h), (255, 255, 255))

        cell = _PageThumbnail(source)
        cell.set_thumbnail(img)
        cell.clicked.connect(self._on_cell_clicked)
        cell.drag_started.connect(self._on_drag_started)
        cell.double_clicked.connect(self._on_cell_double_clicked)

        # Insert after selected position or at end
        positions = self._selected_positions()
        insert_pos = (positions[-1] + 1) if positions else len(self._cells)
        self._cells.insert(insert_pos, cell)
        self._cell_thumbnails[cell.cell_id] = img

        self._relayout_grid()
        self._selected_ids = [cell.cell_id]
        self._update_selection_display()
        self._save_btn.setEnabled(True)
        self._sync_edit_view()

    def _on_duplicate(self):
        if not self._selected_ids:
            return

        positions = self._selected_positions()
        insert_at = positions[-1] + 1
        new_ids = []

        for pos in positions:
            orig_cell = self._cells[pos]
            new_source = copy.deepcopy(orig_cell.source)
            new_cell = _PageThumbnail(new_source)

            # Reuse existing thumbnail
            if orig_cell.cell_id in self._cell_thumbnails:
                thumb = self._cell_thumbnails[orig_cell.cell_id]
                new_cell.set_thumbnail(thumb)
                self._cell_thumbnails[new_cell.cell_id] = thumb

            new_cell.clicked.connect(self._on_cell_clicked)
            new_cell.drag_started.connect(self._on_drag_started)
            new_cell.double_clicked.connect(self._on_cell_double_clicked)

            self._cells.insert(insert_at, new_cell)
            new_ids.append(new_cell.cell_id)
            insert_at += 1

        self._relayout_grid()
        self._selected_ids = new_ids
        self._update_selection_display()
        self._save_btn.setEnabled(True)
        self._sync_edit_view()

    def _on_extract_pages(self):
        if not self._selected_ids:
            return

        positions = self._selected_positions()
        sources = [self._cells[p].source for p in positions]

        if not self._current_file:
            return

        output_path = get_output_path(self._current_file, suffix="_extracted")

        self._save_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.start()

        self._save_worker = EnhancedSaveWorker(sources, output_path)
        self._save_worker.progress.connect(self._on_save_progress)
        self._save_worker.finished.connect(self._on_extract_finished)
        self._save_worker.error.connect(self._on_save_error)
        self._save_worker.start()

    def _on_extract_finished(self, result):
        self._progress.finish()
        self._save_btn.setEnabled(True)
        self._save_worker = None

        if result.success:
            self._result_card.show_simple_result(
                result.output_path,
                title=f"Extracted! {result.total_pages} pages",
            )
        else:
            QMessageBox.critical(self, "Error", result.error_message)
            self._progress.reset()

    def _on_insert_pages(self):
        from ui.insert_pages_dialog import InsertPagesDialog
        dlg = InsertPagesDialog(parent=self)
        if dlg.exec() != InsertPagesDialog.DialogCode.Accepted:
            return

        new_sources = dlg.get_selected_sources()
        thumbnails = dlg.get_thumbnails()
        if not new_sources:
            return

        positions = self._selected_positions()
        insert_pos = (positions[-1] + 1) if positions else len(self._cells)
        new_ids = []

        manager = PageManager()
        for src in new_sources:
            cell = _PageThumbnail(src)
            # Use pre-rendered thumbnail if available
            if src.source_page_index in thumbnails:
                img = thumbnails[src.source_page_index]
            else:
                img = manager.render_thumbnail_for_page(src, thumb_width=_PageThumbnail.THUMB_WIDTH)
            cell.set_thumbnail(img)
            self._cell_thumbnails[cell.cell_id] = img

            cell.clicked.connect(self._on_cell_clicked)
            cell.drag_started.connect(self._on_drag_started)
            cell.double_clicked.connect(self._on_cell_double_clicked)

            self._cells.insert(insert_pos, cell)
            new_ids.append(cell.cell_id)
            insert_pos += 1

        self._relayout_grid()
        self._selected_ids = new_ids
        self._update_selection_display()
        self._save_btn.setEnabled(True)
        self._sync_edit_view()

    def _on_add_text(self):
        if not self._selected_ids:
            return
        positions = self._selected_positions()
        if not positions:
            return

        # Use first selected page for preview
        first_cell = self._cells[positions[0]]
        from ui.add_text_dialog import AddTextDialog
        dlg = AddTextDialog(first_cell.source, parent=self)
        if dlg.exec() != AddTextDialog.DialogCode.Accepted:
            return

        annotation = dlg.get_annotation()
        if annotation is None:
            return

        # Apply to all selected pages
        for pos in positions:
            self._cells[pos].source.text_annotations.append(copy.deepcopy(annotation))
            self._cells[pos].update_annotation_indicator()
            if self._current_view == "edit":
                self._edit_view.update_card_at(pos)

        self._save_btn.setEnabled(True)

    def _on_add_image(self):
        if not self._selected_ids:
            return
        positions = self._selected_positions()
        if not positions:
            return

        first_cell = self._cells[positions[0]]
        from ui.add_image_dialog import AddImageDialog
        dlg = AddImageDialog(first_cell.source, parent=self)
        if dlg.exec() != AddImageDialog.DialogCode.Accepted:
            return

        annotation = dlg.get_annotation()
        if annotation is None:
            return

        for pos in positions:
            self._cells[pos].source.image_annotations.append(copy.deepcopy(annotation))
            self._cells[pos].update_annotation_indicator()
            if self._current_view == "edit":
                self._edit_view.update_card_at(pos)

        self._save_btn.setEnabled(True)

    def _on_add_signature(self):
        if not self._selected_ids:
            return
        positions = self._selected_positions()
        if not positions:
            return

        first_cell = self._cells[positions[0]]
        from ui.signature_dialog import SignatureDialog
        dlg = SignatureDialog(first_cell.source, parent=self)
        if dlg.exec() != SignatureDialog.DialogCode.Accepted:
            return

        annotation = dlg.get_annotation()
        if annotation is None:
            return

        for pos in positions:
            self._cells[pos].source.image_annotations.append(copy.deepcopy(annotation))
            self._cells[pos].update_annotation_indicator()
            if self._current_view == "edit":
                self._edit_view.update_card_at(pos)

        self._save_btn.setEnabled(True)

    def _on_manage_annotations(self):
        if not self._selected_ids:
            return
        positions = self._selected_positions()
        if not positions:
            return

        first_cell = self._cells[positions[0]]
        source = first_cell.source

        if not source.text_annotations and not source.image_annotations:
            QMessageBox.information(self, "No Annotations", "This page has no annotations to manage.")
            return

        from ui.manage_annotations_dialog import ManageAnnotationsDialog
        dlg = ManageAnnotationsDialog(source, parent=self)
        dlg.exec()

        if dlg.was_modified():
            first_cell.update_annotation_indicator()
            if self._current_view == "edit":
                self._edit_view.update_card_at(positions[0])
            self._save_btn.setEnabled(True)

    def _on_eraser(self):
        if not self._selected_ids:
            return
        positions = self._selected_positions()
        if not positions:
            return

        first_cell = self._cells[positions[0]]
        from ui.eraser_dialog import EraserDialog
        dlg = EraserDialog(first_cell.source, parent=self)
        if dlg.exec() != EraserDialog.DialogCode.Accepted:
            return

        annotation = dlg.get_annotation()
        if annotation is None:
            return

        first_cell.source.image_annotations.append(annotation)
        first_cell.update_annotation_indicator()
        if self._current_view == "edit":
            self._edit_view.update_card_at(positions[0])

        self._save_btn.setEnabled(True)

    # ------------------------------------------------------------------ View toggle

    def _on_toggle_view(self):
        if self._current_view == "grid":
            self._current_view = "edit"
            self._view_toggle_btn.setText("\u2637 Grid View")
            self._grid_scroll.hide()
            sources = [cell.source for cell in self._cells]
            self._edit_view.rebuild_from_sources(sources)
            self._edit_view.show()
            # Sync selection
            selected_positions = set(self._selected_positions())
            self._edit_view.set_selection(selected_positions)
        else:
            self._current_view = "grid"
            self._view_toggle_btn.setText("\u2630 Edit View")
            self._edit_view.hide()
            self._grid_scroll.show()
            self._relayout_grid()

    def _sync_edit_view(self):
        """Rebuild edit view if it's currently active."""
        if self._current_view == "edit":
            sources = [cell.source for cell in self._cells]
            self._edit_view.rebuild_from_sources(sources)
            selected_positions = set(self._selected_positions())
            self._edit_view.set_selection(selected_positions)

    def _on_edit_view_page_selected(self, page_index: int, event):
        """Bridge: map edit view page click to cell selection logic."""
        if 0 <= page_index < len(self._cells):
            cell_id = self._cells[page_index].cell_id
            self._on_cell_clicked(cell_id, event)
            # Sync selection back to edit view
            selected_positions = set(self._selected_positions())
            self._edit_view.set_selection(selected_positions)

    def _on_cell_double_clicked_by_pos(self, page_index: int):
        """Bridge: open preview from edit view page index."""
        if 0 <= page_index < len(self._cells):
            from ui.page_preview_dialog import PagePreviewDialog
            sources = [cell.source for cell in self._cells]
            dlg = PagePreviewDialog(sources, start_index=page_index, parent=self)
            dlg.exec()

    # ------------------------------------------------------------------ Drag reorder

    def _on_drag_started(self, cell_id: int):
        source_pos = self._pos_of_id(cell_id)
        if source_pos is None:
            return

        self._drag_source = source_pos

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(source_pos))
        drag.setMimeData(mime)

        if self._cells[source_pos]._image_label.pixmap():
            drag.setPixmap(self._cells[source_pos]._image_label.pixmap().scaled(
                80, 100, Qt.AspectRatioMode.KeepAspectRatio,
            ))

        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and self._drag_source is not None:
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        if self._drag_source is None:
            return

        drop_pos = self._find_drop_position(event.position().toPoint())
        if drop_pos is not None and drop_pos != self._drag_source:
            cell = self._cells.pop(self._drag_source)
            self._cells.insert(drop_pos, cell)
            self._selected_ids = [cell.cell_id]
            self._relayout_grid()
            self._update_selection_display()
            self._save_btn.setEnabled(True)
            self._sync_edit_view()

        self._drag_source = None
        event.acceptProposedAction()

    def _find_drop_position(self, global_pos: QPoint) -> Optional[int]:
        for i, cell in enumerate(self._cells):
            cell_rect = cell.geometry()
            mapped = self._grid_container.mapFrom(self, global_pos)
            if cell_rect.contains(mapped):
                return i
        return len(self._cells) - 1 if self._cells else None

    # ------------------------------------------------------------------ Save

    def _on_save_clicked(self):
        if not self._current_file or not self._cells:
            return

        output_path = get_output_path(self._current_file, suffix="_managed")

        page_sources = [cell.source for cell in self._cells]

        self._save_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.start()

        self._save_worker = EnhancedSaveWorker(page_sources, output_path)
        self._save_worker.progress.connect(self._on_save_progress)
        self._save_worker.finished.connect(self._on_save_finished)
        self._save_worker.error.connect(self._on_save_error)
        self._save_worker.start()

    def _on_save_progress(self, step: int, total: int, message: str):
        self._progress.update_progress(step, total, message)

    def _on_save_finished(self, result):
        self._progress.finish()
        self._save_btn.setEnabled(True)
        self._save_worker = None

        if result.success:
            self._result_card.show_simple_result(
                result.output_path,
                title=f"Saved! {result.total_pages} pages",
            )
        else:
            QMessageBox.critical(self, "Error", result.error_message)
            self._progress.reset()

    def _on_save_error(self, error_msg: str):
        self._progress.reset()
        self._save_btn.setEnabled(True)
        self._save_worker = None
        QMessageBox.critical(self, "Error", error_msg)

    # ------------------------------------------------------------------ Cancel / Reset

    def _on_cancel_clicked(self):
        if self._save_worker:
            self._save_worker.cancel()
            self._save_worker.wait(5000)
            self._save_worker = None
        self._progress.reset()
        self._save_btn.setEnabled(len(self._cells) > 0)

    def _on_another(self):
        self._drop_zone.reset()
        self._clear_grid()
        self._toolbar.hide()
        self._grid_scroll.hide()
        self._edit_view.hide()
        self._edit_view.cleanup()
        self._current_view = "grid"
        self._view_toggle_btn.setText("\u2630 Edit View")
        self._save_btn.hide()
        self._selection_label.hide()
        self._result_card.reset()
        self._progress.reset()
        self._current_file = ""

    def cleanup(self):
        if self._thumbnail_worker and self._thumbnail_worker.isRunning():
            self._thumbnail_worker.cancel()
            if not self._thumbnail_worker.wait(5000):
                self._thumbnail_worker.terminate()
                self._thumbnail_worker.wait(2000)
        self._thumbnail_worker = None

        if self._save_worker and self._save_worker.isRunning():
            self._save_worker.cancel()
            if not self._save_worker.wait(5000):
                self._save_worker.terminate()
                self._save_worker.wait(2000)
        self._save_worker = None

        self._edit_view.cleanup()
