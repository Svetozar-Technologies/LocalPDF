"""Dialog for erasing (white-out) content from PDF pages."""

import tempfile
from typing import List, Optional, Tuple

from PIL import Image
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QScrollArea, QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QImage, QPainter, QPainterPath, QPen, QPixmap,
)

from core.page_manager import ImageAnnotation, PageManager, PageSource


class EraserCanvas(QWidget):
    """Freehand white-stroke drawing canvas over a rendered page."""

    strokes_changed = pyqtSignal()

    def __init__(self, background: QPixmap, parent=None):
        super().__init__(parent)
        self._background = background
        self.setFixedSize(background.size())

        self._strokes: List[Tuple[QPainterPath, int]] = []
        self._current_path: Optional[QPainterPath] = None
        self._pen_width = 20
        self._drawing = False

    # -- public API --

    @property
    def pen_width(self) -> int:
        return self._pen_width

    @pen_width.setter
    def pen_width(self, value: int):
        self._pen_width = max(1, value)

    def is_empty(self) -> bool:
        return len(self._strokes) == 0

    def undo(self):
        if self._strokes:
            self._strokes.pop()
            self.update()
            self.strokes_changed.emit()

    def clear(self):
        if self._strokes:
            self._strokes.clear()
            self.update()
            self.strokes_changed.emit()

    def to_pil_image(self) -> Image.Image:
        """Render strokes only (no background) onto a transparent ARGB32 image,
        then convert to PIL RGBA."""
        img = QImage(self.size(), QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)

        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_strokes(painter)
        painter.end()

        # QImage ARGB32 is BGRA in memory — convert to RGBA for PIL
        width, height = img.width(), img.height()
        ptr = img.bits()
        ptr.setsize(width * height * 4)
        raw = bytes(ptr)

        pil_img = Image.frombytes("RGBA", (width, height), raw, "raw", "BGRA")
        return pil_img

    # -- painting --

    def _make_pen(self, width: int) -> QPen:
        pen = QPen(QColor(255, 255, 255))
        pen.setWidth(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    def _paint_strokes(self, painter: QPainter):
        for path, width in self._strokes:
            painter.setPen(self._make_pen(width))
            painter.drawPath(path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background page
        painter.drawPixmap(0, 0, self._background)

        # Completed strokes
        self._paint_strokes(painter)

        # In-progress stroke
        if self._current_path is not None:
            painter.setPen(self._make_pen(self._pen_width))
            painter.drawPath(self._current_path)

        painter.end()

    # -- mouse events --

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True
            self._current_path = QPainterPath()
            self._current_path.moveTo(event.position())
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drawing and self._current_path is not None:
            self._current_path.lineTo(event.position())
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            if self._current_path is not None:
                self._strokes.append((self._current_path, self._pen_width))
                self._current_path = None
                self.update()
                self.strokes_changed.emit()
        super().mouseReleaseEvent(event)


class EraserDialog(QDialog):
    """Modal dialog for erasing content from a PDF page with white strokes."""

    def __init__(self, source: PageSource, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Eraser Tool")
        self.setMinimumSize(800, 700)
        self.resize(800, 700)
        self.setModal(True)

        self._source = source
        self._manager = PageManager()
        self._result: Optional[ImageAnnotation] = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Hint
        hint = QLabel("Draw on the page to erase content")
        hint.setStyleSheet("color: #666; font-size: 12px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # Render page and create canvas
        base_img = self._manager.render_full_page(self._source, max_width=700)
        data = base_img.convert("RGB").tobytes()
        qimg = QImage(
            data, base_img.width, base_img.height,
            3 * base_img.width, QImage.Format.Format_RGB888,
        )
        bg_pixmap = QPixmap.fromImage(qimg)

        self._canvas = EraserCanvas(bg_pixmap)
        self._canvas.strokes_changed.connect(self._on_strokes_changed)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setWidget(self._canvas)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(scroll, 1)

        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(12)

        controls.addWidget(QLabel("Eraser size:"))

        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(5, 50)
        self._size_slider.setValue(20)
        self._size_slider.setFixedWidth(160)
        self._size_slider.valueChanged.connect(self._on_size_changed)
        controls.addWidget(self._size_slider)

        self._size_label = QLabel("20")
        self._size_label.setFixedWidth(28)
        controls.addWidget(self._size_label)

        controls.addStretch()

        self._undo_btn = QPushButton("Undo")
        self._undo_btn.setProperty("class", "secondaryButton")
        self._undo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self._canvas.undo)
        controls.addWidget(self._undo_btn)

        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.setProperty("class", "secondaryButton")
        self._clear_btn.setEnabled(False)
        self._clear_btn.clicked.connect(self._canvas.clear)
        controls.addWidget(self._clear_btn)

        layout.addLayout(controls)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._apply_btn = QPushButton("Apply Eraser")
        self._apply_btn.setObjectName("primaryButton")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self._apply_btn)

        layout.addLayout(btn_row)

    # -- slots --

    def _on_size_changed(self, value: int):
        self._canvas.pen_width = value
        self._size_label.setText(str(value))

    def _on_strokes_changed(self):
        has_strokes = not self._canvas.is_empty()
        self._undo_btn.setEnabled(has_strokes)
        self._clear_btn.setEnabled(has_strokes)
        self._apply_btn.setEnabled(has_strokes)

    def _on_apply(self):
        if self._canvas.is_empty():
            return

        pil_img = self._canvas.to_pil_image()

        # Save to temp PNG
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        pil_img.save(tmp, format="PNG")
        tmp.close()

        self._result = ImageAnnotation(
            image_path=tmp.name,
            x=0.0,
            y=0.0,
            width=1.0,
            height=1.0,
        )
        self.accept()

    def get_annotation(self) -> Optional[ImageAnnotation]:
        return self._result
