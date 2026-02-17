"""Reusable drag-and-drop file zone widget."""

import os
from pathlib import Path
from typing import List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QPen, QColor

from core.utils import format_file_size
from i18n import t


class DropZone(QWidget):
    """
    A dashed-border zone that accepts file drops and clicks.
    Emits file_selected(str) when a valid file is provided.
    """

    file_selected = pyqtSignal(str)
    file_removed = pyqtSignal()

    def __init__(
        self,
        accepted_extensions: List[str] = None,
        placeholder_text: str = "Drop file here or click to browse",
        parent=None,
    ):
        super().__init__(parent)
        self._accepted_extensions = accepted_extensions or [".pdf"]
        self._placeholder_text = placeholder_text
        self._current_file = ""
        self._drag_over = False
        self.setAcceptDrops(True)
        self.setObjectName("dropZone")
        self.setMinimumHeight(150)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()

    def _setup_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon
        self._icon_label = QLabel("\U0001F4C4")
        self._icon_label.setObjectName("dropIcon")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._icon_label)

        # Placeholder text
        self._text_label = QLabel(self._placeholder_text)
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setWordWrap(True)
        self._layout.addWidget(self._text_label)

        # File info (hidden initially)
        self._file_row = QWidget()
        file_layout = QHBoxLayout(self._file_row)
        file_layout.setContentsMargins(0, 0, 0, 0)

        self._file_name_label = QLabel()
        self._file_name_label.setProperty("class", "fileInfo")
        file_layout.addWidget(self._file_name_label)

        self._file_size_label = QLabel()
        self._file_size_label.setProperty("class", "fileSize")
        file_layout.addWidget(self._file_size_label)

        file_layout.addStretch()

        self._remove_btn = QPushButton(t("common.remove"))
        self._remove_btn.setProperty("class", "secondaryButton")
        self._remove_btn.clicked.connect(self.reset)
        file_layout.addWidget(self._remove_btn)

        self._file_row.hide()
        self._layout.addWidget(self._file_row)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and self._validate_extension(urls[0].toLocalFile()):
                event.acceptProposedAction()
                self._drag_over = True
                self.update()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._drag_over = False
        self.update()

    def dropEvent(self, event: QDropEvent):
        self._drag_over = False
        self.update()
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if self._validate_extension(file_path):
                self._set_file(file_path)
                event.acceptProposedAction()
                return
        event.ignore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._current_file:
            self._browse_file()

    def _browse_file(self):
        exts = " ".join(f"*{e}" for e in self._accepted_extensions)
        file_filter = f"Supported Files ({exts})"
        path, _ = QFileDialog.getOpenFileName(self, t("common.select_file"), "", file_filter)
        if path:
            self._set_file(path)

    def _validate_extension(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in self._accepted_extensions

    def _set_file(self, file_path: str):
        self._current_file = file_path
        name = os.path.basename(file_path)
        size = os.path.getsize(file_path)

        self._icon_label.hide()
        self._text_label.hide()
        self._file_name_label.setText(name)
        self._file_size_label.setText(format_file_size(size))
        self._file_row.show()

        self.file_selected.emit(file_path)

    def reset(self):
        self._current_file = ""
        self._icon_label.show()
        self._text_label.show()
        self._file_row.hide()
        self.file_removed.emit()

    def current_file(self) -> str:
        return self._current_file

    def paintEvent(self, event):
        super().paintEvent(event)
        # Draw dashed border
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._drag_over:
            pen = QPen(QColor("#007AFF"), 2, Qt.PenStyle.CustomDashLine)
            pen.setDashPattern([8, 4])
        elif self._current_file:
            pen = QPen(QColor("#34C759"), 2, Qt.PenStyle.SolidLine)
        else:
            pen = QPen(QColor("#E5E5EA"), 2, Qt.PenStyle.CustomDashLine)
            pen.setDashPattern([8, 6])

        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)
        painter.end()
