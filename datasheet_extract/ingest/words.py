"""Build word index from PDF — PyMuPDF text layer, Tesseract OCR if a page has none."""

from __future__ import annotations

import io
import logging
from pathlib import Path

from datasheet_extract.config import OCR_DPI, OCR_LANG, OCR_MIN_WORDS_PER_PAGE
from datasheet_extract.model import Word

log = logging.getLogger(__name__)


def build_word_index(pdf_path: str | Path) -> list[Word]:
    import fitz

    path = Path(pdf_path)
    doc = fitz.open(path)
    words: list[Word] = []
    wid = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        font_map = _font_map_from_dict(page)
        raw = page.get_text("words")
        page_words: list[Word] = []

        for w in raw:
            x0, top, x1, bottom, text = w[0], w[1], w[2], w[3], w[4]
            if not text.strip():
                continue
            size, bold = font_map.get((round(x0, 1), round(top, 1)), (0.0, False))
            page_words.append(
                Word(
                    id=wid,
                    page=page_num,
                    text=text,
                    x0=x0,
                    top=top,
                    x1=x1,
                    bottom=bottom,
                    size=size,
                    bold=bold,
                    conf=1.0,
                )
            )
            wid += 1

        if len(page_words) < OCR_MIN_WORDS_PER_PAGE:
            log.info(
                "Page %d has %d words (< %d) — using OCR",
                page_num,
                len(page_words),
                OCR_MIN_WORDS_PER_PAGE,
            )
            ocr_words = _ocr_page(page, page_num, wid)
            if ocr_words:
                words.extend(ocr_words)
                wid += len(ocr_words)
            elif page_words:
                words.extend(page_words)
        else:
            words.extend(page_words)

    doc.close()
    return words


def _font_map_from_dict(page) -> dict[tuple[float, float], tuple[float, bool]]:
    """Map approximate word origin to (font_size, bold) from get_text('dict')."""
    result: dict[tuple[float, float], tuple[float, bool]] = {}
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text.strip():
                    continue
                bbox = span.get("bbox", (0, 0, 0, 0))
                flags = span.get("flags", 0)
                size = span.get("size", 0.0)
                bold = bool(flags & 2**4)
                key = (round(bbox[0], 1), round(bbox[1], 1))
                result[key] = (size, bold)
    return result


def _ocr_page(page, page_num: int, wid_start: int) -> list[Word]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise RuntimeError(
            "Scanned page detected but pytesseract/Pillow not installed. "
            "Run: pip install pytesseract pillow  (and install the Tesseract binary)"
        ) from e

    pix = page.get_pixmap(dpi=OCR_DPI)
    img = Image.open(io.BytesIO(pix.tobytes("png")))

    try:
        data = pytesseract.image_to_data(img, lang=OCR_LANG, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError as e:
        raise RuntimeError(
            "Scanned page detected but Tesseract binary not found. "
            "Install Tesseract (e.g. brew install tesseract tesseract-lang) and retry."
        ) from e

    pw, ph = page.rect.width, page.rect.height
    sx = pw / pix.width
    sy = ph / pix.height

    words: list[Word] = []
    wid = wid_start
    n = len(data["text"])
    for i in range(n):
        text = (data["text"][i] or "").strip()
        conf_raw = int(data["conf"][i])
        if not text or conf_raw < 0:
            continue
        left = data["left"][i]
        top = data["top"][i]
        width = data["width"][i]
        height = data["height"][i]
        words.append(
            Word(
                id=wid,
                page=page_num,
                text=text,
                x0=left * sx,
                top=top * sy,
                x1=(left + width) * sx,
                bottom=(top + height) * sy,
                size=height * sy,
                bold=False,
                conf=conf_raw / 100.0,
            )
        )
        wid += 1

    log.info("OCR page %d: %d words", page_num, len(words))
    return words
