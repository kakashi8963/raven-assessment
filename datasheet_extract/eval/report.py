"""Per-field diff table and aggregate report."""

from __future__ import annotations

import json
from pathlib import Path

from datasheet_extract.config import Config, GPT4O_PRICING
from datasheet_extract.data.units import units_equal
from datasheet_extract.eval.match import FieldRecord, MatchResult
from datasheet_extract.eval.metrics import (
    AggregateMetrics,
    DocMetrics,
    compute_doc_metrics,
    extract_provenance_from_json,
    load_fields_from_json,
)
from datasheet_extract.ground.normalize import values_equal


def evaluate(pred_path: Path, gold_path: Path, config: Config | None = None) -> tuple[DocMetrics, MatchResult, str]:
    with open(pred_path, encoding="utf-8") as f:
        pred_data = json.load(f)
    with open(gold_path, encoding="utf-8") as f:
        gold_data = json.load(f)

    pred = load_fields_from_json(pred_data)
    gold = load_fields_from_json(gold_data)
    pred_prov = extract_provenance_from_json(pred_data)

    pricing = config.pricing() if config else GPT4O_PRICING
    metrics, result = compute_doc_metrics(
        pred,
        gold,
        source=pred_data.get("source_pdf", pred_path.name),
        pred_provenance=pred_prov,
        pricing=pricing,
    )
    report = format_doc_report(pred, gold, result, metrics, pred_prov)
    return metrics, result, report


def format_doc_report(
    pred: list[FieldRecord],
    gold: list[FieldRecord],
    result: MatchResult,
    metrics: DocMetrics,
    pred_provenance: list[dict] | None = None,
) -> str:
    lines: list[str] = []
    lines.append(f"=== {metrics.source} ===")
    lines.append(
        f"Recall: {metrics.recall:.1%} ({metrics.matched}/{metrics.total_gold}) | "
        f"Precision: {metrics.precision:.1%} ({metrics.matched}/{metrics.total_pred})"
    )
    lines.append(
        f"Value: {metrics.value_accuracy:.1%} | Null: {metrics.null_accuracy:.1%} | "
        f"Unit: {metrics.unit_accuracy:.1%} | Section: {metrics.section_accuracy:.1%} | "
        f"Context: {metrics.context_accuracy:.1%}"
    )
    if metrics.provenance_sanity:
        lines.append(f"Provenance sanity: {metrics.provenance_sanity:.1%}")
    if metrics.provenance_by_method:
        by_m = ", ".join(f"{k}={v:.0%}" for k, v in metrics.provenance_by_method.items())
        lines.append(f"Provenance by method: {by_m}")
    if metrics.cost_usd:
        lines.append(f"Cost: ${metrics.cost_usd:.4f}")

    lines.append("")
    lines.append(f"{'STATUS':<16} {'NAME':<36} {'METHOD/CONF':<14} PRED → GOLD")
    lines.append("-" * 110)

    for pair in sorted(result.pairs, key=lambda p: gold[p.gold_idx].name):
        p, g = pred[pair.pred_idx], gold[pair.gold_idx]
        status = "MATCH"
        if not values_equal(p.value, g.value):
            status = "VALUE-MISMATCH"
        elif g.unit is not None and not units_equal(p.unit, g.unit):
            status = "UNIT-MISMATCH"
        prov = (pred_provenance or [{}])[pair.pred_idx] if pred_provenance else {}
        method_conf = f"{prov.get('method', '?')}/{prov.get('confidence', 0):.2f}"
        lines.append(
            f"{status:<16} {g.name:<36} {method_conf:<14} {repr(p.value)} → {repr(g.value)}"
        )

    for gi in result.unmatched_gold:
        g = gold[gi]
        lines.append(f"{'MISSING':<16} {g.name:<36} {'—':<14} — → {repr(g.value)}")

    for pi in result.unmatched_pred:
        p = pred[pi]
        prov = (pred_provenance or [{}])[pi] if pred_provenance else {}
        method_conf = f"{prov.get('method', '?')}/{prov.get('confidence', 0):.2f}"
        lines.append(f"{'EXTRA':<16} {p.name:<36} {method_conf:<14} {repr(p.value)} → —")

    return "\n".join(lines)


def format_aggregate_report(agg: AggregateMetrics) -> str:
    lines = ["=== AGGREGATE ===", ""]
    lines.append(
        f"{'Document':<25} {'Recall':>8} {'Prec':>8} {'Value':>8} {'Null':>8} {'Unit':>8} {'Cost':>10}"
    )
    lines.append("-" * 85)
    for d in agg.docs:
        lines.append(
            f"{d.source:<25} {d.recall:>7.1%} {d.precision:>7.1%} "
            f"{d.value_accuracy:>7.1%} {d.null_accuracy:>7.1%} {d.unit_accuracy:>7.1%} "
            f"${d.cost_usd:>8.4f}"
        )
    lines.append("-" * 85)
    lines.append(
        f"{'TOTAL':<25} {agg.recall:>7.1%} {agg.precision:>7.1%} "
        f"{'':>8} {'':>8} {'':>8} ${agg.total_cost_usd:>8.4f}"
    )
    return "\n".join(lines)
