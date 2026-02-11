"""Custom widget for target file size input with presets."""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QDoubleSpinBox,
    QLabel, QPushButton,
)
from PyQt6.QtCore import pyqtSignal


class FileSizeInput(QWidget):
    """
    Target file size input: spin box (MB) + preset buttons.
    """

    value_changed = pyqtSignal(float)

    PRESETS = {
        "Email (2 MB)": 2.0,
        "Web (5 MB)": 5.0,
        "Print (10 MB)": 10.0,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Label
        label = QLabel("Target Size")
        label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(label)

        # Input row
        input_row = QHBoxLayout()

        self._spin = QDoubleSpinBox()
        self._spin.setRange(0.1, 500.0)
        self._spin.setSingleStep(0.5)
        self._spin.setValue(5.0)
        self._spin.setSuffix(" MB")
        self._spin.setDecimals(1)
        self._spin.valueChanged.connect(self._on_value_changed)
        input_row.addWidget(self._spin)

        input_row.addSpacing(12)

        # Preset buttons
        self._preset_buttons = []
        for label_text, value in self.PRESETS.items():
            btn = QPushButton(label_text)
            btn.setProperty("class", "presetButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, v=value, b=btn: self._on_preset(v, b))
            input_row.addWidget(btn)
            self._preset_buttons.append((btn, value))

        input_row.addStretch()
        layout.addLayout(input_row)

    def _on_value_changed(self, value: float):
        # Update preset button checked states
        for btn, preset_val in self._preset_buttons:
            btn.setChecked(abs(value - preset_val) < 0.05)
        self.value_changed.emit(value)

    def _on_preset(self, value: float, clicked_btn: QPushButton):
        self._spin.setValue(value)
        for btn, _ in self._preset_buttons:
            btn.setChecked(btn is clicked_btn)

    def value_mb(self) -> float:
        return self._spin.value()

    def value_bytes(self) -> int:
        return int(self._spin.value() * 1024 * 1024)

    def set_value(self, mb: float):
        self._spin.setValue(mb)
