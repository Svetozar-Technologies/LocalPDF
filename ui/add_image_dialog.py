"""Dialog for placing image overlays on PDF pages."""

from typing import Optional

from PIL import Image, ImageDraw
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QMouseEvent

from core.page_manager import PageSource, PageManager, ImageAnnotation
from i18n import t


class _ClickableImagePreview(QLabel):
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


class AddImageDialog(QDialog):
    """Modal dialog for adding an image overlay to a page."""

    def __init__(self, source: PageSource, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("add_image.title"))
        self.setMinimumSize(700, 600)
        self.resize(700, 600)
        self.setModal(True)

        self._source = source
        self._manager = PageManager()
        self._pos_x: float = 0.5
        self._pos_y: float = 0.5
        self._scale: float = 0.25  # 25% of page width
        self._image_path: str = ""
        self._overlay_img: Optional[Image.Image] = None
        self._base_img: Optional[Image.Image] = None
        self._result: Optional[ImageAnnotation] = None

        self._setup_ui()
        self._load_preview()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        hint = QLabel(t("add_image.hint"))
        hint.setStyleSheet("color: #666; font-size: 12px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # Preview
        self._preview = _ClickableImagePreview()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(350)
        self._preview.setCursor(Qt.CursorShape.CrossCursor)
        self._preview.position_clicked.connect(self._on_position_clicked)
        layout.addWidget(self._preview, 1)

        # Image picker row
        img_row = QHBoxLayout()
        img_row.setSpacing(8)

        self._img_label = QLabel(t("add_image.no_image"))
        self._img_label.setStyleSheet("color: #666; font-size: 12px;")
        img_row.addWidget(self._img_label, 1)

        browse_btn = QPushButton(t("add_image.browse"))
        browse_btn.setProperty("class", "secondaryButton")
        browse_btn.clicked.connect(self._on_browse_image)
        img_row.addWidget(browse_btn)

        layout.addLayout(img_row)

        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(12)

        controls.addWidget(QLabel(t("add_image.position")))
        self._position_combo = QComboBox()
        for _pname, _pkey in [("Custom (click)", "Custom (click)"), ("Center", "Center"), ("Top-Left", "Top Left"), ("Top-Right", "Top Right"), ("Bottom-Left", "Bottom Left"), ("Bottom-Right", "Bottom Right")]:
            self._position_combo.addItem(t(f"position.{_pkey}") if _pkey != "Custom (click)" else t("add_image.custom"), _pname)
        self._position_combo.currentIndexChanged.connect(self._on_position_preset)
        controls.addWidget(self._position_combo)

        controls.addWidget(QLabel(t("add_image.scale")))
        self._scale_slider = QSlider(Qt.Orientation.Horizontal)
        self._scale_slider.setRange(5, 100)
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

        cancel_btn = QPushButton(t("common.cancel"))
        cancel_btn.setProperty("class", "secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._apply_btn = QPushButton(t("add_image.apply"))
        self._apply_btn.setObjectName("primaryButton")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self._apply_btn)

        layout.addLayout(btn_row)

    def _load_preview(self):
        self._base_img = self._manager.render_full_page(self._source, max_width=600)
        self._update_preview()

    def _on_browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("add_image.select_dialog"), "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp)",
        )
        if not path:
            return

        self._image_path = path
        self._img_label.setText(path.split("/")[-1])
        try:
            self._overlay_img = Image.open(path).convert("RGBA")
        except Exception:
            self._overlay_img = None
            self._img_label.setText(t("add_image.error_loading"))
            return

        self._apply_btn.setEnabled(True)
        self._update_preview()

    def _on_position_clicked(self, x: float, y: float):
        self._pos_x = x
        self._pos_y = y
        self._position_combo.setCurrentIndex(0)  # "Custom (click)"
        self._update_preview()

    def _on_position_preset(self, index: int):
        presets = {
            1: (0.5, 0.5),    # Center
            2: (0.05, 0.05),  # Top-Left
            3: (0.95, 0.05),  # Top-Right (will offset by width)
            4: (0.05, 0.95),  # Bottom-Left (will offset by height)
            5: (0.95, 0.95),  # Bottom-Right
        }
        if index in presets:
            self._pos_x, self._pos_y = presets[index]
            # Adjust for image size so it's placed relative to its edge
            if index == 1:  # Center
                self._pos_x -= self._scale / 2
                self._pos_y -= self._scale / 2 * self._get_aspect()
            elif index == 3:  # Top-Right
                self._pos_x -= self._scale
            elif index == 4:  # Bottom-Left
                self._pos_y -= self._scale * self._get_aspect()
            elif index == 5:  # Bottom-Right
                self._pos_x -= self._scale
                self._pos_y -= self._scale * self._get_aspect()
            self._update_preview()

    def _get_aspect(self) -> float:
        if self._overlay_img and self._overlay_img.width > 0:
            return self._overlay_img.height / self._overlay_img.width
        return 1.0

    def _on_scale_changed(self, value: int):
        self._scale = value / 100.0
        self._scale_label.setText(f"{value}%")
        self._update_preview()

    def _update_preview(self):
        if self._base_img is None:
            return

        img = self._base_img.copy().convert("RGBA")

        if self._overlay_img is not None:
            # Scale overlay to percentage of page width
            ow = int(img.width * self._scale)
            aspect = self._overlay_img.height / self._overlay_img.width if self._overlay_img.width > 0 else 1
            oh = int(ow * aspect)
            if ow > 0 and oh > 0:
                resized = self._overlay_img.resize((ow, oh), Image.Resampling.LANCZOS)
                px = int(self._pos_x * img.width)
                py = int(self._pos_y * img.height)
                # Clamp to image bounds
                px = max(0, min(px, img.width - ow))
                py = max(0, min(py, img.height - oh))
                img.paste(resized, (px, py), resized)

        # Draw position crosshair
        draw = ImageDraw.Draw(img)
        px = int(self._pos_x * img.width)
        py = int(self._pos_y * img.height)
        draw.line([(px - 10, py), (px + 10, py)], fill=(255, 0, 0), width=1)
        draw.line([(px, py - 10), (px, py + 10)], fill=(255, 0, 0), width=1)

        final = img.convert("RGB")
        self._set_pixmap(final)

    def _set_pixmap(self, img: Image.Image):
        data = img.tobytes()
        qimg = QImage(data, img.width, img.height, 3 * img.width, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(
            self._preview.width(), self._preview.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(scaled)

    def _on_apply(self):
        if not self._image_path or self._overlay_img is None:
            return

        aspect = self._overlay_img.height / self._overlay_img.width if self._overlay_img.width > 0 else 1
        norm_height = self._scale * aspect

        self._result = ImageAnnotation(
            image_path=self._image_path,
            x=self._pos_x,
            y=self._pos_y,
            width=self._scale,
            height=norm_height,
        )
        self.accept()

    def get_annotation(self) -> Optional[ImageAnnotation]:
        return self._result
