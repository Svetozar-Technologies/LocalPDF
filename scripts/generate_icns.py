#!/usr/bin/env python3
"""Generate macOS .icns from SVG using PyQt6 renderer."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

# Required sizes for macOS .icns (name -> pixels)
ICON_SIZES = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}


def render_svg_to_png(svg_path: str, png_path: str, size: int):
    """Render SVG to a PNG at the given size."""
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

    image.save(png_path)
    print(f"  Created {os.path.basename(png_path)} ({size}x{size})")


def main():
    root = Path(__file__).resolve().parent.parent
    svg_path = str(root / "assets" / "icon.svg")
    icns_path = str(root / "assets" / "icon.icns")

    if not os.path.exists(svg_path):
        print(f"ERROR: SVG not found at {svg_path}")
        sys.exit(1)

    # Need QApplication for rendering
    app = QApplication(sys.argv)

    # Create temporary .iconset directory
    with tempfile.TemporaryDirectory() as tmpdir:
        iconset_dir = os.path.join(tmpdir, "LocalPDF.iconset")
        os.makedirs(iconset_dir)

        print("Rendering SVG to PNGs...")
        for filename, size in ICON_SIZES.items():
            png_path = os.path.join(iconset_dir, filename)
            render_svg_to_png(svg_path, png_path, size)

        # Use iconutil to create .icns
        print(f"\nCreating .icns at {icns_path}...")
        result = subprocess.run(
            ["iconutil", "-c", "icns", iconset_dir, "-o", icns_path],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"ERROR: iconutil failed: {result.stderr}")
            sys.exit(1)

    size_kb = os.path.getsize(icns_path) / 1024
    print(f"Done! icon.icns created ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
