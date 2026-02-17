"""Dialog for drawing/uploading a signature and placing it on a PDF page."""

import os
import tempfile
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QFileDialog, QWidget, QTabWidget,
    QColorDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QImage, QPixmap, QMouseEvent, QPainter, QPen, QColor, QPainterPath,
)

from core.page_manager import PageSource, PageManager, ImageAnnotation


# ---------------------------------------------------------------------------
# Freehand signature drawing canvas
# ---------------------------------------------------------------------------

class SignatureCanvas(QWidget):
    """Freehand drawing canvas for signature capture."""

    signature_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(500, 200)
        self.setFixedHeight(200)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setProperty("class", "signatureCanvas")
        self.setStyleSheet(
            "background: white; border: 2px solid #ddd; border-radius: 8px;"
        )

        self._paths: List[QPainterPath] = []
        self._current_path: Optional[QPainterPath] = None
        self._pen_color = QColor(0, 0, 0)
        self._pen_width = 3
        self._is_drawing = False

    def set_pen_color(self, color: QColor):
        self._pen_color = color

    def set_pen_width(self, width: int):
        self._pen_width = width

    def clear(self):
        self._paths.clear()
        self._current_path = None
        self.update()
        self.signature_changed.emit()

    def is_empty(self) -> bool:
        return len(self._paths) == 0

    def to_pil_image(self) -> Optional[Image.Image]:
        """Render the signature to a PIL RGBA Image, cropped to content."""
        if self.is_empty():
            return None

        # Render to QImage with alpha
        qimg = QImage(self.size(), QImage.Format.Format_ARGB32)
        qimg.fill(Qt.GlobalColor.transparent)

        painter = QPainter(qimg)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._pen_color, self._pen_width,
                   Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                   Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        for path in self._paths:
            painter.drawPath(path)
        painter.end()

        # Convert QImage → PIL Image
        # QImage Format_ARGB32: each pixel is 0xAARRGGBB (native endian)
        w, h = qimg.width(), qimg.height()
        ptr = qimg.bits()
        ptr.setsize(w * h * 4)
        raw = bytes(ptr)

        # Convert BGRA → RGBA (Qt stores as BGRA on little-endian)
        rgba_data = bytearray(len(raw))
        for i in range(0, len(raw), 4):
            rgba_data[i] = raw[i + 2]      # R
            rgba_data[i + 1] = raw[i + 1]  # G
            rgba_data[i + 2] = raw[i]      # B
            rgba_data[i + 3] = raw[i + 3]  # A
        pil_img = Image.frombytes("RGBA", (w, h), bytes(rgba_data))

        # Crop to content bounding box
        bbox = pil_img.getbbox()
        if bbox is None:
            return None
        pad = 10
        crop_box = (
            max(0, bbox[0] - pad),
            max(0, bbox[1] - pad),
            min(w, bbox[2] + pad),
            min(h, bbox[3] + pad),
        )
        return pil_img.crop(crop_box)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_drawing = True
            self._current_path = QPainterPath()
            self._current_path.moveTo(event.position())
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_drawing and self._current_path is not None:
            self._current_path.lineTo(event.position())
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_drawing:
            self._is_drawing = False
            if self._current_path is not None:
                self._paths.append(self._current_path)
                self._current_path = None
            self.update()
            self.signature_changed.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # White background
        painter.fillRect(self.rect(), QColor(255, 255, 255))

        # Dashed guideline at ~70% height
        mid_y = int(self.height() * 0.7)
        guide_pen = QPen(QColor(200, 200, 200), 1, Qt.PenStyle.DashLine)
        painter.setPen(guide_pen)
        painter.drawLine(20, mid_y, self.width() - 20, mid_y)

        # Hint text if empty
        if self.is_empty() and self._current_path is None:
            painter.setPen(QColor(180, 180, 180))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sign here")

        # Draw strokes
        stroke_pen = QPen(self._pen_color, self._pen_width,
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                          Qt.PenJoinStyle.RoundJoin)
        painter.setPen(stroke_pen)
        for path in self._paths:
            painter.drawPath(path)
        if self._current_path is not None:
            painter.drawPath(self._current_path)

        painter.end()


# ---------------------------------------------------------------------------
# Clickable page preview for positioning
# ---------------------------------------------------------------------------

