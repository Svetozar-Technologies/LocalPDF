"""Home / tool grid landing screen.

Displays all tools grouped by category as clickable cards. Emits
`tool_selected(index)` when the user picks a tool; MainWindow connects this
to its tab switch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.components.elevated_card import apply_card_shadow
from ui.components.icon import icon_pixmap
from ui.design_tokens import LIGHT
from i18n import t


# Stack indexes here MUST stay in sync with MainWindow's stack order.
COMPRESS = 1
BATCH_COMPRESS = 2
MERGE = 3
SPLIT = 4
PROTECT = 5
WATERMARK = 6
IMAGE_TO_PDF = 7
PDF_TO_IMAGE = 8
PAGE_EDITOR = 9


@dataclass(frozen=True)
class ToolDef:
    icon: str
    title_key: str
    desc_key: str
    target_index: int


_PDF_TOOLS: List[ToolDef] = [
    ToolDef("compress",  "home.compress.title",  "home.compress.desc",  COMPRESS),
    ToolDef("batch",     "home.batch_compress.title", "home.batch_compress.desc", BATCH_COMPRESS),
    ToolDef("merge",     "home.merge.title",     "home.merge.desc",     MERGE),
    ToolDef("split",     "home.split.title",     "home.split.desc",     SPLIT),
    ToolDef("lock",      "home.protect.title",   "home.protect.desc",   PROTECT),
    ToolDef("watermark", "home.watermark.title", "home.watermark.desc", WATERMARK),
]

_CONVERT_TOOLS: List[ToolDef] = [
    ToolDef("image-to-pdf", "home.image_to_pdf.title", "home.image_to_pdf.desc", IMAGE_TO_PDF),
    ToolDef("pdf-to-image", "home.pdf_to_image.title", "home.pdf_to_image.desc", PDF_TO_IMAGE),
]

_PAGE_TOOLS: List[ToolDef] = [
    ToolDef("page-edit", "home.page_editor.title", "home.page_editor.desc", PAGE_EDITOR),
]


class _ToolCard(QFrame):
    """Clickable tool card with icon, title, and description."""

    clicked = pyqtSignal(int)

    def __init__(self, tool: ToolDef, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target = tool.target_index
        self.setProperty("class", "toolCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(116)
        # Subtle elevation so cards lift off the background.
        apply_card_shadow(self)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(14)

        # Icon tile: accent_soft_bg square with the tinted icon centered.
        icon_tile = QFrame()
        icon_tile.setFixedSize(48, 48)
        icon_tile.setStyleSheet(
            f"background-color: {LIGHT.accent_soft_bg};"
            f"border-radius: 12px;"
        )
        tile_layout = QVBoxLayout(icon_tile)
        tile_layout.setContentsMargins(0, 0, 0, 0)
        tile_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setPixmap(icon_pixmap(tool.icon, LIGHT.accent, 24))
        tile_layout.addWidget(icon_label)
        outer.addWidget(icon_tile, 0, Qt.AlignmentFlag.AlignTop)

        # Text column
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 2, 0, 0)
        text_col.setSpacing(4)

        title = QLabel(t(tool.title_key))
        title.setProperty("class", "toolCardTitle")
        text_col.addWidget(title)

        desc = QLabel(t(tool.desc_key))
        desc.setProperty("class", "toolCardDescription")
        desc.setWordWrap(True)
        text_col.addWidget(desc)
        text_col.addStretch()

        outer.addLayout(text_col, 1)

        self._icon_tile = icon_tile
        self._icon_label = icon_label
        self._tool = tool

    def update_theme(self, accent: str, accent_soft_bg: str, dark_mode: bool = False) -> None:
        """Re-tint icon, tile background, and shadow for current theme."""
        self._icon_tile.setStyleSheet(
            f"background-color: {accent_soft_bg};"
            f"border-radius: 12px;"
        )
        self._icon_label.setPixmap(icon_pixmap(self._tool.icon, accent, 24))
        # Heavier shadow on dark backgrounds since light-on-black shadows
        # would otherwise be invisible.
        apply_card_shadow(self, dark_mode=dark_mode)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._target)
        super().mousePressEvent(event)


class HomeWidget(QWidget):
    """Landing screen with a grid of all tools."""

    tool_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("homeWidget")
        self._cards: List[_ToolCard] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("homeContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(36, 32, 36, 32)
        content_layout.setSpacing(8)

        hello = QLabel(t("home.title"))
        hello.setProperty("class", "homeHello")
        content_layout.addWidget(hello)

        subtitle = QLabel(t("home.subtitle"))
        subtitle.setProperty("class", "homeSubtitle")
        subtitle.setWordWrap(True)
        content_layout.addWidget(subtitle)

        content_layout.addSpacing(20)
        self._add_section(content_layout, t("home.section.pdf_tools"), _PDF_TOOLS)
        content_layout.addSpacing(8)
        self._add_section(content_layout, t("home.section.convert"), _CONVERT_TOOLS)
        content_layout.addSpacing(8)
        self._add_section(content_layout, t("home.section.page_tools"), _PAGE_TOOLS)
        content_layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _add_section(self, parent_layout: QVBoxLayout, title: str, tools: List[ToolDef]) -> None:
        header = QLabel(title)
        header.setProperty("class", "toolCardCategory")
        parent_layout.addWidget(header)
        parent_layout.addSpacing(8)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        # 3-column responsive-ish grid (Qt grid doesn't auto-reflow; 3 is a
        # safe default for the 1120px default window after the 260px sidebar).
        cols = 3
        for idx, tool in enumerate(tools):
            row, col = divmod(idx, cols)
            card = _ToolCard(tool)
            card.clicked.connect(self.tool_selected.emit)
            grid.addWidget(card, row, col)
            self._cards.append(card)

        # Force equal column stretching.
        for c in range(cols):
            grid.setColumnStretch(c, 1)

        parent_layout.addLayout(grid)

    def update_theme(self, palette, dark_mode: bool = False) -> None:
        """Re-tint all card icons + tiles when theme changes."""
        for card in self._cards:
            card.update_theme(palette.accent, palette.accent_soft_bg, dark_mode=dark_mode)
