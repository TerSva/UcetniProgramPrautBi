"""MigrationRunner — sekvenční SQL migrace s gap detekcí."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.exceptions import MigrationError


class MigrationRunner:
    """Aplikuje SQL migrace sekvenčně s detekcí mezer v sekvenci.

    Migrace jsou očíslované: 001_*.sql, 002_*.sql, ...
    Každá migrace běží v samostatné transakci.
    """

    def __init__(self, factory: ConnectionFactory, sql_dir: Path) -> None:
        self._factory = factory
        self._sql_dir = sql_dir

    def current_version(self) -> int:
        """Číslo poslední aplikované migrace, nebo 0."""
        conn = self._factory.create()
        try:
            # Zkontroluj, jestli tabulka schema_migrations existuje
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            if row is None:
                return 0
            row = conn.execute(
                "SELECT MAX(version) as max_v FROM schema_migrations"
            ).fetchone()
            return row["max_v"] or 0
        finally:
            conn.close()

    def available_migrations(self) -> list[tuple[int, Path]]:
        """Seřazený seznam (číslo, cesta) pro všechny NNN_*.sql soubory."""
        migrations = []
        for path in sorted(self._sql_dir.glob("*.sql")):
            name = path.stem
            # Prvních 3 znaků = číslo migrace
            try:
                version = int(name[:3])
            except (ValueError, IndexError):
                continue
            migrations.append((version, path))
        return sorted(migrations, key=lambda x: x[0])

    def migrate(self) -> list[int]:
        """Aplikuje chybějící migrace. Vrátí čísla aplikovaných.

        Každá migrace v samostatné transakci.
        Gap v sekvenci → MigrationError.
        """
        self._ensure_schema_migrations_table()
        current = self.current_version()
        available = self.available_migrations()
        applied = self._get_applied_versions()

        # Gap detekce: migrace s nižším číslem než current musí být v applied
        for version, path in available:
            if version <= current and version not in applied:
                raise MigrationError(
                    f"Gap detekován: migrace {version:03d} ({path.name}) "
                    f"chybí v schema_migrations, ale current_version={current}. "
                    f"Nelze pokračovat."
                )

        # Aplikovat chybějící migrace (vyšší než current)
        to_apply = [(v, p) for v, p in available if v > current]
        applied_versions = []

        for version, path in to_apply:
            self._apply_migration(version, path)
            applied_versions.append(version)

        return applied_versions

    def _ensure_schema_migrations_table(self) -> None:
        """Vytvoří tabulku schema_migrations pokud neexistuje."""
        conn = self._factory.create()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                        DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
                )
            """)
            conn.execute("COMMIT")
        finally:
            conn.close()

    def _get_applied_versions(self) -> set[int]:
        """Vrátí sadu již aplikovaných verzí."""
        conn = self._factory.create()
        try:
            rows = conn.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
            return {row["version"] for row in rows}
        finally:
            conn.close()

    def _apply_migration(self, version: int, path: Path) -> None:
        """Aplikuje jednu migraci v transakci."""
        sql = path.read_text(encoding="utf-8")
        conn = self._factory.create()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.executescript(sql)
            # executescript commitne implicitně, takže musíme začít novou transakci
            # pro zápis do schema_migrations
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.execute("COMMIT")
        except Exception as e:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise MigrationError(
                f"Migrace {version:03d} ({path.name}) selhala: {e}"
            ) from e
        finally:
            conn.close()
