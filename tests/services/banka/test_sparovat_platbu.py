"""Testy pro SparovatPlatbuDoklademCommand."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from domain.banka.bankovni_transakce import BankovniTransakce, StavTransakce
from domain.banka.bankovni_ucet import BankovniUcet, FormatCsv
from domain.banka.bankovni_vypis import BankovniVypis
from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import ValidationError
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
from services.commands.sparovat_platbu_dokladem import (
    SparovatPlatbuDoklademCommand,
)


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
def setup_fp(db_factory):
    """Účet + BV doklad + výpis + nespárovaná transakce + FP doklad."""
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
            cislo="BV-2025-03",
            typ=TypDokladu.BANKOVNI_VYPIS,
            datum_vystaveni=date(2025, 3, 1),
            castka_celkem=Money(500000),
        ))

        fp_doklad = doklady_repo.add(Doklad(
            cislo="FP-2025-001",
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2025, 3, 10),
            castka_celkem=Money(500000),
            stav=StavDokladu.ZAUCTOVANY,
            variabilni_symbol="202500001",
        ))

        vypis_repo = SqliteBankovniVypisRepository(uow)
        vypis_id = vypis_repo.add(BankovniVypis(
            bankovni_ucet_id=ucet_id,
            rok=2025,
            mesic=3,
            pocatecni_stav=Money(10000000),
            konecny_stav=Money(9500000),
            pdf_path="/uploads/banka/test.pdf",
            bv_doklad_id=bv_doklad.id,
        ))

        tx_repo = SqliteBankovniTransakceRepository(uow)
        tx_id = tx_repo.add(BankovniTransakce(
            bankovni_vypis_id=vypis_id,
            datum_transakce=date(2025, 3, 15),
            datum_zauctovani=date(2025, 3, 15),
            castka=Money(-500000),
            smer="V",
            popis="Platba dodavateli",
            variabilni_symbol="202500001",
            row_hash="hash_fp_uhrada",
        ))

        uow.commit()

    return {
        "tx_id": tx_id,
        "fp_id": fp_doklad.id,
        "bv_doklad_id": bv_doklad.id,
        "vypis_id": vypis_id,
    }


class TestSparovatPlatbuDoklademCommand:

    def test_sparovani_fp_success(self, db_factory, setup_fp):
        cmd = SparovatPlatbuDoklademCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(setup_fp["tx_id"], setup_fp["fp_id"])

        assert result.doklad_uhrazen is True
        assert len(result.ucetni_zaznam_ids) == 1
        assert result.kurzovy_rozdil is None

        # Ověř stav transakce
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            tx_repo = SqliteBankovniTransakceRepository(uow)
            tx = tx_repo.get(setup_fp["tx_id"])
            assert tx.stav == StavTransakce.SPAROVANO
            assert tx.sparovany_doklad_id == setup_fp["fp_id"]

        # Ověř stav dokladu
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            doklady_repo = SqliteDokladyRepository(uow)
            dok = doklady_repo.get_by_id(setup_fp["fp_id"])
            assert dok.stav == StavDokladu.UHRAZENY

        # Ověř účetní záznam (MD 321 / Dal 221.001)
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            denik_repo = SqliteUcetniDenikRepository(uow)
            zaznamy = denik_repo.list_by_doklad(setup_fp["bv_doklad_id"])
            assert len(zaznamy) == 1
            z = zaznamy[0]
            assert z.md_ucet == "321"
            assert z.dal_ucet == "221.001"
            assert z.castka == Money(500000)

    def test_sparovani_uz_sparovane_rejects(self, db_factory, setup_fp):
        cmd = SparovatPlatbuDoklademCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        # First match succeeds
        cmd.execute(setup_fp["tx_id"], setup_fp["fp_id"])

        # Second attempt fails
        with pytest.raises(ValidationError, match="stavu"):
            cmd.execute(setup_fp["tx_id"], setup_fp["fp_id"])

    def test_sparovani_novy_doklad_rejects(self, db_factory, setup_fp):
        """Nelze spárovat s NOVY dokladem."""
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            doklady_repo = SqliteDokladyRepository(uow)
            novy = doklady_repo.add(Doklad(
                cislo="FP-2025-999",
                typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2025, 3, 10),
                castka_celkem=Money(100000),
                stav=StavDokladu.NOVY,
            ))
            uow.commit()

        cmd = SparovatPlatbuDoklademCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        with pytest.raises(ValidationError, match="zaúčtované"):
            cmd.execute(setup_fp["tx_id"], novy.id)
