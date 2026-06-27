"""Order-independent field matching via greedy max-score assignment."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from datasheet_extract.config import MATCH_SCORE_THRESHOLD
from datasheet_extract.data.units import units_equal
from datasheet_extract.ground.normalize import values_equal


@dataclass
class FieldRecord:
    name: str
    value: str | None
    unit: str | None
    section: str | None
    context: str | None


@dataclass
class MatchPair:
    pred_idx: int
    gold_idx: int
    score: float


@dataclass
class MatchResult:
    pairs: list[MatchPair]
    unmatched_pred: list[int]
    unmatched_gold: list[int]


def normalize_name(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def name_similarity(a: str, b: str) -> float:
    return fuzz.token_set_ratio(normalize_name(a), normalize_name(b)) / 100.0


def section_similarity(a: str | None, b: str | None) -> float:
    if a is None and b is None:
        return 1.0
    if a is None or b is None:
        return 0.0
    return fuzz.token_set_ratio(normalize_name(a), normalize_name(b)) / 100.0


def context_similarity(a: str | None, b: str | None) -> float:
    if a is None and b is None:
        return 1.0
    if a is None or b is None:
        return 0.3
    na = normalize_name(a)
    nb = normalize_name(b)
    if na in nb or nb in na:
        return 1.0
    return fuzz.partial_ratio(na, nb) / 100.0


def pair_score(pred: FieldRecord, gold: FieldRecord) -> float:
    ns = name_similarity(pred.name, gold.name)
    vs = 1.0 if values_equal(pred.value, gold.value) else 0.0
    ss = section_similarity(pred.section, gold.section)
    cs = context_similarity(pred.context, gold.context)
    return 0.55 * ns + 0.30 * vs + 0.10 * ss + 0.05 * cs


def match_fields(
    pred: list[FieldRecord],
    gold: list[FieldRecord],
    threshold: float = MATCH_SCORE_THRESHOLD,
) -> MatchResult:
    if not pred:
        return MatchResult([], [], list(range(len(gold))))
    if not gold:
        return MatchResult([], list(range(len(pred))), [])

    candidates: list[tuple[float, int, int]] = []
    for i, p in enumerate(pred):
        for j, g in enumerate(gold):
            score = pair_score(p, g)
            if score >= threshold:
                candidates.append((score, i, j))

    candidates.sort(reverse=True)
    matched_pred: set[int] = set()
    matched_gold: set[int] = set()
    pairs: list[MatchPair] = []

    for score, i, j in candidates:
        if i in matched_pred or j in matched_gold:
            continue
        pairs.append(MatchPair(pred_idx=i, gold_idx=j, score=score))
        matched_pred.add(i)
        matched_gold.add(j)

    unmatched_pred = [i for i in range(len(pred)) if i not in matched_pred]
    unmatched_gold = [j for j in range(len(gold)) if j not in matched_gold]
    return MatchResult(pairs, unmatched_pred, unmatched_gold)
