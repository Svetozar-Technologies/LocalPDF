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
from ui.image_to_pdf_widget import ImageToPdfWidget
from ui.convert_widget import ConvertWidget
from ui.settings_widget import SettingsWidget
from ui.theme import ThemeManager


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
        self.resize(1000, 700)

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
        self._image_to_pdf_widget = ImageToPdfWidget()
        self._convert_widget = ConvertWidget()
        self._settings_widget = SettingsWidget(theme_manager=self._theme_manager)

        self._stack.addWidget(self._compress_widget)       # 0
        self._stack.addWidget(self._batch_compress_widget)  # 1
        self._stack.addWidget(self._merge_widget)           # 2
        self._stack.addWidget(self._split_widget)           # 3
        self._stack.addWidget(self._image_to_pdf_widget)    # 4
        self._stack.addWidget(self._convert_widget)         # 5
        self._stack.addWidget(self._settings_widget)        # 6

        main_layout.addWidget(self._stack, 1)

    def _create_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # App title
        title = QLabel("LocalPDF")
        title.setObjectName("appTitle")
        layout.addWidget(title)

        subtitle = QLabel("100% Local Processing")
        subtitle.setObjectName("appSubtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Navigation buttons
        nav_items = [
            ("Compress PDF", 0),
            ("Batch Compress", 1),
            ("Merge PDFs", 2),
            ("Split PDF", 3),
            ("Image to PDF", 4),
            ("Convert PPT", 5),
            ("Settings", 6),
        ]

        for label, index in nav_items:
            btn = QPushButton(f"  {label}")
            btn.setProperty("class", "navButton")
            btn.setFixedHeight(48)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=index: self._switch_tab(i))
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        layout.addStretch()

        # Version
        version = QLabel("v1.1.0")
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
        file_menu = menu_bar.addMenu("File")
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # View menu
        view_menu = menu_bar.addMenu("View")
        toggle_theme = QAction("Toggle Dark Mode", self)
        toggle_theme.setShortcut("Ctrl+D")
        toggle_theme.triggered.connect(self._toggle_theme)
        view_menu.addAction(toggle_theme)

        # Navigate
        nav_menu = menu_bar.addMenu("Navigate")

        nav_actions = [
            ("Compress PDF", "Ctrl+1", 0),
            ("Batch Compress", "Ctrl+2", 1),
            ("Merge PDFs", "Ctrl+3", 2),
            ("Split PDF", "Ctrl+4", 3),
            ("Image to PDF", "Ctrl+5", 4),
            ("Convert PPT", "Ctrl+6", 5),
            ("Settings", "Ctrl+,", 6),
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
        self._compress_widget.cleanup()
        self._batch_compress_widget.cleanup()
        self._merge_widget.cleanup()
        self._split_widget.cleanup()
        self._image_to_pdf_widget.cleanup()
        self._convert_widget.cleanup()
        event.accept()
