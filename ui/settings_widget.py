"""Settings tab widget."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QFileDialog, QScrollArea, QComboBox,
)
from PyQt6.QtCore import QSettings

from ui.components.screen_header import ScreenHeader
from i18n import t, LANGUAGES, current_language, set_language


class SettingsWidget(QWidget):
    """Settings: theme, language, output folder, about."""

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

        layout.addWidget(ScreenHeader(t("settings.title")))

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
            # set_language() reloads translations and emits language_changed
            # on the i18n bus; MainWindow listens and rebuilds the shell in
            # place, so the user sees the new language immediately.
            set_language(code)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, t("settings.select_folder"))
        if folder:
            self._settings.setValue("output_folder", folder)
            self._folder_label.setText(folder)

    def _reset_folder(self):
        self._settings.remove("output_folder")
        self._folder_label.setText(t("settings.same_as_input"))
