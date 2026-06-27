"""LLM extraction: single-call → page → merged-section (per page) → line-batch."""

from __future__ import annotations

import logging

from datasheet_extract.config import DENSE_PAGE_LINES, LINES_PER_BATCH, Config
from datasheet_extract.ingest.layout_doc import LayoutDoc
from datasheet_extract.llm.client import LLMClient, is_payload_too_large
from datasheet_extract.model import RawField, Usage

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You extract structured fields from process equipment datasheets (pumps, motors, seals, etc.).

Rules:
1. Emit one field per labeled datum on the sheet, INCLUDING present-but-blank fields with value=null.
   A null value is required output when the label exists but the value cell is empty — not an omission.
2. name = canonical English Title-Case engineering term. Translate French/bilingual labels to standard
   English. Disambiguate repeated labels via the name (e.g. "Revision 00 Date", "Off-Spec Case Total Flow").
3. unit = measurement unit string or null when none applies.
4. section = the section heading this field belongs to (copy from [SECTION] markers or infer from context).
5. context = short disambiguator when the name alone is ambiguous: operating case/column, checkbox state
   (e.g. "checkbox is filled"), note reference (e.g. "per note (15)"), or combined-cell origin.
6. label_line_id / value_line_id = the L# line id you read each from.
7. label_quote / value_quote = VERBATIM substring from that line. Never invent coordinates or text.
8. For checkbox/binary fields with no separate value token, cite the label words as value_quote and put
   the state in context.
9. For synthesized values from a combined cell (e.g. "CS/CS" → "CS" for casing), cite the source cell
   as value_quote and explain in context.

Return JSON: {"fields": [ ... ]} where each field has:
name, value (string|null), unit (string|null), section (string|null), context (string|null),
label_line_id (int|null), value_line_id (int|null), label_quote (string|null), value_quote (string|null).

Few-shot examples (fabricated mini-sheet, not from any real document):

Example input:
[SECTION] OPERATING CONDITIONS
L10 | Nominal Flow: 3.35 m3/h
L11 | Max Flow:
L12 | Driver Type: [x] Electric Motor  [ ] Turbine
L13 | Casing / Impeller: CS/CS

Example output fields:
- {"name":"Nominal Flow","value":"3.35","unit":"m3/h","section":"OPERATING CONDITIONS","context":"nominal flow",
   "label_line_id":10,"value_line_id":10,"label_quote":"Nominal Flow:","value_quote":"3.35"}
- {"name":"Max Flow","value":null,"unit":null,"section":"OPERATING CONDITIONS","context":null,
   "label_line_id":11,"value_line_id":11,"label_quote":"Max Flow:","value_quote":null}
- {"name":"Driver Type","value":"Electric Motor","unit":null,"section":"OPERATING CONDITIONS",
   "context":"checkbox is filled","label_line_id":12,"value_line_id":12,"label_quote":"Driver Type:",
   "value_quote":"Electric Motor"}
- {"name":"Casing Material","value":"CS","unit":null,"section":"OPERATING CONDITIONS",
   "context":"from combined CS/CS cell","label_line_id":13,"value_line_id":13,
   "label_quote":"Casing / Impeller:","value_quote":"CS/CS"}
