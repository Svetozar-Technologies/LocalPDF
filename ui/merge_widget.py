"""PDF Merge tab widget."""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox, QScrollArea,
)
from PyQt6.QtCore import Qt

from ui.components.multi_drop_zone import MultiDropZone
from ui.components.file_list_widget import FileListWidget
from ui.components.progress_widget import ProgressWidget
from ui.components.result_card import ResultCard
from workers.merge_worker import MergeWorker
from core.utils import validate_pdf, get_output_path, format_file_size, check_disk_space


class MergeWidget(QWidget):
    """PDF merge tab: drop multiple PDFs, reorder, merge into one."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: MergeWorker = None
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

        title = QLabel("Merge PDFs")
        title.setProperty("class", "sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("Combine multiple PDF files into a single document. Drag to reorder.")
        subtitle.setProperty("class", "sectionSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._drop_zone = MultiDropZone(
            accepted_extensions=[".pdf"],
            placeholder_text="Drop PDF files here or click to browse",
        )
        layout.addWidget(self._drop_zone)

        self._file_list = FileListWidget(show_status=False)
        layout.addWidget(self._file_list)

        self._merge_btn = QPushButton("Merge PDFs")
        self._merge_btn.setObjectName("primaryButton")
        self._merge_btn.setEnabled(False)
        layout.addWidget(self._merge_btn)

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
        self._drop_zone.files_selected.connect(self._on_files_added)
        self._file_list.files_changed.connect(self._update_button_state)
        self._merge_btn.clicked.connect(self._on_merge_clicked)
        self._progress.cancel_clicked.connect(self._on_cancel_clicked)
        self._result_card.compress_another.connect(self._on_another)

    def _on_files_added(self, paths):
        valid_paths = []
        errors = []
        for path in paths:
            result = validate_pdf(path)
            if result.valid:
                valid_paths.append(path)
            else:
                errors.append(f"{os.path.basename(path)}: {result.error_message}")

        if valid_paths:
            self._file_list.add_files(valid_paths)
            self._drop_zone.set_file_count(self._file_list.count())

        if errors:
            QMessageBox.warning(
                self, "Some Files Skipped",
                "The following files were skipped:\n\n" + "\n".join(errors),
            )

    def _update_button_state(self):
        self._merge_btn.setEnabled(self._file_list.count() >= 2)
        self._drop_zone.set_file_count(self._file_list.count())

    def _on_merge_clicked(self):
        paths = self._file_list.get_paths()
        if len(paths) < 2:
            return

        output_path = get_output_path(paths[0], suffix="_merged")

        total_size = sum(os.path.getsize(p) for p in paths)
        has_space, space_msg = check_disk_space(os.path.dirname(output_path), total_size)
        if not has_space:
            QMessageBox.warning(self, "Disk Space", space_msg)
            return

        self._merge_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.start()

        self._worker = MergeWorker(paths, output_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_merge_finished)
        self._worker.error.connect(self._on_merge_error)
        self._worker.start()

    def _on_progress(self, step: int, total: int, message: str):
        pct = int(step / total * 100) if total > 0 else 0
        self._progress.update_progress(pct, 100, message)

    def _on_merge_finished(self, result):
        self._progress.finish()
        self._merge_btn.setEnabled(True)
        self._worker = None

        if result.success:
            self._result_card.show_simple_result(
                result.output_path,
                title=f"Merged! {result.total_pages} pages, {format_file_size(result.output_size)}",
            )
        else:
            QMessageBox.critical(self, "Error", result.error_message or "Merge failed.")
            self._progress.reset()

    def _on_merge_error(self, error_msg: str):
        self._progress.reset()
        self._merge_btn.setEnabled(True)
        self._worker = None
        QMessageBox.critical(self, "Error", error_msg)

    def _on_cancel_clicked(self):
        if self._worker:
            self._worker.cancel()
            self._worker.wait(5000)
            self._worker = None
        self._progress.reset()
        self._merge_btn.setEnabled(self._file_list.count() >= 2)

    def _on_another(self):
        self._file_list.clear()
        self._drop_zone.set_file_count(0)
        self._result_card.reset()
        self._progress.reset()
        self._merge_btn.setEnabled(False)

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            if not self._worker.wait(5000):
                self._worker.terminate()
                self._worker.wait(2000)
        self._worker = None
