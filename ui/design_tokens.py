"""Design tokens for LocalPDF — Indigo Premium palette.

Single source of truth for the palette, spacing, type, and radius scale.
QSS files author colors directly so designers can edit without round-tripping
through Python — keep the comment headers in both .qss files in sync with the
LIGHT / DARK palettes defined here.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    # Surfaces — three-level hierarchy
    bg: str               # window background
    surface: str          # cards, inputs, drop zones
    surface_elevated: str # raised surfaces (popovers, hover states)
    surface_inset: str    # subtle dividers / inset wells

    # Text
    text_primary: str
    text_secondary: str
    text_tertiary: str
    text_on_accent: str

    # Borders / dividers
    border: str
    border_strong: str
    divider: str

    # Accent (Indigo)
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft_bg: str   # tinted surface for selection / hover
    accent_soft_text: str # accent text on soft bg

    # Semantic
    success: str
    success_soft_bg: str
    success_soft_border: str

    danger: str
    danger_soft_bg: str

    warning: str

    # Sidebar
    sidebar_bg: str
    sidebar_active_bg: str
    sidebar_hover_bg: str


LIGHT = Palette(
    bg="#F7F7F9",
    surface="#FFFFFF",
    surface_elevated="#FFFFFF",
    surface_inset="#F0F0F4",
    text_primary="#0B0B12",
    text_secondary="#5A5A6E",
    text_tertiary="#9A9AAA",
    text_on_accent="#FFFFFF",
    border="#E7E7EC",
    border_strong="#D5D5DC",
    divider="#EEEEF2",
    accent="#4F46E5",
    accent_hover="#4338CA",
    accent_pressed="#3730A3",
    accent_soft_bg="#EEF0FE",
    accent_soft_text="#4338CA",
    success="#16A34A",
    success_soft_bg="#E8F8EE",
    success_soft_border="#B6E9C6",
    danger="#DC2626",
    danger_soft_bg="rgba(220, 38, 38, 0.08)",
    warning="#D97706",
    sidebar_bg="#FAFAFC",
    sidebar_active_bg="#4F46E5",
    sidebar_hover_bg="rgba(11, 11, 18, 0.05)",
)


DARK = Palette(
    bg="#0F0F14",
    surface="#18181F",
    surface_elevated="#22222C",
    surface_inset="#13131A",
    text_primary="#F5F5F7",
    text_secondary="#A1A1B0",
    text_tertiary="#6B6B7B",
    text_on_accent="#FFFFFF",
    border="#2A2A35",
    border_strong="#3A3A48",
    divider="#222230",
    accent="#818CF8",
    accent_hover="#A5B4FC",
    accent_pressed="#6366F1",
    accent_soft_bg="#1E1F3D",
    accent_soft_text="#A5B4FC",
    success="#22C55E",
    success_soft_bg="#0F2A1A",
    success_soft_border="#1F5F30",
    danger="#EF4444",
    danger_soft_bg="rgba(239, 68, 68, 0.14)",
    warning="#F59E0B",
    sidebar_bg="#13131A",
    sidebar_active_bg="#4F46E5",
    sidebar_hover_bg="rgba(255, 255, 255, 0.05)",
)


# Spacing scale (px).
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 20
SPACE_2XL = 24
SPACE_3XL = 32
SPACE_4XL = 40

# Radius scale.
RADIUS_SM = 6
RADIUS_MD = 10
RADIUS_LG = 14
RADIUS_XL = 18
RADIUS_PILL = 22

# Type scale.
TYPE_CAPTION = 11
TYPE_SMALL = 12
TYPE_BODY = 13
TYPE_EMPH = 15
TYPE_H4 = 17
TYPE_H3 = 20
TYPE_H2 = 24
TYPE_H1 = 30

# Sidebar geometry.
SIDEBAR_WIDTH = 260
NAV_BUTTON_HEIGHT = 40
NAV_ICON_SIZE = 18

# Card / shadow defaults.
CARD_SHADOW_BLUR = 24
CARD_SHADOW_Y = 4
CARD_SHADOW_ALPHA_LIGHT = 30  # /255
CARD_SHADOW_ALPHA_DARK = 90
