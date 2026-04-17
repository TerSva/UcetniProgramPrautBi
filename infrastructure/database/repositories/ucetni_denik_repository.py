"""SqliteUcetniDenikRepository — SQLite implementace UcetniDenikRepository.

Žádný update(), žádný delete(). Účetní zápisy jsou immutable.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from domain.shared.errors import NotFoundError, ValidationError
from domain.shared.money import Money
from domain.ucetnictvi.repository import UcetniDenikRepository
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class SqliteUcetniDenikRepository(UcetniDenikRepository):
    """SQLite implementace repository pro účetní deník."""

    def __init__(self, uow: SqliteUnitOfWork) -> None:
        self._uow = uow

    @property
    def _conn(self) -> sqlite3.Connection:
        return self._uow.connection

    def zauctuj(self, predpis: UctovyPredpis) -> tuple[UcetniZaznam, ...]:
        conn = self._conn

        # 1. Doklad existuje?
        row = conn.execute(
            "SELECT 1 FROM doklady WHERE id = ?", (predpis.doklad_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(
                f"Doklad id={predpis.doklad_id} neexistuje"
            )

        # 2. Všechny účty existují a jsou aktivní?
        pouzite_ucty: set[str] = set()
        for z in predpis.zaznamy:
            pouzite_ucty.add(z.md_ucet)
            pouzite_ucty.add(z.dal_ucet)

        placeholders = ",".join("?" * len(pouzite_ucty))
        rows = conn.execute(
            f"SELECT cislo, je_aktivni FROM uctova_osnova "
            f"WHERE cislo IN ({placeholders})",
            tuple(pouzite_ucty),
        ).fetchall()
        nalezene = {r["cislo"]: bool(r["je_aktivni"]) for r in rows}

        chybejici = pouzite_ucty - nalezene.keys()
        if chybejici:
            raise NotFoundError(
                f"Účty neexistují v osnově: {sorted(chybejici)}"
            )

        deaktivovane = {c for c, aktivni in nalezene.items() if not aktivni}
        if deaktivovane:
            raise ValidationError(
                f"Účty jsou deaktivované: {sorted(deaktivovane)}"
            )

        # 3. INSERT všechny záznamy
        ulozene: list[UcetniZaznam] = []
        for z in predpis.zaznamy:
            cursor = conn.execute(
                """INSERT INTO ucetni_zaznamy
                   (doklad_id, datum, md_ucet, dal_ucet, castka, popis,
                    je_storno, stornuje_zaznam_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    z.doklad_id,
                    z.datum.isoformat(),
                    z.md_ucet,
                    z.dal_ucet,
                    z.castka.to_halire(),
                    z.popis,
                    1 if z.je_storno else 0,
                    z.stornuje_zaznam_id,
                ),
            )
            ulozene.append(z.with_id(cursor.lastrowid))

        return tuple(ulozene)

    def add(self, zaznam: UcetniZaznam) -> int:
        """Ulož jeden účetní záznam. Vrátí id."""
        cursor = self._conn.execute(
            """INSERT INTO ucetni_zaznamy
               (doklad_id, datum, md_ucet, dal_ucet, castka, popis,
                je_storno, stornuje_zaznam_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                zaznam.doklad_id,
                zaznam.datum.isoformat(),
                zaznam.md_ucet,
                zaznam.dal_ucet,
                zaznam.castka.to_halire(),
                zaznam.popis,
                1 if zaznam.je_storno else 0,
                zaznam.stornuje_zaznam_id,
            ),
        )
        return cursor.lastrowid

    def get_by_id(self, zaznam_id: int) -> UcetniZaznam:
        row = self._conn.execute(
            "SELECT * FROM ucetni_zaznamy WHERE id = ?", (zaznam_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(
                f"Účetní záznam id={zaznam_id} neexistuje."
            )
        return self._row_to_zaznam(row)

    def delete_by_doklad(self, doklad_id: int) -> int:
        """Smaže všechny účetní záznamy pro daný doklad. Vrátí počet smazaných."""
        cur = self._conn.execute(
            "DELETE FROM ucetni_zaznamy WHERE doklad_id = ?",
            (doklad_id,),
        )
        return cur.rowcount

    def list_by_doklad(self, doklad_id: int) -> tuple[UcetniZaznam, ...]:
        rows = self._conn.execute(
            "SELECT * FROM ucetni_zaznamy WHERE doklad_id = ? ORDER BY id",
            (doklad_id,),
        ).fetchall()
        return tuple(self._row_to_zaznam(r) for r in rows)

    def list_by_obdobi(
        self, od: date, do: date, limit: int = 1000, offset: int = 0
    ) -> tuple[UcetniZaznam, ...]:
        rows = self._conn.execute(
            "SELECT * FROM ucetni_zaznamy "
            "WHERE datum >= ? AND datum <= ? "
            "ORDER BY datum, id LIMIT ? OFFSET ?",
            (od.isoformat(), do.isoformat(), limit, offset),
        ).fetchall()
        return tuple(self._row_to_zaznam(r) for r in rows)

    def list_by_ucet(
        self, ucet_cislo: str, od: date, do: date
    ) -> tuple[UcetniZaznam, ...]:
        rows = self._conn.execute(
            "SELECT * FROM ucetni_zaznamy "
            "WHERE (md_ucet = ? OR dal_ucet = ?) "
            "AND datum >= ? AND datum <= ? "
            "ORDER BY datum, id",
            (ucet_cislo, ucet_cislo, od.isoformat(), do.isoformat()),
        ).fetchall()
        return tuple(self._row_to_zaznam(r) for r in rows)

    def _row_to_zaznam(self, row: sqlite3.Row) -> UcetniZaznam:
        return UcetniZaznam(
            id=row["id"],
            doklad_id=row["doklad_id"],
            datum=date.fromisoformat(row["datum"]),
            md_ucet=row["md_ucet"],
            dal_ucet=row["dal_ucet"],
            castka=Money(row["castka"]),
            popis=row["popis"],
            je_storno=bool(row["je_storno"]),
            stornuje_zaznam_id=row["stornuje_zaznam_id"],
        )
