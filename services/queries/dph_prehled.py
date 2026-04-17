"""DPH přehled queries — měsíční sumarizace a detail transakcí.

Reverse charge = účetní záznam kde MD i Dal začínají na 343
(tzn. 343.100 MD / 343.200 Dal = tranzitní DPH bez odpočtu).

DPH základ se bere z druhého záznamu téhož dokladu, kde MD nebo Dal
je na účtu 343 — základ je na "protějším" řádku.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable

from domain.shared.money import Money
from infrastructure.database.unit_of_work import SqliteUnitOfWork


@dataclass(frozen=True)
class DphMesicItem:
    """Sumarizace DPH za jeden měsíc."""

    rok: int
    mesic: int
    zaklad_celkem: Money
    dph_celkem: Money
    pocet_transakci: int
    je_podane: bool


@dataclass(frozen=True)
class DphTransakceItem:
    """Jedna RC transakce pro detail měsíce."""

    doklad_cislo: str
    doklad_datum: date
    partner_nazev: str | None
    zaklad: Money
    dph: Money
    sazba: Decimal


class DphPrehledQuery:
    """Přehled DPH za rok — měsíční sumarizace."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(self, rok: int) -> list[DphMesicItem]:
        """Vrátí 12 položek (leden–prosinec) pro daný rok."""
        uow = self._uow_factory()
        with uow:
            conn = uow.connection

            # RC záznamy: oba účty (MD i Dal) začínají na '343'
            rows = conn.execute(
                """
                SELECT
                    CAST(strftime('%m', uz.datum) AS INTEGER) AS mesic,
                    uz.castka AS dph_halire,
                    uz.doklad_id
                FROM ucetni_zaznamy uz
                WHERE uz.datum >= ? AND uz.datum <= ?
                  AND uz.md_ucet LIKE '343%'
                  AND uz.dal_ucet LIKE '343%'
                  AND uz.je_storno = 0
                ORDER BY mesic
                """,
                (f"{rok}-01-01", f"{rok}-12-31"),
            ).fetchall()

            # Pro každý doklad s RC řádkem, najdi základ
            # (řádky téhož dokladu kde jen jeden účet je 343)
            doklad_ids = {r["doklad_id"] for r in rows}
            zaklady: dict[int, int] = {}  # doklad_id -> zaklad_halire
            if doklad_ids:
                placeholders = ",".join("?" * len(doklad_ids))
                base_rows = conn.execute(
                    f"""
                    SELECT doklad_id, SUM(castka) AS zaklad
                    FROM ucetni_zaznamy
                    WHERE doklad_id IN ({placeholders})
                      AND NOT (md_ucet LIKE '343%' AND dal_ucet LIKE '343%')
                      AND je_storno = 0
                    GROUP BY doklad_id
                    """,
                    tuple(doklad_ids),
                ).fetchall()
                for br in base_rows:
                    zaklady[br["doklad_id"]] = br["zaklad"]

            # Sumarizace po měsících
            mesic_data: dict[int, dict] = {}
            for r in rows:
                m = r["mesic"]
                if m not in mesic_data:
                    mesic_data[m] = {
                        "dph": 0, "zaklad": 0,
                        "doklady": set(),
                    }
                mesic_data[m]["dph"] += r["dph_halire"]
                mesic_data[m]["doklady"].add(r["doklad_id"])

            for m, data in mesic_data.items():
                for did in data["doklady"]:
                    data["zaklad"] += zaklady.get(did, 0)

            # Flag podáno
            podani_rows = conn.execute(
                "SELECT mesic, podano FROM dph_podani WHERE rok = ?",
                (rok,),
            ).fetchall()
            podano_map = {r["mesic"]: bool(r["podano"]) for r in podani_rows}

        result = []
        for mesic in range(1, 13):
            data = mesic_data.get(mesic)
            if data:
                result.append(DphMesicItem(
                    rok=rok,
                    mesic=mesic,
                    zaklad_celkem=Money(data["zaklad"]),
                    dph_celkem=Money(data["dph"]),
                    pocet_transakci=len(data["doklady"]),
                    je_podane=podano_map.get(mesic, False),
                ))
            else:
                result.append(DphMesicItem(
                    rok=rok,
                    mesic=mesic,
                    zaklad_celkem=Money.zero(),
                    dph_celkem=Money.zero(),
                    pocet_transakci=0,
                    je_podane=podano_map.get(mesic, False),
                ))
        return result


class DphMesicDetailQuery:
    """Detail DPH za konkrétní měsíc — seznam transakcí."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(self, rok: int, mesic: int) -> list[DphTransakceItem]:
        """Vrátí RC transakce za daný měsíc."""
        od = f"{rok}-{mesic:02d}-01"
        # Last day of month
        if mesic == 12:
            do = f"{rok}-12-31"
        else:
            do = f"{rok}-{mesic + 1:02d}-01"

        uow = self._uow_factory()
        with uow:
            conn = uow.connection

            # RC záznamy s info o dokladu
            rows = conn.execute(
                """
                SELECT
                    uz.doklad_id,
                    uz.castka AS dph_halire,
                    uz.datum,
                    d.cislo AS doklad_cislo,
                    d.datum_vystaveni,
                    p.nazev AS partner_nazev
                FROM ucetni_zaznamy uz
                JOIN doklady d ON d.id = uz.doklad_id
                LEFT JOIN partneri p ON p.id = d.partner_id
                WHERE uz.datum >= ? AND uz.datum < ?
                  AND uz.md_ucet LIKE '343%'
                  AND uz.dal_ucet LIKE '343%'
                  AND uz.je_storno = 0
                ORDER BY uz.datum, uz.id
                """,
                (od, do),
            ).fetchall()

            # Pro každý doklad, základ
            doklad_ids = {r["doklad_id"] for r in rows}
            zaklady: dict[int, int] = {}
            if doklad_ids:
                placeholders = ",".join("?" * len(doklad_ids))
                base_rows = conn.execute(
                    f"""
                    SELECT doklad_id, SUM(castka) AS zaklad
                    FROM ucetni_zaznamy
                    WHERE doklad_id IN ({placeholders})
                      AND NOT (md_ucet LIKE '343%' AND dal_ucet LIKE '343%')
                      AND je_storno = 0
                    GROUP BY doklad_id
                    """,
                    tuple(doklad_ids),
                ).fetchall()
                for br in base_rows:
                    zaklady[br["doklad_id"]] = br["zaklad"]

        result = []
        for r in rows:
            dph_money = Money(r["dph_halire"])
            zaklad_money = Money(zaklady.get(r["doklad_id"], 0))
            # Compute sazba from dph/zaklad
            if zaklad_money.to_halire() > 0:
                sazba = Decimal(str(
                    round(dph_money.to_halire() * 100 / zaklad_money.to_halire(), 1)
                ))
            else:
                sazba = Decimal("21.0")
            result.append(DphTransakceItem(
                doklad_cislo=r["doklad_cislo"],
                doklad_datum=date.fromisoformat(r["datum"]),
                partner_nazev=r["partner_nazev"],
                zaklad=zaklad_money,
                dph=dph_money,
                sazba=sazba,
            ))
        return result
