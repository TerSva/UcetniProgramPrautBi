"""Shared fixtures pro repository testy."""

from pathlib import Path

import pytest

from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.unit_of_work import SqliteUnitOfWork

MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent.parent.parent
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
def uow(db_factory) -> SqliteUnitOfWork:
    """UoW instance (neaktivní — test musí použít with)."""
    return SqliteUnitOfWork(db_factory)
