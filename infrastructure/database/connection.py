"""ConnectionFactory — vyrábí SQLite connections se správnou konfigurací.

Žádný singleton, žádný globální state. Každé volání create() vrací novou connection.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class ConnectionFactory:
    """Vyrábí SQLite connections s pragmy pro účetní systém.

    Konfigurace:
        - foreign_keys = ON
        - journal_mode = WAL (přeskočeno pro :memory:)
        - synchronous = NORMAL
        - busy_timeout = 5000
        - cache_size = -64000 (64 MB)
        - row_factory = sqlite3.Row
        - isolation_level = None (explicitní transakce přes BEGIN)
    """

    def __init__(self, db_path: Path | str) -> None:
        if db_path == ":memory:":
            self._db_path_str = ":memory:"
            self._is_memory = True
        else:
            self._db_path_str = str(Path(db_path))
            self._is_memory = False

    def create(self) -> sqlite3.Connection:
        """Nová connection se správnou konfigurací."""
        conn = sqlite3.connect(
            self._db_path_str,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        conn.row_factory = sqlite3.Row
        # Explicitní řízení transakcí — žádné automatické BEGIN od Pythonu
        conn.isolation_level = None

        conn.execute("PRAGMA foreign_keys = ON")
        if not self._is_memory:
            conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA cache_size = -64000")

        return conn
