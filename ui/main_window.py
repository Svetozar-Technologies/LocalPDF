"""Main application window with sidebar navigation and Home tool grid."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QStackedWidget, QLabel, QFrame,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction

from ui.compress_widget import CompressWidget
from ui.batch_compress_widget import BatchCompressWidget
from ui.merge_widget import MergeWidget
from ui.split_widget import SplitWidget
from ui.protect_widget import ProtectWidget
from ui.watermark_widget import WatermarkWidget
from ui.image_to_pdf_widget import ImageToPdfWidget
from ui.pdf_to_image_widget import PDFToImageWidget
from ui.page_manager_widget import PageManagerWidget
from ui.settings_widget import SettingsWidget
from ui.home_widget import HomeWidget
from ui.theme import ThemeManager
from ui.components.icon import themed_icon, invalidate_cache as invalidate_icon_cache
from ui.design_tokens import (
    DARK, LIGHT, NAV_BUTTON_HEIGHT, NAV_ICON_SIZE, SIDEBAR_WIDTH,
)
import i18n
from i18n import t


# Stack indexes. Home is the landing screen at index 0; tool screens follow.
HOME = 0
COMPRESS = 1
BATCH_COMPRESS = 2
MERGE = 3
SPLIT = 4
PROTECT = 5
WATERMARK = 6
IMAGE_TO_PDF = 7
PDF_TO_IMAGE = 8
PAGE_EDITOR = 9
SETTINGS = 10


def _strip_emoji_prefix(label: str) -> str:
    """Sidebar translations bake an emoji + double-space prefix into the
    label. We render real icons separately, so strip it for display."""
    if "  " in label:
        return label.split("  ", 1)[1].strip()
    return label.strip()


class MainWindow(QMainWindow):
    """Main window with sidebar navigation, Home grid, and tool screens."""

    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self._theme_manager = theme_manager
        self._nav_buttons: list[QPushButton] = []
        # (button, icon_name) for theme-aware re-tinting.
        self._nav_icon_specs: list[tuple[QPushButton, str]] = []
        self._setup_ui()
        self._setup_menu_bar()
        self._switch_tab(HOME)

        # Live language changes rebuild the whole shell in place.
        i18n.bus().language_changed.connect(self._on_language_changed)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _setup_ui(self):
        self.setWindowTitle("LocalPDF")
        self.setMinimumSize(960, 680)
        self.resize(1180, 800)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)

        self._stack = QStackedWidget()
        self._stack.setObjectName("contentArea")

        self._home_widget = HomeWidget()
        self._home_widget.tool_selected.connect(self._switch_tab)

        self._compress_widget = CompressWidget()
        self._batch_compress_widget = BatchCompressWidget()
        self._merge_widget = MergeWidget()
        self._split_widget = SplitWidget()
        self._protect_widget = ProtectWidget()
        self._watermark_widget = WatermarkWidget()
        self._image_to_pdf_widget = ImageToPdfWidget()
        self._pdf_to_image_widget = PDFToImageWidget()
        self._page_manager_widget = PageManagerWidget()
        self._settings_widget = SettingsWidget(theme_manager=self._theme_manager)

        # Order MUST match the index constants above.
        self._stack.addWidget(self._home_widget)             # 0  HOME
        self._stack.addWidget(self._compress_widget)         # 1
        self._stack.addWidget(self._batch_compress_widget)   # 2
        self._stack.addWidget(self._merge_widget)            # 3
        self._stack.addWidget(self._split_widget)            # 4
        self._stack.addWidget(self._protect_widget)          # 5
        self._stack.addWidget(self._watermark_widget)        # 6
        self._stack.addWidget(self._image_to_pdf_widget)     # 7
        self._stack.addWidget(self._pdf_to_image_widget)     # 8
        self._stack.addWidget(self._page_manager_widget)     # 9
        self._stack.addWidget(self._settings_widget)         # 10

        main_layout.addWidget(self._stack, 1)

        # Initial paint: icons + home card tints respect the saved theme.
        self._refresh_nav_icons()
        self._home_widget.update_theme(self._palette(), dark_mode=self._is_dark())

    def _create_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel(t("app.title"))
        title.setObjectName("appTitle")
        layout.addWidget(title)

        subtitle = QLabel(t("app.subtitle"))
        subtitle.setObjectName("appSubtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(4)

        # --- Home ---
        self._add_nav_button(layout, "home", t("sidebar.home"), HOME)

        # --- PDF Tools ---
        layout.addWidget(self._make_section_label(t("sidebar.pdf_tools")))
        self._add_nav_button(layout, "compress",  _strip_emoji_prefix(t("sidebar.compress")),       COMPRESS)
        self._add_nav_button(layout, "batch",     _strip_emoji_prefix(t("sidebar.batch_compress")), BATCH_COMPRESS)
        self._add_nav_button(layout, "merge",     _strip_emoji_prefix(t("sidebar.merge")),          MERGE)
        self._add_nav_button(layout, "split",     _strip_emoji_prefix(t("sidebar.split")),          SPLIT)
        self._add_nav_button(layout, "lock",      _strip_emoji_prefix(t("sidebar.protect")),        PROTECT)
        self._add_nav_button(layout, "watermark", _strip_emoji_prefix(t("sidebar.watermark")),      WATERMARK)

        # --- Convert ---
        layout.addWidget(self._make_section_label(t("sidebar.convert")))
        self._add_nav_button(layout, "image-to-pdf", _strip_emoji_prefix(t("sidebar.image_to_pdf")), IMAGE_TO_PDF)
        self._add_nav_button(layout, "pdf-to-image", _strip_emoji_prefix(t("sidebar.pdf_to_image")), PDF_TO_IMAGE)

        # --- Page Tools ---
        layout.addWidget(self._make_section_label(t("sidebar.page_tools")))
        self._add_nav_button(layout, "page-edit", _strip_emoji_prefix(t("sidebar.page_editor")), PAGE_EDITOR)

        layout.addStretch()

        # --- Settings ---
        self._add_nav_button(layout, "settings", _strip_emoji_prefix(t("sidebar.settings")), SETTINGS)

        return sidebar

    def _make_section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sidebarSection")
        return label

    def _add_nav_button(self, layout: QVBoxLayout, icon_name: str, label: str, index: int) -> None:
        btn = QPushButton(" " + label)  # leading space so text isn't flush against icon
        btn.setProperty("class", "navButton")
        btn.setFixedHeight(NAV_BUTTON_HEIGHT)
        btn.setIconSize(QSize(NAV_ICON_SIZE, NAV_ICON_SIZE))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda checked=False, i=index: self._switch_tab(i))
        layout.addWidget(btn)
        self._nav_buttons.append(btn)
        self._nav_icon_specs.append((btn, icon_name))

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _switch_tab(self, index: int):
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        # Active state changes icon color; refresh.
        self._refresh_nav_icons()

    def _palette(self):
        return DARK if self._is_dark() else LIGHT

    def _is_dark(self) -> bool:
        return self._theme_manager.current_theme() == ThemeManager.DARK

    def _refresh_nav_icons(self):
        palette = self._palette()
        idle_color = palette.text_secondary
        active_color = palette.text_on_accent
        for btn, icon_name in self._nav_icon_specs:
            is_active = btn.property("active") == "true"
            color = active_color if is_active else idle_color
            btn.setIcon(themed_icon(icon_name, color, color, NAV_ICON_SIZE))

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------
    def _setup_menu_bar(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu(t("menu.file"))
        quit_action = QAction(t("menu.quit"), self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = menu_bar.addMenu(t("menu.view"))
        toggle_theme = QAction(t("menu.toggle_dark_mode"), self)
        toggle_theme.setShortcut("Ctrl+D")
        toggle_theme.triggered.connect(self._toggle_theme)
        view_menu.addAction(toggle_theme)

        nav_menu = menu_bar.addMenu(t("menu.navigate"))

        nav_actions = [
            (t("sidebar.home"),         "Ctrl+H", HOME),
            (t("compress.title"),       "Ctrl+1", COMPRESS),
            (t("batch_compress.title"), "Ctrl+2", BATCH_COMPRESS),
            (t("merge.title"),          "Ctrl+3", MERGE),
            (t("split.title"),          "Ctrl+4", SPLIT),
            (t("protect.title"),        "Ctrl+5", PROTECT),
            (t("watermark.title"),      "Ctrl+6", WATERMARK),
            (t("image_to_pdf.title"),   "Ctrl+7", IMAGE_TO_PDF),
            (t("pdf_to_image.title"),   "Ctrl+8", PDF_TO_IMAGE),
            (t("page_manager.title"),   "Ctrl+9", PAGE_EDITOR),
            (t("settings.title"),       "Ctrl+,", SETTINGS),
        ]

        for label, shortcut, index in nav_actions:
            action = QAction(label, self)
            action.setShortcut(shortcut)
            action.triggered.connect(lambda checked=False, i=index: self._switch_tab(i))
            nav_menu.addAction(action)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------
    def _toggle_theme(self):
        self._theme_manager.toggle_theme()
        invalidate_icon_cache()
        self._refresh_nav_icons()
        self._home_widget.update_theme(self._palette(), dark_mode=self._is_dark())

    # ------------------------------------------------------------------
    # Language hot-swap
    # ------------------------------------------------------------------
    def _on_language_changed(self, code: str):
        """Rebuild the shell in place so all widgets pick up the new language."""
        from PyQt6.QtWidgets import QApplication

        active = self._stack.currentIndex()

        # Stop background work on tool widgets before tearing them down.
        for w in self._tool_widgets():
            try:
                w.cleanup()
            except Exception:
                pass

        # Update app-wide layout direction (Arabic etc.).
        app = QApplication.instance()
        if app is not None:
            app.setLayoutDirection(
                Qt.LayoutDirection.RightToLeft if i18n.is_rtl() else Qt.LayoutDirection.LeftToRight
            )

        # Rebuild menu bar from scratch — clear() removes its actions cleanly.
        self.menuBar().clear()

        # Reset nav state, then rebuild the central widget.
        self._nav_buttons.clear()
        self._nav_icon_specs.clear()
        self._setup_ui()
        self._setup_menu_bar()

        # Restore active tab (clamp in case stack count ever changes).
        active = min(active, self._stack.count() - 1)
        self._switch_tab(active)

    def _tool_widgets(self):
        return [
            self._compress_widget, self._batch_compress_widget,
            self._merge_widget, self._split_widget,
            self._protect_widget, self._watermark_widget,
            self._image_to_pdf_widget, self._pdf_to_image_widget,
            self._page_manager_widget,
        ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        for w in self._tool_widgets():
            w.cleanup()
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        event.accept()
