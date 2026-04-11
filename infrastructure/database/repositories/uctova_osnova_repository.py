"""SqliteUctovaOsnovaRepository — SQLite implementace UctovaOsnovaRepository."""

from __future__ import annotations

import sqlite3

from domain.shared.errors import ConflictError, NotFoundError
from domain.ucetnictvi.repository import UctovaOsnovaRepository
from domain.ucetnictvi.typy import TypUctu
from domain.ucetnictvi.ucet import Ucet
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class SqliteUctovaOsnovaRepository(UctovaOsnovaRepository):
    """SQLite implementace repository pro účtovou osnovu."""

    def __init__(self, uow: SqliteUnitOfWork) -> None:
        self._uow = uow

    @property
    def _conn(self) -> sqlite3.Connection:
        return self._uow.connection

    def add(self, ucet: Ucet) -> Ucet:
        try:
            self._conn.execute(
                """INSERT INTO uctova_osnova (cislo, nazev, typ, je_aktivni)
                   VALUES (?, ?, ?, ?)""",
                (ucet.cislo, ucet.nazev, ucet.typ.value, int(ucet.je_aktivni)),
            )
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e) or "PRIMARY" in str(e):
                raise ConflictError(
                    f"Účet s číslem {ucet.cislo!r} již existuje."
                ) from e
            raise
        return ucet

    def update(self, ucet: Ucet) -> None:
        cursor = self._conn.execute(
            """UPDATE uctova_osnova SET nazev = ?, typ = ?, je_aktivni = ?
               WHERE cislo = ?""",
            (ucet.nazev, ucet.typ.value, int(ucet.je_aktivni), ucet.cislo),
        )
        if cursor.rowcount == 0:
            raise NotFoundError(f"Účet s číslem {ucet.cislo!r} neexistuje.")

    def get_by_cislo(self, cislo: str) -> Ucet:
        row = self._conn.execute(
            "SELECT * FROM uctova_osnova WHERE cislo = ?", (cislo,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Účet s číslem {cislo!r} neexistuje.")
        return self._row_to_ucet(row)

    def existuje(self, cislo: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM uctova_osnova WHERE cislo = ?", (cislo,)
        ).fetchone()
        return row is not None

    def list_all(self, jen_aktivni: bool = True) -> list[Ucet]:
        if jen_aktivni:
            rows = self._conn.execute(
                "SELECT * FROM uctova_osnova WHERE je_aktivni = 1 ORDER BY cislo"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM uctova_osnova ORDER BY cislo"
            ).fetchall()
        return [self._row_to_ucet(r) for r in rows]

    def list_by_typ(self, typ: TypUctu, jen_aktivni: bool = True) -> list[Ucet]:
        if jen_aktivni:
            rows = self._conn.execute(
                "SELECT * FROM uctova_osnova WHERE typ = ? AND je_aktivni = 1 "
                "ORDER BY cislo",
                (typ.value,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM uctova_osnova WHERE typ = ? ORDER BY cislo",
                (typ.value,),
            ).fetchall()
        return [self._row_to_ucet(r) for r in rows]

    def _row_to_ucet(self, row: sqlite3.Row) -> Ucet:
        return Ucet(
            cislo=row["cislo"],
            nazev=row["nazev"],
            typ=TypUctu(row["typ"]),
            je_aktivni=bool(row["je_aktivni"]),
        )
