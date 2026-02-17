"""PPT to PDF conversion tab widget."""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QRadioButton, QButtonGroup, QGroupBox, QLineEdit, QCheckBox,
    QFileDialog, QScrollArea, QSlider,
)
from PyQt6.QtCore import Qt

from ui.components.drop_zone import DropZone
from ui.components.progress_widget import ProgressWidget
from ui.components.result_card import ResultCard
from workers.convert_worker import ConvertWorker
from core.utils import validate_ppt, get_output_path, detect_libreoffice
from core.branded_pdf import BrandingConfig
from i18n import t


class ConvertWidget(QWidget):
    """PPT to PDF conversion tab with simple and branded modes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = ""
        self._worker: ConvertWorker = None
        self._cover_image_path = ""
        self._setup_ui()
        self._connect_signals()
        self._check_libreoffice()

    def _setup_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel(t("convert.title"))
        title.setProperty("class", "sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel(t("convert.subtitle"))
        subtitle.setProperty("class", "sectionSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Drop zone
        self._drop_zone = DropZone(
            accepted_extensions=[".ppt", ".pptx"],
            placeholder_text=t("convert.drop_text"),
        )
        layout.addWidget(self._drop_zone)

        # Mode selection
        mode_group = QGroupBox(t("convert.mode_group"))
        mode_layout = QVBoxLayout(mode_group)

        self._mode_group = QButtonGroup(self)
        self._simple_radio = QRadioButton(t("convert.mode_simple"))
        self._branded_radio = QRadioButton(t("convert.mode_branded"))
        self._simple_radio.setChecked(True)
        self._mode_group.addButton(self._simple_radio, 0)
        self._mode_group.addButton(self._branded_radio, 1)
        mode_layout.addWidget(self._simple_radio)
        mode_layout.addWidget(self._branded_radio)
        layout.addWidget(mode_group)

        # Branded options (hidden by default)
        self._branded_options = QGroupBox(t("convert.branded_options"))
        branded_layout = QVBoxLayout(self._branded_options)

        # Brand name
        brand_row = QHBoxLayout()
        brand_row.addWidget(QLabel(t("convert.brand_name")))
        self._brand_input = QLineEdit()
        self._brand_input.setPlaceholderText(t("convert.brand_placeholder"))
        brand_row.addWidget(self._brand_input)
        branded_layout.addLayout(brand_row)

        # Subject name
        row1 = QHBoxLayout()
        row1.addWidget(QLabel(t("convert.subject_name")))
        self._subject_input = QLineEdit()
        self._subject_input.setPlaceholderText(t("convert.subject_placeholder"))
        self._subject_input.setText("ANATOMY")
        row1.addWidget(self._subject_input)
        branded_layout.addLayout(row1)

        # Watermark
        row2 = QHBoxLayout()
        row2.addWidget(QLabel(t("convert.watermark_text")))
        self._watermark_input = QLineEdit()
        self._watermark_input.setPlaceholderText(t("convert.watermark_placeholder"))
        row2.addWidget(self._watermark_input)
        branded_layout.addLayout(row2)

        # Watermark opacity
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel(t("convert.watermark_opacity")))
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setMinimum(1)
        self._opacity_slider.setMaximum(100)
        self._opacity_slider.setValue(6)
        self._opacity_slider.setTickInterval(10)
        self._opacity_label = QLabel("6%")
        self._opacity_label.setFixedWidth(40)
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )
        opacity_row.addWidget(self._opacity_slider)
        opacity_row.addWidget(self._opacity_label)
        branded_layout.addLayout(opacity_row)

        # Page format
        format_row = QHBoxLayout()
        format_row.addWidget(QLabel(t("convert.page_format")))
        self._format_group = QButtonGroup(self)
        self._portrait_radio = QRadioButton(t("convert.portrait_format"))
        self._landscape_radio = QRadioButton(t("convert.landscape_format"))
        self._portrait_radio.setChecked(True)
        self._format_group.addButton(self._portrait_radio, 0)
        self._format_group.addButton(self._landscape_radio, 1)
        format_row.addWidget(self._portrait_radio)
        format_row.addWidget(self._landscape_radio)
        branded_layout.addLayout(format_row)

        # Cover page checkbox
        self._cover_check = QCheckBox(t("convert.include_cover"))
        self._cover_check.setChecked(True)
        branded_layout.addWidget(self._cover_check)

        # Cover image
        cover_row = QHBoxLayout()
        self._cover_btn = QPushButton(t("convert.select_cover"))
        self._cover_btn.setProperty("class", "secondaryButton")
        self._cover_btn.clicked.connect(self._select_cover_image)
        cover_row.addWidget(self._cover_btn)
        self._cover_path_label = QLabel(t("convert.no_image"))
        self._cover_path_label.setProperty("class", "textCaption")
        cover_row.addWidget(self._cover_path_label, 1)
        branded_layout.addLayout(cover_row)

        self._branded_options.hide()
        layout.addWidget(self._branded_options)

        # Convert button
        self._convert_btn = QPushButton(t("convert.button"))
        self._convert_btn.setObjectName("primaryButton")
        self._convert_btn.setEnabled(False)
        layout.addWidget(self._convert_btn)

        # Progress
        self._progress = ProgressWidget()
        layout.addWidget(self._progress)

        # Result
        self._result_card = ResultCard()
        layout.addWidget(self._result_card)

        # LibreOffice status
        self._lo_status = QLabel()
        self._lo_status.setStyleSheet("font-size: 12px; padding-top: 8px;")
        layout.addWidget(self._lo_status)

        # Install LibreOffice button (shown when LO is missing)
        self._install_lo_btn = QPushButton(t("convert.install_lo"))
        self._install_lo_btn.setObjectName("primaryButton")
        self._install_lo_btn.setToolTip(t("convert.install_lo_tooltip"))
        self._install_lo_btn.clicked.connect(self._on_install_libreoffice)
        self._install_lo_btn.hide()
        layout.addWidget(self._install_lo_btn)

        layout.addStretch()

        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _connect_signals(self):
        self._drop_zone.file_selected.connect(self._on_file_selected)
        self._drop_zone.file_removed.connect(self._on_file_removed)
        self._convert_btn.clicked.connect(self._on_convert_clicked)
        self._progress.cancel_clicked.connect(self._on_cancel_clicked)
        self._result_card.compress_another.connect(self._on_another)
        self._mode_group.buttonClicked.connect(self._on_mode_changed)

    def _check_libreoffice(self):
        lo = detect_libreoffice()
        if lo.found:
            version = lo.version.split('\n')[0] if lo.version else ""
            self._lo_status.setText(t("convert.lo_detected", version=version))
            self._lo_status.setProperty("class", "statusGreen")
            self._install_lo_btn.hide()
        else:
            self._lo_status.setText(t("convert.lo_not_found"))
            self._lo_status.setProperty("class", "statusRed")
            self._convert_btn.setEnabled(False)
            self._convert_btn.setToolTip(t("convert.lo_install_hint"))
            self._install_lo_btn.show()

    def _on_mode_changed(self):
        if self._branded_radio.isChecked():
            self._branded_options.show()
        else:
            self._branded_options.hide()

    def _select_cover_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("convert.select_cover_dialog"), "",
            "Images (*.png *.jpg *.jpeg *.bmp *.svg)",
        )
        if path:
            self._cover_image_path = path
            self._cover_path_label.setText(os.path.basename(path))

    def _on_file_selected(self, file_path: str):
        result = validate_ppt(file_path)
        if not result.valid:
            QMessageBox.warning(self, t("common.invalid_file"), result.error_message)
            self._drop_zone.reset()
            return

        self._current_file = file_path
        # Only enable if LibreOffice is found
        lo = detect_libreoffice()
        self._convert_btn.setEnabled(lo.found)
        self._result_card.reset()
        self._progress.reset()

    def _on_file_removed(self):
        self._current_file = ""
        self._convert_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.reset()

    def _on_convert_clicked(self):
        if not self._current_file:
            return

        output_path = get_output_path(self._current_file, suffix="_converted")
        # Change extension to .pdf
        if not output_path.lower().endswith(".pdf"):
            output_path = os.path.splitext(output_path)[0] + ".pdf"

        branded = self._branded_radio.isChecked()
        branding_config = None

        if branded:
            subject = self._subject_input.text().strip() or "Subject"
            watermark = self._watermark_input.text().strip()
            brand_name = self._brand_input.text().strip()
            orientation = "landscape" if self._landscape_radio.isChecked() else "portrait"
            opacity = self._opacity_slider.value() / 100.0
            branding_config = BrandingConfig(
                input_pdf_path="",  # Will be set by worker
                output_path="",     # Will be set by worker
                subject_name=subject,
                watermark_text=watermark,
                watermark_opacity=opacity,
                include_cover=self._cover_check.isChecked(),
                cover_image_path=self._cover_image_path or None,
                brand_name=brand_name,
                page_orientation=orientation,
            )

        self._convert_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.start()

        self._worker = ConvertWorker(
            input_path=self._current_file,
            output_path=output_path,
            branded=branded,
            branding_config=branding_config,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_convert_finished)
        self._worker.error.connect(self._on_convert_error)
        self._worker.start()

    def _on_progress(self, step: int, total: int, message: str):
        self._progress.update_progress(step, total, message)

    def _on_convert_finished(self, result):
        self._progress.finish()
        self._convert_btn.setEnabled(True)
        self._worker = None

        if hasattr(result, 'libreoffice_missing') and result.libreoffice_missing:
            reply = QMessageBox.question(
                self, t("convert.lo_required_title"),
                t("convert.lo_required_msg"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._on_install_libreoffice()
            self._progress.reset()
            return

        success = result.success
        output = getattr(result, 'output_path', '')

        if success and output and os.path.exists(output):
            self._result_card.show_simple_result(output, title=t("convert.complete"))
        else:
            error_msg = getattr(result, 'error_message', t("convert.failed"))
            QMessageBox.critical(self, t("common.error"), error_msg)
            self._progress.reset()

    def _on_convert_error(self, error_msg: str):
        self._progress.reset()
        self._convert_btn.setEnabled(True)
        self._worker = None
        QMessageBox.critical(self, t("common.error"), error_msg)

    def _on_cancel_clicked(self):
        if self._worker:
            self._worker.cancel()
            self._worker.wait(5000)
            self._worker = None
        self._progress.reset()
        self._convert_btn.setEnabled(True)

    def _on_another(self):
        self._drop_zone.reset()
        self._result_card.reset()
        self._progress.reset()
        self._current_file = ""
        self._convert_btn.setEnabled(False)

    def _on_install_libreoffice(self):
        from ui.libreoffice_install_dialog import LibreOfficeInstallDialog
        dialog = LibreOfficeInstallDialog(self)
        dialog.install_completed.connect(self._on_libreoffice_installed)
        dialog.exec()

    def _on_libreoffice_installed(self, soffice_path: str):
        self._check_libreoffice()
        if self._current_file:
            lo = detect_libreoffice()
            self._convert_btn.setEnabled(lo.found)

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            if not self._worker.wait(5000):
                self._worker.terminate()
                self._worker.wait(2000)
        self._worker = None
