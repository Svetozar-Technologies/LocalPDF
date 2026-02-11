"""Theme management: light/dark mode toggle, QSS loading."""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QFont

from core.utils import get_asset_path


class ThemeManager:
    """Manages application theming with light/dark mode support."""

    LIGHT = "light"
    DARK = "dark"

    def __init__(self, app: QApplication):
        self._app = app
        self._settings = QSettings("PrepLadder", "LocalPDF")
        self._current_theme = self._settings.value("theme", self.LIGHT)
        self._setup_font()

    def _setup_font(self):
        """Set system-native font for macOS/Windows."""
        if sys.platform == "darwin":
            font = QFont(".AppleSystemUIFont", 13)
        elif sys.platform == "win32":
            font = QFont("Segoe UI", 10)
        else:
            font = QFont("Ubuntu", 10)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        self._app.setFont(font)

    def apply_theme(self, theme: str = None):
        """Load and apply the QSS file for the given theme."""
        if theme:
            self._current_theme = theme
        qss = self._load_qss(f"{self._current_theme}.qss")
        self._app.setStyleSheet(qss)
        self._settings.setValue("theme", self._current_theme)

    def toggle_theme(self) -> str:
        """Switch between light and dark. Returns new theme name."""
        new_theme = self.DARK if self._current_theme == self.LIGHT else self.LIGHT
        self.apply_theme(new_theme)
        return new_theme

    def current_theme(self) -> str:
        return self._current_theme

    @staticmethod
    def _load_qss(filename: str) -> str:
        """Read QSS file from assets/styles/ directory."""
        qss_path = get_asset_path(f"assets/styles/{filename}")
        try:
            with open(qss_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            return ""
