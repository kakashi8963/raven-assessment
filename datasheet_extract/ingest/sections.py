"""Section detection via font/caps heuristics, with merge of micro-sections."""

from __future__ import annotations

import re
import statistics

from datasheet_extract.config import MIN_HEADER_CHARS, MIN_SECTION_LINES
from datasheet_extract.model import Line, Section, Word

_TRAILING_NOTE_NUM = re.compile(r"\s+\d{1,3}$")


def detect_sections(words: list[Word], lines: list[Line]) -> list[Section]:
    if not lines:
        return []

    body_sizes = [w.size for w in words if w.size > 0]
    p75 = statistics.quantiles(body_sizes, n=4)[2] if len(body_sizes) >= 4 else 0.0

    header_line_ids: list[int] = []
    for line in lines:
        line_words = [w for w in words if w.id in line.word_ids]
        if not line_words:
            continue
        if _is_header_line(line, line_words, p75):
            header_line_ids.append(line.id)

    sections: list[Section] = []
    sid = 0

    for i, hid in enumerate(header_line_ids):
        hline = next(l for l in lines if l.id == hid)
        next_hid = header_line_ids[i + 1] if i + 1 < len(header_line_ids) else None
        if next_hid is None:
            span_lines = [l for l in lines if l.id >= hid]
        else:
            span_lines = [l for l in lines if hid <= l.id < next_hid]

        sections.append(
            Section(
                id=sid,
                page=hline.page,
                name=hline.text.strip(),
                line_ids=[l.id for l in span_lines],
            )
        )
        sid += 1

    sections = _merge_small_sections(sections)
    _assign_line_sections(lines, sections)
    return sections


def _merge_small_sections(sections: list[Section]) -> list[Section]:
    """Fold micro-sections (table fragments, footnote rows) into the previous section."""
    if not sections:
        return []

    merged: list[Section] = []
    for sec in sections:
        if merged and len(sec.line_ids) < MIN_SECTION_LINES:
            prev = merged[-1]
            prev.line_ids.extend(sec.line_ids)
        else:
            merged.append(
                Section(
                    id=len(merged),
                    page=sec.page,
                    name=sec.name,
                    line_ids=list(sec.line_ids),
                )
            )

    return merged


def _assign_line_sections(lines: list[Line], sections: list[Section]) -> None:
    line_to_section: dict[int, int] = {}
    for sec in sections:
        for lid in sec.line_ids:
            line_to_section[lid] = sec.id

    for i, line in enumerate(lines):
        sid = line_to_section.get(line.id)
        if sid is not None:
            lines[i] = Line(
                id=line.id,
                page=line.page,
                word_ids=line.word_ids,
                text=line.text,
                bbox=line.bbox,
                section_id=sid,
            )


def _is_header_line(line: Line, line_words: list[Word], p75_size: float) -> bool:
    text = line.text.strip()
    if not text or len(text) > 120:
        return False

    words = text.split()
    if len(words) == 1 and len(text) < MIN_HEADER_CHARS:
        return False

    # Table row fragments like "HANDLED 14" or "NUMBER TWO (1W+1S) 5"
    if _TRAILING_NOTE_NUM.search(text) and len(words) <= 5:
        return False

    digit_ratio = sum(c.isdigit() for c in text) / max(len(text), 1)
    if digit_ratio > 0.35:
        return False

    sized = [w.size for w in line_words if w.size > 0]
    avg_size = statistics.mean(sized) if sized else 0.0
    any_bold = any(w.bold for w in line_words)
    all_caps = text.upper() == text and any(c.isalpha() for c in text)
    short = len(words) <= 12
    left_aligned = min(w.x0 for w in line_words) < 100 if line_words else False

    if avg_size > p75_size and p75_size > 0:
        return True
    if any_bold and short and (all_caps or len(text) >= MIN_HEADER_CHARS):
        return True
    if all_caps and short and left_aligned and len(text) >= MIN_HEADER_CHARS:
        return True
    return False
