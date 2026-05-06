"""NeuhrazeneDokladyQuery — seznam neuhrazených FP/FV pro párování."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from domain.doklady.typy import Mena, StavDokladu, TypDokladu
from domain.shared.money import Money
from infrastructure.database.unit_of_work import SqliteUnitOfWork


@dataclass(frozen=True)
class NeuhrazenyDokladItem:
    """DTO pro neuhrazený doklad — kandidát na spárování."""

    id: int
    cislo: str
    typ: TypDokladu
    datum: date
    partner_nazev: str | None
    castka_celkem: Money
    castka_mena: Money | None
    mena: Mena
    variabilni_symbol: str | None


class NeuhrazeneDokladyQuery:
    """Vrátí neuhrazené FP/FV doklady pro ruční párování."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(
        self,
        typ: TypDokladu | None = None,
        castka_od: Money | None = None,
        castka_do: Money | None = None,
        search: str | None = None,
    ) -> list[NeuhrazenyDokladItem]:
        """Najde neuhrazené FP/FV.

        Args:
            typ: filtr na typ dokladu (FP/FV). None = obojí.
            castka_od: minimální absolutní částka.
            castka_do: maximální absolutní částka.
            search: fulltext v cislo + partner_nazev.
        """
        uow = self._uow_factory()
        with uow:
            # ZF se neúčtují samostatně — bere se v NOVY stavu rovněž.
            # FV/FP jsou v ZAUCTOVANY/CASTECNE_UHRAZENY (po zaúčtování).
            sql = """
                SELECT d.id, d.cislo, d.typ, d.datum_vystaveni,
                       d.castka_celkem, d.castka_mena, d.mena,
                       d.variabilni_symbol,
                       p.nazev AS partner_nazev
                FROM doklady d
                LEFT JOIN partneri p ON d.partner_id = p.id
                WHERE d.typ IN ('FP', 'FV', 'ZF')
                  AND (
                    (d.typ IN ('FP', 'FV') AND d.stav IN (?, ?))
                    OR (d.typ = 'ZF' AND d.stav IN (?, ?, ?))
                  )
            """
            params: list = [
                StavDokladu.ZAUCTOVANY.value,
                StavDokladu.CASTECNE_UHRAZENY.value,
                StavDokladu.NOVY.value,
                StavDokladu.ZAUCTOVANY.value,
                StavDokladu.CASTECNE_UHRAZENY.value,
            ]

            if typ is not None:
                sql += " AND d.typ = ?"
                params.append(typ.value)

            if castka_od is not None:
                sql += " AND ABS(d.castka_celkem) >= ?"
                params.append(abs(castka_od.to_halire()))

            if castka_do is not None:
                sql += " AND ABS(d.castka_celkem) <= ?"
                params.append(abs(castka_do.to_halire()))

            if search:
                sql += " AND (d.cislo LIKE ? OR p.nazev LIKE ?)"
                needle = f"%{search}%"
                params.extend([needle, needle])

            sql += " ORDER BY d.datum_vystaveni DESC, d.id DESC"

            rows = uow.connection.execute(sql, params).fetchall()

            return [
                NeuhrazenyDokladItem(
                    id=r["id"],
                    cislo=r["cislo"],
                    typ=TypDokladu(r["typ"]),
                    datum=date.fromisoformat(r["datum_vystaveni"]),
                    partner_nazev=r["partner_nazev"],
                    castka_celkem=Money(r["castka_celkem"]),
                    castka_mena=(
                        Money(r["castka_mena"])
                        if r["castka_mena"] is not None
                        else None
                    ),
                    mena=Mena(r["mena"]) if r["mena"] else Mena.CZK,
                    variabilni_symbol=r["variabilni_symbol"],
                )
                for r in rows
            ]
