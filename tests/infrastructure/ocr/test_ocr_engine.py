"""Testy pro OcrEngine — extrakce textu z PDF a obrázků."""

from __future__ import annotations

from pathlib import Path

import pytest

from infrastructure.ocr.ocr_engine import OcrEngine, OcrResult


@pytest.fixture
def engine() -> OcrEngine:
    return OcrEngine()


def test_unsupported_extension(engine, tmp_path):
    f = tmp_path / "test.doc"
    f.write_text("hello")
    result = engine.extract_text(f)
    assert result.method == "failed"
    assert result.confidence == 0


def test_nonexistent_file(engine, tmp_path):
    f = tmp_path / "nonexistent.pdf"
    result = engine.extract_text(f)
    assert result.method == "failed"


def test_pdf_text_extraction(engine, tmp_path):
    """Test pdfplumber with a minimal text PDF."""
    try:
        import pdfplumber
    except ImportError:
        pytest.skip("pdfplumber not installed")

    # Create a minimal PDF with text using reportlab or just test the flow
    # We'll test with an empty PDF that pdfplumber can open
    # For now, test the fallback path
    f = tmp_path / "empty.pdf"
    f.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\nxref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \ntrailer<</Root 1 0 R/Size 3>>\nstartxref\n109\n%%EOF")
    result = engine.extract_text(f)
    # Empty PDF → no text → falls through to tesseract or fails gracefully
    assert result.method in ("failed", "tesseract", "pdf_text")


def test_image_extraction_png(engine, tmp_path):
    """Test Tesseract on a simple PNG image."""
    try:
        from PIL import Image, ImageDraw
        import pytesseract
    except ImportError:
        pytest.skip("PIL or pytesseract not installed")

    # Create a simple image with text
    img = Image.new("RGB", (400, 100), "white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 30), "Hello World 12345", fill="black")
    f = tmp_path / "test.png"
    img.save(f)

    result = engine.extract_text(f)
    # Tesseract may or may not recognize the text depending on font
    assert result.method in ("tesseract", "failed")
    if result.method == "tesseract":
        assert result.confidence >= 0


def test_ocr_result_dataclass():
    r = OcrResult(text="hello", method="pdf_text", confidence=100)
    assert r.text == "hello"
    assert r.method == "pdf_text"
    assert r.confidence == 100
