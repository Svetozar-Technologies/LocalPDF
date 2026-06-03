"""Internationalization (i18n) module for LocalPDF.

Translations live as JSON files in this directory keyed by language code.
`t()` looks up a string in the current language with English fallback.

Language can be changed at runtime via `set_language(code)` — this reloads
the in-memory translations and emits `language_changed` so the UI can
rebuild itself without an app restart.
"""

import json
import os
from collections import OrderedDict
from typing import Optional

from PyQt6.QtCore import QObject, QSettings, pyqtSignal

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


class _Bus(QObject):
    """Module-level signal bus for i18n events."""
    language_changed = pyqtSignal(str)  # emits new language code


_bus: Optional[_Bus] = None


def bus() -> _Bus:
    """Return the singleton signal bus. Created lazily so a QApplication
    doesn't need to exist at import time."""
    global _bus
    if _bus is None:
        _bus = _Bus()
    return _bus


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


def set_language(code: str) -> bool:
    """Switch language at runtime.

    Persists the choice, reloads translations, and emits
    `bus().language_changed`. Returns True if the language actually changed.
    """
    global _translations, _current_lang

    if code not in LANGUAGES or code == _current_lang:
        return False

    settings = QSettings("Svetozar Technologies", "LocalPDF")
    settings.setValue("language", code)

    _current_lang = code
    _translations = _load_json(code) if code != "en" else _fallback

    bus().language_changed.emit(code)
    return True
