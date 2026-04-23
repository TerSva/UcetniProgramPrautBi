"""Testy pro SmazatVypisCommand — včetně obnovy stavu dokladů."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from domain.banka.bankovni_transakce import BankovniTransakce, StavTransakce
from domain.banka.bankovni_ucet import BankovniUcet, FormatCsv
from domain.banka.bankovni_vypis import BankovniVypis
from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
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
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.banka.smazat_vypis import SmazatVypisCommand


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
def setup_sparovany_vypis(db_factory):
    """Výpis se spárovanou transakcí → FP je UHRAZENY."""
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        ucet_repo = SqliteBankovniUcetRepository(uow)
        ucet_id = ucet_repo.add(BankovniUcet(
            nazev="Money Banka",
            cislo_uctu="670100-2213456789/6210",
            ucet_kod="221.001",
            format_csv=FormatCsv.MONEY_BANKA,
        ))

        doklady_repo = SqliteDokladyRepository(uow)
        bv_doklad = doklady_repo.add(Doklad(
            cislo="BV-2025-04",
            typ=TypDokladu.BANKOVNI_VYPIS,
            datum_vystaveni=date(2025, 4, 1),
            castka_celkem=Money(300000),
        ))

        # FP doklad — uhrazený
        fp = doklady_repo.add(Doklad(
            cislo="FP-2025-020",
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2025, 4, 5),
            castka_celkem=Money(300000),
            stav=StavDokladu.UHRAZENY,
        ))

        vypis_repo = SqliteBankovniVypisRepository(uow)
        vypis_id = vypis_repo.add(BankovniVypis(
            bankovni_ucet_id=ucet_id,
            rok=2025,
            mesic=4,
            pocatecni_stav=Money(10000000),
            konecny_stav=Money(9700000),
            pdf_path="/tmp/test_smazat.pdf",
            bv_doklad_id=bv_doklad.id,
        ))

        tx_repo = SqliteBankovniTransakceRepository(uow)
        tx_id = tx_repo.add(BankovniTransakce(
            bankovni_vypis_id=vypis_id,
            datum_transakce=date(2025, 4, 10),
            datum_zauctovani=date(2025, 4, 10),
            castka=Money(-300000),
            smer="V",
            popis="Platba dodavateli",
            row_hash="hash_sparovani_test",
            stav=StavTransakce.SPAROVANO,
            sparovany_doklad_id=fp.id,
        ))

        uow.commit()

    return {
        "vypis_id": vypis_id,
        "fp_id": fp.id,
        "bv_doklad_id": bv_doklad.id,
    }


class TestSmazatVypisCommand:

    def test_smazani_obnovi_stav_dokladu(self, db_factory, setup_sparovany_vypis):
        """Smazání výpisu se spárovanou transakcí vrátí doklad na ZAUCTOVANY."""
        cmd = SmazatVypisCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(setup_sparovany_vypis["vypis_id"])

        assert result.success is True
        assert result.obnoveno_dokladu == 1
        assert result.smazano_transakci == 1

        # Ověř, že FP doklad je zpátky na ZAUCTOVANY
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            fp = repo.get_by_id(setup_sparovany_vypis["fp_id"])
            assert fp.stav == StavDokladu.ZAUCTOVANY

    def test_smazani_bez_sparovanych(self, db_factory):
        """Smazání výpisu bez spárovaných transakcí neobnovi nic."""
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            ucet_repo = SqliteBankovniUcetRepository(uow)
            ucet_id = ucet_repo.add(BankovniUcet(
                nazev="Test",
                cislo_uctu="123/0100",
                ucet_kod="221.002",
                format_csv=FormatCsv.MONEY_BANKA,
            ))
            doklady_repo = SqliteDokladyRepository(uow)
            bv = doklady_repo.add(Doklad(
                cislo="BV-2025-99",
                typ=TypDokladu.BANKOVNI_VYPIS,
                datum_vystaveni=date(2025, 1, 1),
                castka_celkem=Money(0),
            ))
            vypis_repo = SqliteBankovniVypisRepository(uow)
            vypis_id = vypis_repo.add(BankovniVypis(
                bankovni_ucet_id=ucet_id,
                rok=2025,
                mesic=1,
                pocatecni_stav=Money(0),
                konecny_stav=Money(0),
                pdf_path="/tmp/test_empty.pdf",
                bv_doklad_id=bv.id,
            ))
            uow.commit()

        cmd = SmazatVypisCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(vypis_id)
        assert result.success is True
        assert result.obnoveno_dokladu == 0

    def test_smazani_neexistujici(self, db_factory):
        cmd = SmazatVypisCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(99999)
        assert result.success is False
