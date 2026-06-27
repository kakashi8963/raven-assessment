"""Evaluation metrics: coverage, precision, value/unit/section/context, provenance-sanity, cost."""

from __future__ import annotations

from dataclasses import dataclass, field

from datasheet_extract.data.units import units_equal
from datasheet_extract.eval.match import FieldRecord, MatchResult, match_fields
from datasheet_extract.ground.normalize import values_equal
from datasheet_extract.model import Usage


@dataclass
class DocMetrics:
    source: str = ""
    total_gold: int = 0
    total_pred: int = 0
    matched: int = 0
    recall: float = 0.0
    precision: float = 0.0
    value_accuracy: float = 0.0
    null_accuracy: float = 0.0
    unit_accuracy: float = 0.0
    section_accuracy: float = 0.0
    context_accuracy: float = 0.0
    provenance_sanity: float = 0.0
    provenance_by_method: dict[str, float] = field(default_factory=dict)
    usage: Usage = field(default_factory=Usage)
    cost_usd: float = 0.0


@dataclass
class AggregateMetrics:
    docs: list[DocMetrics] = field(default_factory=list)

    @property
    def recall(self) -> float:
        total = sum(d.total_gold for d in self.docs)
        matched = sum(d.matched for d in self.docs)
        return matched / total if total else 0.0

    @property
    def precision(self) -> float:
        total = sum(d.total_pred for d in self.docs)
        matched = sum(d.matched for d in self.docs)
        return matched / total if total else 0.0

    @property
    def total_cost_usd(self) -> float:
        return sum(d.cost_usd for d in self.docs)


def load_fields_from_json(data: dict) -> list[FieldRecord]:
    """Load golden keys only — ignores inline provenance."""
    return [
        FieldRecord(
            name=f["name"],
            value=f.get("value"),
            unit=f.get("unit"),
            section=f.get("section"),
            context=f.get("context"),
        )
        for f in data.get("fields", [])
    ]


def extract_provenance_from_json(data: dict) -> list[dict]:
    return [f.get("provenance", {}) for f in data.get("fields", [])]


def compute_doc_metrics(
    pred: list[FieldRecord],
    gold: list[FieldRecord],
    source: str = "",
    pred_provenance: list[dict] | None = None,
    usage: Usage | None = None,
    pricing: dict[str, float] | None = None,
) -> tuple[DocMetrics, MatchResult]:
    result = match_fields(pred, gold)
    m = DocMetrics(
        source=source,
        total_gold=len(gold),
        total_pred=len(pred),
        matched=len(result.pairs),
    )
    m.recall = m.matched / m.total_gold if m.total_gold else 0.0
    m.precision = m.matched / m.total_pred if m.total_pred else 0.0

    value_ok = null_ok = null_total = unit_ok = unit_total = 0
    section_ok = context_ok = 0
    prov_ok = prov_total = 0
    prov_by_method: dict[str, list[bool]] = {}

    for pair in result.pairs:
        p, g = pred[pair.pred_idx], gold[pair.gold_idx]
        if values_equal(p.value, g.value):
            value_ok += 1
        if g.value is None:
            null_total += 1
            if p.value is None:
                null_ok += 1
        if g.unit is not None:
            unit_total += 1
            if units_equal(p.unit, g.unit):
                unit_ok += 1
        if p.section == g.section or (
            p.section and g.section and p.section.rstrip(":") == g.section.rstrip(":")
        ):
            section_ok += 1
        from datasheet_extract.eval.match import context_similarity

        if context_similarity(p.context, g.context) >= 0.5:
            context_ok += 1

        if g.value is not None and pred_provenance:
            prov = pred_provenance[pair.pred_idx] if pair.pred_idx < len(pred_provenance) else {}
            sane = _provenance_sanity(g.value, prov)
            prov_total += 1
            if sane:
                prov_ok += 1
            method = prov.get("method", "unknown")
            prov_by_method.setdefault(method, []).append(sane)

    n = len(result.pairs) or 1
    m.value_accuracy = value_ok / n
    m.null_accuracy = null_ok / null_total if null_total else 1.0
    m.unit_accuracy = unit_ok / unit_total if unit_total else 1.0
    m.section_accuracy = section_ok / n
    m.context_accuracy = context_ok / n
    m.provenance_sanity = prov_ok / prov_total if prov_total else 0.0
    m.provenance_by_method = {k: sum(v) / len(v) for k, v in prov_by_method.items()}

    if usage:
        m.usage = usage
    if usage and pricing:
        m.cost_usd = usage.cost_usd(pricing)

    return m, result


def _provenance_sanity(value: str, prov: dict) -> bool:
    """Check if value grounding used the cited line (anchor method)."""
    return prov.get("method", "failed") == "anchor"
