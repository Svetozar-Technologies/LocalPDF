"""Main application window with sidebar navigation."""

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
from ui.convert_widget import ConvertWidget
from ui.page_manager_widget import PageManagerWidget
from ui.settings_widget import SettingsWidget
from ui.theme import ThemeManager
from i18n import t


class MainWindow(QMainWindow):
    """Main window with sidebar navigation and stacked content area."""

    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self._theme_manager = theme_manager
        self._nav_buttons = []
        self._setup_ui()
        self._setup_menu_bar()
        self._switch_tab(0)

    def _setup_ui(self):
        self.setWindowTitle("LocalPDF")
        self.setMinimumSize(900, 650)
        self.resize(1050, 750)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)

        # Content area
        self._stack = QStackedWidget()
        self._stack.setObjectName("contentArea")

        self._compress_widget = CompressWidget()
        self._batch_compress_widget = BatchCompressWidget()
        self._merge_widget = MergeWidget()
        self._split_widget = SplitWidget()
        self._protect_widget = ProtectWidget()
        self._watermark_widget = WatermarkWidget()
        self._image_to_pdf_widget = ImageToPdfWidget()
        self._pdf_to_image_widget = PDFToImageWidget()
        self._convert_widget = ConvertWidget()
        self._page_manager_widget = PageManagerWidget()
        self._settings_widget = SettingsWidget(theme_manager=self._theme_manager)

        self._stack.addWidget(self._compress_widget)        # 0
        self._stack.addWidget(self._batch_compress_widget)   # 1
        self._stack.addWidget(self._merge_widget)            # 2
        self._stack.addWidget(self._split_widget)            # 3
        self._stack.addWidget(self._protect_widget)          # 4
        self._stack.addWidget(self._watermark_widget)        # 5
        self._stack.addWidget(self._image_to_pdf_widget)     # 6
        self._stack.addWidget(self._pdf_to_image_widget)     # 7
        self._stack.addWidget(self._convert_widget)          # 8
        self._stack.addWidget(self._page_manager_widget)     # 9
        self._stack.addWidget(self._settings_widget)         # 10

        main_layout.addWidget(self._stack, 1)

    def _create_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # App title
        title = QLabel(t("app.title"))
        title.setObjectName("appTitle")
        layout.addWidget(title)

        subtitle = QLabel(t("app.subtitle"))
        subtitle.setObjectName("appSubtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(4)

        # --- PDF Tools section ---
        section1 = QLabel("  " + t("sidebar.pdf_tools"))
        section1.setObjectName("sidebarSection")
        layout.addWidget(section1)

        pdf_tools = [
            (t("sidebar.compress"), 0),
            (t("sidebar.batch_compress"), 1),
            (t("sidebar.merge"), 2),
            (t("sidebar.split"), 3),
            (t("sidebar.protect"), 4),
            (t("sidebar.watermark"), 5),
        ]

        for label, index in pdf_tools:
            btn = QPushButton(label)
            btn.setProperty("class", "navButton")
            btn.setFixedHeight(38)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=index: self._switch_tab(i))
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        # --- Convert section ---
        section2 = QLabel("  " + t("sidebar.convert"))
        section2.setObjectName("sidebarSection")
        layout.addWidget(section2)

        convert_tools = [
            (t("sidebar.image_to_pdf"), 6),
            (t("sidebar.pdf_to_image"), 7),
            (t("sidebar.convert_ppt"), 8),
        ]

        for label, index in convert_tools:
            btn = QPushButton(label)
            btn.setProperty("class", "navButton")
            btn.setFixedHeight(38)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=index: self._switch_tab(i))
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        # --- Page Tools section ---
        section3 = QLabel("  " + t("sidebar.page_tools"))
        section3.setObjectName("sidebarSection")
        layout.addWidget(section3)

        page_tools = [
            (t("sidebar.page_editor"), 9),
        ]

        for label, index in page_tools:
            btn = QPushButton(label)
            btn.setProperty("class", "navButton")
            btn.setFixedHeight(38)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=index: self._switch_tab(i))
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        # --- Settings (at bottom) ---
        layout.addStretch()

        settings_btn = QPushButton(t("sidebar.settings"))
        settings_btn.setProperty("class", "navButton")
        settings_btn.setFixedHeight(38)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(lambda checked: self._switch_tab(10))
        layout.addWidget(settings_btn)
        self._nav_buttons.append(settings_btn)

        # Version
        version = QLabel(t("app.version"))
        version.setObjectName("versionLabel")
        layout.addWidget(version)

        return sidebar

    def _switch_tab(self, index: int):
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu(t("menu.file"))
        quit_action = QAction(t("menu.quit"), self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # View menu
        view_menu = menu_bar.addMenu(t("menu.view"))
        toggle_theme = QAction(t("menu.toggle_dark_mode"), self)
        toggle_theme.setShortcut("Ctrl+D")
        toggle_theme.triggered.connect(self._toggle_theme)
        view_menu.addAction(toggle_theme)

        # Navigate
        nav_menu = menu_bar.addMenu(t("menu.navigate"))

        nav_actions = [
            (t("compress.title"), "Ctrl+1", 0),
            (t("batch_compress.title"), "Ctrl+2", 1),
            (t("merge.title"), "Ctrl+3", 2),
            (t("split.title"), "Ctrl+4", 3),
            (t("protect.title"), "Ctrl+5", 4),
            (t("watermark.title"), "Ctrl+6", 5),
            (t("image_to_pdf.title"), "Ctrl+7", 6),
            (t("pdf_to_image.title"), "Ctrl+8", 7),
            (t("convert.title"), "Ctrl+9", 8),
            (t("page_manager.title"), "Ctrl+0", 9),
            (t("settings.title"), "Ctrl+,", 10),
        ]

        for label, shortcut, index in nav_actions:
            action = QAction(label, self)
            action.setShortcut(shortcut)
            action.triggered.connect(lambda checked, i=index: self._switch_tab(i))
            nav_menu.addAction(action)

    def _toggle_theme(self):
        self._theme_manager.toggle_theme()

    def closeEvent(self, event):
        """Clean up workers on close."""
        widgets = [
            self._compress_widget, self._batch_compress_widget,
            self._merge_widget, self._split_widget,
            self._protect_widget, self._watermark_widget,
            self._image_to_pdf_widget, self._pdf_to_image_widget,
            self._convert_widget, self._page_manager_widget,
        ]
        for w in widgets:
            w.cleanup()
        # Process any pending signals (finished, deleteLater, etc.)
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        event.accept()
