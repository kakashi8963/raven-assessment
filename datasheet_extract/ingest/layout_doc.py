"""LayoutDoc: words + lines + sections with render() for LLM prompts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from datasheet_extract.ingest.lines import reconstruct_lines
from datasheet_extract.ingest.sections import detect_sections
from datasheet_extract.ingest.words import build_word_index
from datasheet_extract.model import Line, Section, Word


@dataclass
class LayoutDoc:
    source_pdf: str
    words: list[Word]
    lines: list[Line]
    sections: list[Section] = field(default_factory=list)
    word_by_id: dict[int, Word] = field(default_factory=dict)
    line_by_id: dict[int, Line] = field(default_factory=dict)
    section_by_id: dict[int, Section] = field(default_factory=dict)

    @classmethod
    def from_pdf(cls, pdf_path: str | Path) -> LayoutDoc:
        path = Path(pdf_path)
        words = build_word_index(path)
        lines = reconstruct_lines(words)
        sections = detect_sections(words, lines)

        doc = cls(
            source_pdf=path.name,
            words=words,
            lines=lines,
            sections=sections,
        )
        doc.word_by_id = {w.id: w for w in words}
        doc.line_by_id = {l.id: l for l in lines}
        doc.section_by_id = {s.id: s for s in sections}
        return doc

    def render(
        self,
        *,
        section_id: int | None = None,
        page: int | None = None,
        line_ids: set[int] | None = None,
    ) -> str:
        """Render lines as L<id> | text with [SECTION] markers."""
        lines_out: list[str] = []
        current_section: int | None = None

        target_lines = self.lines
        if section_id is not None:
            sec = self.section_by_id.get(section_id)
            if sec:
                target_ids = set(sec.line_ids)
                target_lines = [l for l in self.lines if l.id in target_ids]
        if page is not None:
            target_lines = [l for l in target_lines if l.page == page]
        if line_ids is not None:
            target_lines = [l for l in target_lines if l.id in line_ids]

        for line in target_lines:
            if line.section_id is not None and line.section_id != current_section:
                current_section = line.section_id
                sec = self.section_by_id.get(current_section)
                if sec:
                    lines_out.append(f"[SECTION] {sec.name}")
            lines_out.append(f"L{line.id} | {line.text}")

        return "\n".join(lines_out)

    def page_numbers(self) -> list[int]:
        return sorted({l.page for l in self.lines})

    def sections_on_page(self, page: int) -> list[Section]:
        """Merged sections that have at least one line on this page."""
        page_line_ids = {l.id for l in self.lines if l.page == page}
        out: list[Section] = []
        for sec in self.sections:
            if any(lid in page_line_ids for lid in sec.line_ids):
                out.append(sec)
        return out

    def lines_on_page(self, page: int) -> list[Line]:
        return [l for l in self.lines if l.page == page]

    def section_for_line(self, line_id: int | None) -> Section | None:
        if line_id is None:
            return None
        line = self.line_by_id.get(line_id)
        if line is None or line.section_id is None:
            return None
        return self.section_by_id.get(line.section_id)
