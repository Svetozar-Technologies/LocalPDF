"""Continuous scroll edit view for the Page Manager — Sejda-like full-page vertical scroll."""

from typing import Dict, List, Optional, Set

from PIL import Image
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QSizePolicy, QHBoxLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRect
from PyQt6.QtGui import QImage, QPixmap, QMouseEvent

from core.page_manager import PageSource
from i18n import t


# ---------------------------------------------------------------------------
# Single page card in the continuous scroll
# ---------------------------------------------------------------------------

class _EditPageCard(QFrame):
    """A single page rendered at readable size with paper-like appearance."""

    PAGE_WIDTH = 600

    clicked = pyqtSignal(int, object)          # (card_index, QMouseEvent)
    double_clicked = pyqtSignal(int)            # card_index
    page_clicked = pyqtSignal(int, float, float)  # (card_index, norm_x, norm_y)

    def __init__(self, index: int, source: PageSource, parent=None):
        super().__init__(parent)
        self._index = index
        self._source = source
        self._selected = False
        self._rendered = False
        self.setProperty("class", "editPageCard")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(4)

        # Page image
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Placeholder sized to correct aspect ratio
        aspect = self._source.height / self._source.width if self._source.width > 0 else 842 / 595
        placeholder_h = int(self.PAGE_WIDTH * aspect)
        self._image_label.setFixedSize(self.PAGE_WIDTH, placeholder_h)
        self._image_label.setStyleSheet(
            "background: #f8f8f8; border: 1px solid #e0e0e0; border-radius: 2px;"
        )
        self._image_label.setText(t("page_manager.loading"))
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Info row below image
        info_row = QHBoxLayout()
        info_row.setSpacing(8)

        self._page_label = QLabel(t("page_manager.page_label", number=self._index + 1))
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setStyleSheet("font-size: 12px; color: #666; padding: 2px;")
        info_row.addWidget(self._page_label, 1)

        self._ann_label = QLabel("")
        self._ann_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ann_label.setStyleSheet("font-size: 10px; color: #FF9800;")
        self._ann_label.hide()
        info_row.addWidget(self._ann_label)

        layout.addLayout(info_row)

        self.update_annotation_indicator()

    @property
    def index(self) -> int:
        return self._index

    @index.setter
    def index(self, value: int):
        self._index = value
        self._page_label.setText(t("page_manager.page_label", number=value + 1))

    @property
    def source(self) -> PageSource:
        return self._source

    @property
    def rendered(self) -> bool:
        return self._rendered

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool):
        self._selected = value
        if value:
            self.setStyleSheet(
                "_EditPageCard { border: 3px solid #2196F3; border-radius: 6px; background: #E3F2FD; }"
            )
        else:
            self.setStyleSheet("")

    def set_page_image(self, img: Image.Image):
        img_rgb = img.convert("RGB")
        data = img_rgb.tobytes()
        qimg = QImage(data, img_rgb.width, img_rgb.height,
                       3 * img_rgb.width, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self._image_label.setFixedSize(pixmap.width(), pixmap.height())
        self._image_label.setPixmap(pixmap)
        self._image_label.setText("")
        self._rendered = True

    def set_placeholder(self):
        aspect = self._source.height / self._source.width if self._source.width > 0 else 842 / 595
        placeholder_h = int(self.PAGE_WIDTH * aspect)
        self._image_label.setFixedSize(self.PAGE_WIDTH, placeholder_h)
        self._image_label.setPixmap(QPixmap())
        self._image_label.setText(t("page_manager.loading"))
        self._rendered = False

    def update_annotation_indicator(self):
        has_ann = bool(self._source.text_annotations or self._source.image_annotations)
        if has_ann:
            count = len(self._source.text_annotations) + len(self._source.image_annotations)
            if count != 1:
                self._ann_label.setText(t("page_manager.annotation_count_plural", count=count))
            else:
                self._ann_label.setText(t("page_manager.annotation_count", count=count))
            self._ann_label.show()
        else:
            self._ann_label.hide()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index, event)
            # Compute normalized position relative to the page image
            if self._image_label.pixmap() and not self._image_label.pixmap().isNull():
                local_pos = self._image_label.mapFrom(self, event.pos())
                pw = self._image_label.pixmap().width()
                ph = self._image_label.pixmap().height()
                if pw > 0 and ph > 0:
                    nx = local_pos.x() / pw
                    ny = local_pos.y() / ph
                    if 0 <= nx <= 1 and 0 <= ny <= 1:
                        self.page_clicked.emit(self._index, nx, ny)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self._index)
        super().mouseDoubleClickEvent(event)


# ---------------------------------------------------------------------------
# Continuous scroll view with lazy rendering
# ---------------------------------------------------------------------------

