"""SqliteUnitOfWork — context manager pro atomické DB operace.

Jediný způsob jak zapisovat do DB. Žádný connection.commit() mimo UoW.
Jedno UoW = jedna transakce = jedna logická operace.
"""

from __future__ import annotations

import sqlite3

from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.exceptions import UnitOfWorkError


class SqliteUnitOfWork:
    """Context manager pro atomické databázové operace.

    Sémantika:
        - __enter__: vyrobí connection, BEGIN IMMEDIATE
        - commit(): uloží změny, UoW je poté "spotřebovaná"
        - rollback(): zahodí změny, UoW je poté "spotřebovaná"
        - __exit__ bez commit/rollback: automatický rollback
        - __exit__ po výjimce: automatický rollback, výjimka propaguje
        - Po spotřebování: jakýkoli přístup → UnitOfWorkError

    Nested UoW (reentrant) není podporováno.
    """

    def __init__(self, factory: ConnectionFactory) -> None:
        self._factory = factory
        self._conn: sqlite3.Connection | None = None
        self._active = False
        self._finished = False

    def __enter__(self) -> SqliteUnitOfWork:
        if self._active:
            raise UnitOfWorkError("UoW není reentrant — nelze vnořit with blok.")
        self._conn = self._factory.create()
        self._conn.execute("BEGIN IMMEDIATE")
        self._active = True
        self._finished = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self._finished:
            # Nebyl zavolán commit() ani rollback() — automatický rollback
            self._do_rollback()
        self._cleanup()
        # Výjimka propaguje (nevracíme True)

    @property
    def connection(self) -> sqlite3.Connection:
        """Aktivní connection. Dostupná jen uvnitř with bloku před commit/rollback."""
        self._check_usable()
        assert self._conn is not None
        return self._conn

    def commit(self) -> None:
        """Explicitní commit. Po volání je UoW spotřebovaná."""
        self._check_usable()
        assert self._conn is not None
        self._conn.execute("COMMIT")
        self._finished = True

    def rollback(self) -> None:
        """Explicitní rollback. Po volání je UoW spotřebovaná."""
        self._check_usable()
        self._do_rollback()

    def _check_usable(self) -> None:
        """Kontrola, že UoW je v použitelném stavu."""
        if not self._active:
            raise UnitOfWorkError(
                "UoW není aktivní — použij ji uvnitř 'with' bloku."
            )
        if self._finished:
            raise UnitOfWorkError(
                "UoW je již spotřebovaná (commit/rollback proběhl). "
                "Vytvoř novou instanci pro další operaci."
            )

    def _do_rollback(self) -> None:
        """Interní rollback."""
        if self._conn is not None:
            try:
                self._conn.execute("ROLLBACK")
            except Exception:
                pass  # Connection může být v broken state po chybě
        self._finished = True

    def _cleanup(self) -> None:
        """Uzavření connection a deaktivace UoW."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        self._active = False
