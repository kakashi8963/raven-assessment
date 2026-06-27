"""Grounding algorithm tests."""

from __future__ import annotations

from datasheet_extract.ground.normalize import normalize_for_match, values_equal
from datasheet_extract.ground.provenance import ground_field
from datasheet_extract.ingest.layout_doc import LayoutDoc
from datasheet_extract.model import Line, RawField, Section, Word


def _mini_doc() -> LayoutDoc:
    words = [
        Word(0, 0, "Nominal", 50, 100, 110, 112, 10),
        Word(1, 0, "Flow:", 110, 100, 150, 112, 10),
        Word(2, 0, "3,35", 160, 100, 190, 112, 10),
        Word(3, 0, "m3/h", 195, 100, 230, 112, 10),
        Word(4, 0, "Area:", 50, 120, 90, 132, 10),
        Word(5, 0, "032", 100, 120, 130, 132, 10),
    ]
    lines = [
        Line(0, 0, (0, 1, 2, 3), "Nominal Flow: 3,35 m3/h", (50, 100, 230, 112), section_id=0),
        Line(1, 0, (4, 5), "Area: 032", (50, 120, 130, 132), section_id=0),
    ]
    sections = [Section(0, 0, "OPERATING CONDITIONS", line_ids=[0, 1])]
    doc = LayoutDoc(source_pdf="test.pdf", words=words, lines=lines, sections=sections)
    doc.word_by_id = {w.id: w for w in words}
    doc.line_by_id = {l.id: l for l in lines}
    doc.section_by_id = {s.id: s for s in sections}
    return doc


def test_locale_normalization_for_match():
    assert normalize_for_match("3,35") == normalize_for_match("3.35")


def test_values_equal_null():
    assert values_equal(None, None)
    assert not values_equal("x", None)


def test_ground_field_anchor_exact():
    doc = _mini_doc()
    rf = RawField(
        name="Nominal Flow",
        value="3,35",
        unit="m3/h",
        section="OPERATING CONDITIONS",
        context=None,
        label_line_id=0,
        value_line_id=0,
        label_quote="Nominal Flow:",
        value_quote="3,35",
    )
    prov = ground_field(rf, doc)
    assert prov.method == "anchor"
    assert prov.value_bbox is not None
    assert prov.value_word_ids


def test_ground_null_value():
    doc = _mini_doc()
    rf = RawField(
        name="Max Flow",
        value=None,
        unit=None,
        section="OPERATING CONDITIONS",
        context=None,
        label_line_id=0,
        value_line_id=0,
        label_quote="Nominal",
        value_quote=None,
    )
    prov = ground_field(rf, doc)
    assert prov.value_bbox is None
    assert prov.label_bbox is not None
