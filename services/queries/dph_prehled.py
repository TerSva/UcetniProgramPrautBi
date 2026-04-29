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


def _classify_sazba(zaklad: Money, dph: Money) -> Decimal:
    """Klasifikuje skutečnou DPH sazbu na 21 nebo 12 podle poměru.

    Tolerance ±0.5 procentního bodu pokrývá zaokrouhlování při zaúčtování.
    Pokud poměr neodpovídá ani 21 ani 12, vrátí 0 (neklasifikováno).
    """
    if zaklad.to_halire() <= 0:
        return Decimal("21.0")
    ratio = Decimal(dph.to_halire()) / Decimal(zaklad.to_halire())
    if abs(ratio - Decimal("0.21")) < Decimal("0.005"):
        return Decimal("21.0")
    if abs(ratio - Decimal("0.12")) < Decimal("0.005"):
        return Decimal("12.0")
    return Decimal("21.0")


@dataclass(frozen=True)
class DphPriznaniRadky:
    """Řádky přiznání k DPH (formulář EPO) pro identifikovanou osobu.

    Zachycuje všech 11 řádků relevantních pro §6g osobu — i prázdné
    (pro 12% sazbu i ř. 7 zboží), aby šel kompletní formulář předat.
    """

    rok: int
    mesic: int
    radek_7_zbozi_jcs: Money
    radek_9_sluzby_jcs: Money
    radek_10_sluzby_21: Money
    radek_11_sluzby_12: Money
    radek_43_zaklad_21: Money
    radek_44_dph_21: Money
    radek_47_zaklad_12: Money
    radek_48_dph_12: Money
    radek_62_celkova_dan: Money
    radek_64_odpocet: Money
    radek_66_dan_povinnost: Money

    @classmethod
    def from_transakce(
        cls,
        rok: int,
        mesic: int,
        transakce: list["DphTransakceItem"],
    ) -> "DphPriznaniRadky":
        """Spočítá řádky přiznání ze seznamu RC transakcí za měsíc.

        Identifikovaná osoba: ř. 64 (odpočet) je vždy 0 — to je
        vlastní podstata jejího statusu (na rozdíl od plátce DPH).
        """
        zaklad_21 = Money.zero()
        dph_21 = Money.zero()
        zaklad_12 = Money.zero()
        dph_12 = Money.zero()

        for t in transakce:
            if t.sazba == Decimal("12.0"):
                zaklad_12 = zaklad_12 + t.zaklad
                dph_12 = dph_12 + t.dph
            else:
                zaklad_21 = zaklad_21 + t.zaklad
                dph_21 = dph_21 + t.dph

        sluzby_celkem = zaklad_21 + zaklad_12
        celkova_dan = dph_21 + dph_12
        odpocet = Money.zero()
        dan_povinnost = celkova_dan - odpocet

        return cls(
            rok=rok,
            mesic=mesic,
            radek_7_zbozi_jcs=Money.zero(),
            radek_9_sluzby_jcs=sluzby_celkem,
            radek_10_sluzby_21=zaklad_21,
            radek_11_sluzby_12=zaklad_12,
            radek_43_zaklad_21=zaklad_21,
            radek_44_dph_21=dph_21,
            radek_47_zaklad_12=zaklad_12,
            radek_48_dph_12=dph_12,
            radek_62_celkova_dan=celkova_dan,
            radek_64_odpocet=odpocet,
            radek_66_dan_povinnost=dan_povinnost,
        )

    def to_epo_text(self) -> str:
        """Formát pro vložení do EPO portálu — celé Kč, řádek po řádku.

        EPO formulář vyžaduje celá Kč (žádné haléře). Zaokrouhlování:
        ROUND_HALF_UP (matematické). Vynechány nulové řádky kromě
        ř. 64/66 — uživatel potřebuje vidět i nulu (potvrzení 0 odpočtu).
        """
        def kc(m: Money) -> int:
            from decimal import Decimal as _D, ROUND_HALF_UP, localcontext
            with localcontext() as ctx:
                ctx.rounding = ROUND_HALF_UP
                return int(_D(m.to_halire()).scaleb(-2).quantize(_D("1")))

        lines: list[str] = []
        if self.radek_7_zbozi_jcs.to_halire() > 0:
            lines.append(f"Řádek 7: {kc(self.radek_7_zbozi_jcs)}")
        if self.radek_9_sluzby_jcs.to_halire() > 0:
            lines.append(f"Řádek 9: {kc(self.radek_9_sluzby_jcs)}")
        if self.radek_10_sluzby_21.to_halire() > 0:
            lines.append(f"Řádek 10: {kc(self.radek_10_sluzby_21)}")
        if self.radek_11_sluzby_12.to_halire() > 0:
            lines.append(f"Řádek 11: {kc(self.radek_11_sluzby_12)}")
        if self.radek_43_zaklad_21.to_halire() > 0:
            lines.append(f"Řádek 43: {kc(self.radek_43_zaklad_21)}")
        if self.radek_44_dph_21.to_halire() > 0:
            lines.append(f"Řádek 44: {kc(self.radek_44_dph_21)}")
        if self.radek_47_zaklad_12.to_halire() > 0:
            lines.append(f"Řádek 47: {kc(self.radek_47_zaklad_12)}")
        if self.radek_48_dph_12.to_halire() > 0:
            lines.append(f"Řádek 48: {kc(self.radek_48_dph_12)}")
        if self.radek_62_celkova_dan.to_halire() > 0:
            lines.append(f"Řádek 62: {kc(self.radek_62_celkova_dan)}")
        # 64 a 66 vždy — i nula je informace pro identifikovanou osobu
        lines.append(f"Řádek 64: {kc(self.radek_64_odpocet)}")
        lines.append(f"Řádek 66: {kc(self.radek_66_dan_povinnost)}")
        return "\n".join(lines)


