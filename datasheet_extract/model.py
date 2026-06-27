"""Core data shapes for the extraction pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Word:
    id: int
    page: int
    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    size: float = 0.0
    bold: bool = False
    conf: float = 1.0  # 1.0 for text layer; OCR confidence 0–1 for scanned pages


@dataclass(frozen=True)
class Line:
    id: int
    page: int
    word_ids: tuple[int, ...]
    text: str
    bbox: tuple[float, float, float, float]
    section_id: int | None = None


@dataclass
class Section:
    id: int
    page: int
    name: str
    line_ids: list[int] = field(default_factory=list)


@dataclass
class RawField:
    name: str
    value: str | None
    unit: str | None
    section: str | None
    context: str | None
    label_line_id: int | None = None
    value_line_id: int | None = None
    label_quote: str | None = None
    value_quote: str | None = None


@dataclass
class Provenance:
    label_page: int | None = None
    label_bbox: tuple[float, float, float, float] | None = None
    label_word_ids: list[int] = field(default_factory=list)
    value_page: int | None = None
    value_bbox: tuple[float, float, float, float] | None = None
    value_word_ids: list[int] = field(default_factory=list)
    method: str = "failed"  # anchor | search | failed
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        def _bbox(b: tuple[float, float, float, float] | None) -> list[float] | None:
            return list(b) if b else None

        return {
            "label_page": self.label_page,
            "label_bbox": _bbox(self.label_bbox),
            "label_word_ids": self.label_word_ids,
            "value_page": self.value_page,
            "value_bbox": _bbox(self.value_bbox),
            "value_word_ids": self.value_word_ids,
            "method": self.method,
            "confidence": self.confidence,
        }


@dataclass
class FieldOut:
    name: str
    value: str | None
    unit: str | None
    section: str | None
    context: str | None
    provenance: Provenance = field(default_factory=Provenance)

    def to_output_dict(self) -> dict[str, Any]:
        """Golden's 5 keys plus inline provenance."""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "section": self.section,
            "context": self.context,
            "provenance": self.provenance.to_dict(),
        }


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0

    def cost_usd(self, pricing: dict[str, float]) -> float:
        return (
            self.prompt_tokens * pricing["input"] / 1_000_000
            + self.completion_tokens * pricing["output"] / 1_000_000
        )
