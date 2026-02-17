"""Progress bar with status message and cancel button."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QProgressBar,
    QLabel, QPushButton,
)
from PyQt6.QtCore import pyqtSignal

from i18n import t


class ProgressWidget(QWidget):
    """Progress bar + status label + cancel button. Hidden by default."""

    cancel_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)

        # Progress bar row
        bar_row = QHBoxLayout()

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        bar_row.addWidget(self._bar, 1)

        self._pct_label = QLabel("0%")
        self._pct_label.setProperty("class", "progressPct")
        bar_row.addWidget(self._pct_label)

        layout.addLayout(bar_row)

        # Status + cancel row
        status_row = QHBoxLayout()

        self._status_label = QLabel(t("progress.preparing"))
        self._status_label.setProperty("class", "textCaption")
        status_row.addWidget(self._status_label, 1)

        self._cancel_btn = QPushButton(t("common.cancel"))
        self._cancel_btn.setObjectName("cancelButton")
        self._cancel_btn.clicked.connect(self.cancel_clicked.emit)
        status_row.addWidget(self._cancel_btn)

        layout.addLayout(status_row)

    def start(self):
        """Show widget and reset to 0%."""
        self._bar.setValue(0)
        self._pct_label.setText("0%")
        self._status_label.setText(t("progress.starting"))
        self._cancel_btn.setEnabled(True)
        self.show()

    def update_progress(self, current: int, total: int, message: str):
        """Update progress bar and status text."""
        pct = int(current / total * 100) if total > 0 else 0
        pct = min(pct, 100)
        self._bar.setValue(pct)
        self._pct_label.setText(f"{pct}%")
        self._status_label.setText(message)

    def finish(self):
        """Set to 100%, disable cancel."""
        self._bar.setValue(100)
        self._pct_label.setText("100%")
        self._cancel_btn.setEnabled(False)

    def reset(self):
        """Hide the widget."""
        self._bar.setValue(0)
        self.hide()
