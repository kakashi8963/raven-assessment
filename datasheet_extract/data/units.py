"""Unit equivalence table for evaluation matching only."""

from __future__ import annotations

import re

# Normalize unit strings for comparison
UNIT_ALIASES: dict[str, str] = {
    "m³/h": "m3/h",
    "m³/hr": "m3/h",
    "m3/hr": "m3/h",
    "m³": "m3",
    "l/min": "l/min",
    "lpm": "l/min",
    "°f": "f",
    "deg f": "f",
    "°c": "c",
    "deg c": "c",
    "bar(g)": "bar",
    "barg": "bar",
    "kpag": "kpa",
    "kw": "kw",
    "hp": "hp",
    "rpm": "rpm",
    "mm": "mm",
    "in": "in",
    "%": "%",
}


def normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    u = unit.strip().lower()
    u = u.replace("³", "3").replace("°", "")
    u = re.sub(r"\s+", "", u)
    return UNIT_ALIASES.get(u, u)


def units_equal(a: str | None, b: str | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return normalize_unit(a) == normalize_unit(b)
