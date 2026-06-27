"""Ground LLM citations to word-level bounding boxes."""

from __future__ import annotations

from rapidfuzz import fuzz

from datasheet_extract.config import FUZZY_RATIO_THRESHOLD
from datasheet_extract.ground.normalize import normalize_for_match, strip_spaces
from datasheet_extract.ingest.layout_doc import LayoutDoc
from datasheet_extract.model import Line, Provenance, RawField, Word


def ground_field(rf: RawField, doc: LayoutDoc) -> Provenance:
    label_prov = _ground_side(
        doc,
        quote=rf.label_quote,
        line_id=rf.label_line_id,
        section_name=rf.section,
        anchor_bbox=None,
        is_value=False,
    )

    if rf.value is None:
        conf = min(label_prov[4], 1.0) if label_prov[4] else 0.0
        return Provenance(
            label_page=label_prov[0],
            label_bbox=label_prov[1],
            label_word_ids=label_prov[2],
            value_page=None,
            value_bbox=None,
            value_word_ids=[],
            method=label_prov[3],
            confidence=conf,
        )

    value_prov = _ground_side(
        doc,
        quote=rf.value_quote,
        line_id=rf.value_line_id,
        section_name=rf.section,
        anchor_bbox=label_prov[1],
        is_value=True,
    )

    method = _combine_method(label_prov[3], value_prov[3])
    confidence = min(label_prov[4], value_prov[4])

    return Provenance(
        label_page=label_prov[0],
        label_bbox=label_prov[1],
        label_word_ids=label_prov[2],
        value_page=value_prov[0],
        value_bbox=value_prov[1],
        value_word_ids=value_prov[2],
        method=method,
        confidence=confidence,
    )


def _ground_side(
    doc: LayoutDoc,
    quote: str | None,
    line_id: int | None,
    section_name: str | None,
    anchor_bbox: tuple[float, float, float, float] | None,
    is_value: bool,
) -> tuple[int | None, tuple[float, float, float, float] | None, list[int], str, float]:
    if not quote:
        return None, None, [], "failed", 0.0

    q_norm = normalize_for_match(quote)
    window = _window_lines(doc, line_id, section_name)

    # anchor: exact match in cited line window
    for line in window:
        run = _local_align(quote, line, doc)
        if run:
            page, bbox, wids = run
            conf = _confidence_for_words(doc, wids, 1.0)
            return page, bbox, wids, "anchor", conf

    # anchor: fuzzy match in window
    best_ratio = 0.0
    best_run = None
    for line in window:
        ratio = fuzz.partial_ratio(normalize_for_match(line.text), q_norm) / 100.0
        if ratio > best_ratio:
            run = _local_align(quote, line, doc)
            if run and ratio > best_ratio:
                best_ratio = ratio
                best_run = run
    if best_run and best_ratio >= FUZZY_RATIO_THRESHOLD:
        page, bbox, wids = best_run
        conf = _confidence_for_words(doc, wids, 0.8)
        return page, bbox, wids, "anchor", conf

    # search: doc-wide fallback
    candidates = _search_doc(doc, quote)
    if candidates:
        chosen = _disambiguate(candidates, anchor_bbox, is_value)
        page, bbox, wids = chosen
        base_conf = 0.5 if len(candidates) == 1 else 0.35
        conf = _confidence_for_words(doc, wids, base_conf)
        return page, bbox, wids, "search", conf

    return None, None, [], "failed", 0.0


def _confidence_for_words(doc: LayoutDoc, word_ids: list[int], base: float) -> float:
    confs = [doc.word_by_id[w].conf for w in word_ids if w in doc.word_by_id]
    if not confs:
        return base
    return min(base, min(confs))


def _window_lines(doc: LayoutDoc, line_id: int | None, section_name: str | None) -> list[Line]:
    if line_id is not None and line_id in doc.line_by_id:
        sec = doc.section_for_line(line_id)
        if sec:
            ids = set(sec.line_ids)
            pool = [l for l in doc.lines if l.id in ids]
        else:
            pool = doc.lines
        idx = next((i for i, l in enumerate(pool) if l.id == line_id), 0)
        return pool[max(0, idx - 2) : idx + 3]

    if section_name:
        for sec in doc.sections:
            if normalize_for_match(sec.name) == normalize_for_match(section_name):
                ids = set(sec.line_ids)
                return [l for l in doc.lines if l.id in ids]

    return doc.lines


def _local_align(
    quote: str,
    line: Line,
    doc: LayoutDoc,
) -> tuple[int, tuple[float, float, float, float], list[int]] | None:
    words = [doc.word_by_id[w] for w in line.word_ids if w in doc.word_by_id]
    if not words:
        return None

    q_compact = strip_spaces(normalize_for_match(quote))
    line_compact = strip_spaces(normalize_for_match(line.text))

    if q_compact and q_compact in line_compact:
        run = _find_contiguous_run(words, quote)
        if run:
            return _run_to_bbox(line.page, run)

    if quote in line.text:
        run = _find_contiguous_run(words, quote)
        if run:
            return _run_to_bbox(line.page, run)

    return None


def _find_contiguous_run(words: list[Word], quote: str) -> list[Word] | None:
    if not words or not quote:
        return None

    q_tokens = quote.split()
    if len(q_tokens) == 1:
        for w in words:
            if quote in w.text or normalize_for_match(quote) in normalize_for_match(w.text):
                return [w]
        return None

    for i in range(len(words)):
        matched: list[Word] = []
        qi = 0
        for j in range(i, len(words)):
            wt = words[j].text
            if q_tokens[qi] in wt or normalize_for_match(q_tokens[qi]) in normalize_for_match(wt):
                matched.append(words[j])
                qi += 1
                if qi >= len(q_tokens):
                    return matched
            elif matched:
                break
    return None


def _run_to_bbox(page: int, run: list[Word]) -> tuple[int, tuple[float, float, float, float], list[int]]:
    bbox = (
        min(w.x0 for w in run),
        min(w.top for w in run),
        max(w.x1 for w in run),
        max(w.bottom for w in run),
    )
    return page, bbox, [w.id for w in run]


def _search_doc(
    doc: LayoutDoc,
    quote: str,
) -> list[tuple[int, tuple[float, float, float, float], list[int]]]:
    results: list[tuple[int, tuple[float, float, float, float], list[int]]] = []
    for line in doc.lines:
        run = _local_align(quote, line, doc)
        if run:
            results.append(run)
    return results


def _disambiguate(
    candidates: list[tuple[int, tuple[float, float, float, float], list[int]]],
    anchor_bbox: tuple[float, float, float, float] | None,
    is_value: bool,
) -> tuple[int, tuple[float, float, float, float], list[int]]:
    if len(candidates) == 1 or anchor_bbox is None:
        return candidates[0]

    ax0, ay0, ax1, ay1 = anchor_bbox

    def score(c: tuple[int, tuple[float, float, float, float], list[int]]) -> float:
        _, bbox, _ = c
        x0, y0, x1, y1 = bbox
        if is_value:
            right_bonus = max(0, x0 - ax1) * 0.1
            below_bonus = max(0, y0 - ay1) * 0.1
            dist = ((x0 - ax1) ** 2 + (y0 - ay0) ** 2) ** 0.5
            return -(dist - right_bonus - below_bonus)
        dist = ((x0 - ax0) ** 2 + (y0 - ay0) ** 2) ** 0.5
        return -dist

    return max(candidates, key=score)


def _combine_method(a: str, b: str) -> str:
    priority = {"anchor": 3, "search": 2, "failed": 1}
    return a if priority.get(a, 0) <= priority.get(b, 0) else b
