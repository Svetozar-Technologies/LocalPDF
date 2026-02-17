"""Reusable multi-file drag-and-drop zone widget."""

import os
from pathlib import Path
from typing import List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QPen, QColor

from i18n import t


class MultiDropZone(QWidget):
    """
    A dashed-border zone that accepts multiple file drops and clicks.
    Emits files_selected(list[str]) when valid files are provided.
    Stateless — parent manages the file list.
    """

    files_selected = pyqtSignal(list)

    def __init__(
        self,
        accepted_extensions: List[str] = None,
        placeholder_text: str = "Drop files here or click to browse",
        parent=None,
    ):
        super().__init__(parent)
        self._accepted_extensions = [e.lower() for e in (accepted_extensions or [".pdf"])]
        self._placeholder_text = placeholder_text
        self._file_count = 0
        self._drag_over = False
        self.setAcceptDrops(True)
        self.setObjectName("multiDropZone")
        self.setMinimumHeight(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()

    def _setup_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon_label = QLabel("\U0001F4C2")
        self._icon_label.setObjectName("dropIcon")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._icon_label)

        self._text_label = QLabel(self._placeholder_text)
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setWordWrap(True)
        self._layout.addWidget(self._text_label)

    def set_file_count(self, count: int):
        """Update visual to show how many files are loaded."""
        self._file_count = count
        if count > 0:
            self._text_label.setText(t("drop_zone.files_loaded", count=count))
        else:
            self._text_label.setText(self._placeholder_text)
        self.update()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(self._validate_extension(u.toLocalFile()) for u in urls):
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
        valid_paths = []
        for url in urls:
            path = url.toLocalFile()
            if self._validate_extension(path):
                valid_paths.append(path)
        if valid_paths:
            self.files_selected.emit(valid_paths)
            event.acceptProposedAction()
        else:
            event.ignore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._browse_files()

    def _browse_files(self):
        exts = " ".join(f"*{e}" for e in self._accepted_extensions)
        file_filter = f"Supported Files ({exts})"
        paths, _ = QFileDialog.getOpenFileNames(self, t("common.select_files"), "", file_filter)
        if paths:
            self.files_selected.emit(paths)

    def _validate_extension(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in self._accepted_extensions

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._drag_over:
            pen = QPen(QColor("#007AFF"), 2, Qt.PenStyle.CustomDashLine)
            pen.setDashPattern([8, 4])
        elif self._file_count > 0:
            pen = QPen(QColor("#34C759"), 2, Qt.PenStyle.SolidLine)
        else:
            pen = QPen(QColor("#E5E5EA"), 2, Qt.PenStyle.CustomDashLine)
            pen.setDashPattern([8, 6])

        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)
        painter.end()
