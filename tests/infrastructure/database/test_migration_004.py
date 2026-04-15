"""Testy pro migraci 004_storno_zapisy.sql.

Ověřuje, že migrace:
  * přidá sloupec je_storno (INTEGER NOT NULL DEFAULT 0) do ucetni_zaznamy
  * přidá sloupec stornuje_zaznam_id (INTEGER, nullable, FK self)
  * vytvoří partial index idx_zaznamy_stornuje
  * CHECK constraint na je_storno IN (0, 1) funguje
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


def _seed_doklad_and_ucty(conn) -> None:
    conn.execute(
        """INSERT INTO doklady (cislo, typ, datum_vystaveni, castka_celkem, stav)
           VALUES ('TEST-001', 'FV', '2026-01-01', 1000, 'novy')"""
    )
    # uctova_osnova už má účty 311/601 z migrace 002


class TestMigration004Columns:

    def test_je_storno_column_exists(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            cols = conn.execute("PRAGMA table_info(ucetni_zaznamy)").fetchall()
        finally:
            conn.close()
        names = {row["name"] for row in cols}
        assert "je_storno" in names
        assert "stornuje_zaznam_id" in names

    def test_je_storno_not_null_default_0(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            cols = conn.execute("PRAGMA table_info(ucetni_zaznamy)").fetchall()
        finally:
            conn.close()
        col = next(c for c in cols if c["name"] == "je_storno")
        assert col["type"].upper() == "INTEGER"
        assert col["notnull"] == 1
        assert str(col["dflt_value"]) == "0"

    def test_stornuje_id_nullable_integer(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            cols = conn.execute("PRAGMA table_info(ucetni_zaznamy)").fetchall()
        finally:
            conn.close()
        col = next(c for c in cols if c["name"] == "stornuje_zaznam_id")
        assert col["type"].upper() == "INTEGER"
        assert col["notnull"] == 0


class TestMigration004Index:

    def test_partial_index_exists(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            indexes = conn.execute(
                "PRAGMA index_list(ucetni_zaznamy)"
            ).fetchall()
        finally:
            conn.close()
        names = {row["name"] for row in indexes}
        assert "idx_zaznamy_stornuje" in names

    def test_index_is_partial(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            row = conn.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type='index' AND name='idx_zaznamy_stornuje'"
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert "WHERE" in row["sql"].upper()
        assert "stornuje_zaznam_id" in row["sql"]


class TestMigration004CheckConstraint:

    def test_check_rejects_2(self, migrated_factory):
        import sqlite3

        conn = migrated_factory.create()
        try:
            _seed_doklad_and_ucty(conn)
            conn.commit()
            with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
                conn.execute(
                    """INSERT INTO ucetni_zaznamy
                       (doklad_id, datum, md_ucet, dal_ucet, castka, je_storno)
                       VALUES (1, '2026-01-01', '311', '601', 1000, 2)"""
                )
                conn.commit()
        finally:
            conn.close()

    def test_check_accepts_0_a_1(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            _seed_doklad_and_ucty(conn)
            conn.execute(
                """INSERT INTO ucetni_zaznamy
                   (doklad_id, datum, md_ucet, dal_ucet, castka, je_storno)
                   VALUES (1, '2026-01-01', '311', '601', 1000, 0)"""
                )
            conn.execute(
                """INSERT INTO ucetni_zaznamy
                   (doklad_id, datum, md_ucet, dal_ucet, castka, je_storno,
                    stornuje_zaznam_id)
                   VALUES (1, '2026-01-02', '601', '311', 1000, 1, 1)"""
                )
            conn.commit()
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM ucetni_zaznamy"
            ).fetchone()["c"]
        finally:
            conn.close()
        assert count == 2


class TestMigration004DefaultPropagation:

    def test_existing_insert_bez_je_storno_dostane_0(self, migrated_factory):
        """INSERT bez je_storno sloupce → default 0."""
        conn = migrated_factory.create()
        try:
            _seed_doklad_and_ucty(conn)
            conn.execute(
                """INSERT INTO ucetni_zaznamy
                   (doklad_id, datum, md_ucet, dal_ucet, castka)
                   VALUES (1, '2026-01-01', '311', '601', 1000)"""
            )
            conn.commit()
            row = conn.execute(
                "SELECT je_storno, stornuje_zaznam_id FROM ucetni_zaznamy"
            ).fetchone()
        finally:
            conn.close()
        assert row["je_storno"] == 0
        assert row["stornuje_zaznam_id"] is None


class TestMigration004FK:

    def test_fk_self_reference(self, migrated_factory):
        """stornuje_zaznam_id odkazuje na ucetni_zaznamy(id)."""
        conn = migrated_factory.create()
        try:
            fks = conn.execute(
                "PRAGMA foreign_key_list(ucetni_zaznamy)"
            ).fetchall()
        finally:
            conn.close()
        self_fk = [
            fk for fk in fks
            if fk["from"] == "stornuje_zaznam_id"
        ]
        assert len(self_fk) == 1
        assert self_fk[0]["table"] == "ucetni_zaznamy"
        assert self_fk[0]["to"] == "id"
