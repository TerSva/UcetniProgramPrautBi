"""Testy pro PocatecniStavyCommand."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.shared.money import Money
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from scripts.seed_chart_of_accounts import seed_chart_of_accounts
from services.commands.pocatecni_stavy import PocatecniStavyCommand


MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "infrastructure" / "database" / "migrations" / "sql"
)


@pytest.fixture
def factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    f = ConnectionFactory(db_path)
    MigrationRunner(f, MIGRATIONS_SQL_DIR).migrate()
    seed_chart_of_accounts(f)
    return f


@pytest.fixture
def cmd(factory) -> PocatecniStavyCommand:
    return PocatecniStavyCommand(uow_factory=lambda: SqliteUnitOfWork(factory))


def test_pridat_and_list(cmd):
    cmd.pridat(rok=2025, ucet_kod="221", castka=Money(100000), strana="MD")
    cmd.pridat(rok=2025, ucet_kod="411", castka=Money(100000), strana="DAL")
    stavy = cmd.list_by_rok(2025)
    assert len(stavy) == 2
    assert stavy[0].ucet_kod == "221"
    assert stavy[1].ucet_kod == "411"


def test_smazat(cmd):
    result = cmd.pridat(rok=2025, ucet_kod="221", castka=Money(100000), strana="MD")
    cmd.smazat(result.id)
    assert cmd.list_by_rok(2025) == []


def test_list_by_rok_filters(cmd):
    cmd.pridat(rok=2025, ucet_kod="221", castka=Money(100000), strana="MD")
    cmd.pridat(rok=2026, ucet_kod="311", castka=Money(50000), strana="MD")
    assert len(cmd.list_by_rok(2025)) == 1
    assert len(cmd.list_by_rok(2026)) == 1


def test_generovat_id_doklad(cmd, factory):
    cmd.pridat(rok=2025, ucet_kod="221", castka=Money(100000), strana="MD")
    cmd.pridat(rok=2025, ucet_kod="411", castka=Money(100000), strana="DAL")
    doklad_id = cmd.generovat_id_doklad(2025)
    assert doklad_id is not None

    # Verify doklad exists
    from infrastructure.database.repositories.doklady_repository import (
        SqliteDokladyRepository,
    )
    uow = SqliteUnitOfWork(factory)
    with uow:
        drepo = SqliteDokladyRepository(uow)
        loaded = drepo.get_by_cislo("ID-2025-PS")
    assert loaded is not None
    from domain.doklady.typy import StavDokladu
    assert loaded.stav == StavDokladu.ZAUCTOVANY


def test_generovat_id_doklad_no_stavy(cmd):
    result = cmd.generovat_id_doklad(2025)
    assert result is None


def test_generovat_id_doklad_duplicate(cmd):
    cmd.pridat(rok=2025, ucet_kod="221", castka=Money(100000), strana="MD")
    first = cmd.generovat_id_doklad(2025)
    assert first is not None
    second = cmd.generovat_id_doklad(2025)
    assert second is None
