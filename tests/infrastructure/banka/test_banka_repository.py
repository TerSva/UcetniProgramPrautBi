"""Testy pro bankovní repositories."""

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


class TestSqliteBankovniUcetRepository:

    def test_add_and_get(self, db_factory):
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

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteBankovniUcetRepository(uow2)
            ucet = repo2.get(uid)
            assert ucet is not None
            assert ucet.nazev == "Money Banka"
            assert ucet.format_csv == FormatCsv.MONEY_BANKA
            assert ucet.ucet_kod == "221.001"

    def test_list_aktivni_filters_inactive(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteBankovniUcetRepository(uow)
            # Seed migration 012 already adds 2 active accounts
            base_count = len(repo.list_aktivni())
            repo.add(BankovniUcet(
                nazev="Active Extra", cislo_uctu="99/0100", ucet_kod="221.099",
            ))
            repo.add(BankovniUcet(
                nazev="Inactive", cislo_uctu="98/0100", ucet_kod="221.098",
                je_aktivni=False,
            ))
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteBankovniUcetRepository(uow2)
            aktivni = repo2.list_aktivni()
            assert len(aktivni) == base_count + 1
            nazvy = [u.nazev for u in aktivni]
            assert "Active Extra" in nazvy
            assert "Inactive" not in nazvy

    def test_get_nonexistent_returns_none(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteBankovniUcetRepository(uow)
            assert repo.get(999) is None


class TestSqliteBankovniVypisRepository:

    def _create_ucet_and_doklad(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            ucet_repo = SqliteBankovniUcetRepository(uow)
            ucet_id = ucet_repo.add(BankovniUcet(
                nazev="Test", cislo_uctu="1/0100", ucet_kod="221.001",
            ))
            doklady_repo = SqliteDokladyRepository(uow)
            doklad = doklady_repo.add(Doklad(
                cislo="BV-2025-03",
                typ=TypDokladu.BANKOVNI_VYPIS,
                datum_vystaveni=date(2025, 3, 1),
                castka_celkem=Money(0),
            ))
            uow.commit()
        return ucet_id, doklad.id

    def test_add_and_get(self, db_factory):
        ucet_id, doklad_id = self._create_ucet_and_doklad(db_factory)

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteBankovniVypisRepository(uow)
            vid = repo.add(BankovniVypis(
                bankovni_ucet_id=ucet_id,
                rok=2025,
                mesic=3,
                pocatecni_stav=Money(100000),
                konecny_stav=Money(200000),
                pdf_path="/test.pdf",
                bv_doklad_id=doklad_id,
            ))
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteBankovniVypisRepository(uow2)
            v = repo2.get(vid)
            assert v is not None
            assert v.rok == 2025
            assert v.mesic == 3
            assert v.pocatecni_stav == Money(100000)

    def test_get_by_ucet_mesic(self, db_factory):
        ucet_id, doklad_id = self._create_ucet_and_doklad(db_factory)

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteBankovniVypisRepository(uow)
            repo.add(BankovniVypis(
                bankovni_ucet_id=ucet_id,
                rok=2025,
                mesic=3,
                pocatecni_stav=Money(0),
                konecny_stav=Money(0),
                pdf_path="/test.pdf",
                bv_doklad_id=doklad_id,
            ))
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteBankovniVypisRepository(uow2)
            v = repo2.get_by_ucet_mesic(ucet_id, 2025, 3)
            assert v is not None
            assert repo2.get_by_ucet_mesic(ucet_id, 2025, 4) is None


class TestSqliteBankovniTransakceRepository:

    def _setup(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            ucet_repo = SqliteBankovniUcetRepository(uow)
            ucet_id = ucet_repo.add(BankovniUcet(
                nazev="Test", cislo_uctu="1/0100", ucet_kod="221.001",
            ))
            doklady_repo = SqliteDokladyRepository(uow)
            doklad = doklady_repo.add(Doklad(
                cislo="BV-2025-03",
                typ=TypDokladu.BANKOVNI_VYPIS,
                datum_vystaveni=date(2025, 3, 1),
                castka_celkem=Money(0),
            ))
            vypis_repo = SqliteBankovniVypisRepository(uow)
            vypis_id = vypis_repo.add(BankovniVypis(
                bankovni_ucet_id=ucet_id,
                rok=2025, mesic=3,
                pocatecni_stav=Money(0),
                konecny_stav=Money(0),
                pdf_path="/test.pdf",
                bv_doklad_id=doklad.id,
            ))
            uow.commit()
        return vypis_id

    def test_add_and_get(self, db_factory):
        vypis_id = self._setup(db_factory)

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteBankovniTransakceRepository(uow)
            tid = repo.add(BankovniTransakce(
                bankovni_vypis_id=vypis_id,
                datum_transakce=date(2025, 3, 15),
                datum_zauctovani=date(2025, 3, 15),
                castka=Money(-15000),
                smer="V",
                row_hash="hash_unique_1",
                popis="Test",
            ))
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteBankovniTransakceRepository(uow2)
            tx = repo2.get(tid)
            assert tx is not None
            assert tx.castka == Money(-15000)
            assert tx.stav == StavTransakce.NESPAROVANO

    def test_exists_hash(self, db_factory):
        vypis_id = self._setup(db_factory)

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteBankovniTransakceRepository(uow)
            repo.add(BankovniTransakce(
                bankovni_vypis_id=vypis_id,
                datum_transakce=date(2025, 3, 15),
                datum_zauctovani=date(2025, 3, 15),
                castka=Money(10000),
                smer="P",
                row_hash="unique_hash_abc",
            ))
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteBankovniTransakceRepository(uow2)
            assert repo2.exists_hash("unique_hash_abc")
            assert not repo2.exists_hash("nonexistent")

    def test_count_by_stav(self, db_factory):
        vypis_id = self._setup(db_factory)

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteBankovniTransakceRepository(uow)
            repo.add(BankovniTransakce(
                bankovni_vypis_id=vypis_id,
                datum_transakce=date(2025, 3, 15),
                datum_zauctovani=date(2025, 3, 15),
                castka=Money(10000),
                smer="P",
                row_hash="h1",
            ))
            repo.add(BankovniTransakce(
                bankovni_vypis_id=vypis_id,
                datum_transakce=date(2025, 3, 16),
                datum_zauctovani=date(2025, 3, 16),
                castka=Money(20000),
                smer="P",
                row_hash="h2",
            ))
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteBankovniTransakceRepository(uow2)
            assert repo2.count_by_stav(vypis_id, StavTransakce.NESPAROVANO) == 2
            assert repo2.count_by_stav(vypis_id, StavTransakce.SPAROVANO) == 0
