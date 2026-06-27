"""Emit one JSON: golden's 5 keys + inline provenance per field."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from datasheet_extract.config import MIN_FIELD_NAME_LEN, MIN_NAME_ALPHA_RATIO, OCR_MIN_LABEL_CONF
from datasheet_extract.ingest.layout_doc import LayoutDoc
from datasheet_extract.model import FieldOut, RawField

log = logging.getLogger(__name__)

_BOILERPLATE = re.compile(
    r"^("
    r"confidential|unclassified|hold list|hold comment|"
    r"section (title|header|number)|general note \d+|"
    r"revision modification log|document title|page \d|"
    r"unknown field|remarks document|section \d+"
    r")$",
    re.IGNORECASE,
)

_JUNK_NAME = re.compile(r"^[\d\s./\\|:-]+$")


def canonicalize_section(section: str | None) -> str | None:
    if section is None:
        return None
    s = section.strip()
    while s.endswith(":"):
        s = s[:-1].rstrip()
    return s or None


def filter_raw_fields(raw_fields: list[RawField], doc: LayoutDoc) -> list[RawField]:
    """Drop OCR junk, boilerplate, and duplicate label-line extractions."""
    kept: list[RawField] = []
    dropped = 0

    for rf in raw_fields:
        if _should_drop(rf, doc):
            dropped += 1
            continue
        kept.append(rf)

    kept = _dedupe_by_label_line(kept)
    if dropped:
        log.info("Post-filter dropped %d fields (%d remaining)", dropped, len(kept))
    return kept


def _should_drop(rf: RawField, doc: LayoutDoc) -> bool:
    name = rf.name.strip()
    if len(name) < MIN_FIELD_NAME_LEN:
        return True
    if name.isdigit() or _JUNK_NAME.match(name):
        return True
    if _BOILERPLATE.match(name):
        return True

    alpha = sum(c.isalpha() for c in name)
    if name and alpha / len(name) < MIN_NAME_ALPHA_RATIO:
        return True

    if rf.label_line_id is not None:
        line = doc.line_by_id.get(rf.label_line_id)
        if line:
            confs = [doc.word_by_id[w].conf for w in line.word_ids if w in doc.word_by_id]
            if confs and min(confs) < OCR_MIN_LABEL_CONF and len(name) <= 5:
                return True

    return False


def _dedupe_by_label_line(fields: list[RawField]) -> list[RawField]:
    """Keep one field per label_line_id — prefer longer name, then non-null value."""
    by_line: dict[int, RawField] = {}
    no_line: list[RawField] = []

    for rf in fields:
        if rf.label_line_id is None:
            no_line.append(rf)
            continue
        prev = by_line.get(rf.label_line_id)
        if prev is None or _field_rank(rf) > _field_rank(prev):
            by_line[rf.label_line_id] = rf

    return no_line + list(by_line.values())


def _field_rank(rf: RawField) -> tuple[int, int, int]:
    return (
        1 if rf.value is not None else 0,
        len(rf.name),
        len(rf.value or ""),
    )


def assemble_fields(raw_fields: list, provenances: list) -> list[FieldOut]:
    """Type-check, canonicalize sections, dedupe."""
    out: list[FieldOut] = []
    seen: set[tuple] = set()

    for rf, prov in zip(raw_fields, provenances):
        value = rf.value
        if value is not None and not isinstance(value, str):
            value = str(value)

        section = canonicalize_section(rf.section)
        field = FieldOut(
            name=rf.name.strip(),
            value=value,
            unit=rf.unit,
            section=section,
            context=rf.context,
            provenance=prov,
        )

        key = (field.name, field.value, field.section, field.context, rf.value_line_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(field)

    return out


def emit_output(source_pdf: str, fields: list[FieldOut], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "source_pdf": source_pdf,
        "fields": [f.to_output_dict() for f in fields],
    }
    json_path = output_path if output_path.suffix == ".json" else output_path.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return json_path