"""


def extract_fields(doc: LayoutDoc, config: Config) -> tuple[list[RawField], Usage]:
    client = LLMClient(config)
    user = "Extract all fields from this datasheet.\n\n" + doc.render()

    try:
        data = client.chat_json(SYSTEM_PROMPT, user)
        return _parse_response(data), client.usage
    except RuntimeError as e:
        if is_payload_too_large(e):
            log.warning("Single-call payload too large — falling back to hybrid page/section extraction")
        else:
            log.warning("Single-call extraction failed (%s) — falling back to hybrid page/section extraction", e)

    return _extract_hybrid(doc, client)


def _extract_hybrid(doc: LayoutDoc, client: LLMClient) -> tuple[list[RawField], Usage]:
    fields: list[RawField] = []

    for page in doc.page_numbers():
        batch = _extract_page(doc, client, page)
        fields.extend(batch)
        log.info("Page %d done — %d fields total", page + 1, len(fields))

    return fields, client.usage


def _extract_page(doc: LayoutDoc, client: LLMClient, page: int) -> list[RawField]:
    page_lines = doc.lines_on_page(page)

    if len(page_lines) <= DENSE_PAGE_LINES:
        try:
            rendered = doc.render(page=page)
            user = f"Extract all fields from page {page + 1} of this datasheet.\n\n{rendered}"
            return _parse_response(client.chat_json(SYSTEM_PROMPT, user))
        except RuntimeError:
            log.warning("Page %d whole-page call failed — trying section chunks", page + 1)

    log.info(
        "Page %d: %d lines — using merged-section chunks",
        page + 1,
        len(page_lines),
    )
    return _extract_page_by_sections(doc, client, page)


def _extract_page_by_sections(doc: LayoutDoc, client: LLMClient, page: int) -> list[RawField]:
    fields: list[RawField] = []
    sections = doc.sections_on_page(page)

    if not sections:
        return _extract_line_batches(doc, client, page, doc.lines_on_page(page))

    for sec in sections:
        rendered = doc.render(section_id=sec.id, page=page)
        if not rendered.strip():
            continue
        try:
            user = (
                f'Extract all fields from section "{sec.name}" on page {page + 1}.\n\n{rendered}'
            )
            fields.extend(_parse_response(client.chat_json(SYSTEM_PROMPT, user)))
        except RuntimeError:
            log.warning(
                'Section "%s" on page %d failed — line batches',
                sec.name[:40],
                page + 1,
            )
            sec_lines = [l for l in doc.lines_on_page(page) if l.id in set(sec.line_ids)]
            fields.extend(_extract_line_batches(doc, client, page, sec_lines, sec.name))

    return fields


def _extract_line_batches(
    doc: LayoutDoc,
    client: LLMClient,
    page: int,
    lines: list,
    section_name: str | None = None,
) -> list[RawField]:
    fields: list[RawField] = []
    label = section_name or f"page {page + 1}"

    for i in range(0, len(lines), LINES_PER_BATCH):
        batch = lines[i : i + LINES_PER_BATCH]
        ids = {l.id for l in batch}
        rendered = doc.render(page=page, line_ids=ids)
        user = (
            f'Extract all fields from "{label}" on page {page + 1}, '
            f"lines {batch[0].id}–{batch[-1].id}.\n\n{rendered}"
        )
        fields.extend(_parse_response(client.chat_json(SYSTEM_PROMPT, user)))

    return fields


def _coalesce_str(value) -> str | None:
    if value is None or value == "" or value == "null":
        return None
    return str(value)


def _coalesce_int(value) -> int | None:
    if value is None or value == "" or value == "null":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_response(data: dict) -> list[RawField]:
    raw_fields = data.get("fields", [])
    if not isinstance(raw_fields, list):
        log.warning("Skipped invalid response: fields must be a list")
        return []

    out: list[RawField] = []
    for i, item in enumerate(raw_fields):
        if not isinstance(item, dict):
            log.warning("Skipped invalid field[%d]: not a dict", i)
            continue
        name = (item.get("name") or "").strip()
        if not name:
            log.warning("Skipped invalid field[%d]: empty name", i)
            continue

        value = item.get("value")
        if value == "" or value == "null":
            value = None
        elif value is not None and not isinstance(value, str):
            value = str(value)

        out.append(
            RawField(
                name=name,
                value=value,
                unit=_coalesce_str(item.get("unit")),
                section=_coalesce_str(item.get("section")),
                context=_coalesce_str(item.get("context")),
                label_line_id=_coalesce_int(item.get("label_line_id")),
                value_line_id=_coalesce_int(item.get("value_line_id")),
                label_quote=_coalesce_str(item.get("label_quote")),
                value_quote=_coalesce_str(item.get("value_quote")),
            )
        )
    return out
