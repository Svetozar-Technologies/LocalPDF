"""ScreenHeader — standard title + subtitle + actions slot.

Every top-level screen should use this for a consistent header. The actions
slot accepts arbitrary widgets aligned to the right of the title (e.g. a
secondary "Choose file" button).
"""

from typing import Iterable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


class ScreenHeader(QWidget):
    def __init__(
        self,
        title: str,
        subtitle: Optional[str] = None,
        actions: Optional[Iterable[QWidget]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("screenHeader")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self._title = QLabel(title)
        self._title.setProperty("class", "screenTitle")
        text_col.addWidget(self._title)

        self._subtitle: Optional[QLabel] = None
        if subtitle:
            self._subtitle = QLabel(subtitle)
            self._subtitle.setProperty("class", "screenSubtitle")
            self._subtitle.setWordWrap(True)
            text_col.addWidget(self._subtitle)

        outer.addLayout(text_col, 1)

        if actions:
            actions_row = QHBoxLayout()
            actions_row.setContentsMargins(0, 0, 0, 0)
            actions_row.setSpacing(8)
            actions_row.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            for w in actions:
                actions_row.addWidget(w)
            outer.addLayout(actions_row, 0)

    def set_title(self, title: str) -> None:
        self._title.setText(title)

    def set_subtitle(self, subtitle: str) -> None:
        if self._subtitle is not None:
            self._subtitle.setText(subtitle)
