"""Settings tab widget."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QFileDialog, QScrollArea,
)
from PyQt6.QtCore import Qt, QSettings

from core.utils import detect_libreoffice, get_libreoffice_install_instructions


class SettingsWidget(QWidget):
    """Settings tab: theme, output folder, LibreOffice status."""

    def __init__(self, theme_manager=None, parent=None):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._settings = QSettings("PrepLadder", "LocalPDF")
        self._setup_ui()

    def _setup_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Settings")
        title.setProperty("class", "sectionTitle")
        layout.addWidget(title)

        # Appearance
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QVBoxLayout(appearance_group)

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme:"))
        self._theme_btn = QPushButton("Switch to Dark Mode")
        self._theme_btn.setProperty("class", "secondaryButton")
        self._theme_btn.clicked.connect(self._toggle_theme)
        theme_row.addWidget(self._theme_btn)
        theme_row.addStretch()
        appearance_layout.addLayout(theme_row)

        layout.addWidget(appearance_group)

        # Default output folder
        output_group = QGroupBox("Default Output Folder")
        output_layout = QVBoxLayout(output_group)

        folder_row = QHBoxLayout()
        self._folder_label = QLabel(self._settings.value("output_folder", "Same as input file"))
        self._folder_label.setStyleSheet("font-size: 13px; color: #555;")
        folder_row.addWidget(self._folder_label, 1)

        browse_btn = QPushButton("Browse")
        browse_btn.setProperty("class", "secondaryButton")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(browse_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.setProperty("class", "secondaryButton")
        reset_btn.clicked.connect(self._reset_folder)
        folder_row.addWidget(reset_btn)

        output_layout.addLayout(folder_row)
        layout.addWidget(output_group)

        # LibreOffice
        lo_group = QGroupBox("LibreOffice (for PPT conversion)")
        lo_layout = QVBoxLayout(lo_group)

        self._lo_label = QLabel("Checking...")
        self._lo_label.setWordWrap(True)
        self._lo_label.setStyleSheet("font-size: 13px;")
        lo_layout.addWidget(self._lo_label)

        self._lo_install_btn = QPushButton("View Install Instructions")
        self._lo_install_btn.setProperty("class", "secondaryButton")
        self._lo_install_btn.clicked.connect(self._show_lo_instructions)
        self._lo_install_btn.hide()
        lo_layout.addWidget(self._lo_install_btn)

        layout.addWidget(lo_group)

        # About
        about_group = QGroupBox("About")
        about_layout = QVBoxLayout(about_group)
        about_text = QLabel(
            "LocalPDF v1.0\n\n"
            "Free PDF compression and PPT conversion tool.\n"
            "100% local processing — your files never leave your computer.\n\n"
            "Built with Python, PyQt6, and PyMuPDF."
        )
        about_text.setWordWrap(True)
        about_text.setStyleSheet("font-size: 13px; color: #555; line-height: 1.4;")
        about_layout.addWidget(about_text)
        layout.addWidget(about_group)

        layout.addStretch()

        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        # Refresh LibreOffice status
        self._refresh_lo_status()
        self._update_theme_button()

    def _toggle_theme(self):
        if self._theme_manager:
            self._theme_manager.toggle_theme()
            self._update_theme_button()

    def _update_theme_button(self):
        if self._theme_manager:
            current = self._theme_manager.current_theme()
            if current == "dark":
                self._theme_btn.setText("Switch to Light Mode")
            else:
                self._theme_btn.setText("Switch to Dark Mode")

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self._settings.setValue("output_folder", folder)
            self._folder_label.setText(folder)

    def _reset_folder(self):
        self._settings.remove("output_folder")
        self._folder_label.setText("Same as input file")

    def _refresh_lo_status(self):
        lo = detect_libreoffice()
        if lo.found:
            version = lo.version.split('\n')[0] if lo.version else "unknown version"
            self._lo_label.setText(f"Installed: {version}\nPath: {lo.path}")
            self._lo_label.setProperty("class", "statusGreen")
            self._lo_install_btn.hide()
        else:
            self._lo_label.setText("Not installed. Required for PPT to PDF conversion.")
            self._lo_label.setProperty("class", "statusRed")
            self._lo_install_btn.show()

    def _show_lo_instructions(self):
        from PyQt6.QtWidgets import QMessageBox
        instructions = get_libreoffice_install_instructions()
        QMessageBox.information(self, "Install LibreOffice", instructions)
