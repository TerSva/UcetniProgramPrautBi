"""Integrační testy pro migrate_ocr_uploads_to_prilohy skript."""

from datetime import date, datetime
from pathlib import Path

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.ocr.ocr_upload import OcrUpload, StavUploadu
from domain.shared.money import Money
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ocr_upload_repository import (
    SqliteOcrUploadRepository,
)
from infrastructure.database.repositories.priloha_repository import (
    SqlitePrilohaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from infrastructure.storage.priloha_storage import PrilohaStorage

MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent
    / "infrastructure"
    / "database"
    / "migrations"
    / "sql"
)


@pytest.fixture
def setup(tmp_path):
    """Připraví DB, OCR inbox a 3 uploady."""
    db_path = tmp_path / "test.db"
    factory = ConnectionFactory(db_path)
    runner = MigrationRunner(factory, MIGRATIONS_SQL_DIR)
    runner.migrate()

    ocr_inbox = tmp_path / "ocr_inbox"
    ocr_inbox.mkdir()
    doklady_root = tmp_path / "doklady"

    # Vytvoř 2 doklady + 2 OCR uploady s vazbou + 1 upload bez dokladu
    uow = SqliteUnitOfWork(factory)
    with uow:
        drepo = SqliteDokladyRepository(uow)
        orepo = SqliteOcrUploadRepository(uow)

        d1 = drepo.add(Doklad(
            cislo="FP-2025-0001",
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2025, 1, 15),
            castka_celkem=Money(100_00),
        ))
        d2 = drepo.add(Doklad(
            cislo="FP-2025-0002",
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2025, 2, 20),
            castka_celkem=Money(200_00),
        ))

        # Upload 1 — s dokladem
        u1 = OcrUpload(
            file_path=str(ocr_inbox / "hash1.pdf"),
            file_name="faktura1.pdf",
            file_hash="hash1",
            mime_type="application/pdf",
            stav=StavUploadu.SCHVALENY,
            vytvoreny_doklad_id=d1.id,
        )
        orepo.add(u1)
        (ocr_inbox / "hash1.pdf").write_bytes(b"%PDF content 1")

        # Upload 2 — s dokladem
        u2 = OcrUpload(
            file_path=str(ocr_inbox / "hash2.pdf"),
            file_name="RCH0002:25.pdf",
            file_hash="hash2",
            mime_type="application/pdf",
            stav=StavUploadu.SCHVALENY,
            vytvoreny_doklad_id=d2.id,
        )
        orepo.add(u2)
        (ocr_inbox / "hash2.pdf").write_bytes(b"%PDF content 2")

        # Upload 3 — bez dokladu (neměl by se migrovat)
        u3 = OcrUpload(
            file_path=str(ocr_inbox / "hash3.pdf"),
            file_name="nezpracovany.pdf",
            file_hash="hash3",
            mime_type="application/pdf",
            stav=StavUploadu.NAHRANY,
        )
        orepo.add(u3)
        (ocr_inbox / "hash3.pdf").write_bytes(b"%PDF content 3")

        uow.commit()

    return {
        "factory": factory,
        "ocr_inbox": ocr_inbox,
        "doklady_root": doklady_root,
        "d1_id": d1.id,
        "d2_id": d2.id,
    }


def _run_migration(factory, ocr_inbox, doklady_root):
    """Simuluje logiku migračního skriptu."""
    storage = PrilohaStorage(root=doklady_root)

    uow = SqliteUnitOfWork(factory)
    with uow:
        ocr_repo = SqliteOcrUploadRepository(uow)
        drepo = SqliteDokladyRepository(uow)
        prepo = SqlitePrilohaRepository(uow)

        uploads = ocr_repo.list_with_created_doklad()
        for upload in uploads:
            doklad = drepo.get_by_id(upload.vytvoreny_doklad_id)
            existing = prepo.list_by_doklad(doklad.id)
            if existing:
                continue

            source = ocr_inbox / f"{upload.file_hash}.pdf"
            if not source.exists():
                continue

            rel_path, size = storage.save(
                source,
                doklad_typ=doklad.typ.value,
                doklad_cislo=doklad.cislo,
                original_name=upload.file_name,
                rok=doklad.datum_vystaveni.year,
            )

            from domain.doklady.priloha import PrilohaDokladu

            priloha = PrilohaDokladu(
                id=None,
                doklad_id=doklad.id,
                nazev_souboru=upload.file_name,
                relativni_cesta=rel_path,
                velikost_bytes=size,
                mime_type="application/pdf",
                vytvoreno=datetime.now(),
            )
            prepo.add(priloha)

        uow.commit()


class TestMigrateOcrUploads:
    """Migrace OCR uploadů → přílohy dokladů."""

    def test_migrates_two_uploads(self, setup):
        _run_migration(
            setup["factory"], setup["ocr_inbox"], setup["doklady_root"],
        )

        uow = SqliteUnitOfWork(setup["factory"])
        with uow:
            prepo = SqlitePrilohaRepository(uow)
            p1 = prepo.list_by_doklad(setup["d1_id"])
            p2 = prepo.list_by_doklad(setup["d2_id"])
            assert len(p1) == 1
            assert len(p2) == 1
            assert p1[0].nazev_souboru == "faktura1.pdf"
            assert p2[0].nazev_souboru == "RCH0002:25.pdf"
            uow.commit()

    def test_files_on_disk(self, setup):
        _run_migration(
            setup["factory"], setup["ocr_inbox"], setup["doklady_root"],
        )

        uow = SqliteUnitOfWork(setup["factory"])
        with uow:
            prepo = SqlitePrilohaRepository(uow)
            prilohy = prepo.list_by_doklad(setup["d1_id"])
            full = setup["doklady_root"].parent / prilohy[0].relativni_cesta
            assert full.exists()
            uow.commit()

    def test_sanitized_filename_on_disk(self, setup):
        _run_migration(
            setup["factory"], setup["ocr_inbox"], setup["doklady_root"],
        )

        uow = SqliteUnitOfWork(setup["factory"])
        with uow:
            prepo = SqlitePrilohaRepository(uow)
            prilohy = prepo.list_by_doklad(setup["d2_id"])
            # Fyzická cesta má sanitizovaný název
            assert "RCH0002_25.pdf" in prilohy[0].relativni_cesta
            # DB má originální název
            assert prilohy[0].nazev_souboru == "RCH0002:25.pdf"
            uow.commit()

    def test_idempotent_second_run(self, setup):
        _run_migration(
            setup["factory"], setup["ocr_inbox"], setup["doklady_root"],
        )
        _run_migration(
            setup["factory"], setup["ocr_inbox"], setup["doklady_root"],
        )

        uow = SqliteUnitOfWork(setup["factory"])
        with uow:
            prepo = SqlitePrilohaRepository(uow)
            p1 = prepo.list_by_doklad(setup["d1_id"])
            p2 = prepo.list_by_doklad(setup["d2_id"])
            # Stále jen 1 příloha na doklad, ne 2
            assert len(p1) == 1
            assert len(p2) == 1
            uow.commit()

    def test_upload_without_doklad_not_migrated(self, setup):
        _run_migration(
            setup["factory"], setup["ocr_inbox"], setup["doklady_root"],
        )

        uow = SqliteUnitOfWork(setup["factory"])
        with uow:
            prepo = SqlitePrilohaRepository(uow)
            # Upload 3 nemá doklad, takže celkem jen 2 přílohy
            conn = uow.connection
            count = conn.execute(
                "SELECT COUNT(*) FROM prilohy_dokladu"
            ).fetchone()[0]
            assert count == 2
            uow.commit()
