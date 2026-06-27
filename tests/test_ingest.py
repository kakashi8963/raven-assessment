"""Tests for ingest layer (lines, sections) using synthetic word data."""

from __future__ import annotations

from datasheet_extract.ingest.lines import reconstruct_lines
from datasheet_extract.ingest.sections import detect_sections
from datasheet_extract.model import Word


def _word(wid: int, page: int, text: str, x0: float, top: float, size: float = 10.0, bold: bool = False) -> Word:
    return Word(
        id=wid,
        page=page,
        text=text,
        x0=x0,
        top=top,
        x1=x0 + len(text) * 6,
        bottom=top + 12,
        size=size,
        bold=bold,
    )


def test_reconstruct_lines_single_page():
    words = [
        _word(0, 0, "Area:", 50, 100),
        _word(1, 0, "032", 120, 100),
        _word(2, 0, "Client:", 50, 120),
        _word(3, 0, "ACME", 120, 120),
    ]
    lines = reconstruct_lines(words)
    assert len(lines) == 2
    assert "Area:" in lines[0].text and "032" in lines[0].text
    assert lines[0].word_ids == (0, 1)


def test_section_detection_finds_header():
    words = [
        _word(0, 0, "OPERATING", 50, 50, size=14.0, bold=True),
        _word(1, 0, "CONDITIONS", 120, 50, size=14.0, bold=True),
        _word(2, 0, "Flow:", 50, 80),
        _word(3, 0, "3.35", 120, 80),
    ]
    lines = reconstruct_lines(words)
    sections = detect_sections(words, lines)
    assert len(sections) >= 1
    assert "OPERATING" in sections[0].name
    assert any(l.section_id == 0 for l in lines)
