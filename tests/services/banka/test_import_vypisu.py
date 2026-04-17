"""Testy pro ImportVypisuCommand."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from domain.banka.bankovni_ucet import BankovniUcet, FormatCsv
from domain.shared.money import Money
from infrastructure.banka.csv_parser import ParsedTransaction
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.banka_repository import (
    SqliteBankovniUcetRepository,
    SqliteBankovniVypisRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.banka.import_vypisu import ImportVypisuCommand


@pytest.fixture
def db_factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    factory = ConnectionFactory(db_path)
    migrations_dir = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "infrastructure"
        / "database"
        / "migrations"
        / "sql"
    )
    runner = MigrationRunner(factory, migrations_dir)
    runner.migrate()
    return factory


@pytest.fixture
def ucet_id(db_factory) -> int:
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteBankovniUcetRepository(uow)
        uid = repo.add(BankovniUcet(
            nazev="Money Banka",
            cislo_uctu="670100-2213456789/6210",
            ucet_kod="221.001",
            format_csv=FormatCsv.MONEY_BANKA,
        ))
        uow.commit()
    return uid


def _make_tx(datum, castka_hal, vs=None, popis=None) -> ParsedTransaction:
    return ParsedTransaction(
        datum_transakce=datum,
        datum_zauctovani=datum,
        castka=Money(castka_hal),
        smer="P" if castka_hal > 0 else "V",
        variabilni_symbol=vs,
        konstantni_symbol=None,
        specificky_symbol=None,
        protiucet=None,
        popis=popis,
        row_hash=f"hash_{datum}_{castka_hal}_{vs}",
    )


class TestImportVypisuCommand:

    def test_import_success(self, db_factory, ucet_id, tmp_path):
        upload_dir = tmp_path / "uploads"
        csv_path = tmp_path / "test.csv"
        pdf_path = tmp_path / "test.pdf"
        csv_path.write_text("test csv content")
        pdf_path.write_text("test pdf content")

        cmd = ImportVypisuCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
            upload_dir=upload_dir,
        )

        txs = [
            _make_tx(date(2025, 3, 15), -150000, popis="Poplatek za vedení"),
            _make_tx(date(2025, 3, 16), 2500050, vs="1234567890"),
        ]

        result = cmd.execute(
            csv_path=csv_path,
            pdf_path=pdf_path,
            ucet_id=ucet_id,
            matched_transactions=txs,
            ps=Money(10000000),
            ks=Money(12350050),
        )

        assert result.success
        assert result.pocet_transakci == 2
        assert result.doklad_cislo == "BV-2025-03"
        assert result.vypis_id is not None

    def test_empty_transactions_fails(self, db_factory, ucet_id, tmp_path):
        cmd = ImportVypisuCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
            upload_dir=tmp_path / "uploads",
        )
        result = cmd.execute(
            csv_path=tmp_path / "x.csv",
            pdf_path=tmp_path / "x.pdf",
            ucet_id=ucet_id,
            matched_transactions=[],
            ps=Money(0),
            ks=Money(0),
        )
        assert not result.success
        assert "Žádné" in result.error

    def test_duplicate_import_fails(self, db_factory, ucet_id, tmp_path):
        upload_dir = tmp_path / "uploads"
        csv_path = tmp_path / "test.csv"
        pdf_path = tmp_path / "test.pdf"
        csv_path.write_text("test csv content")
        pdf_path.write_text("test pdf content")

        cmd = ImportVypisuCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
            upload_dir=upload_dir,
        )

        txs = [_make_tx(date(2025, 3, 15), -10000)]
        kwargs = dict(
            csv_path=csv_path,
            pdf_path=pdf_path,
            ucet_id=ucet_id,
            matched_transactions=txs,
            ps=Money(0),
            ks=Money(0),
        )

        r1 = cmd.execute(**kwargs)
        assert r1.success

        # Different hash for second attempt
        txs2 = [_make_tx(date(2025, 3, 15), -20000)]
        kwargs["matched_transactions"] = txs2
        r2 = cmd.execute(**kwargs)
        assert not r2.success
        assert "již existuje" in r2.error

    def test_pdf_copied_to_upload_dir(self, db_factory, ucet_id, tmp_path):
        upload_dir = tmp_path / "uploads"
        csv_path = tmp_path / "test.csv"
        pdf_path = tmp_path / "test.pdf"
        csv_path.write_text("csv content")
        pdf_path.write_text("pdf content")

        cmd = ImportVypisuCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
            upload_dir=upload_dir,
        )

        txs = [_make_tx(date(2025, 1, 10), 50000)]
        cmd.execute(
            csv_path=csv_path,
            pdf_path=pdf_path,
            ucet_id=ucet_id,
            matched_transactions=txs,
            ps=Money(0),
            ks=Money(50000),
        )

        assert (upload_dir / "221.001_2025_01.pdf").exists()
        assert (upload_dir / "221.001_2025_01.csv").exists()
