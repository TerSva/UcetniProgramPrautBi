"""SqliteDokladyRepository — SQLite implementace DokladyRepository.

Mapování: Money ↔ INTEGER, date ↔ TEXT ISO, enum ↔ TEXT value.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

from domain.doklady.doklad import Doklad
from domain.doklady.repository import DokladyRepository
from domain.doklady.typy import Mena, StavDokladu, TypDokladu
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
                    datum_splatnosti, partner_id, castka_celkem, mena, stav, popis,
                    k_doreseni, poznamka_doreseni, castka_mena, kurz)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    doklad.mena.value,
                    doklad.stav.value,
                    doklad.popis,
                    1 if doklad.k_doreseni else 0,
                    doklad.poznamka_doreseni,
                    doklad.castka_mena.to_halire()
                    if doklad.castka_mena is not None
                    else None,
                    str(doklad.kurz) if doklad.kurz is not None else None,
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
            k_doreseni=doklad.k_doreseni,
            poznamka_doreseni=doklad.poznamka_doreseni,
            mena=doklad.mena,
            castka_mena=doklad.castka_mena,
            kurz=doklad.kurz,
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
               partner_id = ?, castka_celkem = ?, mena = ?, stav = ?, popis = ?,
               k_doreseni = ?, poznamka_doreseni = ?,
               castka_mena = ?, kurz = ?,
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
                doklad.mena.value,
                doklad.stav.value,
                doklad.popis,
                1 if doklad.k_doreseni else 0,
                doklad.poznamka_doreseni,
                doklad.castka_mena.to_halire()
                if doklad.castka_mena is not None
                else None,
                str(doklad.kurz) if doklad.kurz is not None else None,
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

    def count_all(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM doklady"
        ).fetchone()
        return int(row[0])

    def list_k_doreseni(
        self, limit: int = 100, offset: int = 0
    ) -> list[Doklad]:
        rows = self._conn.execute(
            "SELECT * FROM doklady WHERE k_doreseni = 1 "
            "ORDER BY datum_vystaveni DESC, id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [self._row_to_doklad(r) for r in rows]

    def find_by_vs(self, vs: str) -> Doklad | None:
        """Najde doklad podle variabilního symbolu (hledá v čísle dokladu).

        VS matching: hledáme FP/FV kde číslo dokladu obsahuje VS.
        Např. VS "2025042" najde "FP-2025-042" nebo "FV-2025-042".
        """
        # Try exact match on cislo first
        row = self._conn.execute(
            "SELECT * FROM doklady WHERE cislo = ? AND typ IN ('FV', 'FP')",
            (vs,),
        ).fetchone()
        if row:
            return self._row_to_doklad(row)

        # Try matching VS as part of cislo (strip dashes/zeros)
        vs_clean = vs.lstrip("0")
        rows = self._conn.execute(
            "SELECT * FROM doklady WHERE typ IN ('FV', 'FP') "
            "ORDER BY datum_vystaveni DESC",
        ).fetchall()
        for r in rows:
            cislo = r["cislo"]
            # Extract number parts from cislo like "FP-2025-042"
            cislo_digits = "".join(c for c in cislo if c.isdigit())
            if cislo_digits and (
                cislo_digits == vs
                or cislo_digits.lstrip("0") == vs_clean
                or vs in cislo_digits
            ):
                return self._row_to_doklad(r)

        return None

    def delete(self, doklad_id: int) -> None:
        # 1. Doklad existuje? + načíst stav
        row = self._conn.execute(
            "SELECT stav FROM doklady WHERE id = ?", (doklad_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Doklad s id={doklad_id} neexistuje.")

        # 2. Stav je NOVY?
        if row["stav"] != StavDokladu.NOVY.value:
            raise ValidationError(
                f"Nelze smazat doklad id={doklad_id} ve stavu "
                f"{row['stav']!r}. Pro zaúčtované doklady použij "
                f"storno přes opravný doklad."
            )

        # 3. Safety net: nemá účetní zápisy v deníku?
        count = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM ucetni_zaznamy WHERE doklad_id = ?",
            (doklad_id,),
        ).fetchone()["cnt"]
        if count > 0:
            raise ValidationError(
                f"Doklad id={doklad_id} má {count} účetních zápisů v deníku. "
                f"Toto je inkonzistence — zaúčtovaný doklad ve stavu NOVY. "
                f"Nelze smazat, použij storno."
            )

        # 4. Delete
        self._conn.execute("DELETE FROM doklady WHERE id = ?", (doklad_id,))

    def _row_to_doklad(self, row: sqlite3.Row) -> Doklad:
        """Mapuje sqlite3.Row na Doklad entitu."""
        mena_val = row["mena"] if row["mena"] else "CZK"
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
            k_doreseni=bool(row["k_doreseni"]),
            poznamka_doreseni=row["poznamka_doreseni"],
            mena=Mena(mena_val),
            castka_mena=(
                Money(row["castka_mena"])
                if row["castka_mena"] is not None
                else None
            ),
            kurz=(
                Decimal(row["kurz"])
                if row["kurz"] is not None
                else None
            ),
        )
