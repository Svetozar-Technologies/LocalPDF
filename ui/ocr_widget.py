"""OCR (Scan to Text) tab widget."""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QScrollArea, QGroupBox, QRadioButton, QButtonGroup, QComboBox,
    QTextEdit, QApplication,
)
from PyQt6.QtCore import Qt

from ui.components.drop_zone import DropZone
from ui.components.progress_widget import ProgressWidget
from ui.components.result_card import ResultCard
from workers.ocr_worker import OCRWorker
from core.utils import validate_pdf, validate_image, get_output_path, detect_tesseract


class OCRWidget(QWidget):
    """OCR tab: extract text from scanned PDFs and images."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = ""
        self._file_is_pdf = False
        self._worker: OCRWorker = None
        self._setup_ui()
        self._connect_signals()
        self._check_tesseract()

    def _setup_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("OCR — Scan to Text")
        title.setProperty("class", "sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("Extract text from scanned PDFs and images using Tesseract OCR. 100% offline.")
        subtitle.setProperty("class", "sectionSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Drop zone (accepts PDF and images)
        self._drop_zone = DropZone(
            accepted_extensions=[".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"],
            placeholder_text="Drop PDF or image here or click to browse",
        )
        layout.addWidget(self._drop_zone)

        # OCR Options
        options_group = QGroupBox("OCR Options")
        options_layout = QVBoxLayout(options_group)

        # Language selection
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Language:"))
        self._lang_combo = QComboBox()
        self._lang_combo.addItem("English", "eng")
        lang_row.addWidget(self._lang_combo)
        lang_row.addStretch()
        options_layout.addLayout(lang_row)

        # Output mode
        self._mode_group = QButtonGroup(self)
        self._extract_radio = QRadioButton("Extract text (copy/paste)")
        self._searchable_radio = QRadioButton("Create searchable PDF (invisible text layer)")
        self._extract_radio.setChecked(True)
        self._mode_group.addButton(self._extract_radio, 0)
        self._mode_group.addButton(self._searchable_radio, 1)
        options_layout.addWidget(self._extract_radio)
        options_layout.addWidget(self._searchable_radio)

        layout.addWidget(options_group)

        # OCR button
        self._ocr_btn = QPushButton("Run OCR")
        self._ocr_btn.setObjectName("primaryButton")
        self._ocr_btn.setEnabled(False)
        layout.addWidget(self._ocr_btn)

        # Progress
        self._progress = ProgressWidget()
        layout.addWidget(self._progress)

        # Result card
        self._result_card = ResultCard()
        layout.addWidget(self._result_card)

        # Text output area
        self._text_group = QGroupBox("Extracted Text")
        text_layout = QVBoxLayout(self._text_group)

        self._text_output = QTextEdit()
        self._text_output.setReadOnly(True)
        self._text_output.setMinimumHeight(200)
        self._text_output.setPlaceholderText("OCR results will appear here...")
        text_layout.addWidget(self._text_output)

        text_btn_row = QHBoxLayout()
        self._copy_btn = QPushButton("Copy to Clipboard")
        self._copy_btn.setProperty("class", "secondaryButton")
        self._copy_btn.setEnabled(False)
        text_btn_row.addWidget(self._copy_btn)

        self._another_btn = QPushButton("Process Another")
        self._another_btn.setProperty("class", "secondaryButton")
        text_btn_row.addWidget(self._another_btn)

        text_btn_row.addStretch()
        text_layout.addLayout(text_btn_row)

        self._text_group.hide()
        layout.addWidget(self._text_group)

        # Tesseract status
        self._tess_status = QLabel()
        self._tess_status.setStyleSheet("font-size: 12px; padding-top: 8px;")
        layout.addWidget(self._tess_status)

        layout.addStretch()

        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _connect_signals(self):
        self._drop_zone.file_selected.connect(self._on_file_selected)
        self._drop_zone.file_removed.connect(self._on_file_removed)
        self._ocr_btn.clicked.connect(self._on_ocr_clicked)
        self._progress.cancel_clicked.connect(self._on_cancel_clicked)
        self._copy_btn.clicked.connect(self._on_copy_clicked)
        self._another_btn.clicked.connect(self._on_another)
        self._result_card.compress_another.connect(self._on_another)

    def _check_tesseract(self):
        tess = detect_tesseract()
        if tess.found:
            version = tess.version or "unknown version"
            self._tess_status.setText(f"Tesseract detected: {version}")
            self._tess_status.setProperty("class", "statusGreen")

            # Populate languages
            self._lang_combo.clear()
            lang_names = {
                "eng": "English", "fra": "French", "deu": "German",
                "spa": "Spanish", "ita": "Italian", "por": "Portuguese",
                "chi_sim": "Chinese (Simplified)", "chi_tra": "Chinese (Traditional)",
                "jpn": "Japanese", "kor": "Korean", "hin": "Hindi",
                "ara": "Arabic", "rus": "Russian",
            }
            for lang in tess.languages:
                display = lang_names.get(lang, lang)
                self._lang_combo.addItem(display, lang)
        else:
            self._tess_status.setText("Tesseract not found — required for OCR")
            self._tess_status.setProperty("class", "statusRed")
            self._ocr_btn.setEnabled(False)
            self._ocr_btn.setToolTip("Install Tesseract to enable OCR")

    def _on_file_selected(self, file_path: str):
        ext = os.path.splitext(file_path)[1].lower()
        self._file_is_pdf = (ext == ".pdf")

        if self._file_is_pdf:
            result = validate_pdf(file_path)
        else:
            result = validate_image(file_path)

        if not result.valid:
            QMessageBox.warning(self, "Invalid File", result.error_message)
            self._drop_zone.reset()
            return

        self._current_file = file_path

        # Enable/disable searchable PDF option based on file type
        self._searchable_radio.setEnabled(self._file_is_pdf)
        if not self._file_is_pdf and self._searchable_radio.isChecked():
            self._extract_radio.setChecked(True)

        tess = detect_tesseract()
        self._ocr_btn.setEnabled(tess.found)
        self._result_card.reset()
        self._progress.reset()
        self._text_group.hide()

    def _on_file_removed(self):
        self._current_file = ""
        self._file_is_pdf = False
        self._ocr_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.reset()
        self._text_group.hide()

    def _on_ocr_clicked(self):
        if not self._current_file:
            return

        language = self._lang_combo.currentData() or "eng"
        make_searchable = self._searchable_radio.isChecked() and self._file_is_pdf

        if make_searchable:
            output_path = get_output_path(self._current_file, suffix="_searchable")
            mode = "searchable_pdf"
        elif self._file_is_pdf:
            output_path = ""
            mode = "extract_pdf"
        else:
            output_path = ""
            mode = "extract_image"

        self._ocr_btn.setEnabled(False)
        self._result_card.reset()
        self._text_group.hide()
        self._progress.start()

        self._worker = OCRWorker(
            mode=mode,
            input_path=self._current_file,
            output_path=output_path,
            language=language,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_ocr_finished)
        self._worker.error.connect(self._on_ocr_error)
        self._worker.start()

    def _on_progress(self, step: int, total: int, message: str):
        self._progress.update_progress(step, total, message)

    def _on_ocr_finished(self, result):
        self._progress.finish()
        self._ocr_btn.setEnabled(True)
        self._worker = None

        if result.tesseract_missing:
            tess = detect_tesseract()
            msg = result.error_message
            if tess.install_instructions:
                msg += "\n\n" + tess.install_instructions
            QMessageBox.warning(self, "Tesseract Required", msg)
            self._progress.reset()
            return

        if result.success:
            # Show searchable PDF result
            if result.output_path:
                self._result_card.show_simple_result(
                    result.output_path,
                    title=f"Searchable PDF created! {result.pages_processed} pages",
                )

            # Show extracted text
            if result.text:
                self._text_output.setPlainText(result.text)
                self._copy_btn.setEnabled(True)
                self._text_group.show()
        else:
            QMessageBox.critical(self, "Error", result.error_message or "OCR failed.")
            self._progress.reset()

    def _on_ocr_error(self, error_msg: str):
        self._progress.reset()
        self._ocr_btn.setEnabled(True)
        self._worker = None
        QMessageBox.critical(self, "Error", error_msg)

    def _on_copy_clicked(self):
        text = self._text_output.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            # Brief feedback
            self._copy_btn.setText("Copied!")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(2000, lambda: self._copy_btn.setText("Copy to Clipboard"))

    def _on_cancel_clicked(self):
        if self._worker:
            self._worker.cancel()
            self._worker.wait(5000)
            self._worker = None
        self._progress.reset()
        tess = detect_tesseract()
        self._ocr_btn.setEnabled(bool(self._current_file) and tess.found)

    def _on_another(self):
        self._drop_zone.reset()
        self._result_card.reset()
        self._progress.reset()
        self._text_output.clear()
        self._text_group.hide()
        self._copy_btn.setEnabled(False)
        self._current_file = ""
        self._file_is_pdf = False
        self._ocr_btn.setEnabled(False)

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            if not self._worker.wait(5000):
                self._worker.terminate()
                self._worker.wait(2000)
        self._worker = None
