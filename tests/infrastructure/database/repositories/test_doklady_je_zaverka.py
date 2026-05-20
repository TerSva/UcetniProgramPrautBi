"""Round-trip testy pro Doklad.je_zaverka — perzistence v repository."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.errors import ValidationError
from domain.shared.money import Money
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork


MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent.parent.parent
    / "infrastructure" / "database" / "migrations" / "sql"
)


@pytest.fixture
def factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    f = ConnectionFactory(db_path)
    MigrationRunner(f, MIGRATIONS_SQL_DIR).migrate()
    return f


def _new_doklad(cislo: str, je_zaverka: bool = False) -> Doklad:
    return Doklad(
        cislo=cislo,
        typ=TypDokladu.INTERNI_DOKLAD,
        datum_vystaveni=date(2025, 12, 31),
        castka_celkem=Money(10000),
        je_zaverka=je_zaverka,
    )


def test_doklad_default_je_zaverka_false():
    d = _new_doklad("ID-2025-X1")
    assert d.je_zaverka is False


def test_doklad_explicit_je_zaverka_true():
    d = _new_doklad("ID-2025-Z1", je_zaverka=True)
    assert d.je_zaverka is True


def test_doklad_je_zaverka_must_be_bool():
    with pytest.raises(TypeError, match="je_zaverka musí být bool"):
        Doklad(
            cislo="X",
            typ=TypDokladu.INTERNI_DOKLAD,
            datum_vystaveni=date(2025, 12, 31),
            castka_celkem=Money(0),
            je_zaverka=1,  # type: ignore[arg-type]
        )


def test_repository_round_trip_je_zaverka_false(factory):
    """Vytvořit Doklad bez je_zaverka, uložit, načíst → False."""
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        repo.add(_new_doklad("ID-FALSE"))
        uow.commit()

    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        repo2 = SqliteDokladyRepository(uow2)
        loaded = repo2.get_by_cislo("ID-FALSE")
        assert loaded.je_zaverka is False


def test_repository_round_trip_je_zaverka_true(factory):
    """Vytvořit Doklad s je_zaverka=True, uložit, načíst → True."""
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        repo.add(_new_doklad("ID-TRUE", je_zaverka=True))
        uow.commit()

    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        repo2 = SqliteDokladyRepository(uow2)
        loaded = repo2.get_by_cislo("ID-TRUE")
        assert loaded.je_zaverka is True
        assert loaded.id is not None


def test_repository_update_zachovava_je_zaverka(factory):
    """Update existujícího je_zaverka=True dokladu zachová příznak."""
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        repo.add(_new_doklad("ID-UPD", je_zaverka=True))
        uow.commit()

    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        repo2 = SqliteDokladyRepository(uow2)
        loaded = repo2.get_by_cislo("ID-UPD")
        loaded.zauctuj()
        repo2.update(loaded)
        uow2.commit()

    uow3 = SqliteUnitOfWork(factory)
    with uow3:
        repo3 = SqliteDokladyRepository(uow3)
        reloaded = repo3.get_by_cislo("ID-UPD")
        assert reloaded.je_zaverka is True


def test_add_vraci_doklad_s_je_zaverka_zachovanym(factory):
    """add() vrací Doklad zachovávající je_zaverka."""
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        result = repo.add(_new_doklad("ID-ADDRET", je_zaverka=True))
        uow.commit()
    assert result.je_zaverka is True
    assert result.id is not None
