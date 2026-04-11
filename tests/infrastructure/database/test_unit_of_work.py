"""Testy pro SqliteUnitOfWork."""

import sqlite3
from pathlib import Path

import pytest

from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.exceptions import UnitOfWorkError
from infrastructure.database.unit_of_work import SqliteUnitOfWork


@pytest.fixture
def file_factory(tmp_path) -> ConnectionFactory:
    """Factory se souborovou DB (pro test persistence mezi connections)."""
    return ConnectionFactory(tmp_path / "test.db")


@pytest.fixture
def mem_factory() -> ConnectionFactory:
    """Factory s :memory: DB."""
    return ConnectionFactory(":memory:")


def _setup_test_table(factory: ConnectionFactory) -> None:
    """Vytvoří testovací tabulku."""
    conn = factory.create()
    conn.execute("BEGIN")
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("COMMIT")
    conn.close()


class TestCommit:

    def test_commit_ulozi_data(self, file_factory):
        """Commit uloží data — po výstupu z with jsou data v DB."""
        _setup_test_table(file_factory)

        with SqliteUnitOfWork(file_factory) as uow:
            uow.connection.execute("INSERT INTO test VALUES (1, 'hello')")
            uow.commit()

        # Ověř novou connection
        conn = file_factory.create()
        try:
            row = conn.execute("SELECT * FROM test WHERE id=1").fetchone()
            assert row["value"] == "hello"
        finally:
            conn.close()

    def test_bez_commitu_rollback(self, file_factory):
        """Bez explicitního commit() se data NEUKLOŽÍ (default je rollback)."""
        _setup_test_table(file_factory)

        with SqliteUnitOfWork(file_factory) as uow:
            uow.connection.execute("INSERT INTO test VALUES (1, 'lost')")
            # Žádný commit()

        conn = file_factory.create()
        try:
            row = conn.execute("SELECT * FROM test WHERE id=1").fetchone()
            assert row is None
        finally:
            conn.close()


class TestRollback:

    def test_vyjimka_rollback_a_propaguje(self, file_factory):
        """Výjimka uvnitř with → automatický rollback, výjimka propaguje."""
        _setup_test_table(file_factory)

        with pytest.raises(ValueError, match="test error"):
            with SqliteUnitOfWork(file_factory) as uow:
                uow.connection.execute("INSERT INTO test VALUES (1, 'lost')")
                raise ValueError("test error")

        conn = file_factory.create()
        try:
            row = conn.execute("SELECT * FROM test WHERE id=1").fetchone()
            assert row is None
        finally:
            conn.close()

    def test_explicitni_rollback(self, file_factory):
        """Explicitní rollback() zahodí změny."""
        _setup_test_table(file_factory)

        with SqliteUnitOfWork(file_factory) as uow:
            uow.connection.execute("INSERT INTO test VALUES (1, 'lost')")
            uow.rollback()

        conn = file_factory.create()
        try:
            row = conn.execute("SELECT * FROM test WHERE id=1").fetchone()
            assert row is None
        finally:
            conn.close()


class TestSpotrebovani:
    """Po commit/rollback je UoW spotřebovaná — další operace → UnitOfWorkError."""

    def test_connection_po_commit(self, file_factory):
        """Přístup k connection po commit → UnitOfWorkError."""
        _setup_test_table(file_factory)

        with SqliteUnitOfWork(file_factory) as uow:
            uow.connection.execute("INSERT INTO test VALUES (1, 'ok')")
            uow.commit()
            with pytest.raises(UnitOfWorkError, match="spotřebovaná"):
                _ = uow.connection

    def test_druhy_commit(self, file_factory):
        """Druhý commit() → UnitOfWorkError."""
        _setup_test_table(file_factory)

        with SqliteUnitOfWork(file_factory) as uow:
            uow.connection.execute("INSERT INTO test VALUES (1, 'ok')")
            uow.commit()
            with pytest.raises(UnitOfWorkError, match="spotřebovaná"):
                uow.commit()

    def test_connection_po_rollback(self, file_factory):
        """Přístup k connection po rollback → UnitOfWorkError."""
        _setup_test_table(file_factory)

        with SqliteUnitOfWork(file_factory) as uow:
            uow.rollback()
            with pytest.raises(UnitOfWorkError, match="spotřebovaná"):
                _ = uow.connection

    def test_commit_po_exit(self, file_factory):
        """commit() po výstupu z with → UnitOfWorkError."""
        _setup_test_table(file_factory)

        uow = SqliteUnitOfWork(file_factory)
        with uow:
            uow.connection.execute("INSERT INTO test VALUES (1, 'ok')")
            uow.commit()

        with pytest.raises(UnitOfWorkError, match="není aktivní"):
            uow.commit()

    def test_connection_po_exit(self, file_factory):
        """Přístup k connection po výstupu z with → UnitOfWorkError."""
        _setup_test_table(file_factory)

        uow = SqliteUnitOfWork(file_factory)
        with uow:
            uow.commit()

        with pytest.raises(UnitOfWorkError, match="není aktivní"):
            _ = uow.connection


class TestForeignKeys:

    def test_fk_aktivni_uvnitr_uow(self, file_factory):
        """Foreign keys jsou aktivní — porušení FK → IntegrityError."""
        # Vytvoř schéma s FK
        conn = file_factory.create()
        conn.execute("BEGIN")
        conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        conn.execute(
            "CREATE TABLE child (id INTEGER, parent_id INTEGER "
            "REFERENCES parent(id) ON DELETE RESTRICT)"
        )
        conn.execute("COMMIT")
        conn.close()

        with pytest.raises(sqlite3.IntegrityError):
            with SqliteUnitOfWork(file_factory) as uow:
                # parent_id=999 neexistuje
                uow.connection.execute(
                    "INSERT INTO child VALUES (1, 999)"
                )
                uow.commit()


class TestSekvencniUow:

    def test_dve_sekvencni_uow(self, file_factory):
        """Dvě sekvenční UoW — po commitu první vidí druhá data."""
        _setup_test_table(file_factory)

        with SqliteUnitOfWork(file_factory) as uow1:
            uow1.connection.execute("INSERT INTO test VALUES (1, 'first')")
            uow1.commit()

        with SqliteUnitOfWork(file_factory) as uow2:
            row = uow2.connection.execute(
                "SELECT * FROM test WHERE id=1"
            ).fetchone()
            assert row["value"] == "first"
            uow2.commit()


class TestReentrant:

    def test_vnoreny_with_selze(self, file_factory):
        """Vnořený with se stejnou UoW instancí → UnitOfWorkError."""
        _setup_test_table(file_factory)

        uow = SqliteUnitOfWork(file_factory)
        with uow:
            with pytest.raises(UnitOfWorkError, match="reentrant"):
                with uow:
                    pass
