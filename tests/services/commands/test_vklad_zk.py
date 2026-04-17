"""Testy pro VkladZKCommand."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from domain.shared.money import Money
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from scripts.seed_chart_of_accounts import seed_chart_of_accounts
from services.commands.vklad_zk import VkladZKCommand


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
def cmd(factory) -> VkladZKCommand:
    return VkladZKCommand(uow_factory=lambda: SqliteUnitOfWork(factory))


def test_execute_creates_two_doklady(cmd, factory):
    ids = cmd.execute(
        castka_zk=Money(20000000),
        datum=date(2025, 1, 1),
        bankovni_ucet="221",
        rok=2025,
    )
    assert len(ids) == 2

    uow = SqliteUnitOfWork(factory)
    with uow:
        drepo = SqliteDokladyRepository(uow)
        d1 = drepo.get_by_cislo("ID-2025-001")
        d2 = drepo.get_by_cislo("ID-2025-002")

    from domain.doklady.typy import StavDokladu
    assert d1 is not None
    assert d1.castka_celkem == Money(20000000)
    assert d1.stav == StavDokladu.ZAUCTOVANY

    assert d2 is not None
    assert d2.castka_celkem == Money(20000000)
    assert d2.stav == StavDokladu.ZAUCTOVANY


def test_execute_creates_ucetni_zaznamy(cmd, factory):
    cmd.execute(
        castka_zk=Money(20000000),
        datum=date(2025, 1, 1),
        bankovni_ucet="221",
        rok=2025,
    )

    uow = SqliteUnitOfWork(factory)
    with uow:
        denik = SqliteUcetniDenikRepository(uow)
        drepo = SqliteDokladyRepository(uow)
        d1 = drepo.get_by_cislo("ID-2025-001")
        d2 = drepo.get_by_cislo("ID-2025-002")

        zaznamy_1 = denik.list_by_doklad(d1.id)
        assert len(zaznamy_1) == 1
        assert zaznamy_1[0].md_ucet == "353"
        assert zaznamy_1[0].dal_ucet == "411"

        zaznamy_2 = denik.list_by_doklad(d2.id)
        assert len(zaznamy_2) == 1
        assert zaznamy_2[0].md_ucet == "221"
        assert zaznamy_2[0].dal_ucet == "353"


def test_execute_duplicate_skips(cmd):
    ids1 = cmd.execute(
        castka_zk=Money(20000000),
        datum=date(2025, 1, 1),
        bankovni_ucet="221",
        rok=2025,
    )
    ids2 = cmd.execute(
        castka_zk=Money(20000000),
        datum=date(2025, 1, 1),
        bankovni_ucet="221",
        rok=2025,
    )
    assert len(ids1) == 2
    assert len(ids2) == 0
