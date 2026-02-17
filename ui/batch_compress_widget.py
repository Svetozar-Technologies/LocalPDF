"""Batch PDF Compression tab widget."""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox, QScrollArea,
)
from PyQt6.QtCore import Qt

from ui.components.multi_drop_zone import MultiDropZone
from ui.components.file_list_widget import FileListWidget, FileStatus
from ui.components.file_size_input import FileSizeInput
from ui.components.progress_widget import ProgressWidget
from ui.components.result_card import ResultCard
from workers.batch_compress_worker import BatchCompressWorker
from core.utils import validate_pdf, format_file_size
from i18n import t


class BatchCompressWidget(QWidget):
    """Batch compression tab: compress multiple PDFs at once."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: BatchCompressWorker = None
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

        title = QLabel(t("batch_compress.title"))
        title.setProperty("class", "sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel(t("batch_compress.subtitle"))
        subtitle.setProperty("class", "sectionSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._drop_zone = MultiDropZone(
            accepted_extensions=[".pdf"],
            placeholder_text=t("batch_compress.drop_text"),
        )
        layout.addWidget(self._drop_zone)

        self._file_list = FileListWidget(show_status=True)
        layout.addWidget(self._file_list)

        self._size_input = FileSizeInput()
        layout.addWidget(self._size_input)

        self._compress_btn = QPushButton(t("batch_compress.button"))
        self._compress_btn.setObjectName("primaryButton")
        self._compress_btn.setEnabled(False)
        layout.addWidget(self._compress_btn)

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
        self._compress_btn.clicked.connect(self._on_compress_clicked)
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
                self, t("common.some_files_skipped"),
                t("common.files_skipped_msg", errors="\n".join(errors)),
            )

    def _update_button_state(self):
        self._compress_btn.setEnabled(self._file_list.count() >= 1)
        self._drop_zone.set_file_count(self._file_list.count())

    def _on_compress_clicked(self):
        paths = self._file_list.get_paths()
        if not paths:
            return

        target_bytes = self._size_input.value_bytes()

        # Reset all statuses to pending
        for i in range(self._file_list.count()):
            self._file_list.update_file_status(i, FileStatus.PENDING)

        self._compress_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.start()

        self._worker = BatchCompressWorker(paths, target_bytes)
        self._worker.progress.connect(self._on_progress)
        self._worker.file_started.connect(self._on_file_started)
        self._worker.file_finished.connect(self._on_file_finished)
        self._worker.finished.connect(self._on_batch_finished)
        self._worker.error.connect(self._on_batch_error)
        self._worker.start()

    def _on_progress(self, step: int, total: int, message: str):
        self._progress.update_progress(step, total, message)

    def _on_file_started(self, index: int, name: str):
        self._file_list.update_file_status(index, FileStatus.PROCESSING)

    def _on_file_finished(self, index: int, file_result):
        if file_result.success:
            out_name = os.path.basename(file_result.output_path)
            result_text = (
                f"{format_file_size(file_result.original_size)} "
                f"\u2192 {format_file_size(file_result.compressed_size)} "
                f"({out_name})"
            )
            self._file_list.update_file_status(index, FileStatus.DONE, result_text=result_text)
        else:
            self._file_list.update_file_status(
                index, FileStatus.ERROR, error_text=file_result.error_message,
            )

    def _on_batch_finished(self, result):
        self._progress.finish()
        self._compress_btn.setEnabled(True)
        self._worker = None

        output_folder = getattr(result, 'output_folder', '') or ""

        if result.total_original_size > 0:
            self._result_card.show_result(
                result.total_original_size,
                result.total_compressed_size,
                output_folder,
                title=t("batch_compress.complete", succeeded=result.succeeded, total=result.total_files),
            )
        else:
            self._result_card.show_simple_result(
                output_folder,
                title=t("batch_compress.complete_mixed", succeeded=result.succeeded, failed=result.failed),
            )

    def _on_batch_error(self, error_msg: str):
        self._progress.reset()
        self._compress_btn.setEnabled(True)
        self._worker = None
        QMessageBox.critical(self, t("common.error"), error_msg)

    def _on_cancel_clicked(self):
        if self._worker:
            self._worker.cancel()
            self._worker.wait(5000)
            self._worker = None
        self._progress.reset()
        self._compress_btn.setEnabled(self._file_list.count() >= 1)

    def _on_another(self):
        self._file_list.clear()
        self._drop_zone.set_file_count(0)
        self._result_card.reset()
        self._progress.reset()
        self._compress_btn.setEnabled(False)

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            if not self._worker.wait(5000):
                self._worker.terminate()
                self._worker.wait(2000)
        self._worker = None
