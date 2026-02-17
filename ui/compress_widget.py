"""Compression tab widget."""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox, QScrollArea,
)
from PyQt6.QtCore import Qt

from ui.components.drop_zone import DropZone
from ui.components.file_size_input import FileSizeInput
from ui.components.progress_widget import ProgressWidget
from ui.components.result_card import ResultCard
from workers.compress_worker import CompressWorker
from core.compressor import CompressionConfig
from core.utils import validate_pdf, get_output_path, format_file_size, check_disk_space
from i18n import t


class CompressWidget(QWidget):
    """PDF compression tab with drop zone, target size, progress, and results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = ""
        self._worker: CompressWorker = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        # Scroll area wrapper
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel(t("compress.title"))
        title.setProperty("class", "sectionTitle")
        layout.addWidget(title)

        subtitle = QLabel(t("compress.subtitle"))
        subtitle.setProperty("class", "sectionSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Drop zone
        self._drop_zone = DropZone(
            accepted_extensions=[".pdf"],
            placeholder_text=t("compress.drop_text"),
        )
        layout.addWidget(self._drop_zone)

        # Target size input
        self._size_input = FileSizeInput()
        layout.addWidget(self._size_input)

        # Compress button
        self._compress_btn = QPushButton(t("compress.button"))
        self._compress_btn.setObjectName("primaryButton")
        self._compress_btn.setEnabled(False)
        layout.addWidget(self._compress_btn)

        # Progress
        self._progress = ProgressWidget()
        layout.addWidget(self._progress)

        # Result
        self._result_card = ResultCard()
        layout.addWidget(self._result_card)

        layout.addStretch()

        scroll.setWidget(container)

        # Set scroll as main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _connect_signals(self):
        self._drop_zone.file_selected.connect(self._on_file_selected)
        self._drop_zone.file_removed.connect(self._on_file_removed)
        self._compress_btn.clicked.connect(self._on_compress_clicked)
        self._progress.cancel_clicked.connect(self._on_cancel_clicked)
        self._result_card.compress_another.connect(self._on_another)

    def _on_file_selected(self, file_path: str):
        result = validate_pdf(file_path)
        if not result.valid:
            QMessageBox.warning(self, t("common.invalid_file"), result.error_message)
            self._drop_zone.reset()
            return

        self._current_file = file_path
        self._compress_btn.setEnabled(True)
        self._result_card.reset()
        self._progress.reset()

    def _on_file_removed(self):
        self._current_file = ""
        self._compress_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.reset()

    def _on_compress_clicked(self):
        if not self._current_file:
            return

        target_bytes = self._size_input.value_bytes()
        current_size = os.path.getsize(self._current_file)

        # Already small enough?
        if current_size <= target_bytes:
            QMessageBox.information(
                self, t("compress.already_small_title"),
                t("compress.already_small_msg",
                  current_size=format_file_size(current_size),
                  target_size=f"{self._size_input.value_mb():.1f} MB"),
            )
            return

        output_path = get_output_path(self._current_file)

        # Check disk space
        has_space, space_msg = check_disk_space(os.path.dirname(output_path), current_size)
        if not has_space:
            QMessageBox.warning(self, t("common.disk_space"), space_msg)
            return

        config = CompressionConfig(
            input_path=self._current_file,
            output_path=output_path,
            target_size_bytes=target_bytes,
        )

        self._compress_btn.setEnabled(False)
        self._result_card.reset()
        self._progress.start()

        self._worker = CompressWorker(config)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_compress_finished)
        self._worker.error.connect(self._on_compress_error)
        self._worker.start()

    def _on_progress(self, step: int, total: int, message: str):
        self._progress.update_progress(step, total, message)

    def _on_compress_finished(self, result):
        self._progress.finish()
        self._compress_btn.setEnabled(True)
        self._worker = None

        if result.already_small:
            QMessageBox.information(
                self, t("compress.already_small_title"),
                t("compress.already_small_short"),
            )
            self._progress.reset()
            return

        if result.text_only:
            self._result_card.show_result(
                result.original_size, result.compressed_size, result.output_path,
                title=t("compress.lossless_title"),
            )
            QMessageBox.information(
                self, t("compress.text_only_title"),
                t("compress.text_only_msg"),
            )
            return

        if result.target_impossible:
            min_mb = result.minimum_achievable_size / (1024 * 1024)
            QMessageBox.warning(
                self, t("compress.target_too_small_title"),
                t("compress.target_too_small_msg", min_size=f"{min_mb:.1f}"),
            )
            self._progress.reset()
            return

        if result.success:
            self._result_card.show_result(
                result.original_size, result.compressed_size, result.output_path,
            )
        else:
            QMessageBox.critical(self, t("common.error"), result.error_message or t("compress.failed"))
            self._progress.reset()

    def _on_compress_error(self, error_msg: str):
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
        self._compress_btn.setEnabled(True)

    def _on_another(self):
        self._drop_zone.reset()
        self._result_card.reset()
        self._progress.reset()
        self._current_file = ""
        self._compress_btn.setEnabled(False)

    def cleanup(self):
        """Call on app close to stop running workers."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            if not self._worker.wait(5000):
                self._worker.terminate()
                self._worker.wait(2000)
        self._worker = None
