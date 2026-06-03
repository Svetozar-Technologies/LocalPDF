"""Helpers for elevation (drop shadow) on cards.

QSS cannot render true box-shadows, so we attach a QGraphicsDropShadowEffect
to widgets that want elevation. Use `apply_card_shadow(widget)` for default
card elevation, or `apply_shadow(widget, blur=..., y=..., alpha=...)` for
custom values.
"""

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QWidget

from ui.design_tokens import (
    CARD_SHADOW_ALPHA_DARK,
    CARD_SHADOW_ALPHA_LIGHT,
    CARD_SHADOW_BLUR,
    CARD_SHADOW_Y,
)


def apply_shadow(
    widget: QWidget,
    *,
    blur: int = CARD_SHADOW_BLUR,
    y: int = CARD_SHADOW_Y,
    alpha: int = CARD_SHADOW_ALPHA_LIGHT,
    color: str = "#000000",
) -> QGraphicsDropShadowEffect:
    """Attach a drop shadow to the widget and return the effect."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setXOffset(0)
    effect.setYOffset(y)
    qcolor = QColor(color)
    qcolor.setAlpha(alpha)
    effect.setColor(qcolor)
    widget.setGraphicsEffect(effect)
    return effect


def apply_card_shadow(widget: QWidget, *, dark_mode: bool = False) -> QGraphicsDropShadowEffect:
    """Default card elevation. Pass dark_mode=True for stronger shadow on dark backgrounds."""
    alpha = CARD_SHADOW_ALPHA_DARK if dark_mode else CARD_SHADOW_ALPHA_LIGHT
    return apply_shadow(widget, alpha=alpha)
