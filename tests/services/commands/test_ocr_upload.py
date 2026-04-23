"""Testy pro OcrUploadCommand."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from domain.doklady.typy import TypDokladu
from domain.ocr.ocr_upload import StavUploadu
from domain.shared.money import Money
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.ocr_upload_repository import (
    SqliteOcrUploadRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from infrastructure.ocr.invoice_parser import InvoiceParser, ParsedInvoice
from infrastructure.ocr.ocr_engine import OcrEngine, OcrResult
from services.commands.ocr_upload import OcrUploadCommand


MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "infrastructure" / "database" / "migrations" / "sql"
)


@pytest.fixture
def factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    f = ConnectionFactory(db_path)
    MigrationRunner(f, MIGRATIONS_SQL_DIR).migrate()
    return f


@pytest.fixture
def mock_engine() -> OcrEngine:
    engine = MagicMock(spec=OcrEngine)
    engine.extract_text.return_value = OcrResult(
        text="Meta Platforms Ireland Limited\nFBADS-404-12345\nTotal: 44,00 CZK\n23.04.2025",
        method="pdf_text",
        confidence=100,
    )
    return engine


@pytest.fixture
def cmd(factory, tmp_path, mock_engine) -> OcrUploadCommand:
    return OcrUploadCommand(
        uow_factory=lambda: SqliteUnitOfWork(factory),
        upload_dir=tmp_path / "uploads",
        ocr_engine=mock_engine,
    )


@pytest.fixture
def sample_pdf(tmp_path) -> Path:
    f = tmp_path / "test_invoice.pdf"
    f.write_bytes(b"%PDF-1.4 test content for hashing")
    return f


def test_upload_file(cmd, sample_pdf, factory):
    upload_id, is_dup = cmd.upload_file(sample_pdf)
    assert upload_id is not None
    assert is_dup is False

    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteOcrUploadRepository(uow)
        upload = repo.get(upload_id)

    assert upload is not None
    assert upload.file_name == "test_invoice.pdf"
    assert upload.stav == StavUploadu.NAHRANY


def test_upload_duplicate_returns_same_id(cmd, sample_pdf):
    id1, dup1 = cmd.upload_file(sample_pdf)
    id2, dup2 = cmd.upload_file(sample_pdf)
    assert id1 == id2
    assert dup1 is False
    assert dup2 is True


def test_process_ocr(cmd, sample_pdf, factory):
    upload_id, _ = cmd.upload_file(sample_pdf)
    cmd.process_ocr(upload_id)

    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteOcrUploadRepository(uow)
        upload = repo.get(upload_id)

    assert upload.stav == StavUploadu.ZPRACOVANY
    assert upload.ocr_method == "pdf_text"
    assert upload.parsed_data is not None
    assert upload.parsed_data.get("dodavatel_nazev") == "Meta Platforms Ireland Limited"


def test_upload_and_process(cmd, sample_pdf, factory):
    upload_id, status = cmd.upload_and_process(sample_pdf)
    assert status == "new"

    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteOcrUploadRepository(uow)
        upload = repo.get(upload_id)

    assert upload.stav == StavUploadu.ZPRACOVANY


def test_upload_and_process_duplicate_zpracovany(cmd, sample_pdf):
    """Opakovaný upload zpracovaného souboru vrátí 'duplicate'."""
    _id1, s1 = cmd.upload_and_process(sample_pdf)
    _id2, s2 = cmd.upload_and_process(sample_pdf)
    assert s1 == "new"
    assert s2 == "duplicate"
    assert _id1 == _id2


def test_upload_and_process_requeued_after_reject(cmd, sample_pdf, factory):
    """Zamítnutý soubor se po opětovném nahrání znovu zpracuje."""
    upload_id, _ = cmd.upload_and_process(sample_pdf)
    cmd.reject(upload_id)

    # Ověř stav ZAMITNUTY
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteOcrUploadRepository(uow)
        upload = repo.get(upload_id)
    assert upload.stav == StavUploadu.ZAMITNUTY

    # Znovu nahraj → měl by se resetovat a zpracovat
    id2, status = cmd.upload_and_process(sample_pdf)
    assert id2 == upload_id
    assert status == "requeued"

    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteOcrUploadRepository(uow)
        upload = repo.get(id2)
    assert upload.stav == StavUploadu.ZPRACOVANY


def test_approve(cmd, sample_pdf, factory):
    upload_id, _ = cmd.upload_and_process(sample_pdf)

    doklad_id = cmd.approve(
        upload_id=upload_id,
        typ=TypDokladu.FAKTURA_PRIJATA,
        cislo="FP-2025-OCR-001",
        datum_vystaveni=date(2025, 4, 23),
        castka_celkem=Money(4400),
        popis="Meta reklamy",
    )
    assert doklad_id is not None

    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteOcrUploadRepository(uow)
        upload = repo.get(upload_id)

    assert upload.stav == StavUploadu.SCHVALENY
    assert upload.vytvoreny_doklad_id == doklad_id


def test_upload_and_process_approved_returns_status(cmd, sample_pdf, factory):
    """Schválený soubor po opětovném nahrání vrátí 'approved'."""
    upload_id, _ = cmd.upload_and_process(sample_pdf)
    cmd.approve(
        upload_id=upload_id,
        typ=TypDokladu.FAKTURA_PRIJATA,
        cislo="FP-2025-DUP-001",
        datum_vystaveni=date(2025, 4, 23),
        castka_celkem=Money(1000),
    )
    _id2, status = cmd.upload_and_process(sample_pdf)
    assert status == "approved"


def test_reject(cmd, sample_pdf, factory):
    upload_id, _ = cmd.upload_and_process(sample_pdf)
    cmd.reject(upload_id)

    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteOcrUploadRepository(uow)
        upload = repo.get(upload_id)

    assert upload.stav == StavUploadu.ZAMITNUTY


def test_batch_approve(cmd, tmp_path, factory):
    # Create 3 different PDFs
    ids = []
    for i in range(3):
        f = tmp_path / f"invoice_{i}.pdf"
        f.write_bytes(f"%PDF-1.4 content {i}".encode())
        uid, _status = cmd.upload_and_process(f)
        ids.append(uid)

    doklad_ids = cmd.batch_approve(
        upload_ids=ids,
        typ=TypDokladu.FAKTURA_PRIJATA,
        cislo_prefix="FP-2025-BATCH",
        datum_vystaveni=date(2025, 4, 23),
        popis_prefix="Meta batch",
    )
    assert len(doklad_ids) == 3

    # Verify all uploads are SCHVALENY
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteOcrUploadRepository(uow)
        for uid in ids:
            upload = repo.get(uid)
            assert upload.stav == StavUploadu.SCHVALENY
