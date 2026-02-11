"""PDF to Image tab widget."""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QScrollArea, QGroupBox, QRadioButton, QButtonGroup, QComboBox, QLineEdit,
    QFileDialog,
)
from PyQt6.QtCore import Qt

from ui.components.drop_zone import DropZone
from ui.components.progress_widget import ProgressWidget
from ui.components.result_card import ResultCard
from workers.pdf_to_image_worker import PDFToImageWorker
from core.pdf_to_image import ImageFormat
from core.splitter import PageRangeParser
from core.utils import validate_pdf, format_file_size, check_disk_space


class PDFToImageWidget(QWidget):
    """PDF-to-Image export tab: export pages as PNG or JPEG."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = ""
        self._page_count = 0
        self._worker: PDFToImageWorker = None
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

        title = QLabel("PDF to Image")
        title.setProperty("class", "sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("Export PDF pages as high-quality images. 100% local processing.")
        subtitle.setProperty("class", "sectionSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Drop zone
        self._drop_zone = DropZone(
            accepted_extensions=[".pdf"],
            placeholder_text="Drop PDF here or click to browse",
        )
        layout.addWidget(self._drop_zone)

        # Page info
        self._page_info = QLabel("")
        self._page_info.setProperty("class", "pageInfo")
        self._page_info.hide()
        layout.addWidget(self._page_info)

        # Options group
        options_group = QGroupBox("Export Options")
        options_layout = QVBoxLayout(options_group)

        # Page range
        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Pages:"))
        self._range_input = QLineEdit()
        self._range_input.setPlaceholderText("All pages (or e.g., 1-5, 3, 7-10)")
        range_row.addWidget(self._range_input, 1)
        options_layout.addLayout(range_row)

        # Format selection
        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Format:"))
        self._format_group = QButtonGroup(self)
        self._png_radio = QRadioButton("PNG (lossless)")
        self._jpeg_radio = QRadioButton("JPEG (smaller files)")
        self._png_radio.setChecked(True)
        self._format_group.addButton(self._png_radio)
        self._format_group.addButton(self._jpeg_radio)
        format_row.addWidget(self._png_radio)
        format_row.addWidget(self._jpeg_radio)
        format_row.addStretch()
        options_layout.addLayout(format_row)

        # DPI selection
        dpi_row = QHBoxLayout()
        dpi_row.addWidget(QLabel("Resolution:"))
        self._dpi_combo = QComboBox()
        self._dpi_combo.addItems(["72 DPI (screen)", "150 DPI (standard)", "300 DPI (print quality)", "600 DPI (high quality)"])
        self._dpi_combo.setCurrentIndex(2)  # Default 300 DPI
        dpi_row.addWidget(self._dpi_combo)
        dpi_row.addStretch()
        options_layout.addLayout(dpi_row)

        layout.addWidget(options_group)

        # Export button
        self._export_btn = QPushButton("Export to Images")
        self._export_btn.setObjectName("primaryButton")
        self._export_btn.setEnabled(False)
        layout.addWidget(self._export_btn)

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
        self._export_btn.clicked.connect(self._on_export_clicked)
        self._progress.cancel_clicked.connect(self._on_cancel_clicked)
        self._result_card.compress_another.connect(self._on_another)

    def _on_file_selected(self, file_path: str):
        result = validate_pdf(file_path)
        if not result.valid:
            QMessageBox.warning(self, "Invalid File", result.error_message)
            self._drop_zone.reset()
            return

        self._current_file = file_path
        self._page_count = result.page_count
        self._page_info.setText(f"{result.page_count} pages")
        self._page_info.show()
        self._export_btn.setEnabled(True)
        self._result_card.reset()
        self._progress.reset()

    def _on_file_removed(self):
        self._current_file = ""
        self._page_count = 0
        self._page_info.hide()
        self._export_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.reset()

    def _get_dpi(self) -> int:
        dpi_map = {0: 72, 1: 150, 2: 300, 3: 600}
        return dpi_map.get(self._dpi_combo.currentIndex(), 300)

    def _get_format(self) -> ImageFormat:
        return ImageFormat.JPEG if self._jpeg_radio.isChecked() else ImageFormat.PNG

    def _on_export_clicked(self):
        if not self._current_file:
            return

        # Parse page range
        range_str = self._range_input.text().strip()
        page_numbers = None
        if range_str:
            try:
                page_numbers = PageRangeParser.parse(range_str, self._page_count)
            except ValueError as e:
                QMessageBox.warning(self, "Invalid Page Range", str(e))
                return

        # Select output directory
        output_dir = QFileDialog.getExistingDirectory(
            self, "Select Output Folder",
            os.path.dirname(self._current_file),
        )
        if not output_dir:
            return

        # Check disk space
        file_size = os.path.getsize(self._current_file)
        has_space, space_msg = check_disk_space(output_dir, file_size * 3)
        if not has_space:
            QMessageBox.warning(self, "Disk Space", space_msg)
            return

        self._export_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.start()

        self._worker = PDFToImageWorker(
            input_path=self._current_file,
            output_dir=output_dir,
            page_numbers=page_numbers,
            image_format=self._get_format(),
            dpi=self._get_dpi(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_export_finished)
        self._worker.error.connect(self._on_export_error)
        self._worker.start()

    def _on_progress(self, step: int, total: int, message: str):
        pct = int(step / total * 100) if total > 0 else 0
        self._progress.update_progress(pct, 100, message)

    def _on_export_finished(self, result):
        self._progress.finish()
        self._export_btn.setEnabled(True)
        self._worker = None

        if result.success:
            self._result_card.show_simple_result(
                result.output_dir,
                title=f"Exported {result.pages_exported} pages as images",
            )
        else:
            QMessageBox.critical(self, "Error", result.error_message or "Export failed.")
            self._progress.reset()

    def _on_export_error(self, error_msg: str):
        self._progress.reset()
        self._export_btn.setEnabled(True)
        self._worker = None
        QMessageBox.critical(self, "Error", error_msg)

    def _on_cancel_clicked(self):
        if self._worker:
            self._worker.cancel()
            self._worker.wait(5000)
            self._worker = None
        self._progress.reset()
        self._export_btn.setEnabled(bool(self._current_file))

    def _on_another(self):
        self._drop_zone.reset()
        self._result_card.reset()
        self._progress.reset()
        self._range_input.clear()
        self._current_file = ""
        self._page_count = 0
        self._page_info.hide()
        self._export_btn.setEnabled(False)

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(5000)
