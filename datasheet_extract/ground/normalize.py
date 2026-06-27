"""Normalization for matching only — never mutates emitted values."""

from __future__ import annotations

import re
import unicodedata


def normalize_for_match(text: str | None) -> str:
    if text is None:
        return ""
    s = unicodedata.normalize("NFKC", text)
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    # Locale: comma between digits → period
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)
    # Unit glyph unification
    s = s.replace("m³/h", "m3/h").replace("m³", "m3")
    s = s.replace("°f", "f").replace("°c", "c").replace("°", "")
    s = re.sub(r"[^\w\s./-]", "", s)
    return s


def values_equal(a: str | None, b: str | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return normalize_for_match(a) == normalize_for_match(b)


def strip_spaces(text: str) -> str:
    return re.sub(r"\s+", "", text)
