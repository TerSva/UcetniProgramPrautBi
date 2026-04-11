"""SqliteDokladyRepository — SQLite implementace DokladyRepository.

Mapování: Money ↔ INTEGER, date ↔ TEXT ISO, enum ↔ TEXT value.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from domain.doklady.doklad import Doklad
from domain.doklady.repository import DokladyRepository
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import ConflictError, NotFoundError, ValidationError
from domain.shared.money import Money
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class SqliteDokladyRepository(DokladyRepository):
    """SQLite implementace repository pro doklady."""

    def __init__(self, uow: SqliteUnitOfWork) -> None:
        self._uow = uow

    @property
    def _conn(self) -> sqlite3.Connection:
        return self._uow.connection

    def add(self, doklad: Doklad) -> Doklad:
        if doklad.id is not None:
            raise ValidationError(
                "Cannot add Doklad that already has id — use update() instead."
            )
        try:
            cursor = self._conn.execute(
                """INSERT INTO doklady
                   (cislo, typ, datum_vystaveni, datum_zdanitelneho_plneni,
                    datum_splatnosti, partner_id, castka_celkem, mena, stav, popis)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    doklad.cislo,
                    doklad.typ.value,
                    doklad.datum_vystaveni.isoformat(),
                    doklad.datum_zdanitelneho_plneni.isoformat()
                    if doklad.datum_zdanitelneho_plneni
                    else None,
                    doklad.datum_splatnosti.isoformat()
                    if doklad.datum_splatnosti
                    else None,
                    doklad.partner_id,
                    doklad.castka_celkem.to_halire(),
                    "CZK",
                    doklad.stav.value,
                    doklad.popis,
                ),
            )
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e) or "cislo" in str(e):
                raise ConflictError(
                    f"Doklad s číslem {doklad.cislo!r} již existuje."
                ) from e
            raise

        return Doklad(
            cislo=doklad.cislo,
            typ=doklad.typ,
            datum_vystaveni=doklad.datum_vystaveni,
            castka_celkem=doklad.castka_celkem,
            partner_id=doklad.partner_id,
            datum_zdanitelneho_plneni=doklad.datum_zdanitelneho_plneni,
            datum_splatnosti=doklad.datum_splatnosti,
            popis=doklad.popis,
            stav=doklad.stav,
            id=cursor.lastrowid,
        )

    def update(self, doklad: Doklad) -> None:
        if doklad.id is None:
            raise ValidationError(
                "Cannot update Doklad without id — use add() instead."
            )
        cursor = self._conn.execute(
            """UPDATE doklady SET
               cislo = ?, typ = ?, datum_vystaveni = ?,
               datum_zdanitelneho_plneni = ?, datum_splatnosti = ?,
               partner_id = ?, castka_celkem = ?, stav = ?, popis = ?,
               upraveno = strftime('%Y-%m-%d %H:%M:%S', 'now')
               WHERE id = ?""",
            (
                doklad.cislo,
                doklad.typ.value,
                doklad.datum_vystaveni.isoformat(),
                doklad.datum_zdanitelneho_plneni.isoformat()
                if doklad.datum_zdanitelneho_plneni
                else None,
                doklad.datum_splatnosti.isoformat()
                if doklad.datum_splatnosti
                else None,
                doklad.partner_id,
                doklad.castka_celkem.to_halire(),
                doklad.stav.value,
                doklad.popis,
                doklad.id,
            ),
        )
        if cursor.rowcount == 0:
            raise NotFoundError(f"Doklad s id={doklad.id} neexistuje.")

    def get_by_id(self, doklad_id: int) -> Doklad:
        row = self._conn.execute(
            "SELECT * FROM doklady WHERE id = ?", (doklad_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Doklad s id={doklad_id} neexistuje.")
        return self._row_to_doklad(row)

    def get_by_cislo(self, cislo: str) -> Doklad:
        row = self._conn.execute(
            "SELECT * FROM doklady WHERE cislo = ?", (cislo,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Doklad s číslem {cislo!r} neexistuje.")
        return self._row_to_doklad(row)

    def existuje_cislo(self, cislo: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM doklady WHERE cislo = ?", (cislo,)
        ).fetchone()
        return row is not None

    def list_by_typ(
        self, typ: TypDokladu, limit: int = 100, offset: int = 0
    ) -> list[Doklad]:
        rows = self._conn.execute(
            "SELECT * FROM doklady WHERE typ = ? "
            "ORDER BY datum_vystaveni DESC LIMIT ? OFFSET ?",
            (typ.value, limit, offset),
        ).fetchall()
        return [self._row_to_doklad(r) for r in rows]

    def list_by_stav(
        self, stav: StavDokladu, limit: int = 100, offset: int = 0
    ) -> list[Doklad]:
        rows = self._conn.execute(
            "SELECT * FROM doklady WHERE stav = ? "
            "ORDER BY datum_vystaveni DESC LIMIT ? OFFSET ?",
            (stav.value, limit, offset),
        ).fetchall()
        return [self._row_to_doklad(r) for r in rows]

    def list_by_obdobi(
        self, od: date, do: date, limit: int = 1000, offset: int = 0
    ) -> list[Doklad]:
        rows = self._conn.execute(
            "SELECT * FROM doklady WHERE datum_vystaveni >= ? AND datum_vystaveni <= ? "
            "ORDER BY datum_vystaveni DESC LIMIT ? OFFSET ?",
            (od.isoformat(), do.isoformat(), limit, offset),
        ).fetchall()
        return [self._row_to_doklad(r) for r in rows]

    def _row_to_doklad(self, row: sqlite3.Row) -> Doklad:
        """Mapuje sqlite3.Row na Doklad entitu."""
        return Doklad(
            id=row["id"],
            cislo=row["cislo"],
            typ=TypDokladu(row["typ"]),
            datum_vystaveni=date.fromisoformat(row["datum_vystaveni"]),
            datum_zdanitelneho_plneni=(
                date.fromisoformat(row["datum_zdanitelneho_plneni"])
                if row["datum_zdanitelneho_plneni"]
                else None
            ),
            datum_splatnosti=(
                date.fromisoformat(row["datum_splatnosti"])
                if row["datum_splatnosti"]
                else None
            ),
            partner_id=row["partner_id"],
            castka_celkem=Money(row["castka_celkem"]),
            popis=row["popis"],
            stav=StavDokladu(row["stav"]),
        )
