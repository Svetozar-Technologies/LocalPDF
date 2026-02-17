"""Dialog for managing (viewing / deleting) annotations on a PDF page."""

import os
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QWidget, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap

from core.page_manager import PageSource, PageManager, TextAnnotation, ImageAnnotation
from i18n import t


# Marker colours: blue for text, orange for image/signature
_TEXT_MARKER_COLOR = (66, 133, 244)
_IMAGE_MARKER_COLOR = (255, 152, 0)
_MARKER_RADIUS = 12


class ManageAnnotationsDialog(QDialog):
    """Modal dialog listing all annotations on a page with delete + live preview."""

    def __init__(self, source: PageSource, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("annotations.title"))
        self.setMinimumSize(750, 650)
        self.resize(750, 650)
        self.setModal(True)

        self._source = source
        self._manager = PageManager()
        self._modified = False

        self._setup_ui()
        self._rebuild()

    # ------------------------------------------------------------------ public

    def was_modified(self) -> bool:
        return self._modified

    # ------------------------------------------------------------------ UI

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Page preview
        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(350)
        layout.addWidget(self._preview, 1)

        # Annotation list (scroll area)
        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setMinimumHeight(180)
        self._list_scroll.setMaximumHeight(250)
        self._list_scroll.setFrameShape(QScrollArea.Shape.StyledPanel)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout.setSpacing(6)
        self._list_scroll.setWidget(self._list_container)
        layout.addWidget(self._list_scroll)

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton(t("common.close"))
        close_btn.setProperty("class", "secondaryButton")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------ rebuild

    def _rebuild(self):
        """Re-render preview with markers and rebuild the annotation list."""
        entries = self._build_entries()
        self._render_preview(entries)
        self._render_list(entries)

    def _build_entries(self) -> List[Tuple[int, str, str, str, object]]:
        """Build a flat ordered list: (number, kind, type_label, description, annotation).

        Text annotations first, then image annotations.
        """
        entries: List[Tuple[int, str, str, str, object]] = []
        num = 1
        for ann in self._source.text_annotations:
            desc = ann.text if len(ann.text) <= 30 else ann.text[:27] + "..."
            entries.append((num, "text", t("annotations.type_text"), desc, ann))
            num += 1
        for ann in self._source.image_annotations:
            desc = os.path.basename(ann.image_path) if ann.image_path else "image"
            if len(desc) > 30:
                desc = desc[:27] + "..."
            entries.append((num, "image", t("annotations.type_image"), desc, ann))
            num += 1
        return entries

    # ------------------------------------------------------------------ preview

    def _render_preview(self, entries: List[Tuple]):
        img = self._manager.render_full_page(self._source, max_width=600)
        draw = ImageDraw.Draw(img)

        font = self._marker_font()

        for num, kind, _tl, _desc, ann in entries:
            px = int(ann.x * img.width)
            py = int(ann.y * img.height)
            color = _TEXT_MARKER_COLOR if kind == "text" else _IMAGE_MARKER_COLOR
            r = _MARKER_RADIUS

            # Clamp to keep the circle inside the image
            px = max(r, min(px, img.width - r - 1))
            py = max(r, min(py, img.height - r - 1))

            draw.ellipse(
                [(px - r, py - r), (px + r, py + r)],
                fill=color, outline=(255, 255, 255),
            )
            text = str(num)
            bbox = font.getbbox(text)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text(
                (px - tw // 2, py - th // 2 - 1),
                text, fill=(255, 255, 255), font=font,
            )

        self._set_pixmap(img)

    def _set_pixmap(self, img: Image.Image):
        img_rgb = img.convert("RGB")
        data = img_rgb.tobytes()
        qimg = QImage(data, img_rgb.width, img_rgb.height, 3 * img_rgb.width, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(
            self._preview.width() or 600, self._preview.height() or 400,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(scaled)

    @staticmethod
    def _marker_font():
        for path in (
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ):
            try:
                return ImageFont.truetype(path, 13)
            except (OSError, IOError):
                continue
        try:
            return ImageFont.load_default(size=13)
        except TypeError:
            return ImageFont.load_default()

    # ------------------------------------------------------------------ list

    def _render_list(self, entries: List[Tuple]):
        # Clear existing rows
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not entries:
            empty = QLabel(t("annotations.no_annotations"))
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #999; font-size: 13px; padding: 20px;")
            self._list_layout.addWidget(empty)
            return

        for num, kind, type_label, desc, ann in entries:
            row = QFrame()
            row.setFrameShape(QFrame.Shape.StyledPanel)
            row.setStyleSheet(
                "QFrame { background: #fafafa; border: 1px solid #e0e0e0; border-radius: 4px; }"
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 6, 10, 6)
            row_layout.setSpacing(10)

            # Number badge
            color_hex = "#{:02x}{:02x}{:02x}".format(
                *(_TEXT_MARKER_COLOR if kind == "text" else _IMAGE_MARKER_COLOR)
            )
            badge = QLabel(str(num))
            badge.setFixedSize(24, 24)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"background: {color_hex}; color: white; border-radius: 12px; "
                f"font-weight: bold; font-size: 11px;"
            )
            row_layout.addWidget(badge)

            # Type label
            type_lbl = QLabel(type_label)
            type_lbl.setFixedWidth(60)
            type_lbl.setStyleSheet("font-weight: bold; font-size: 12px; color: #333;")
            row_layout.addWidget(type_lbl)

            # Description
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("font-size: 12px; color: #555;")
            desc_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            row_layout.addWidget(desc_lbl, 1)

            # Delete button
            del_btn = QPushButton(t("common.delete"))
            del_btn.setFixedWidth(70)
            del_btn.setStyleSheet(
                "QPushButton { background: #f44336; color: white; border: none; "
                "border-radius: 4px; padding: 4px 8px; font-size: 11px; }"
                "QPushButton:hover { background: #d32f2f; }"
            )
            del_btn.clicked.connect(lambda checked=False, a=ann, k=kind: self._on_delete(a, k))
            row_layout.addWidget(del_btn)

            self._list_layout.addWidget(row)

        self._list_layout.addStretch()

    # ------------------------------------------------------------------ delete

    def _on_delete(self, annotation, kind: str):
        if kind == "text" and annotation in self._source.text_annotations:
            self._source.text_annotations.remove(annotation)
            self._modified = True
        elif kind == "image" and annotation in self._source.image_annotations:
            self._source.image_annotations.remove(annotation)
            self._modified = True

        self._rebuild()
