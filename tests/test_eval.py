"""Evaluation matching and metrics on hand-made predictions."""

from __future__ import annotations

from datasheet_extract.data.units import units_equal
from datasheet_extract.eval.match import FieldRecord, match_fields, name_similarity
from datasheet_extract.eval.metrics import compute_doc_metrics
from datasheet_extract.ground.normalize import values_equal


def test_name_similarity_fuzzy():
    assert name_similarity("Nominal Flow", "nominal flow") >= 0.9


def test_values_equal_locale():
    assert values_equal("3.35", "3,35")


def test_units_equal():
    assert units_equal("m3/h", "m³/h")


def test_hungarian_matching():
    gold = [
        FieldRecord("Nominal Flow", "3.35", "m3/h", "OPERATING CONDITIONS", "nominal flow"),
        FieldRecord("Coupling Type", None, None, None, None),
    ]
    pred = [
        FieldRecord("Nominal Flow", "3,35", "m3/h", "OPERATING CONDITIONS", "nominal flow"),
        FieldRecord("Coupling Type", None, None, None, None),
        FieldRecord("Extra Field", "x", None, None, None),
    ]
    result = match_fields(pred, gold)
    assert len(result.pairs) == 2
    assert len(result.unmatched_pred) == 1
    assert len(result.unmatched_gold) == 0


def test_doc_metrics_recall_precision():
    gold = [
        FieldRecord("Area", "032", None, None, None),
        FieldRecord("Client", None, None, None, None),
    ]
    pred = [
        FieldRecord("Area", "032", None, None, None),
    ]
    metrics, result = compute_doc_metrics(pred, gold, source="test.pdf")
    assert metrics.recall == 0.5
    assert metrics.precision == 1.0
    assert metrics.matched == 1
