"""Internationalization (i18n) module for LocalPDF."""

import json
import os
from collections import OrderedDict

from PyQt6.QtCore import QSettings

from core.utils import get_asset_path


# Supported languages: code -> native display name
LANGUAGES = OrderedDict([
    ("en", "English"),
    ("hi", "हिन्दी"),
    ("ru", "Русский"),
    ("zh", "中文"),
    ("ja", "日本語"),
    ("es", "Español"),
    ("fr", "Français"),
    ("ar", "العربية"),
])

_translations: dict = {}
_fallback: dict = {}
_current_lang: str = "en"


def _load_json(code: str) -> dict:
    """Load a translation JSON file by language code."""
    path = get_asset_path(os.path.join("i18n", f"{code}.json"))
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def init():
    """Initialize the translation system. Call once at app startup."""
    global _translations, _fallback, _current_lang

    settings = QSettings("Svetozar Technologies", "LocalPDF")
    _current_lang = settings.value("language", "en")
    if _current_lang not in LANGUAGES:
        _current_lang = "en"

    _fallback = _load_json("en")

    if _current_lang != "en":
        _translations = _load_json(_current_lang)
    else:
        _translations = _fallback


def t(key: str, **kwargs) -> str:
    """Translate a key, with optional named format arguments.

    Falls back to English if key is missing in current language.
    Falls back to the raw key if missing everywhere.
    """
    text = _translations.get(key) or _fallback.get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def current_language() -> str:
    """Return the current language code."""
    return _current_lang


def is_rtl() -> bool:
    """Return True if the current language is right-to-left."""
    meta = _translations.get("_meta", {})
    if isinstance(meta, dict):
        return meta.get("direction", "ltr") == "rtl"
    return False


def set_language(code: str):
    """Save language preference. Takes effect on next app restart."""
    settings = QSettings("Svetozar Technologies", "LocalPDF")
    settings.setValue("language", code)
