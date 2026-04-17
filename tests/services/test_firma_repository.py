"""Testy pro FirmaRepository a PocatecniStavyRepository."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from domain.firma.firma import Firma
from domain.firma.pocatecni_stav import PocatecniStav
from domain.shared.money import Money
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.firma_repository import (
    SqliteFirmaRepository,
)
from infrastructure.database.repositories.pocatecni_stavy_repository import (
    SqlitePocatecniStavyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from scripts.seed_chart_of_accounts import seed_chart_of_accounts


MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent
    / "infrastructure" / "database" / "migrations" / "sql"
)


@pytest.fixture
def factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    f = ConnectionFactory(db_path)
    MigrationRunner(f, MIGRATIONS_SQL_DIR).migrate()
    seed_chart_of_accounts(f)
    return f


# ── Firma Repository ──


def test_firma_get_returns_none_when_empty(factory):
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteFirmaRepository(uow)
        assert repo.get() is None


def test_firma_upsert_and_get(factory):
    firma = Firma(
        nazev="PRAUT s.r.o.",
        ico="22545107",
        dic="CZ22545107",
        sidlo="Tršnice 36",
        datum_zalozeni=date(2025, 1, 1),
        zakladni_kapital=Money(20000000),
    )
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteFirmaRepository(uow)
        repo.upsert(firma)
        uow.commit()

    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        repo2 = SqliteFirmaRepository(uow2)
        loaded = repo2.get()

    assert loaded is not None
    assert loaded.nazev == "PRAUT s.r.o."
    assert loaded.ico == "22545107"
    assert loaded.zakladni_kapital == Money(20000000)
    assert loaded.datum_zalozeni == date(2025, 1, 1)
    assert loaded.id == 1


def test_firma_upsert_updates_existing(factory):
    firma1 = Firma(nazev="Test s.r.o.")
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteFirmaRepository(uow)
        repo.upsert(firma1)
        uow.commit()

    firma2 = Firma(nazev="Updated s.r.o.", ico="12345678")
    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        repo2 = SqliteFirmaRepository(uow2)
        repo2.upsert(firma2)
        uow2.commit()

    uow3 = SqliteUnitOfWork(factory)
    with uow3:
        repo3 = SqliteFirmaRepository(uow3)
        loaded = repo3.get()

    assert loaded.nazev == "Updated s.r.o."
    assert loaded.ico == "12345678"


# ── PocatecniStavy Repository ──


def test_ps_add_and_list(factory):
    stav = PocatecniStav(
        ucet_kod="221", castka=Money(100000), strana="MD", rok=2025,
    )
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqlitePocatecniStavyRepository(uow)
        result = repo.add(stav)
        uow.commit()

    assert result.id is not None
    assert result.ucet_kod == "221"

    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        repo2 = SqlitePocatecniStavyRepository(uow2)
        stavy = repo2.list_by_rok(2025)

    assert len(stavy) == 1
    assert stavy[0].castka == Money(100000)


def test_ps_delete(factory):
    stav = PocatecniStav(
        ucet_kod="221", castka=Money(100000), strana="MD", rok=2025,
    )
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqlitePocatecniStavyRepository(uow)
        result = repo.add(stav)
        uow.commit()

    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        repo2 = SqlitePocatecniStavyRepository(uow2)
        repo2.delete(result.id)
        uow2.commit()

    uow3 = SqliteUnitOfWork(factory)
    with uow3:
        repo3 = SqlitePocatecniStavyRepository(uow3)
        assert repo3.list_by_rok(2025) == []
