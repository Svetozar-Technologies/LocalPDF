"""Reorderable file list widget with optional status badges."""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal

from core.utils import format_file_size


class FileStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


@dataclass
class FileEntry:
    path: str
    name: str
    size_bytes: int
    status: FileStatus = FileStatus.PENDING
    result_text: str = ""
    error_text: str = ""


class _FileRow(QFrame):
    """Single row in the file list."""

    move_up_clicked = pyqtSignal(int)
    move_down_clicked = pyqtSignal(int)
    remove_clicked = pyqtSignal(int)

    def __init__(self, index: int, entry: FileEntry, show_status: bool = False, parent=None):
        super().__init__(parent)
        self._index = index
        self._entry = entry
        self._show_status = show_status
        self.setProperty("class", "fileRow")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Index label
        self._index_label = QLabel(f"{self._index + 1}.")
        self._index_label.setFixedWidth(28)
        self._index_label.setProperty("class", "fileRowIndex")
        layout.addWidget(self._index_label)

        # Filename (elided)
        self._name_label = QLabel(self._entry.name)
        self._name_label.setProperty("class", "fileName")
        self._name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._name_label.setMinimumWidth(100)
        layout.addWidget(self._name_label, 1)

        # Size
        self._size_label = QLabel(format_file_size(self._entry.size_bytes))
        self._size_label.setProperty("class", "fileRowSize")
        self._size_label.setFixedWidth(70)
        layout.addWidget(self._size_label)

        # Status badge (optional)
        if self._show_status:
            self._status_label = QLabel("")
            self._status_label.setFixedWidth(100)
            self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._update_status_display()
            layout.addWidget(self._status_label)

        # Up button
        up_btn = QPushButton("\u25B2")
        up_btn.setProperty("class", "rowAction")
        up_btn.setFixedSize(28, 28)
        up_btn.setToolTip("Move up")
        up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        up_btn.clicked.connect(lambda: self.move_up_clicked.emit(self._index))
        layout.addWidget(up_btn)

        # Down button
        down_btn = QPushButton("\u25BC")
        down_btn.setProperty("class", "rowAction")
        down_btn.setFixedSize(28, 28)
        down_btn.setToolTip("Move down")
        down_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        down_btn.clicked.connect(lambda: self.move_down_clicked.emit(self._index))
        layout.addWidget(down_btn)

        # Remove button
        remove_btn = QPushButton("\u2715")
        remove_btn.setProperty("class", "rowActionRemove")
        remove_btn.setFixedSize(28, 28)
        remove_btn.setToolTip("Remove")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self._index))
        layout.addWidget(remove_btn)

    def _update_status_display(self):
        if not self._show_status:
            return
        status = self._entry.status
        if status == FileStatus.PENDING:
            self._status_label.setText("Pending")
            self._status_label.setProperty("class", "statusPending")
        elif status == FileStatus.PROCESSING:
            self._status_label.setText("Processing...")
            self._status_label.setProperty("class", "statusProcessing")
        elif status == FileStatus.DONE:
            text = self._entry.result_text or "Done"
            self._status_label.setText(text)
            self._status_label.setProperty("class", "statusDone")
        elif status == FileStatus.ERROR:
            text = self._entry.error_text or "Error"
            self._status_label.setText(text)
            self._status_label.setProperty("class", "statusError")
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)

    def update_status(self, status: FileStatus, result_text: str = "", error_text: str = ""):
        self._entry.status = status
        self._entry.result_text = result_text
        self._entry.error_text = error_text
        if self._show_status:
            self._update_status_display()

    def set_index(self, index: int):
        self._index = index
        self._index_label.setText(f"{index + 1}.")


class FileListWidget(QWidget):
    """
    Displays a reorderable list of files with per-file actions.
    Supports: add, remove, reorder (up/down buttons), optional status column.
    """

    files_changed = pyqtSignal()
    file_removed = pyqtSignal(int)

    def __init__(self, show_status: bool = False, parent=None):
        super().__init__(parent)
        self._show_status = show_status
        self._entries: List[FileEntry] = []
        self._rows: List[_FileRow] = []
        self.setObjectName("fileListWidget")
        self._setup_ui()

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setMaximumHeight(280)

        self._container = QWidget()
        self._list_layout = QVBoxLayout(self._container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._container)
        outer_layout.addWidget(self._scroll)

        # Empty state label
        self._empty_label = QLabel("No files added yet")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setProperty("class", "helperText")
        self._empty_label.setMinimumHeight(40)
        outer_layout.addWidget(self._empty_label)

        self._update_visibility()

    def _update_visibility(self):
        has_files = len(self._entries) > 0
        self._scroll.setVisible(has_files)
        self._empty_label.setVisible(not has_files)

    def add_files(self, paths: List[str]):
        """Add files to the list, skipping duplicates by path."""
        existing_paths = {e.path for e in self._entries}
        added = False
        for path in paths:
            if path in existing_paths:
                continue
            if not os.path.exists(path):
                continue
            entry = FileEntry(
                path=path,
                name=os.path.basename(path),
                size_bytes=os.path.getsize(path),
            )
            self._entries.append(entry)
            existing_paths.add(path)
            added = True

        if added:
            self._rebuild_rows()
            self.files_changed.emit()

    def remove_file(self, index: int):
        """Remove file at index."""
        if 0 <= index < len(self._entries):
            self._entries.pop(index)
            self._rebuild_rows()
            self.file_removed.emit(index)
            self.files_changed.emit()

    def move_up(self, index: int):
        """Swap file at index with index-1."""
        if index > 0:
            self._entries[index], self._entries[index - 1] = (
                self._entries[index - 1], self._entries[index]
            )
            self._rebuild_rows()
            self.files_changed.emit()

    def move_down(self, index: int):
        """Swap file at index with index+1."""
        if index < len(self._entries) - 1:
            self._entries[index], self._entries[index + 1] = (
                self._entries[index + 1], self._entries[index]
            )
            self._rebuild_rows()
            self.files_changed.emit()

    def get_files(self) -> List[FileEntry]:
        return list(self._entries)

    def get_paths(self) -> List[str]:
        return [e.path for e in self._entries]

    def update_file_status(
        self, index: int, status: FileStatus,
        result_text: str = "", error_text: str = "",
    ):
        """Update the status badge for a specific file (batch mode)."""
        if 0 <= index < len(self._entries):
            self._entries[index].status = status
            self._entries[index].result_text = result_text
            self._entries[index].error_text = error_text
            if index < len(self._rows):
                self._rows[index].update_status(status, result_text, error_text)

    def clear(self):
        self._entries.clear()
        self._rebuild_rows()
        self.files_changed.emit()

    def count(self) -> int:
        return len(self._entries)

    def _rebuild_rows(self):
        """Rebuild all row widgets from entries."""
        # Remove old rows
        for row in self._rows:
            self._list_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        # Create new rows
        for i, entry in enumerate(self._entries):
            row = _FileRow(i, entry, show_status=self._show_status)
            row.move_up_clicked.connect(self.move_up)
            row.move_down_clicked.connect(self.move_down)
            row.remove_clicked.connect(self.remove_file)
            self._list_layout.insertWidget(i, row)
            self._rows.append(row)

        self._update_visibility()