class EditViewWidget(QWidget):
    """Continuous vertical scroll view showing all pages at readable size.
    Implements lazy rendering: only pages near the viewport are rendered."""

    page_selected = pyqtSignal(int, object)       # (page_index, QMouseEvent)
    page_double_clicked = pyqtSignal(int)          # page_index
    page_position_clicked = pyqtSignal(int, float, float)

    RENDER_BUFFER = 2  # extra pages above/below viewport to pre-render
    PAGE_WIDTH = 600

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: List[_EditPageCard] = []
        self._render_cache: Dict[int, Image.Image] = {}
        self._pending_renders: Set[int] = set()
        self._render_workers: list = []
        self._scroll_timer = QTimer()
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(100)
        self._scroll_timer.timeout.connect(self._on_scroll_debounced)
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll_area.verticalScrollBar().valueChanged.connect(
            self._on_scroll_changed,
        )

        self._container = QWidget()
        self._v_layout = QVBoxLayout(self._container)
        self._v_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._v_layout.setSpacing(24)
        self._v_layout.setContentsMargins(40, 24, 40, 24)

        self._scroll_area.setWidget(self._container)
        outer.addWidget(self._scroll_area)

    # ------------------------------------------------------------------ Public API

    def rebuild_from_sources(self, sources: List[PageSource]):
        """Clear and rebuild all page cards from the given source list."""
        self._clear_cards()
        for i, src in enumerate(sources):
            card = _EditPageCard(i, src)
            card.clicked.connect(self.page_selected.emit)
            card.double_clicked.connect(self.page_double_clicked.emit)
            card.page_clicked.connect(self.page_position_clicked.emit)
            self._cards.append(card)
            self._v_layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignHCenter)
        # Trigger initial viewport render after layout settles
        QTimer.singleShot(50, self._render_visible_pages)

    def update_card_at(self, index: int):
        """Re-render a single card (e.g., after annotation change)."""
        if 0 <= index < len(self._cards):
            card = self._cards[index]
            card.update_annotation_indicator()
            # Invalidate cache and re-render
            if index in self._render_cache:
                del self._render_cache[index]
            card.set_placeholder()
            self._render_page(index)

    def scroll_to_page(self, index: int):
        """Scroll the view to bring the given page into view."""
        if 0 <= index < len(self._cards):
            self._scroll_area.ensureWidgetVisible(self._cards[index], 50, 50)

    def set_selection(self, selected_indices: Set[int]):
        """Update visual selection state of all cards."""
        for i, card in enumerate(self._cards):
            card.selected = (i in selected_indices)

    # ------------------------------------------------------------------ Scroll handling

    def _on_scroll_changed(self, _value: int):
        self._scroll_timer.start()

    def _on_scroll_debounced(self):
        self._render_visible_pages()

    def _get_visible_range(self) -> tuple:
        """Return (first_visible_index, last_visible_index) based on viewport."""
        if not self._cards:
            return (0, 0)

        viewport = self._scroll_area.viewport()
        vp_top = self._scroll_area.verticalScrollBar().value()
        vp_bottom = vp_top + viewport.height()

        first_visible = None
        last_visible = None

        for i, card in enumerate(self._cards):
            # Get card position relative to the scroll container
            card_top = card.y()
            card_bottom = card_top + card.height()

            if card_bottom >= vp_top and card_top <= vp_bottom:
                if first_visible is None:
                    first_visible = i
                last_visible = i

        if first_visible is None:
            return (0, min(self.RENDER_BUFFER, len(self._cards) - 1))

        return (
            max(0, first_visible - self.RENDER_BUFFER),
            min(len(self._cards) - 1, last_visible + self.RENDER_BUFFER),
        )

    def _render_visible_pages(self):
        """Render pages in and near the viewport that haven't been rendered yet."""
        if not self._cards:
            return

        first, last = self._get_visible_range()
        for i in range(first, last + 1):
            if not self._cards[i].rendered and i not in self._pending_renders:
                self._render_page(i)

    def _render_page(self, index: int):
        """Start a background render for the given page index."""
        if index in self._pending_renders:
            return
        self._pending_renders.add(index)

        from workers.page_manager_worker import FullPageRenderWorker
        source = self._cards[index].source
        worker = FullPageRenderWorker(source, max_width=self.PAGE_WIDTH)
        worker.finished.connect(lambda img, idx=index: self._on_page_rendered(idx, img))
        worker.error.connect(lambda msg, idx=index: self._on_page_render_error(idx, msg))
        self._render_workers.append(worker)
        worker.start()

    def _on_page_rendered(self, index: int, img: Image.Image):
        self._pending_renders.discard(index)
        if 0 <= index < len(self._cards):
            self._render_cache[index] = img
            self._cards[index].set_page_image(img)

    def _on_page_render_error(self, index: int, msg: str):
        self._pending_renders.discard(index)

    # ------------------------------------------------------------------ Cleanup

    def _clear_cards(self):
        for worker in self._render_workers:
            if hasattr(worker, "cancel"):
                worker.cancel()
        self._render_workers.clear()
        self._pending_renders.clear()
        self._render_cache.clear()

        for card in self._cards:
            self._v_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

    def cleanup(self):
        self._clear_cards()
