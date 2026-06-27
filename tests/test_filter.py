"""Tests for post-filter and section merge."""

from __future__ import annotations

from datasheet_extract.emit import filter_raw_fields, _dedupe_by_label_line
from datasheet_extract.ingest.layout_doc import LayoutDoc
from datasheet_extract.ingest.lines import reconstruct_lines
from datasheet_extract.ingest.sections import detect_sections
from datasheet_extract.model import Line, RawField, Word


def _word(wid, page, text, x0, top, size=10.0, bold=False, conf=1.0):
    return Word(wid, page, text, x0, top, x0 + 50, top + 12, size, bold, conf)


def test_filter_drops_junk_names():
    words = [_word(0, 0, "42", 50, 100, conf=0.3)]
    lines = [Line(0, 0, (0,), "42", (50, 100, 100, 112))]
    doc = LayoutDoc("t.pdf", words, lines)
    doc.word_by_id = {0: words[0]}
    doc.line_by_id = {0: lines[0]}

    raw = [
        RawField("42", "x", None, None, None, 0, 0, "42", "x"),
        RawField("Nominal Flow", "3.35", "m3/h", None, None, 0, 0, "Flow", "3.35"),
    ]
    kept = filter_raw_fields(raw, doc)
    assert len(kept) == 1
    assert kept[0].name == "Nominal Flow"


def test_dedupe_by_label_line():
    fields = [
        RawField("Note", None, None, None, None, 5, 5, "Note", None),
        RawField("General Note 59", "text", None, None, None, 5, 5, "Note", "text"),
    ]
    out = _dedupe_by_label_line(fields)
    assert len(out) == 1
    assert out[0].name == "General Note 59"


def test_merge_small_sections():
    words = [
        _word(0, 0, "OPERATING", 50, 50, size=14, bold=True),
        _word(1, 0, "CONDITIONS", 120, 50, size=14, bold=True),
        _word(2, 0, "Flow:", 50, 80),
        _word(3, 0, "3.35", 120, 80),
        _word(4, 0, "14", 50, 100, bold=True),
    ]
    lines = reconstruct_lines(words)
    sections = detect_sections(words, lines)
    # "14" alone should not become its own merged section spanning 1 line
    assert len(sections) <= 2
    assert any("OPERATING" in s.name for s in sections)
