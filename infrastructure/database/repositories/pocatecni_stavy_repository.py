"""SqlitePocatecniStavyRepository — CRUD pro počáteční stavy účtů."""

from __future__ import annotations

import sqlite3

from domain.firma.pocatecni_stav import PocatecniStav
from domain.shared.money import Money
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class SqlitePocatecniStavyRepository:

    def __init__(self, uow: SqliteUnitOfWork) -> None:
        self._uow = uow

    @property
    def _conn(self) -> sqlite3.Connection:
        return self._uow.connection

    def add(self, stav: PocatecniStav) -> PocatecniStav:
        cursor = self._conn.execute(
            """INSERT INTO pocatecni_stavy
               (ucet_kod, castka, strana, rok, poznamka)
               VALUES (?, ?, ?, ?, ?)""",
            (
                stav.ucet_kod,
                stav.castka.to_halire(),
                stav.strana,
                stav.rok,
                stav.poznamka,
            ),
        )
        return PocatecniStav(
            id=cursor.lastrowid,
            ucet_kod=stav.ucet_kod,
            castka=stav.castka,
            strana=stav.strana,
            rok=stav.rok,
            poznamka=stav.poznamka,
        )

    def delete(self, stav_id: int) -> None:
        self._conn.execute(
            "DELETE FROM pocatecni_stavy WHERE id = ?", (stav_id,),
        )

    def list_by_rok(self, rok: int) -> list[PocatecniStav]:
        rows = self._conn.execute(
            "SELECT * FROM pocatecni_stavy WHERE rok = ? ORDER BY id",
            (rok,),
        ).fetchall()
        return [self._row_to_stav(r) for r in rows]

    def _row_to_stav(self, row: sqlite3.Row) -> PocatecniStav:
        return PocatecniStav(
            id=row["id"],
            ucet_kod=row["ucet_kod"],
            castka=Money(row["castka"]),
            strana=row["strana"],
            rok=row["rok"],
            poznamka=row["poznamka"],
        )
