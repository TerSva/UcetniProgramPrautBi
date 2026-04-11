"""Shared fixtures pro service testy."""

from pathlib import Path

import pytest

from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.repositories.uctova_osnova_repository import (
    SqliteUctovaOsnovaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork

MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent
    / "infrastructure"
    / "database"
    / "migrations"
    / "sql"
)


@pytest.fixture
def db_factory(tmp_path) -> ConnectionFactory:
    """Connection factory s tempfile DB + aplikovanými migracemi."""
    db_path = tmp_path / "test.db"
    factory = ConnectionFactory(db_path)
    runner = MigrationRunner(factory, MIGRATIONS_SQL_DIR)
    runner.migrate()
    return factory


@pytest.fixture
def service_factories(db_factory):
    """Factory funkce pro service testy."""
    return {
        "uow": lambda: SqliteUnitOfWork(db_factory),
        "doklady": lambda uow: SqliteDokladyRepository(uow),
        "denik": lambda uow: SqliteUcetniDenikRepository(uow),
        "osnova": lambda uow: SqliteUctovaOsnovaRepository(uow),
        "db_factory": db_factory,
    }
