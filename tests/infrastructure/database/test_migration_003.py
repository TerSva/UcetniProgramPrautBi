"""Testy pro migraci 003_doklady_doreseni.sql.

Ověřuje, že migrace:
  * přidá sloupce k_doreseni (INTEGER NOT NULL DEFAULT 0) a poznamka_doreseni (TEXT)
  * vytvoří partial index idx_doklady_k_doreseni
  * CHECK constraint na k_doreseni IN (0, 1) funguje
"""

from pathlib import Path

import pytest

from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner

MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "infrastructure"
    / "database"
    / "migrations"
    / "sql"
)


@pytest.fixture
def migrated_factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    factory = ConnectionFactory(db_path)
    runner = MigrationRunner(factory, MIGRATIONS_SQL_DIR)
    runner.migrate()
    return factory


class TestMigration003Columns:

    def test_k_doreseni_column_exists(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            cols = conn.execute("PRAGMA table_info(doklady)").fetchall()
        finally:
            conn.close()
        names = {row["name"] for row in cols}
        assert "k_doreseni" in names
        assert "poznamka_doreseni" in names

    def test_k_doreseni_not_null_default_0(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            cols = conn.execute("PRAGMA table_info(doklady)").fetchall()
        finally:
            conn.close()
        k_doreseni_col = next(c for c in cols if c["name"] == "k_doreseni")
        assert k_doreseni_col["type"].upper() == "INTEGER"
        assert k_doreseni_col["notnull"] == 1
        # default "0" (SQLite vrací jako string)
        assert str(k_doreseni_col["dflt_value"]) == "0"

    def test_poznamka_doreseni_text_nullable(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            cols = conn.execute("PRAGMA table_info(doklady)").fetchall()
        finally:
            conn.close()
        pozn = next(c for c in cols if c["name"] == "poznamka_doreseni")
        assert pozn["type"].upper() == "TEXT"
        assert pozn["notnull"] == 0


class TestMigration003Index:

    def test_partial_index_exists(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            indexes = conn.execute(
                "PRAGMA index_list(doklady)"
            ).fetchall()
        finally:
            conn.close()
        names = {row["name"] for row in indexes}
        assert "idx_doklady_k_doreseni" in names

    def test_index_is_partial(self, migrated_factory):
        """Ověř, že index má WHERE klauzuli (partial index)."""
        conn = migrated_factory.create()
        try:
            row = conn.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type='index' AND name='idx_doklady_k_doreseni'"
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert "WHERE" in row["sql"].upper()
        assert "k_doreseni" in row["sql"]


class TestMigration003CheckConstraint:

    def test_check_constraint_rejects_2(self, migrated_factory):
        """INSERT s k_doreseni=2 musí selhat na CHECK constraint."""
        import sqlite3

        conn = migrated_factory.create()
        try:
            with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
                conn.execute(
                    """INSERT INTO doklady
                       (cislo, typ, datum_vystaveni, castka_celkem, stav,
                        k_doreseni)
                       VALUES ('TEST-001', 'FV', '2026-01-01', 1000, 'novy', 2)"""
                )
                conn.commit()
        finally:
            conn.close()

    def test_check_constraint_accepts_0_and_1(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            conn.execute(
                """INSERT INTO doklady
                   (cislo, typ, datum_vystaveni, castka_celkem, stav,
                    k_doreseni)
                   VALUES ('TEST-001', 'FV', '2026-01-01', 1000, 'novy', 0)"""
            )
            conn.execute(
                """INSERT INTO doklady
                   (cislo, typ, datum_vystaveni, castka_celkem, stav,
                    k_doreseni)
                   VALUES ('TEST-002', 'FV', '2026-01-01', 1000, 'novy', 1)"""
            )
            conn.commit()
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM doklady"
            ).fetchone()["c"]
        finally:
            conn.close()
        assert count == 2


class TestMigration003DefaultPropagation:

    def test_existing_insert_without_flag_gets_0(self, migrated_factory):
        """INSERT bez k_doreseni sloupce → default 0 (díky NOT NULL DEFAULT 0)."""
        conn = migrated_factory.create()
        try:
            conn.execute(
                """INSERT INTO doklady
                   (cislo, typ, datum_vystaveni, castka_celkem, stav)
                   VALUES ('TEST-DEFAULT', 'FV', '2026-01-01', 1000, 'novy')"""
            )
            conn.commit()
            row = conn.execute(
                "SELECT k_doreseni, poznamka_doreseni FROM doklady "
                "WHERE cislo = 'TEST-DEFAULT'"
            ).fetchone()
        finally:
            conn.close()
        assert row["k_doreseni"] == 0
        assert row["poznamka_doreseni"] is None
