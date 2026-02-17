#!/usr/bin/env python3
"""Generate Windows .ico from SVG using PyQt6 renderer + Pillow."""

import os
import sys
from pathlib import Path

from PIL import Image
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

ICO_SIZES = [16, 32, 48, 64, 128, 256]


def render_svg_to_pil(svg_path: str, size: int) -> Image.Image:
    """Render SVG to a PIL Image at the given size."""
    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        print(f"ERROR: Failed to load SVG: {svg_path}")
        sys.exit(1)

    image = QImage(QSize(size, size), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    # QImage ARGB32 → PIL RGBA
    ptr = image.bits()
    ptr.setsize(size * size * 4)
    pil_img = Image.frombytes("RGBA", (size, size), bytes(ptr), "raw", "BGRA")
    return pil_img


def main():
    root = Path(__file__).resolve().parent.parent
    svg_path = str(root / "assets" / "icon.svg")
    ico_path = str(root / "assets" / "icon.ico")

    if not os.path.exists(svg_path):
        print(f"ERROR: SVG not found at {svg_path}")
        sys.exit(1)

    app = QApplication(sys.argv)

    print("Rendering SVG to ICO sizes...")
    images = []
    for size in ICO_SIZES:
        img = render_svg_to_pil(svg_path, size)
        images.append(img)
        print(f"  {size}x{size}")

    # Save as multi-resolution .ico (first image is the base, rest are appended)
    images[0].save(ico_path, format="ICO", sizes=[(s, s) for s in ICO_SIZES], append_images=images[1:])

    size_kb = os.path.getsize(ico_path) / 1024
    print(f"Done! icon.ico created ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
