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
        je_d = (
            None if ucet.je_danovy is None else int(bool(ucet.je_danovy))
        )
        try:
            self._conn.execute(
                """INSERT INTO uctova_osnova
                   (cislo, nazev, typ, je_aktivni, parent_kod, popis, je_danovy)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    ucet.cislo, ucet.nazev, ucet.typ.value,
                    int(ucet.je_aktivni), ucet.parent_kod, ucet.popis,
                    je_d,
                ),
            )
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e) or "PRIMARY" in str(e):
                raise ConflictError(
                    f"Účet s číslem {ucet.cislo!r} již existuje."
                ) from e
            raise
        return ucet

    def update(self, ucet: Ucet) -> None:
        je_d = (
            None if ucet.je_danovy is None else int(bool(ucet.je_danovy))
        )
        cursor = self._conn.execute(
            """UPDATE uctova_osnova
               SET nazev = ?, typ = ?, je_aktivni = ?, popis = ?,
                   je_danovy = ?
               WHERE cislo = ?""",
            (
                ucet.nazev, ucet.typ.value, int(ucet.je_aktivni),
                ucet.popis, je_d, ucet.cislo,
            ),
        )
        if cursor.rowcount == 0:
            raise NotFoundError(f"Účet s číslem {ucet.cislo!r} neexistuje.")

    def delete(self, cislo: str) -> None:
        cursor = self._conn.execute(
            "DELETE FROM uctova_osnova WHERE cislo = ?", (cislo,)
        )
        if cursor.rowcount == 0:
            raise NotFoundError(f"Účet s číslem {cislo!r} neexistuje.")

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

    def get_analytiky(self, parent_kod: str) -> list[Ucet]:
        rows = self._conn.execute(
            "SELECT * FROM uctova_osnova WHERE parent_kod = ? ORDER BY cislo",
            (parent_kod,),
        ).fetchall()
        return [self._row_to_ucet(r) for r in rows]

    def _row_to_ucet(self, row: sqlite3.Row) -> Ucet:
        je_d_raw = row["je_danovy"] if "je_danovy" in row.keys() else None
        je_d = None if je_d_raw is None else bool(je_d_raw)
        return Ucet(
            cislo=row["cislo"],
            nazev=row["nazev"],
            typ=TypUctu(row["typ"]),
            je_aktivni=bool(row["je_aktivni"]),
            parent_kod=row["parent_kod"] if "parent_kod" in row.keys() else None,
            popis=row["popis"] if "popis" in row.keys() else None,
            je_danovy=je_d,
        )
