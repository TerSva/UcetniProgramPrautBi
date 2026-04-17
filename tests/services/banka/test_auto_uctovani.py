"""Testy pro AutoUctovaniBankyCommand."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from domain.banka.bankovni_transakce import BankovniTransakce, StavTransakce
from domain.banka.bankovni_ucet import BankovniUcet, FormatCsv
from domain.banka.bankovni_vypis import BankovniVypis
from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.money import Money
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.banka_repository import (
    SqliteBankovniTransakceRepository,
    SqliteBankovniUcetRepository,
    SqliteBankovniVypisRepository,
)
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.banka.auto_uctovani import AutoUctovaniBankyCommand


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
def setup_data(db_factory):
    """Vytvoří účet, BV doklad, výpis a transakce."""
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        # Účet
        ucet_repo = SqliteBankovniUcetRepository(uow)
        ucet_id = ucet_repo.add(BankovniUcet(
            nazev="Money Banka",
            cislo_uctu="670100-2213456789/6210",
            ucet_kod="221.001",
            format_csv=FormatCsv.MONEY_BANKA,
        ))

        # BV doklad
        doklady_repo = SqliteDokladyRepository(uow)
        bv_doklad = doklady_repo.add(Doklad(
            cislo="BV-2025-03",
            typ=TypDokladu.BANKOVNI_VYPIS,
            datum_vystaveni=date(2025, 3, 1),
            castka_celkem=Money(27000),
        ))

        # Výpis
        vypis_repo = SqliteBankovniVypisRepository(uow)
        vypis_id = vypis_repo.add(BankovniVypis(
            bankovni_ucet_id=ucet_id,
            rok=2025,
            mesic=3,
            pocatecni_stav=Money(10000000),
            konecny_stav=Money(12350050),
            pdf_path="/uploads/banka/test.pdf",
            bv_doklad_id=bv_doklad.id,
        ))

        # Transakce
        tx_repo = SqliteBankovniTransakceRepository(uow)
        tx_repo.add(BankovniTransakce(
            bankovni_vypis_id=vypis_id,
            datum_transakce=date(2025, 3, 15),
            datum_zauctovani=date(2025, 3, 15),
            castka=Money(-15000),
            smer="V",
            popis="Poplatek za vedení účtu",
            row_hash="hash_poplatek",
        ))
        tx_repo.add(BankovniTransakce(
            bankovni_vypis_id=vypis_id,
            datum_transakce=date(2025, 3, 16),
            datum_zauctovani=date(2025, 3, 16),
            castka=Money(500),
            smer="P",
            popis="Úrok připsaný",
            row_hash="hash_urok",
        ))
        tx_repo.add(BankovniTransakce(
            bankovni_vypis_id=vypis_id,
            datum_transakce=date(2025, 3, 17),
            datum_zauctovani=date(2025, 3, 17),
            castka=Money(-7500),
            smer="V",
            popis="Daň z úroků",
            row_hash="hash_dan",
        ))
        tx_repo.add(BankovniTransakce(
            bankovni_vypis_id=vypis_id,
            datum_transakce=date(2025, 3, 18),
            datum_zauctovani=date(2025, 3, 18),
            castka=Money(-5000),
            smer="V",
            popis="Převod na spořicí účet",
            row_hash="hash_prevod",
        ))

        uow.commit()
    return {"vypis_id": vypis_id, "ucet_id": ucet_id}


class TestAutoUctovaniBankyCommand:

    def test_auto_zauctovani_fees_and_interest(self, db_factory, setup_data):
        cmd = AutoUctovaniBankyCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(setup_data["vypis_id"])

        # Poplatek + Úrok + Daň = 3 auto-zaúčtováno, Převod = 1 přeskočeno
        assert result.pocet_zauctovano == 3
        assert result.pocet_preskoceno == 1

    def test_already_processed_not_reprocessed(self, db_factory, setup_data):
        cmd = AutoUctovaniBankyCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        r1 = cmd.execute(setup_data["vypis_id"])
        assert r1.pocet_zauctovano == 3

        r2 = cmd.execute(setup_data["vypis_id"])
        # Second run: only the 1 unmatched tx remains
        assert r2.pocet_zauctovano == 0
        assert r2.pocet_preskoceno == 1

    def test_nonexistent_vypis(self, db_factory):
        cmd = AutoUctovaniBankyCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(9999)
        assert result.chyby
        assert "nenalezen" in result.chyby[0].lower()
