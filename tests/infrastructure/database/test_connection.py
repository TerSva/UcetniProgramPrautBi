"""Testy pro ConnectionFactory."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from infrastructure.database.connection import ConnectionFactory


@pytest.fixture
def tmp_db(tmp_path) -> Path:
    return tmp_path / "test.db"


class TestConnectionFactory:

    def test_wal_mode_na_souboru(self, tmp_db):
        """Factory vyrobí connection s WAL módem na souborovém DB."""
        factory = ConnectionFactory(tmp_db)
        conn = factory.create()
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode == "wal"
        finally:
            conn.close()

    def test_memory_bez_wal(self):
        """Factory vyrobí :memory: connection bez WAL (a bez chyby)."""
        factory = ConnectionFactory(":memory:")
        conn = factory.create()
        try:
            # :memory: defaultuje na "memory" nebo "delete", ne "wal"
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode != "wal"
        finally:
            conn.close()

    def test_foreign_keys_on(self):
        factory = ConnectionFactory(":memory:")
        conn = factory.create()
        try:
            fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            assert fk == 1
        finally:
            conn.close()

    def test_busy_timeout(self):
        factory = ConnectionFactory(":memory:")
        conn = factory.create()
        try:
            timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            assert timeout == 5000
        finally:
            conn.close()

    def test_row_factory_sqlite_row(self):
        """row_factory = sqlite3.Row — přístup přes row['column_name']."""
        factory = ConnectionFactory(":memory:")
        conn = factory.create()
        try:
            conn.execute("CREATE TABLE t (id INTEGER, name TEXT)")
            conn.execute("INSERT INTO t VALUES (1, 'test')")
            row = conn.execute("SELECT * FROM t").fetchone()
            assert row["id"] == 1
            assert row["name"] == "test"
        finally:
            conn.close()

    def test_dve_volani_ruzne_instance(self):
        """Dvě volání factory.create() vrací různé connection instance."""
        factory = ConnectionFactory(":memory:")
        conn1 = factory.create()
        conn2 = factory.create()
        try:
            assert conn1 is not conn2
        finally:
            conn1.close()
            conn2.close()

    def test_isolation_level_none(self):
        """Connection má isolation_level = None (explicitní transakce)."""
        factory = ConnectionFactory(":memory:")
        conn = factory.create()
        try:
            assert conn.isolation_level is None
        finally:
            conn.close()

    def test_path_objekt(self, tmp_db):
        """Factory akceptuje Path objekt."""
        factory = ConnectionFactory(tmp_db)
        conn = factory.create()
        try:
            conn.execute("CREATE TABLE t (id INTEGER)")
            assert True
        finally:
            conn.close()

    def test_string_cesta(self, tmp_path):
        """Factory akceptuje string cestu."""
        db_str = str(tmp_path / "test2.db")
        factory = ConnectionFactory(db_str)
        conn = factory.create()
        try:
            conn.execute("CREATE TABLE t (id INTEGER)")
            assert True
        finally:
            conn.close()
