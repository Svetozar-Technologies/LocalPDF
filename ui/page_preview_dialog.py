"""Full-page preview dialog with navigation."""

from typing import List

from PIL import Image
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QApplication,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap, QKeyEvent

from core.page_manager import PageSource, PageManager
from i18n import t


class PagePreviewDialog(QDialog):
    """Modal dialog showing a high-res page preview with navigation."""

    def __init__(self, page_sources: List[PageSource], start_index: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("preview.title"))
        self.setModal(True)

        # Size to ~80% of screen
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            self.resize(int(geom.width() * 0.8), int(geom.height() * 0.8))
        else:
            self.resize(900, 700)

        self._sources = page_sources
        self._current = max(0, min(start_index, len(page_sources) - 1))
        self._manager = PageManager()

        self._setup_ui()
        self._render_current()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Image area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setWidget(self._image_label)
        layout.addWidget(self._scroll, 1)

        # Navigation bar
        nav = QHBoxLayout()
        nav.setSpacing(12)

        self._prev_btn = QPushButton(t("preview.previous"))
        self._prev_btn.setProperty("class", "secondaryButton")
        self._prev_btn.clicked.connect(self._go_prev)
        nav.addWidget(self._prev_btn)

        nav.addStretch()

        self._page_label = QLabel()
        self._page_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        nav.addWidget(self._page_label)

        nav.addStretch()

        self._next_btn = QPushButton(t("preview.next"))
        self._next_btn.setProperty("class", "secondaryButton")
        self._next_btn.clicked.connect(self._go_next)
        nav.addWidget(self._next_btn)

        layout.addLayout(nav)

    def _render_current(self):
        if not self._sources:
            return

        # Determine max_width from available space
        max_w = max(400, self._scroll.viewport().width() - 20)
        src = self._sources[self._current]
        img = self._manager.render_full_page(src, max_width=max_w)

        img_rgb = img.convert("RGB")
        data = img_rgb.tobytes()
        qimg = QImage(data, img_rgb.width, img_rgb.height, 3 * img_rgb.width, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self._image_label.setPixmap(pixmap)

        total = len(self._sources)
        self._page_label.setText(t("preview.page_of", current=self._current + 1, total=total))
        self._prev_btn.setEnabled(self._current > 0)
        self._next_btn.setEnabled(self._current < total - 1)

    def _go_prev(self):
        if self._current > 0:
            self._current -= 1
            self._render_current()

    def _go_next(self):
        if self._current < len(self._sources) - 1:
            self._current += 1
            self._render_current()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Left:
            self._go_prev()
        elif event.key() == Qt.Key.Key_Right:
            self._go_next()
        elif event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
