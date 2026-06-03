"""SVG icon rendering with runtime color tinting.

Reads an SVG from assets/icons/, renders it at the requested size, then
recolors it via Source-In composition so the same SVG file can be used in
light, dark, and active states.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from core.utils import get_asset_path


_pixmap_cache: dict[Tuple[str, str, int], QPixmap] = {}


def _resolve_path(name: str) -> Path:
    """Accept either a short name ('compress') or a full filename ('compress.svg')."""
    filename = name if name.endswith(".svg") else f"{name}.svg"
    return Path(get_asset_path(f"assets/icons/{filename}"))


def icon_pixmap(name: str, color: str, size: int = 18) -> QPixmap:
    """Return a tinted QPixmap of the given icon."""
    key = (name, color, size)
    cached = _pixmap_cache.get(key)
    if cached is not None:
        return cached

    path = _resolve_path(name)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    if not path.exists():
        _pixmap_cache[key] = pixmap
        return pixmap

    renderer = QSvgRenderer(str(path))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color))
    painter.end()

    _pixmap_cache[key] = pixmap
    return pixmap


def themed_icon(name: str, color: str, color_active: str | None = None, size: int = 18) -> QIcon:
    """Build a QIcon with optional active/selected state color."""
    icon = QIcon()
    icon.addPixmap(icon_pixmap(name, color, size), QIcon.Mode.Normal, QIcon.State.Off)
    if color_active:
        icon.addPixmap(icon_pixmap(name, color_active, size), QIcon.Mode.Selected, QIcon.State.Off)
        icon.addPixmap(icon_pixmap(name, color_active, size), QIcon.Mode.Active, QIcon.State.Off)
    return icon


def invalidate_cache() -> None:
    """Clear the pixmap cache (call on theme change)."""
    _pixmap_cache.clear()
