"""PDF Watermark tab widget."""

import io
import os
import fitz
from PIL import Image as PILImage, ImageEnhance
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QScrollArea, QGroupBox, QRadioButton, QButtonGroup, QLineEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QSlider, QFileDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap

from ui.components.drop_zone import DropZone
from ui.components.progress_widget import ProgressWidget
from ui.components.result_card import ResultCard
from workers.watermark_worker import WatermarkWorker
from core.watermark import TextWatermarkConfig, ImageWatermarkConfig
from core.utils import validate_pdf, get_output_path, check_disk_space


class WatermarkWidget(QWidget):
    """PDF Watermark tab: add text or image watermarks to PDFs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = ""
        self._watermark_image = ""
        self._worker: WatermarkWorker = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("Add Watermark")
        title.setProperty("class", "sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("Add text or image watermarks to your PDF. 100% local processing.")
        subtitle.setProperty("class", "sectionSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Drop zone
        self._drop_zone = DropZone(
            accepted_extensions=[".pdf"],
            placeholder_text="Drop PDF here or click to browse",
        )
        layout.addWidget(self._drop_zone)

        # Watermark type selection
        type_group = QGroupBox("Watermark Type")
        type_layout = QVBoxLayout(type_group)

        self._type_group = QButtonGroup(self)
        self._text_radio = QRadioButton("Text watermark")
        self._image_radio = QRadioButton("Image watermark (logo)")
        self._text_radio.setChecked(True)
        self._type_group.addButton(self._text_radio, 0)
        self._type_group.addButton(self._image_radio, 1)
        type_layout.addWidget(self._text_radio)
        type_layout.addWidget(self._image_radio)

        layout.addWidget(type_group)

        # Text watermark options
        self._text_options = QGroupBox("Text Watermark Settings")
        text_layout = QVBoxLayout(self._text_options)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Text:"))
        self._text_input = QLineEdit()
        self._text_input.setText("CONFIDENTIAL")
        self._text_input.setPlaceholderText("Watermark text")
        row1.addWidget(self._text_input)
        text_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Font Size:"))
        self._fontsize_spin = QSpinBox()
        self._fontsize_spin.setRange(10, 200)
        self._fontsize_spin.setValue(60)
        row2.addWidget(self._fontsize_spin)

        row2.addSpacing(20)
        row2.addWidget(QLabel("Rotation:"))
        self._rotation_spin = QSpinBox()
        self._rotation_spin.setRange(0, 360)
        self._rotation_spin.setValue(45)
        self._rotation_spin.setSuffix("\u00b0")
        row2.addWidget(self._rotation_spin)
        row2.addStretch()
        text_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Opacity:"))
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(5, 80)
        self._opacity_slider.setValue(15)
        row3.addWidget(self._opacity_slider)
        self._opacity_label = QLabel("15%")
        self._opacity_label.setFixedWidth(40)
        row3.addWidget(self._opacity_label)
        text_layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Color:"))
        self._color_combo = QComboBox()
        self._color_combo.addItems([
            "Gray", "Red", "Blue", "Green", "Black",
        ])
        row4.addWidget(self._color_combo)
        row4.addStretch()
        text_layout.addLayout(row4)

        layout.addWidget(self._text_options)

        # Image watermark options
        self._image_options = QGroupBox("Image Watermark Settings")
        img_layout = QVBoxLayout(self._image_options)

        img_row1 = QHBoxLayout()
        self._img_select_btn = QPushButton("Select Watermark Image")
        self._img_select_btn.setProperty("class", "secondaryButton")
        img_row1.addWidget(self._img_select_btn)
        self._img_path_label = QLabel("No image selected")
        self._img_path_label.setProperty("class", "textCaption")
        img_row1.addWidget(self._img_path_label, 1)
        img_layout.addLayout(img_row1)

        img_row2 = QHBoxLayout()
        img_row2.addWidget(QLabel("Size:"))
        self._img_scale_spin = QDoubleSpinBox()
        self._img_scale_spin.setRange(0.05, 1.0)
        self._img_scale_spin.setSingleStep(0.05)
        self._img_scale_spin.setValue(0.30)
        self._img_scale_spin.setSuffix("x page width")
        img_row2.addWidget(self._img_scale_spin)

        img_row2.addSpacing(20)
        img_row2.addWidget(QLabel("Opacity:"))
        self._img_opacity_spin = QDoubleSpinBox()
        self._img_opacity_spin.setRange(0.05, 1.0)
        self._img_opacity_spin.setSingleStep(0.05)
        self._img_opacity_spin.setValue(0.30)
        img_row2.addWidget(self._img_opacity_spin)
        img_row2.addStretch()
        img_layout.addLayout(img_row2)

        img_row3 = QHBoxLayout()
        img_row3.addWidget(QLabel("Position:"))
        self._position_combo = QComboBox()
        self._position_combo.addItems([
            "Center", "Top Left", "Top Right", "Bottom Left", "Bottom Right",
        ])
        img_row3.addWidget(self._position_combo)
        img_row3.addStretch()
        img_layout.addLayout(img_row3)

        # Live preview
        preview_header = QLabel("Preview (page 1)")
        preview_header.setProperty("class", "textCaption")
        img_layout.addWidget(preview_header)

        self._preview_label = QLabel("Select a PDF and watermark image to see preview")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumHeight(300)
        self._preview_label.setStyleSheet(
            "border: 1px solid #555; border-radius: 4px; padding: 8px; background: #1e1e1e;"
        )
        img_layout.addWidget(self._preview_label)

        self._image_options.hide()
        layout.addWidget(self._image_options)

        # Watermark button
        self._watermark_btn = QPushButton("Add Watermark")
        self._watermark_btn.setObjectName("primaryButton")
        self._watermark_btn.setEnabled(False)
        layout.addWidget(self._watermark_btn)

        # Progress
        self._progress = ProgressWidget()
        layout.addWidget(self._progress)

        # Result
        self._result_card = ResultCard()
        layout.addWidget(self._result_card)

        layout.addStretch()

        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _connect_signals(self):
        self._drop_zone.file_selected.connect(self._on_file_selected)
        self._drop_zone.file_removed.connect(self._on_file_removed)
        self._type_group.buttonClicked.connect(self._on_type_changed)
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )
        self._img_select_btn.clicked.connect(self._select_image)
        self._img_scale_spin.valueChanged.connect(self._update_preview)
        self._img_opacity_spin.valueChanged.connect(self._update_preview)
        self._position_combo.currentIndexChanged.connect(self._update_preview)
        self._watermark_btn.clicked.connect(self._on_watermark_clicked)
        self._progress.cancel_clicked.connect(self._on_cancel_clicked)
        self._result_card.compress_another.connect(self._on_another)

    def _on_type_changed(self):
        if self._text_radio.isChecked():
            self._text_options.show()
            self._image_options.hide()
        else:
            self._text_options.hide()
            self._image_options.show()
            self._update_preview()

    def _select_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Watermark Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.svg)",
        )
        if path:
            self._watermark_image = path
            self._img_path_label.setText(os.path.basename(path))
            self._update_preview()

    def _on_file_selected(self, file_path: str):
        result = validate_pdf(file_path)
        if not result.valid:
            QMessageBox.warning(self, "Invalid File", result.error_message)
            self._drop_zone.reset()
            return

        self._current_file = file_path
        self._watermark_btn.setEnabled(True)
        self._result_card.reset()
        self._progress.reset()
        self._update_preview()

    def _on_file_removed(self):
        self._current_file = ""
        self._watermark_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.reset()

    def _get_color_tuple(self) -> tuple:
        color_map = {
            "Gray": (0.5, 0.5, 0.5),
            "Red": (0.8, 0.1, 0.1),
            "Blue": (0.1, 0.1, 0.8),
            "Green": (0.1, 0.5, 0.1),
            "Black": (0.0, 0.0, 0.0),
        }
        return color_map.get(self._color_combo.currentText(), (0.5, 0.5, 0.5))

    def _get_position_str(self) -> str:
        pos_map = {
            "Center": "center",
            "Top Left": "top-left",
            "Top Right": "top-right",
            "Bottom Left": "bottom-left",
            "Bottom Right": "bottom-right",
        }
        return pos_map.get(self._position_combo.currentText(), "center")

    def _update_preview(self):
        """Render a live preview of the image watermark on page 1."""
        if not self._current_file or not self._watermark_image or not self._image_radio.isChecked():
            return

        try:
            # Render page 1 of the PDF
            doc = fitz.open(self._current_file)
            page = doc[0]
            preview_width = 450
            zoom = preview_width / page.rect.width
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            base = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()

            # Open and scale watermark image
            wm = PILImage.open(self._watermark_image).convert("RGBA")
            scale = self._img_scale_spin.value()
            wm_w = int(base.width * scale)
            wm_h = int(wm_w * wm.height / wm.width)
            if wm_w < 1 or wm_h < 1:
                return
            wm = wm.resize((wm_w, wm_h), PILImage.LANCZOS)

            # Apply opacity to alpha channel
            opacity = self._img_opacity_spin.value()
            alpha = wm.split()[3]
            alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
            wm.putalpha(alpha)

            # Calculate position (same logic as PDFWatermarker._get_position)
            position = self._get_position_str()
            margin = int(36 * zoom)
            bw, bh = base.size
            if position == "top-left":
                x, y = margin, margin
            elif position == "top-right":
                x, y = bw - wm_w - margin, margin
            elif position == "bottom-left":
                x, y = margin, bh - wm_h - margin
            elif position == "bottom-right":
                x, y = bw - wm_w - margin, bh - wm_h - margin
            else:  # center
                x, y = (bw - wm_w) // 2, (bh - wm_h) // 2

            # Composite
            base = base.convert("RGBA")
            base.paste(wm, (x, y), wm)
            result = base.convert("RGB")

            # Convert to QPixmap
            buf = io.BytesIO()
            result.save(buf, format="PNG")
            qimg = QImage()
            qimg.loadFromData(buf.getvalue())
            pixmap = QPixmap.fromImage(qimg)
            self._preview_label.setPixmap(pixmap)
            self._preview_label.setMinimumHeight(pixmap.height())

        except Exception as e:
            self._preview_label.setText(f"Preview error: {e}")

    def _on_watermark_clicked(self):
        if not self._current_file:
            return

        output_path = get_output_path(self._current_file, suffix="_watermarked")

        if self._text_radio.isChecked():
            text = self._text_input.text().strip()
            if not text:
                QMessageBox.warning(self, "No Text", "Please enter watermark text.")
                return

            config = TextWatermarkConfig(
                input_path=self._current_file,
                output_path=output_path,
                text=text,
                font_size=self._fontsize_spin.value(),
                color=self._get_color_tuple(),
                opacity=self._opacity_slider.value() / 100.0,
                rotation=self._rotation_spin.value(),
            )

            self._start_worker("text", text_config=config)
        else:
            if not self._watermark_image:
                QMessageBox.warning(self, "No Image", "Please select a watermark image.")
                return

            config = ImageWatermarkConfig(
                input_path=self._current_file,
                output_path=output_path,
                image_path=self._watermark_image,
                opacity=self._img_opacity_spin.value(),
                scale=self._img_scale_spin.value(),
                position=self._get_position_str(),
            )

            self._start_worker("image", image_config=config)

    def _start_worker(self, mode, text_config=None, image_config=None):
        self._watermark_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.start()

        self._worker = WatermarkWorker(
            mode=mode,
            text_config=text_config,
            image_config=image_config,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, step: int, total: int, message: str):
        self._progress.update_progress(step, total, message)

    def _on_finished(self, result):
        self._progress.finish()
        self._watermark_btn.setEnabled(True)
        self._worker = None

        if result.success:
            self._result_card.show_simple_result(
                result.output_path,
                title=f"Watermarked! {result.pages_processed} pages",
            )
        else:
            QMessageBox.critical(self, "Error", result.error_message or "Watermarking failed.")
            self._progress.reset()

    def _on_error(self, error_msg: str):
        self._progress.reset()
        self._watermark_btn.setEnabled(True)
        self._worker = None
        QMessageBox.critical(self, "Error", error_msg)

    def _on_cancel_clicked(self):
        if self._worker:
            self._worker.cancel()
            self._worker.wait(5000)
            self._worker = None
        self._progress.reset()
        self._watermark_btn.setEnabled(bool(self._current_file))

    def _on_another(self):
        self._drop_zone.reset()
        self._result_card.reset()
        self._progress.reset()
        self._current_file = ""
        self._watermark_image = ""
        self._img_path_label.setText("No image selected")
        self._preview_label.setText("Select a PDF and watermark image to see preview")
        self._preview_label.setPixmap(QPixmap())
        self._watermark_btn.setEnabled(False)

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            if not self._worker.wait(5000):
                self._worker.terminate()
                self._worker.wait(2000)
        self._worker = None
