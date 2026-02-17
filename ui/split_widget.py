"""PDF Split / Extract Pages tab widget."""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QScrollArea, QLineEdit, QCheckBox, QGroupBox,
)
from PyQt6.QtCore import Qt

from ui.components.drop_zone import DropZone
from ui.components.progress_widget import ProgressWidget
from ui.components.result_card import ResultCard
from workers.split_worker import SplitWorker
from core.splitter import PageRangeParser
from core.utils import validate_pdf, get_output_path, format_file_size, check_disk_space


class SplitWidget(QWidget):
    """PDF split/extract tab: select pages from a PDF to extract."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = ""
        self._page_count = 0
        self._worker: SplitWorker = None
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

        title = QLabel("Split / Extract Pages")
        title.setProperty("class", "sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("Extract specific pages from a PDF or split into individual page files.")
        subtitle.setProperty("class", "sectionSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

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

        # Page selection group
        page_group = QGroupBox("Page Selection")
        page_layout = QVBoxLayout(page_group)

        self._range_input = QLineEdit()
        self._range_input.setPlaceholderText("e.g., 1-5, 3, 7-10")
        page_layout.addWidget(self._range_input)

        helper = QLabel("Enter page numbers separated by commas. Use hyphens for ranges.")
        helper.setProperty("class", "helperText")
        helper.setWordWrap(True)
        page_layout.addWidget(helper)

        self._split_check = QCheckBox("Split into individual pages (one PDF per page)")
        page_layout.addWidget(self._split_check)

        layout.addWidget(page_group)

        self._extract_btn = QPushButton("Extract Pages")
        self._extract_btn.setObjectName("primaryButton")
        self._extract_btn.setEnabled(False)
        layout.addWidget(self._extract_btn)

        self._progress = ProgressWidget()
        layout.addWidget(self._progress)

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
        self._range_input.textChanged.connect(self._update_button_state)
        self._extract_btn.clicked.connect(self._on_extract_clicked)
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
        self._result_card.reset()
        self._progress.reset()
        self._update_button_state()

    def _on_file_removed(self):
        self._current_file = ""
        self._page_count = 0
        self._page_info.hide()
        self._extract_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.reset()

    def _update_button_state(self):
        has_file = bool(self._current_file)
        has_range = bool(self._range_input.text().strip())
        self._extract_btn.setEnabled(has_file and has_range)

    def _on_extract_clicked(self):
        if not self._current_file:
            return

        range_str = self._range_input.text().strip()
        try:
            page_numbers = PageRangeParser.parse(range_str, self._page_count)
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Page Range", str(e))
            return

        split_individual = self._split_check.isChecked()

        if split_individual:
            output_dir = os.path.dirname(self._current_file)
            has_space, space_msg = check_disk_space(
                output_dir, os.path.getsize(self._current_file),
            )
            if not has_space:
                QMessageBox.warning(self, "Disk Space", space_msg)
                return

            self._worker = SplitWorker(
                input_path=self._current_file,
                output_path="",
                output_dir=output_dir,
                page_numbers=page_numbers,
                split_individual=True,
            )
        else:
            output_path = get_output_path(self._current_file, suffix="_extracted")
            has_space, space_msg = check_disk_space(
                os.path.dirname(output_path), os.path.getsize(self._current_file),
            )
            if not has_space:
                QMessageBox.warning(self, "Disk Space", space_msg)
                return

            self._worker = SplitWorker(
                input_path=self._current_file,
                output_path=output_path,
                output_dir="",
                page_numbers=page_numbers,
                split_individual=False,
            )

        self._extract_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.start()

        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_split_finished)
        self._worker.error.connect(self._on_split_error)
        self._worker.start()

    def _on_progress(self, step: int, total: int, message: str):
        pct = int(step / total * 100) if total > 0 else 0
        self._progress.update_progress(pct, 100, message)

    def _on_split_finished(self, result):
        self._progress.finish()
        self._extract_btn.setEnabled(True)
        self._worker = None

        if result.success:
            if len(result.output_paths) == 1:
                self._result_card.show_simple_result(
                    result.output_paths[0],
                    title=f"Extracted {result.total_pages_extracted} pages ({format_file_size(result.total_output_size)})",
                )
            else:
                # Multiple files — show the folder
                folder = os.path.dirname(result.output_paths[0])
                self._result_card.show_simple_result(
                    folder,
                    title=f"Created {len(result.output_paths)} files ({format_file_size(result.total_output_size)} total)",
                )
        else:
            QMessageBox.critical(self, "Error", result.error_message or "Split failed.")
            self._progress.reset()

    def _on_split_error(self, error_msg: str):
        self._progress.reset()
        self._extract_btn.setEnabled(True)
        self._worker = None
        QMessageBox.critical(self, "Error", error_msg)

    def _on_cancel_clicked(self):
        if self._worker:
            self._worker.cancel()
            self._worker.wait(5000)
            self._worker = None
        self._progress.reset()
        self._update_button_state()

    def _on_another(self):
        self._drop_zone.reset()
        self._result_card.reset()
        self._progress.reset()
        self._range_input.clear()
        self._split_check.setChecked(False)
        self._current_file = ""
        self._page_count = 0
        self._page_info.hide()
        self._extract_btn.setEnabled(False)

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            if not self._worker.wait(5000):
                self._worker.terminate()
                self._worker.wait(2000)
        self._worker = None
