"""OCR fallback tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from datasheet_extract.ingest.words import build_word_index

ROOT = Path(__file__).resolve().parent.parent
P600173 = ROOT / "pds-P600173.pdf"


@pytest.mark.skipif(not P600173.exists(), reason="pds-P600173.pdf not present")
@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract binary not installed")
def test_ocr_fallback_p600173():
    words = build_word_index(P600173)
    assert len(words) > 100
    assert all(w.conf <= 1.0 for w in words)
    pages = {w.page for w in words}
    assert pages == {0, 1}
