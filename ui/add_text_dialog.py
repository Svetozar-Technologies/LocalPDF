"""Dialog for placing text annotations on PDF pages."""

from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QComboBox, QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QMouseEvent

from core.page_manager import PageSource, PageManager, TextAnnotation


class _ClickablePreview(QLabel):
    """Label that emits click position as normalized coordinates."""

    position_clicked = pyqtSignal(float, float)  # normalized x, y

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.pixmap():
            pw = self.pixmap().width()
            ph = self.pixmap().height()
            if pw > 0 and ph > 0:
                # Account for label centering
                lw, lh = self.width(), self.height()
                ox = max(0, (lw - pw) // 2)
                oy = max(0, (lh - ph) // 2)
                rx = (event.pos().x() - ox) / pw
                ry = (event.pos().y() - oy) / ph
                if 0 <= rx <= 1 and 0 <= ry <= 1:
                    self.position_clicked.emit(rx, ry)
        super().mousePressEvent(event)


class AddTextDialog(QDialog):
    """Modal dialog for adding a text annotation to a page."""

    def __init__(self, source: PageSource, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Text Annotation")
        self.setMinimumSize(700, 600)
        self.resize(700, 600)
        self.setModal(True)

        self._source = source
        self._manager = PageManager()
        self._pos_x: float = 0.5
        self._pos_y: float = 0.5
        self._base_img: Optional[Image.Image] = None
        self._result: Optional[TextAnnotation] = None

        self._setup_ui()
        self._load_preview()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        hint = QLabel("Click on the page to set text position")
        hint.setStyleSheet("color: #666; font-size: 12px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # Preview
        self._preview = _ClickablePreview()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(350)
        self._preview.setCursor(Qt.CursorShape.CrossCursor)
        self._preview.position_clicked.connect(self._on_position_clicked)
        layout.addWidget(self._preview, 1)

        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(8)

        controls.addWidget(QLabel("Text:"))
        self._text_input = QLineEdit()
        self._text_input.setPlaceholderText("Enter text...")
        self._text_input.textChanged.connect(self._update_preview)
        controls.addWidget(self._text_input, 1)

        controls.addWidget(QLabel("Size:"))
        self._size_spin = QSpinBox()
        self._size_spin.setRange(10, 72)
        self._size_spin.setValue(14)
        self._size_spin.valueChanged.connect(self._update_preview)
        controls.addWidget(self._size_spin)

        controls.addWidget(QLabel("Color:"))
        self._color_combo = QComboBox()
        self._color_combo.addItems(["Black", "Red", "Blue", "Green"])
        self._color_combo.currentIndexChanged.connect(self._update_preview)
        controls.addWidget(self._color_combo)

        layout.addLayout(controls)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._apply_btn = QPushButton("Apply Text")
        self._apply_btn.setObjectName("primaryButton")
        self._apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self._apply_btn)

        layout.addLayout(btn_row)

    def _load_preview(self):
        self._base_img = self._manager.render_full_page(self._source, max_width=600)
        self._update_preview()

    def _on_position_clicked(self, x: float, y: float):
        self._pos_x = x
        self._pos_y = y
        self._update_preview()

    def _get_color_rgb(self) -> Tuple[float, float, float]:
        colors = {
            "Black": (0.0, 0.0, 0.0),
            "Red": (1.0, 0.0, 0.0),
            "Blue": (0.0, 0.0, 1.0),
            "Green": (0.0, 0.5, 0.0),
        }
        return colors.get(self._color_combo.currentText(), (0.0, 0.0, 0.0))

    def _update_preview(self):
        if self._base_img is None:
            return

        img = self._base_img.copy()
        text = self._text_input.text()

        if text:
            draw = ImageDraw.Draw(img)
            px = int(self._pos_x * img.width)
            py = int(self._pos_y * img.height)
            font_size = self._size_spin.value()

            # Map color
            r, g, b = self._get_color_rgb()
            fill = (int(r * 255), int(g * 255), int(b * 255))

            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            except Exception:
                font = ImageFont.load_default()

            draw.text((px, py), text, fill=fill, font=font)

            # Draw crosshair
            draw.line([(px - 10, py), (px + 10, py)], fill=(255, 0, 0), width=1)
            draw.line([(px, py - 10), (px, py + 10)], fill=(255, 0, 0), width=1)
        else:
            # Draw position marker
            draw = ImageDraw.Draw(img)
            px = int(self._pos_x * img.width)
            py = int(self._pos_y * img.height)
            draw.line([(px - 10, py), (px + 10, py)], fill=(255, 0, 0), width=1)
            draw.line([(px, py - 10), (px, py + 10)], fill=(255, 0, 0), width=1)

        self._set_pixmap(img)

    def _set_pixmap(self, img: Image.Image):
        img_rgb = img.convert("RGB")
        data = img_rgb.tobytes()
        qimg = QImage(data, img_rgb.width, img_rgb.height, 3 * img_rgb.width, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(
            self._preview.width(), self._preview.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(scaled)

    def _on_apply(self):
        text = self._text_input.text().strip()
        if not text:
            return

        self._result = TextAnnotation(
            text=text,
            x=self._pos_x,
            y=self._pos_y,
            font_size=self._size_spin.value(),
            color=self._get_color_rgb(),
        )
        self.accept()

    def get_annotation(self) -> Optional[TextAnnotation]:
        return self._result
