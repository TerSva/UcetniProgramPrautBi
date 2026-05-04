"""Query pro účetní záznamy konkrétního dokladu.

Vrací:
  1. Zápisy přímo na tomto dokladu (zaúčtování).
  2. Zápisy na jiných dokladech (BV, PD, ID) které představují úhradu
     tohoto dokladu — nalezené přes sparovany_doklad_id na bankovních
     transakcích nebo přes číslo dokladu v popisu zápisu.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from domain.shared.money import Money
from infrastructure.database.unit_of_work import SqliteUnitOfWork


@dataclass(frozen=True)
class UcetniZapisItem:
    """DTO pro jeden účetní záznam v detailu dokladu."""

    id: int
    datum: date
    zdroj_doklad: str
    md_ucet: str
    dal_ucet: str
    castka: Money
    popis: str | None
    je_storno: bool


class UcetniZapisyDokladuQuery:
    """Načte účetní záznamy pro daný doklad — včetně úhrad z jiných dokladů."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def list_by_doklad(self, doklad_id: int) -> list[UcetniZapisItem]:
        uow = self._uow_factory()
        with uow:
            # Nejdřív zjisti číslo dokladu pro hledání v popisu
            cislo_row = uow.connection.execute(
                "SELECT cislo FROM doklady WHERE id = ?",
                (doklad_id,),
            ).fetchone()
            cislo = cislo_row[0] if cislo_row else ""

            cur = uow.connection.execute(
                """
                -- 1. Zápisy přímo na tomto dokladu
                SELECT uz.id AS zapis_id, uz.datum, d.cislo AS zdroj_doklad,
                       uz.md_ucet, uz.dal_ucet, uz.castka,
                       uz.popis, uz.je_storno
                FROM ucetni_zaznamy uz
                JOIN doklady d ON d.id = uz.doklad_id
                WHERE uz.doklad_id = ?

                UNION ALL

                -- 2. Úhrady přes spárované bankovní transakce
                SELECT uz.id AS zapis_id, uz.datum, d.cislo AS zdroj_doklad,
                       uz.md_ucet, uz.dal_ucet, uz.castka,
                       uz.popis, uz.je_storno
                FROM ucetni_zaznamy uz
                JOIN doklady d ON d.id = uz.doklad_id
                JOIN bankovni_transakce bt
                  ON bt.ucetni_zapis_id = uz.id
                WHERE bt.sparovany_doklad_id = ?
                  AND uz.doklad_id != ?

                UNION ALL

                -- 3. Úhrady, kurzové rozdíly, atd. — popis obsahuje
                -- číslo dokladu, zápis je na PD/ID/BV. BV pokrývá
                -- kurzové ztráty/zisky vznikající při spárování.
                SELECT uz.id AS zapis_id, uz.datum, d.cislo AS zdroj_doklad,
                       uz.md_ucet, uz.dal_ucet, uz.castka,
                       uz.popis, uz.je_storno
                FROM ucetni_zaznamy uz
                JOIN doklady d ON d.id = uz.doklad_id
                WHERE uz.popis LIKE ?
                  AND uz.doklad_id != ?
                  AND d.typ IN ('PD', 'ID', 'BV')

                ORDER BY datum, zapis_id
                """,
                (doklad_id, doklad_id, doklad_id,
                 f"%{cislo}%", doklad_id),
            )
            rows = cur.fetchall()

            # Deduplikace — branch 2 a 3 mohou najít stejný záznam
            seen: set[int] = set()
            result: list[UcetniZapisItem] = []
            for r in rows:
                zapis_id = r[0]
                if zapis_id in seen:
                    continue
                seen.add(zapis_id)
                result.append(
                    UcetniZapisItem(
                        id=zapis_id,
                        datum=date.fromisoformat(r[1]),
                        zdroj_doklad=r[2],
                        md_ucet=r[3],
                        dal_ucet=r[4],
                        castka=Money(r[5]),
                        popis=r[6],
                        je_storno=bool(r[7]),
                    )
                )
            return result
