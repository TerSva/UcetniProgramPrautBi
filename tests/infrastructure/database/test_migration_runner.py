"""Testy pro MigrationRunner."""

import re
from pathlib import Path

import pytest

from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.exceptions import MigrationError
from infrastructure.database.migrations.runner import MigrationRunner


@pytest.fixture
def file_factory(tmp_path) -> ConnectionFactory:
    return ConnectionFactory(tmp_path / "test.db")


@pytest.fixture
def sql_dir(tmp_path) -> Path:
    """Dočasný adresář pro testovací SQL soubory."""
    d = tmp_path / "sql"
    d.mkdir()
    return d


def _write_migration(sql_dir: Path, filename: str, content: str) -> None:
    (sql_dir / filename).write_text(content, encoding="utf-8")


class TestCurrentVersion:

    def test_prazdna_db_verze_nula(self, file_factory, sql_dir):
        """Prázdná DB → current_version() vrací 0."""
        runner = MigrationRunner(file_factory, sql_dir)
        assert runner.current_version() == 0

    def test_po_migraci_vraci_verzi(self, file_factory, sql_dir):
        """Po migrate() vrací current_version() číslo poslední migrace."""
        _write_migration(sql_dir, "001_create.sql", "CREATE TABLE t (id INTEGER);")
        _write_migration(sql_dir, "002_add.sql", "ALTER TABLE t ADD COLUMN name TEXT;")
        runner = MigrationRunner(file_factory, sql_dir)
        runner.migrate()
        assert runner.current_version() == 2


class TestAvailableMigrations:

    def test_serazeny_seznam(self, file_factory, sql_dir):
        """available_migrations() vrací seřazený seznam."""
        _write_migration(sql_dir, "002_second.sql", "")
        _write_migration(sql_dir, "001_first.sql", "")
        _write_migration(sql_dir, "003_third.sql", "")
        runner = MigrationRunner(file_factory, sql_dir)
        migrations = runner.available_migrations()
        assert [v for v, _ in migrations] == [1, 2, 3]

    def test_ignoruje_ne_sql_soubory(self, file_factory, sql_dir):
        """Ignoruje soubory bez .sql přípony."""
        _write_migration(sql_dir, "001_first.sql", "")
        (sql_dir / "readme.txt").write_text("ignore me")
        runner = MigrationRunner(file_factory, sql_dir)
        assert len(runner.available_migrations()) == 1


class TestMigrate:

    def test_aplikuje_vsechny_migrace(self, file_factory, sql_dir):
        """migrate() na prázdné DB aplikuje všechny migrace v pořadí."""
        _write_migration(sql_dir, "001_create.sql", "CREATE TABLE t (id INTEGER);")
        _write_migration(sql_dir, "002_add.sql", "ALTER TABLE t ADD COLUMN name TEXT;")
        runner = MigrationRunner(file_factory, sql_dir)
        applied = runner.migrate()
        assert applied == [1, 2]

    def test_druhe_volani_nic_neaplikuje(self, file_factory, sql_dir):
        """Druhé volání migrate() neaplikuje nic (vrátí prázdný seznam)."""
        _write_migration(sql_dir, "001_create.sql", "CREATE TABLE t (id INTEGER);")
        runner = MigrationRunner(file_factory, sql_dir)
        runner.migrate()
        assert runner.migrate() == []

    def test_selhani_migrace_neohrozi_verzi(self, file_factory, sql_dir):
        """Migrace selže → current_version() se nezmění, výjimka propaguje."""
        _write_migration(sql_dir, "001_create.sql", "CREATE TABLE t (id INTEGER);")
        _write_migration(sql_dir, "002_bad.sql", "THIS IS NOT VALID SQL;")
        runner = MigrationRunner(file_factory, sql_dir)

        with pytest.raises(MigrationError, match="002"):
            runner.migrate()

        assert runner.current_version() == 1

    def test_gap_detekce(self, file_factory, sql_dir):
        """Gap: migrace 001 a 003 aplikovány, pak přidáme soubor 002 → MigrationError."""
        _write_migration(sql_dir, "001_first.sql", "CREATE TABLE t1 (id INTEGER);")
        _write_migration(sql_dir, "003_third.sql", "CREATE TABLE t3 (id INTEGER);")
        runner = MigrationRunner(file_factory, sql_dir)

        # Aplikuje 001 a 003 (v souborech chybí 002, takže obě projdou)
        runner.migrate()
        assert runner.current_version() == 3

        # Teď někdo přidá soubor 002 — ale v DB záznam chybí → gap
        _write_migration(sql_dir, "002_second.sql", "CREATE TABLE t2 (id INTEGER);")

        with pytest.raises(MigrationError, match="Gap"):
            runner.migrate()

    def test_gap_detekce_chybejici_v_db(self, file_factory, sql_dir):
        """Soubor migrace existuje, ale v DB chybí záznam — gap."""
        # Připravíme DB kde current_version = 2, ale v souborech je 001, 002, 003
        # a v schema_migrations chybí záznam pro 001 (simulated gap)
        _write_migration(sql_dir, "001_first.sql", "CREATE TABLE t1 (id INTEGER);")
        _write_migration(sql_dir, "002_second.sql", "CREATE TABLE t2 (id INTEGER);")

        runner = MigrationRunner(file_factory, sql_dir)
        runner.migrate()  # Aplikuje 001, 002
        assert runner.current_version() == 2

        # Smažeme záznam 001 z schema_migrations (simulace nekonzistence)
        conn = file_factory.create()
        conn.execute("BEGIN")
        conn.execute("DELETE FROM schema_migrations WHERE version = 1")
        conn.execute("COMMIT")
        conn.close()

        # Přidáme 003
        _write_migration(sql_dir, "003_third.sql", "CREATE TABLE t3 (id INTEGER);")

        with pytest.raises(MigrationError, match="Gap"):
            runner.migrate()

    def test_applied_at_iso_timestamp(self, file_factory, sql_dir):
        """schema_migrations má sloupec applied_at s validním ISO timestampem."""
        _write_migration(sql_dir, "001_create.sql", "CREATE TABLE t (id INTEGER);")
        runner = MigrationRunner(file_factory, sql_dir)
        runner.migrate()

        conn = file_factory.create()
        try:
            row = conn.execute(
                "SELECT applied_at FROM schema_migrations WHERE version=1"
            ).fetchone()
            # ISO 8601: YYYY-MM-DD HH:MM:SS
            assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", row["applied_at"])
        finally:
            conn.close()
