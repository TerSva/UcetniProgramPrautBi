"""SqlitePrilohaRepository — SQLite implementace PrilohaRepository."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from domain.doklady.priloha import PrilohaDokladu
from domain.doklady.priloha_repository import PrilohaRepository
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class SqlitePrilohaRepository(PrilohaRepository):
    """SQLite implementace repository pro přílohy dokladů."""

    def __init__(self, uow: SqliteUnitOfWork) -> None:
        self._uow = uow

    @property
    def _conn(self) -> sqlite3.Connection:
        return self._uow.connection

    def add(self, priloha: PrilohaDokladu) -> PrilohaDokladu:
        cursor = self._conn.execute(
            """INSERT INTO prilohy_dokladu
               (doklad_id, nazev_souboru, relativni_cesta,
                velikost_bytes, mime_type, vytvoreno)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                priloha.doklad_id,
                priloha.nazev_souboru,
                priloha.relativni_cesta,
                priloha.velikost_bytes,
                priloha.mime_type,
                priloha.vytvoreno.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        return PrilohaDokladu(
            id=cursor.lastrowid,
            doklad_id=priloha.doklad_id,
            nazev_souboru=priloha.nazev_souboru,
            relativni_cesta=priloha.relativni_cesta,
            velikost_bytes=priloha.velikost_bytes,
            mime_type=priloha.mime_type,
            vytvoreno=priloha.vytvoreno,
        )

    def list_by_doklad(self, doklad_id: int) -> list[PrilohaDokladu]:
        rows = self._conn.execute(
            "SELECT * FROM prilohy_dokladu WHERE doklad_id = ? ORDER BY id",
            (doklad_id,),
        ).fetchall()
        return [self._row_to_priloha(r) for r in rows]

    def get_by_id(self, id: int) -> PrilohaDokladu | None:
        row = self._conn.execute(
            "SELECT * FROM prilohy_dokladu WHERE id = ?", (id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_priloha(row)

    def delete(self, id: int) -> None:
        self._conn.execute(
            "DELETE FROM prilohy_dokladu WHERE id = ?", (id,),
        )

    def _row_to_priloha(self, row: sqlite3.Row) -> PrilohaDokladu:
        vytvoreno_raw = row["vytvoreno"]
        if isinstance(vytvoreno_raw, datetime):
            vytvoreno = vytvoreno_raw
        else:
            vytvoreno = datetime.fromisoformat(str(vytvoreno_raw))
        return PrilohaDokladu(
            id=row["id"],
            doklad_id=row["doklad_id"],
            nazev_souboru=row["nazev_souboru"],
            relativni_cesta=row["relativni_cesta"],
            velikost_bytes=row["velikost_bytes"],
            mime_type=row["mime_type"],
            vytvoreno=vytvoreno,
        )