@dataclass(frozen=True)
class ViesItem:
    """Jeden řádek souhrnného hlášení (poskytnutá služba do EU)."""

    doklad_cislo: str
    doklad_datum: date
    partner_nazev: str | None
    partner_dic: str | None
    zaklad: Money


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
            sazba = _classify_sazba(zaklad_money, dph_money)
            result.append(DphTransakceItem(
                doklad_cislo=r["doklad_cislo"],
                doklad_datum=date.fromisoformat(r["datum"]),
                partner_nazev=r["partner_nazev"],
                zaklad=zaklad_money,
                dph=dph_money,
                sazba=sazba,
            ))
        return result


class DphPriznaniQuery:
    """Vrátí řádky přiznání k DPH za měsíc (formát EPO)."""

    def __init__(
        self,
        detail_query: "DphMesicDetailQuery",
    ) -> None:
        self._detail_query = detail_query

    def execute(self, rok: int, mesic: int) -> DphPriznaniRadky:
        transakce = self._detail_query.execute(rok, mesic)
        return DphPriznaniRadky.from_transakce(rok, mesic, transakce)


class ViesQuery:
    """Souhrnné hlášení (VIES) — poskytnuté služby do EU.

    Vrátí FV s dph_rezim=REVERSE_CHARGE za rok. Pro identifikovanou
    osobu, která POSKYTLA službu do EU (§102 ZDPH).
    """

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(self, rok: int) -> list[ViesItem]:
        uow = self._uow_factory()
        with uow:
            conn = uow.connection
            rows = conn.execute(
                """
                SELECT d.cislo, d.datum_vystaveni, d.castka_celkem,
                       p.nazev AS partner_nazev,
                       p.dic AS partner_dic
                FROM doklady d
                LEFT JOIN partneri p ON p.id = d.partner_id
                WHERE d.dph_rezim = 'REVERSE_CHARGE'
                  AND d.typ = 'FV'
                  AND d.stav IN ('zauctovany', 'uhrazeny',
                                 'castecne_uhrazeny')
                  AND d.datum_vystaveni >= ?
                  AND d.datum_vystaveni <= ?
                ORDER BY d.datum_vystaveni, d.cislo
                """,
                (f"{rok}-01-01", f"{rok}-12-31"),
            ).fetchall()

        return [
            ViesItem(
                doklad_cislo=r["cislo"],
                doklad_datum=date.fromisoformat(r["datum_vystaveni"]),
                partner_nazev=r["partner_nazev"],
                partner_dic=r["partner_dic"],
                zaklad=Money(r["castka_celkem"]),
            )
            for r in rows
        ]
