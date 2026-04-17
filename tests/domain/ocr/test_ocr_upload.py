"""Testy pro domain/ocr/ocr_upload.py — OcrUpload entita."""

from __future__ import annotations

import pytest

from domain.ocr.ocr_upload import OcrUpload, StavUploadu
from domain.shared.errors import ValidationError


def _make_upload(**kwargs) -> OcrUpload:
    defaults = {
        "file_path": "/tmp/test.pdf",
        "file_name": "test.pdf",
        "file_hash": "abc123",
        "mime_type": "application/pdf",
    }
    defaults.update(kwargs)
    return OcrUpload(**defaults)


def test_create_basic():
    u = _make_upload()
    assert u.stav == StavUploadu.NAHRANY
    assert u.file_name == "test.pdf"


def test_create_jpeg():
    u = _make_upload(mime_type="image/jpeg", file_name="foto.jpg")
    assert u.mime_type == "image/jpeg"


def test_create_invalid_mime_raises():
    with pytest.raises(ValidationError, match="Nepodporovaný"):
        _make_upload(mime_type="text/plain")


def test_create_empty_filename_raises():
    with pytest.raises(ValidationError, match="Název souboru"):
        _make_upload(file_name="")


def test_zpracuj():
    u = _make_upload()
    u.zpracuj(
        ocr_text="Faktura číslo 123",
        ocr_method="pdf_text",
        ocr_confidence=100,
        parsed_data={"typ_dokladu": "fp"},
    )
    assert u.stav == StavUploadu.ZPRACOVANY
    assert u.ocr_text == "Faktura číslo 123"
    assert u.ocr_confidence == 100


def test_zpracuj_wrong_state_raises():
    u = _make_upload()
    u.zpracuj("text", "pdf_text", 100, None)
    with pytest.raises(ValidationError, match="Nelze zpracovat"):
        u.zpracuj("text2", "tesseract", 50, None)


def test_schval():
    u = _make_upload()
    u.zpracuj("text", "pdf_text", 100, None)
    u.schval(doklad_id=42)
    assert u.stav == StavUploadu.SCHVALENY
    assert u.vytvoreny_doklad_id == 42


def test_schval_wrong_state_raises():
    u = _make_upload()
    with pytest.raises(ValidationError, match="Nelze schválit"):
        u.schval(42)


def test_zamitni():
    u = _make_upload()
    u.zpracuj("text", "pdf_text", 100, None)
    u.zamitni()
    assert u.stav == StavUploadu.ZAMITNUTY


def test_zamitni_from_nahrany():
    u = _make_upload()
    u.zamitni()
    assert u.stav == StavUploadu.ZAMITNUTY


def test_zamitni_already_schvaleny_raises():
    u = _make_upload()
    u.zpracuj("text", "pdf_text", 100, None)
    u.schval(42)
    with pytest.raises(ValidationError, match="Nelze zamítnout"):
        u.zamitni()


def test_oznac_chybu():
    u = _make_upload()
    u.oznac_chybu("OCR selhalo")
    assert u.stav == StavUploadu.ZPRACOVANY
    assert u.error == "OCR selhalo"
    assert u.ocr_method == "failed"
    assert u.ocr_confidence == 0
