"""Testy pro NastaveniViewModel."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.firma.firma import Firma
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from ui.viewmodels.nastaveni_vm import NastaveniViewModel


MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "infrastructure" / "database" / "migrations" / "sql"
)


@pytest.fixture
def factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    f = ConnectionFactory(db_path)
    MigrationRunner(f, MIGRATIONS_SQL_DIR).migrate()
    return f


@pytest.fixture
def vm(factory) -> NastaveniViewModel:
    return NastaveniViewModel(uow_factory=lambda: SqliteUnitOfWork(factory))


def test_load_empty(vm):
    vm.load()
    assert vm.firma is None
    assert vm.error is None


def test_save_and_load(vm):
    firma = Firma(nazev="Test s.r.o.")
    vm.save(firma)
    assert vm.error is None
    assert vm.firma is not None
    assert vm.firma.nazev == "Test s.r.o."

    vm.load()
    assert vm.firma is not None
    assert vm.firma.nazev == "Test s.r.o."


def test_save_invalid_firma(vm):
    # Empty nazev triggers ValidationError in Firma.__post_init__
    try:
        firma = Firma(nazev="")
    except Exception:
        pass  # Expected — Firma validates on creation
    else:
        pytest.fail("Firma with empty nazev should raise")
