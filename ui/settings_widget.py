"""Settings tab widget."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QFileDialog, QScrollArea, QComboBox, QMessageBox,
)
from PyQt6.QtCore import Qt, QSettings

from core.utils import detect_libreoffice, get_libreoffice_install_instructions
from i18n import t, LANGUAGES, current_language, set_language


class SettingsWidget(QWidget):
    """Settings tab: theme, output folder, LibreOffice status."""

    def __init__(self, theme_manager=None, parent=None):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._settings = QSettings("Svetozar Technologies", "LocalPDF")
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
        title = QLabel(t("settings.title"))
        title.setProperty("class", "sectionTitle")
        layout.addWidget(title)

        # Appearance
        appearance_group = QGroupBox(t("settings.appearance"))
        appearance_layout = QVBoxLayout(appearance_group)

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel(t("settings.theme")))
        self._theme_btn = QPushButton(t("settings.switch_dark"))
        self._theme_btn.setProperty("class", "secondaryButton")
        self._theme_btn.clicked.connect(self._toggle_theme)
        theme_row.addWidget(self._theme_btn)
        theme_row.addStretch()
        appearance_layout.addLayout(theme_row)

        layout.addWidget(appearance_group)

        # Language
        lang_group = QGroupBox(t("settings.language_group"))
        lang_layout = QHBoxLayout(lang_group)
        lang_layout.addWidget(QLabel(t("settings.language_label")))
        self._lang_combo = QComboBox()
        cur = current_language()
        for code, name in LANGUAGES.items():
            self._lang_combo.addItem(name, code)
            if code == cur:
                self._lang_combo.setCurrentIndex(self._lang_combo.count() - 1)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_layout.addWidget(self._lang_combo)
        lang_layout.addStretch()
        layout.addWidget(lang_group)

        # Default output folder
        output_group = QGroupBox(t("settings.output_folder"))
        output_layout = QVBoxLayout(output_group)

        folder_row = QHBoxLayout()
        self._folder_label = QLabel(
            self._settings.value("output_folder", t("settings.same_as_input"))
        )
        self._folder_label.setProperty("class", "textSecondary")
        folder_row.addWidget(self._folder_label, 1)

        browse_btn = QPushButton(t("common.browse"))
        browse_btn.setProperty("class", "secondaryButton")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(browse_btn)

        reset_btn = QPushButton(t("common.reset"))
        reset_btn.setProperty("class", "secondaryButton")
        reset_btn.clicked.connect(self._reset_folder)
        folder_row.addWidget(reset_btn)

        output_layout.addLayout(folder_row)
        layout.addWidget(output_group)

        # LibreOffice
        lo_group = QGroupBox(t("settings.lo_group"))
        lo_layout = QVBoxLayout(lo_group)

        self._lo_label = QLabel(t("settings.lo_checking"))
        self._lo_label.setWordWrap(True)
        lo_layout.addWidget(self._lo_label)

        self._lo_auto_install_btn = QPushButton(t("settings.lo_auto_install"))
        self._lo_auto_install_btn.setObjectName("primaryButton")
        self._lo_auto_install_btn.clicked.connect(self._auto_install_lo)
        self._lo_auto_install_btn.hide()
        lo_layout.addWidget(self._lo_auto_install_btn)

        self._lo_install_btn = QPushButton(t("settings.lo_instructions"))
        self._lo_install_btn.setProperty("class", "secondaryButton")
        self._lo_install_btn.clicked.connect(self._show_lo_instructions)
        self._lo_install_btn.hide()
        lo_layout.addWidget(self._lo_install_btn)

        layout.addWidget(lo_group)

        # About
        about_group = QGroupBox(t("settings.about"))
        about_layout = QVBoxLayout(about_group)
        about_text = QLabel(t("settings.about_text"))
        about_text.setWordWrap(True)
        about_text.setProperty("class", "textSecondary")
        about_layout.addWidget(about_text)
        layout.addWidget(about_group)

        layout.addStretch()

        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        # Refresh status
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
                self._theme_btn.setText(t("settings.switch_light"))
            else:
                self._theme_btn.setText(t("settings.switch_dark"))

    def _on_language_changed(self, index: int):
        code = self._lang_combo.currentData()
        if code and code != current_language():
            set_language(code)
            QMessageBox.information(
                self, t("settings.restart_title"), t("settings.restart_msg"),
            )

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, t("settings.select_folder"))
        if folder:
            self._settings.setValue("output_folder", folder)
            self._folder_label.setText(folder)

    def _reset_folder(self):
        self._settings.remove("output_folder")
        self._folder_label.setText(t("settings.same_as_input"))

    def _refresh_lo_status(self):
        lo = detect_libreoffice()
        if lo.found:
            version = lo.version.split('\n')[0] if lo.version else "unknown version"
            self._lo_label.setText(t("settings.lo_installed", version=version, path=lo.path))
            self._lo_label.setProperty("class", "statusGreen")
            self._lo_install_btn.hide()
            self._lo_auto_install_btn.hide()
        else:
            self._lo_label.setText(t("settings.lo_not_installed"))
            self._lo_label.setProperty("class", "statusRed")
            self._lo_install_btn.show()
            self._lo_auto_install_btn.show()

    def _auto_install_lo(self):
        from ui.libreoffice_install_dialog import LibreOfficeInstallDialog
        dialog = LibreOfficeInstallDialog(self)
        dialog.install_completed.connect(lambda _: self._refresh_lo_status())
        dialog.exec()

    def _show_lo_instructions(self):
        instructions = get_libreoffice_install_instructions()
        QMessageBox.information(self, t("settings.lo_install_title"), instructions)

