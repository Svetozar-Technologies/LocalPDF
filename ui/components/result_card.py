"""Before/after comparison result card."""

import os
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices

from core.utils import format_file_size


class ResultCard(QWidget):
    """Shows compression/conversion results with before/after and action buttons."""

    compress_another = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._output_path = ""
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        self.setObjectName("resultCard")
        layout = QVBoxLayout(self)

        # Title
        self._title_label = QLabel("Compression Complete!")
        self._title_label.setProperty("class", "resultTitle")
        layout.addWidget(self._title_label)

        # Size comparison row
        size_row = QHBoxLayout()

        self._before_label = QLabel()
        self._before_label.setProperty("class", "resultValue")
        size_row.addWidget(self._before_label)

        arrow = QLabel("  ->  ")
        arrow.setProperty("class", "resultArrow")
        size_row.addWidget(arrow)

        self._after_label = QLabel()
        self._after_label.setProperty("class", "resultValue")
        size_row.addWidget(self._after_label)

        self._reduction_label = QLabel()
        self._reduction_label.setProperty("class", "resultReduction")
        size_row.addWidget(self._reduction_label)

        size_row.addStretch()
        layout.addLayout(size_row)

        # Buttons row
        btn_row = QHBoxLayout()

        self._open_file_btn = QPushButton("Open File")
        self._open_file_btn.setProperty("class", "secondaryButton")
        self._open_file_btn.clicked.connect(self._open_file)
        btn_row.addWidget(self._open_file_btn)

        self._open_folder_btn = QPushButton("Open Folder")
        self._open_folder_btn.setProperty("class", "secondaryButton")
        self._open_folder_btn.clicked.connect(self._open_folder)
        btn_row.addWidget(self._open_folder_btn)

        self._another_btn = QPushButton("Process Another")
        self._another_btn.setProperty("class", "secondaryButton")
        self._another_btn.clicked.connect(self.compress_another.emit)
        btn_row.addWidget(self._another_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def show_result(
        self,
        original_size: int,
        compressed_size: int,
        output_path: str,
        title: str = "Compression Complete!",
    ):
        """Populate and show the card."""
        self._output_path = output_path
        self._title_label.setText(title)
        self._before_label.setText(f"Before: {format_file_size(original_size)}")
        self._after_label.setText(f"After: {format_file_size(compressed_size)}")

        if original_size > 0 and compressed_size < original_size:
            reduction = (1 - compressed_size / original_size) * 100
            self._reduction_label.setText(f"({reduction:.0f}% smaller)")
        else:
            self._reduction_label.setText("")

        # Hide "Open File" if no specific file path
        self._open_file_btn.setVisible(bool(output_path))
        self.show()

    def show_simple_result(self, output_path: str, title: str = "Done!"):
        """Show result without size comparison (for conversions)."""
        self._output_path = output_path
        self._title_label.setText(title)
        self._before_label.setText("")
        self._after_label.setText(f"Saved: {os.path.basename(output_path)}")

        size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        self._reduction_label.setText(f"({format_file_size(size)})" if size > 0 else "")

        # Hide "Open File" if path is a directory or empty
        is_file = bool(output_path) and os.path.isfile(output_path)
        self._open_file_btn.setVisible(is_file)
        self.show()

    def _open_file(self):
        if self._output_path and os.path.exists(self._output_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._output_path))

    def _open_folder(self):
        if self._output_path:
            if os.path.isdir(self._output_path):
                folder = self._output_path
            else:
                folder = os.path.dirname(self._output_path)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def reset(self):
        self.hide()
