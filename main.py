"""LocalPDF - 100% Local PDF Compression & Conversion Tool."""

import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
import fitz  # PyMuPDF

from ui.main_window import MainWindow
from ui.theme import ThemeManager


def main():
    # Suppress non-fatal MuPDF structure tree warnings
    fitz.TOOLS.mupdf_display_errors(False)

    # Ensure working directory for PyInstaller frozen apps
    if getattr(sys, "frozen", False):
        os.chdir(os.path.dirname(sys.executable))

    app = QApplication(sys.argv)
    app.setApplicationName("LocalPDF")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("PrepLadder")

    # Theme
    theme_manager = ThemeManager(app)
    theme_manager.apply_theme()

    # Main window
    window = MainWindow(theme_manager)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
