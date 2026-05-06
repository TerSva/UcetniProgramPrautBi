"""ZalohyPartneraQuery — nezúčtované zálohy konkrétního partnera.

Slouží pro tlačítko „Načíst zálohy" v zauctovani dialogu pro FP/FV.
Vrátí seznam ZF dokladů stejného partnera v stavu ZAUCTOVANY/UHRAZENY,
které ještě nebyly zúčtovány finální fakturou.

Nezúčtovaná = neexistuje účetní zápis MD 324.x / Dal 311.x (vystavená)
              nebo MD 321.x / Dal 314.x (přijatá) navázaný na tuto ZF.

Pro FV (PRAUT inkasuje finální): hledáme **vystavené** zálohy partnera.
Pro FP (PRAUT platí finální): hledáme **přijaté** zálohy partnera.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from domain.doklady.typy import Mena, StavDokladu, TypDokladu
from domain.shared.money import Money
from infrastructure.database.unit_of_work import SqliteUnitOfWork


@dataclass(frozen=True)
class ZalohaItem:
    """Nezúčtovaná zálohová faktura partnera."""

    id: int
    cislo: str
    datum: date
    castka_celkem: Money  # CZK
    castka_mena: Money | None
    mena: Mena
    je_vystavena: bool


class ZalohyPartneraQuery:
    """Vrátí nezúčtované ZF konkrétního partnera dle směru."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(
        self,
        partner_id: int,
        je_vystavena: bool,
    ) -> list[ZalohaItem]:
        """Najde ZF stejného partnera odpovídajícího směru.

        Args:
            partner_id: ID partnera.
            je_vystavena: True = pro FV finální (hledáme vystavené ZF
                partnera-odběratele), False = pro FP finální (přijaté
                zálohy od dodavatele).
        """
        uow = self._uow_factory()
        with uow:
            # 1) Najdi všechny ZF tohoto partnera v ne-stornovaném stavu
            rows = uow.connection.execute(
                """
                SELECT d.id, d.cislo, d.datum_vystaveni,
                       d.castka_celkem, d.castka_mena, d.mena
                FROM doklady d
                WHERE d.typ = 'ZF'
                  AND d.partner_id = ?
                  AND d.je_vystavena = ?
                  AND d.stav IN (?, ?, ?)
                ORDER BY d.datum_vystaveni DESC, d.id DESC
                """,
                (
                    partner_id,
                    1 if je_vystavena else 0,
                    StavDokladu.ZAUCTOVANY.value,
                    StavDokladu.CASTECNE_UHRAZENY.value,
                    StavDokladu.UHRAZENY.value,
                ),
            ).fetchall()

            result: list[ZalohaItem] = []
            for r in rows:
                # 2) Filtr: zahrnout jen ZF, která ještě nebyla zúčtována
                # finální fakturou. Detekce: existuje účetní zápis
                # s popisem obsahujícím cislo ZF a strana 324 nebo 314?
                # Pro vystavenou: zúčtováno = MD 324% (snížení záloh)
                # Pro přijatou:  zúčtováno = Dal 314% (snížení záloh)
                cislo = r["cislo"]
                je_zauctovana_finalni = self._je_zaloha_zuctovana(
                    uow, cislo, je_vystavena,
                )
                if je_zauctovana_finalni:
                    continue

                result.append(ZalohaItem(
                    id=r["id"],
                    cislo=cislo,
                    datum=date.fromisoformat(r["datum_vystaveni"]),
                    castka_celkem=Money(r["castka_celkem"]),
                    castka_mena=(
                        Money(r["castka_mena"])
                        if r["castka_mena"] is not None else None
                    ),
                    mena=Mena(r["mena"]) if r["mena"] else Mena.CZK,
                    je_vystavena=je_vystavena,
                ))
            return result

    def _je_zaloha_zuctovana(
        self,
        uow: SqliteUnitOfWork,
        cislo_zalohy: str,
        je_vystavena: bool,
    ) -> bool:
        """Detekuje, zda už byla záloha zúčtována s finální fakturou.

        Hledá účetní zápis s popisem obsahujícím cislo ZF a strana
        324% (pro vystavenou) nebo 314% (pro přijatou).
        """
        if je_vystavena:
            # Vystavená: zúčtování = MD 324% / Dal 311%
            sloupec = "md_ucet"
            prefix = "324"
        else:
            sloupec = "dal_ucet"
            prefix = "314"
        # noqa: S608 — sloupec/prefix jsou kontrolované konstanty
        row = uow.connection.execute(
            f"""
            SELECT 1 FROM ucetni_zaznamy
            WHERE popis LIKE ?
              AND {sloupec} LIKE ?
              AND je_storno = 0
            LIMIT 1
            """,
            (f"%{cislo_zalohy}%", f"{prefix}%"),
        ).fetchone()
        return row is not None
