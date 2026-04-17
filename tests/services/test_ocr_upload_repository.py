"""Testy pro OcrUploadRepository."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.ocr.ocr_upload import OcrUpload, StavUploadu
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.ocr_upload_repository import (
    SqliteOcrUploadRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork


MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent
    / "infrastructure" / "database" / "migrations" / "sql"
)


@pytest.fixture
def factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    f = ConnectionFactory(db_path)
    MigrationRunner(f, MIGRATIONS_SQL_DIR).migrate()
    return f


def _make_upload(file_hash: str = "abc123") -> OcrUpload:
    return OcrUpload(
        file_path="/tmp/test.pdf",
        file_name="test.pdf",
        file_hash=file_hash,
        mime_type="application/pdf",
    )


def test_add_and_get(factory):
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteOcrUploadRepository(uow)
        upload = _make_upload()
        repo.add(upload)
        uow.commit()

    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        repo2 = SqliteOcrUploadRepository(uow2)
        loaded = repo2.get(upload.id)

    assert loaded is not None
    assert loaded.file_name == "test.pdf"
    assert loaded.stav == StavUploadu.NAHRANY


def test_get_by_hash(factory):
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteOcrUploadRepository(uow)
        repo.add(_make_upload("hash1"))
        repo.add(_make_upload("hash2"))
        uow.commit()

    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        repo2 = SqliteOcrUploadRepository(uow2)
        found = repo2.get_by_hash("hash2")

    assert found is not None
    assert found.file_hash == "hash2"


def test_update(factory):
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteOcrUploadRepository(uow)
        upload = _make_upload()
        repo.add(upload)
        uow.commit()

    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        repo2 = SqliteOcrUploadRepository(uow2)
        loaded = repo2.get(upload.id)
        loaded.zpracuj("Text OCR", "pdf_text", 95, {"typ": "fp"})
        repo2.update(loaded)
        uow2.commit()

    uow3 = SqliteUnitOfWork(factory)
    with uow3:
        repo3 = SqliteOcrUploadRepository(uow3)
        reloaded = repo3.get(upload.id)

    assert reloaded.stav == StavUploadu.ZPRACOVANY
    assert reloaded.ocr_text == "Text OCR"
    assert reloaded.parsed_data == {"typ": "fp"}


def test_list_by_stav(factory):
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteOcrUploadRepository(uow)
        u1 = _make_upload("h1")
        repo.add(u1)
        u2 = _make_upload("h2")
        u2.zpracuj("text", "pdf_text", 100, None)
        u2.stav = StavUploadu.ZPRACOVANY
        repo.add(u2)
        uow.commit()

    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        repo2 = SqliteOcrUploadRepository(uow2)
        nahrany = repo2.list_by_stav(StavUploadu.NAHRANY)
        zpracovany = repo2.list_by_stav(StavUploadu.ZPRACOVANY)
        all_items = repo2.list_by_stav()

    assert len(nahrany) == 1
    assert len(zpracovany) == 1
    assert len(all_items) == 2


def test_count_by_stav(factory):
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteOcrUploadRepository(uow)
        repo.add(_make_upload("h1"))
        repo.add(_make_upload("h2"))
        uow.commit()

    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        repo2 = SqliteOcrUploadRepository(uow2)
        assert repo2.count_by_stav(StavUploadu.NAHRANY) == 2
        assert repo2.count_by_stav(StavUploadu.ZPRACOVANY) == 0


def test_delete(factory):
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteOcrUploadRepository(uow)
        upload = _make_upload()
        repo.add(upload)
        uow.commit()

    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        repo2 = SqliteOcrUploadRepository(uow2)
        repo2.delete(upload.id)
        uow2.commit()

    uow3 = SqliteUnitOfWork(factory)
    with uow3:
        repo3 = SqliteOcrUploadRepository(uow3)
        assert repo3.get(upload.id) is None
