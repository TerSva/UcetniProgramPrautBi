"""Testy ZalohyPartneraQuery — odvození analytiky 324/314 ze zápisu ZF."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.zalohy_partnera import ZalohyPartneraQuery


@pytest.fixture
def factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    f = ConnectionFactory(db_path)
    runner = MigrationRunner(
        f, Path("infrastructure/database/migrations/sql"),
    )
    runner.migrate()
    # Seed účtů a partnerů potřebných pro testy
    uow = SqliteUnitOfWork(f)
    with uow:
        for cislo, nazev in [
            ("221.001", "Bankovní účet 1"),
            ("311.100", "Pohledávky 1"),
            ("324.100", "Přijaté zálohy 100"),
            ("324.001", "Přijaté zálohy 001"),
            ("314.200", "Poskytnuté zálohy 200"),
            ("314.001", "Poskytnuté zálohy 001"),
        ]:
            uow.connection.execute(
                "INSERT OR IGNORE INTO uctova_osnova "
                "(cislo, nazev, typ, je_aktivni) VALUES (?, ?, 'A', 1)",
                (cislo, nazev),
            )
        for pid, nazev in [(7, "P7"), (42, "P42"), (99, "P99")]:
            uow.connection.execute(
                "INSERT OR IGNORE INTO partneri "
                "(id, nazev, kategorie, je_aktivni) "
                "VALUES (?, ?, 'odberatel', 1)",
                (pid, nazev),
            )
        uow.commit()
    return f


def _query(factory) -> ZalohyPartneraQuery:
    return ZalohyPartneraQuery(
        uow_factory=lambda: SqliteUnitOfWork(factory),
    )


class TestUcetZalohaOdvozeni:
    """Analytika 324/314 se odvozuje ze zápisu ZF v deníku."""

    def test_fv_zaloha_pouzije_analytiku_z_dal_ucet(self, factory):
        """Vystavená ZF zaúčtována MD 221.001/Dal 324.100 → ucet_zaloha=324.100."""
        uow = SqliteUnitOfWork(factory)
        with uow:
            drepo = SqliteDokladyRepository(uow)
            denik = SqliteUcetniDenikRepository(uow)
            zf = drepo.add(Doklad(
                cislo="ZF-2025-001",
                typ=TypDokladu.ZALOHA_FAKTURA,
                datum_vystaveni=date(2025, 5, 1),
                castka_celkem=Money(50000_00),
                stav=StavDokladu.UHRAZENY,
                je_vystavena=True,
                partner_id=42,
            ))
            denik.add(UcetniZaznam(
                doklad_id=zf.id, datum=date(2025, 5, 5),
                md_ucet="221.001", dal_ucet="324.100",
                castka=Money(50000_00),
            ))
            uow.commit()

        result = _query(factory).execute(partner_id=42, je_vystavena=True)
        assert len(result) == 1
        assert result[0].cislo == "ZF-2025-001"
        assert result[0].ucet_zaloha == "324.100"

    def test_fp_zaloha_pouzije_analytiku_z_md_ucet(self, factory):
        """Přijatá ZF zaúčtována MD 314.200/Dal 221.001 → ucet_zaloha=314.200."""
        uow = SqliteUnitOfWork(factory)
        with uow:
            drepo = SqliteDokladyRepository(uow)
            denik = SqliteUcetniDenikRepository(uow)
            zf = drepo.add(Doklad(
                cislo="ZF-PRIJATA-1",
                typ=TypDokladu.ZALOHA_FAKTURA,
                datum_vystaveni=date(2025, 5, 1),
                castka_celkem=Money(20000_00),
                stav=StavDokladu.UHRAZENY,
                je_vystavena=False,
                partner_id=99,
            ))
            denik.add(UcetniZaznam(
                doklad_id=zf.id, datum=date(2025, 5, 6),
                md_ucet="314.200", dal_ucet="221.001",
                castka=Money(20000_00),
            ))
            uow.commit()

        result = _query(factory).execute(partner_id=99, je_vystavena=False)
        assert len(result) == 1
        assert result[0].ucet_zaloha == "314.200"

    def test_zf_bez_zapisu_v_deniku_pouzije_fallback(self, factory):
        """ZF v NOVY (zatím bez zápisu) → fallback 324.001 / 314.001."""
        uow = SqliteUnitOfWork(factory)
        with uow:
            drepo = SqliteDokladyRepository(uow)
            drepo.add(Doklad(
                cislo="ZF-NEW",
                typ=TypDokladu.ZALOHA_FAKTURA,
                datum_vystaveni=date(2025, 5, 1),
                castka_celkem=Money(10000_00),
                stav=StavDokladu.ZAUCTOVANY,
                je_vystavena=True,
                partner_id=7,
            ))
            uow.commit()

        result = _query(factory).execute(partner_id=7, je_vystavena=True)
        assert len(result) == 1
        assert result[0].ucet_zaloha == "324.001"