class _ClickableSignaturePreview(QLabel):
    """Label that emits click position as normalized coordinates."""

    position_clicked = pyqtSignal(float, float)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.pixmap():
            pw = self.pixmap().width()
            ph = self.pixmap().height()
            if pw > 0 and ph > 0:
                lw, lh = self.width(), self.height()
                ox = max(0, (lw - pw) // 2)
                oy = max(0, (lh - ph) // 2)
                rx = (event.pos().x() - ox) / pw
                ry = (event.pos().y() - oy) / ph
                if 0 <= rx <= 1 and 0 <= ry <= 1:
                    self.position_clicked.emit(rx, ry)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Main signature dialog
# ---------------------------------------------------------------------------

class SignatureDialog(QDialog):
    """Modal dialog for drawing/uploading a signature and placing it on a page."""

    def __init__(self, source: PageSource, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Signature")
        self.setMinimumSize(750, 700)
        self.resize(750, 700)
        self.setModal(True)

        self._source = source
        self._manager = PageManager()
        self._pos_x: float = 0.1
        self._pos_y: float = 0.82
        self._scale: float = 0.25
        self._signature_img: Optional[Image.Image] = None
        self._base_img: Optional[Image.Image] = None
        self._result: Optional[ImageAnnotation] = None
        self._temp_path: str = ""

        self._setup_ui()
        self._load_preview()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Tab widget: Draw | Upload
        self._tabs = QTabWidget()

        # -- Draw tab --
        draw_tab = QWidget()
        draw_layout = QVBoxLayout(draw_tab)
        draw_layout.setSpacing(8)

        draw_hint = QLabel("Draw your signature below")
        draw_hint.setStyleSheet("color: #666; font-size: 12px;")
        draw_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        draw_layout.addWidget(draw_hint)

        self._canvas = SignatureCanvas()
        self._canvas.signature_changed.connect(self._on_signature_drawn)
        draw_layout.addWidget(self._canvas)

        canvas_controls = QHBoxLayout()
        canvas_controls.setSpacing(8)

        self._color_combo = QComboBox()
        self._color_combo.addItems(["Black", "Blue", "Red"])
        self._color_combo.currentTextChanged.connect(self._on_color_changed)
        canvas_controls.addWidget(QLabel("Pen:"))
        canvas_controls.addWidget(self._color_combo)

        canvas_controls.addWidget(QLabel("Width:"))
        self._width_slider = QSlider(Qt.Orientation.Horizontal)
        self._width_slider.setRange(1, 8)
        self._width_slider.setValue(3)
        self._width_slider.setFixedWidth(100)
        self._width_slider.valueChanged.connect(
            lambda v: self._canvas.set_pen_width(v),
        )
        canvas_controls.addWidget(self._width_slider)

        clear_btn = QPushButton("Clear")
        clear_btn.setProperty("class", "secondaryButton")
        clear_btn.clicked.connect(self._on_clear)
        canvas_controls.addWidget(clear_btn)

        canvas_controls.addStretch()
        draw_layout.addLayout(canvas_controls)

        self._tabs.addTab(draw_tab, "Draw Signature")

        # -- Upload tab --
        upload_tab = QWidget()
        upload_layout = QVBoxLayout(upload_tab)

        upload_hint = QLabel("Upload a signature image (PNG with transparency recommended)")
        upload_hint.setStyleSheet("color: #666; font-size: 12px;")
        upload_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        upload_layout.addWidget(upload_hint)

        self._upload_preview = QLabel("No image selected")
        self._upload_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._upload_preview.setStyleSheet("color: #999; font-size: 13px; padding: 20px;")
        self._upload_preview.setMinimumHeight(100)
        upload_layout.addWidget(self._upload_preview, 1)

        browse_btn = QPushButton("Browse Image...")
        browse_btn.setProperty("class", "secondaryButton")
        browse_btn.clicked.connect(self._on_browse_signature)
        upload_layout.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._tabs.addTab(upload_tab, "Upload Image")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self._tabs)

        # Page preview with click-to-position
        preview_label = QLabel("Click on the page below to set signature position")
        preview_label.setStyleSheet("color: #666; font-size: 12px;")
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(preview_label)

        self._preview = _ClickableSignaturePreview()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(280)
        self._preview.setCursor(Qt.CursorShape.CrossCursor)
        self._preview.position_clicked.connect(self._on_position_clicked)
        layout.addWidget(self._preview, 1)

        # Scale & position controls
        controls = QHBoxLayout()
        controls.setSpacing(8)

        controls.addWidget(QLabel("Position:"))
        self._position_combo = QComboBox()
        self._position_combo.addItems([
            "Custom (click)", "Bottom-Center", "Bottom-Left", "Bottom-Right",
        ])
        self._position_combo.currentIndexChanged.connect(self._on_position_preset)
        controls.addWidget(self._position_combo)

        controls.addWidget(QLabel("Scale:"))
        self._scale_slider = QSlider(Qt.Orientation.Horizontal)
        self._scale_slider.setRange(5, 60)
        self._scale_slider.setValue(25)
        self._scale_slider.valueChanged.connect(self._on_scale_changed)
        controls.addWidget(self._scale_slider)

        self._scale_label = QLabel("25%")
        self._scale_label.setFixedWidth(40)
        controls.addWidget(self._scale_label)

        layout.addLayout(controls)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._apply_btn = QPushButton("Apply Signature")
        self._apply_btn.setObjectName("primaryButton")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self._apply_btn)

        layout.addLayout(btn_row)

    def _load_preview(self):
        self._base_img = self._manager.render_full_page(self._source, max_width=500)
        self._update_preview()

    # ------------------------------------------------------------------ Draw tab handlers

    def _on_signature_drawn(self):
        self._signature_img = self._canvas.to_pil_image()
        self._apply_btn.setEnabled(self._signature_img is not None)
        self._update_preview()

    def _on_color_changed(self, text: str):
        colors = {
            "Black": QColor(0, 0, 0),
            "Blue": QColor(0, 0, 180),
            "Red": QColor(180, 0, 0),
        }
        self._canvas.set_pen_color(colors.get(text, QColor(0, 0, 0)))

    def _on_clear(self):
        self._canvas.clear()
        self._signature_img = None
        self._apply_btn.setEnabled(False)
        self._update_preview()

    # ------------------------------------------------------------------ Upload tab handlers

    def _on_browse_signature(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Signature Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.webp)",
        )
        if not path:
            return
        try:
            self._signature_img = Image.open(path).convert("RGBA")
            self._upload_preview.setText(os.path.basename(path))
            # Show a small preview of the uploaded image
            thumb = self._signature_img.copy()
            thumb.thumbnail((300, 100))
            thumb_rgb = thumb.convert("RGB")
            data = thumb_rgb.tobytes()
            qimg = QImage(data, thumb_rgb.width, thumb_rgb.height,
                          3 * thumb_rgb.width, QImage.Format.Format_RGB888)
            self._upload_preview.setPixmap(QPixmap.fromImage(qimg))
            self._apply_btn.setEnabled(True)
            self._update_preview()
        except Exception:
            self._upload_preview.setText("Error loading image")

    def _on_tab_changed(self, index: int):
        # When switching tabs, clear the signature from the other tab
        if index == 0:
            # Draw tab active — use canvas signature
            self._signature_img = self._canvas.to_pil_image()
        # Upload tab keeps its own state
        self._apply_btn.setEnabled(self._signature_img is not None)
        self._update_preview()

    # ------------------------------------------------------------------ Position & scale

    def _on_position_clicked(self, x: float, y: float):
        self._pos_x = x
        self._pos_y = y
        self._position_combo.setCurrentIndex(0)
        self._update_preview()

    def _on_position_preset(self, index: int):
        presets = {
            1: (0.35, 0.88),   # Bottom-Center
            2: (0.05, 0.88),   # Bottom-Left
            3: (0.65, 0.88),   # Bottom-Right
        }
        if index in presets:
            self._pos_x, self._pos_y = presets[index]
            self._update_preview()

    def _on_scale_changed(self, value: int):
        self._scale = value / 100.0
        self._scale_label.setText(f"{value}%")
        self._update_preview()

    # ------------------------------------------------------------------ Preview rendering

    def _get_aspect(self) -> float:
        if self._signature_img and self._signature_img.width > 0:
            return self._signature_img.height / self._signature_img.width
        return 0.5

    def _update_preview(self):
        if self._base_img is None:
            return

        img = self._base_img.copy().convert("RGBA")

        if self._signature_img is not None:
            ow = int(img.width * self._scale)
            aspect = self._get_aspect()
            oh = int(ow * aspect)
            if ow > 0 and oh > 0:
                resized = self._signature_img.resize((ow, oh), Image.Resampling.LANCZOS)
                px = int(self._pos_x * img.width)
                py = int(self._pos_y * img.height)
                px = max(0, min(px, img.width - ow))
                py = max(0, min(py, img.height - oh))
                img.paste(resized, (px, py), resized)

        # Draw crosshair at position
        draw = ImageDraw.Draw(img)
        cx = int(self._pos_x * img.width)
        cy = int(self._pos_y * img.height)
        draw.line([(cx - 12, cy), (cx + 12, cy)], fill=(255, 0, 0), width=2)
        draw.line([(cx, cy - 12), (cx, cy + 12)], fill=(255, 0, 0), width=2)

        final = img.convert("RGB")
        self._set_pixmap(final)

    def _set_pixmap(self, img: Image.Image):
        data = img.tobytes()
        qimg = QImage(data, img.width, img.height, 3 * img.width,
                       QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(
            self._preview.width(), self._preview.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(scaled)

    # ------------------------------------------------------------------ Apply

    def _on_apply(self):
        if self._signature_img is None:
            return

        # Save signature to a temp PNG file
        temp_dir = tempfile.gettempdir()
        self._temp_path = os.path.join(temp_dir, f"localpdf_sig_{id(self)}.png")
        self._signature_img.save(self._temp_path, "PNG")

        aspect = self._get_aspect()
        norm_height = self._scale * aspect

        self._result = ImageAnnotation(
            image_path=self._temp_path,
            x=self._pos_x,
            y=self._pos_y,
            width=self._scale,
            height=norm_height,
        )
        self.accept()

    def get_annotation(self) -> Optional[ImageAnnotation]:
        return self._result
