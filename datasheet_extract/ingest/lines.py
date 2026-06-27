"""Reconstruct lines from words via y-clustering and x-sort."""

from __future__ import annotations

import statistics
from collections import defaultdict

from datasheet_extract.config import LINE_CLUSTER_Y_TOLERANCE_FACTOR
from datasheet_extract.model import Line, Word


def reconstruct_lines(words: list[Word]) -> list[Line]:
    if not words:
        return []

    lines: list[Line] = []
    lid = 0

    by_page: dict[int, list[Word]] = defaultdict(list)
    for w in words:
        by_page[w.page].append(w)

    for page in sorted(by_page):
        for cluster in _cluster_by_y(by_page[page]):
            cluster.sort(key=lambda w: (w.top, w.x0))
            word_ids = tuple(w.id for w in cluster)
            text = " ".join(w.text for w in cluster)
            bbox = _union_bbox(cluster)
            lines.append(Line(id=lid, page=page, word_ids=word_ids, text=text, bbox=bbox))
            lid += 1

    return lines


def _cluster_by_y(words: list[Word]) -> list[list[Word]]:
    if not words:
        return []

    heights = [w.bottom - w.top for w in words if w.bottom > w.top]
    median_h = statistics.median(heights) if heights else 10.0
    tol = max(2.0, median_h * LINE_CLUSTER_Y_TOLERANCE_FACTOR)

    sorted_words = sorted(words, key=lambda w: (w.top, w.x0))
    clusters: list[list[Word]] = []
    current: list[Word] = [sorted_words[0]]
    ref_top = sorted_words[0].top

    for w in sorted_words[1:]:
        if abs(w.top - ref_top) <= tol:
            current.append(w)
        else:
            clusters.append(current)
            current = [w]
            ref_top = w.top
    clusters.append(current)
    return clusters


def _union_bbox(words: list[Word]) -> tuple[float, float, float, float]:
    return (
        min(w.x0 for w in words),
        min(w.top for w in words),
        max(w.x1 for w in words),
        max(w.bottom for w in words),
    )
