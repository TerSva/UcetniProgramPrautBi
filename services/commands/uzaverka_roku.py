"""UzaverkaRokuCommand — vystaví uzavírací doklady Z1/Z2/Z3 k 31.12.{rok}.

Idempotentní service co převede výsledkovky → 710.100, VH → 431.100,
rozvahové účty → 702.100. Všechny doklady mají je_zaverka=True.

Konzistentní s VykazyQuery — používá `_nacti_obraty_a_ps(vcetne_zaverky=False)`
pro výpočet sald, takže neguje žádné předchozí uzavírací pokusy a netříští
storno protizápisy (rušení je_storno zápisů zachováno).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.errors import ConflictError
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.vykazy_query import VykazyQuery


UCET_702 = "702.100"  # Konečný účet rozvažný
UCET_710 = "710.100"  # Účet zisku a ztráty
UCET_431 = "431.100"  # VH ve schvalovacím řízení


@dataclass(frozen=True)
class UzaverkaResult:
    """Výsledek roční uzávěrky."""

    rok: int
    z1_doklad_id: int
    z2_doklad_id: int
    z3_doklad_id: int
    vh: Money
    """Hospodářský výsledek roku. Kladný = zisk, záporný = ztráta."""
    z1_castka: Money
    """Suma jedné strany Z1 (= součet nákladů + výnosů)."""
    z3_castka: Money
    """Suma jedné strany Z3 (= aktiva + |VH ztráty|, nebo pasiva)."""


class UzaverkaRokuCommand:
    """Vystaví uzavírací doklady Z1/Z2/Z3 pro daný rok.

    Použití přes VykazyQuery (čtení obratů s je_storno protizápisy
    a bez závěrkových z dřívějších pokusů) → konzistence s výkazy.
    """

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        vykazy_query: VykazyQuery,
    ) -> None:
        self._uow_factory = uow_factory
        self._vykazy = vykazy_query

    def execute(self, rok: int) -> UzaverkaResult:
        """Vystaví Z1/Z2/Z3 pro rok. Idempotentní — pokud existují, raise.

        Postup:
          1. Idempotence check (ID-{rok}-Z1 v DB → ConflictError).
          2. Zajistit účty 702.100, 710.100, 431.100.
          3. Načíst obraty (bez závěrkových) přes _nacti_obraty_a_ps.
          4. Z1: 5xx/6xx → 710.100 (datum 31.12.rok, je_zaverka=True).
          5. Z2: VH 710.100 → 431.100.
          6. Z3: rozvahové (A/P včetně 431) → 702.100.
        """
        # 1. Idempotence
        uow_c = self._uow_factory()
        with uow_c:
            existing = uow_c.connection.execute(
                "SELECT cislo FROM doklady WHERE cislo LIKE ?",
                (f"ID-{rok}-Z%",),
            ).fetchall()
            if existing:
                cisla = [r["cislo"] for r in existing]
                raise ConflictError(
                    f"Uzávěrka pro rok {rok} už existuje "
                    f"({len(cisla)} dokladů: {', '.join(cisla)})."
                )

        # 2. Zajistit závěrkové účty (idempotentně)
        self._zajistit_ucty()

        # 3. Načíst obraty (bez závěrkových z případných předchozích pokusů)
        ucty = self._vykazy._nacti_obraty_a_ps(rok, vcetne_zaverky=False)

        datum = date(rok, 12, 31)

        # 4. Z1 — výsledkovky → 710.100
        z1_id, z1_castka, vh = self._vystavit_z1(rok, datum, ucty)

        # 5. Z2 — VH → 431.100
        z2_id = self._vystavit_z2(rok, datum, vh)

        # 6. Z3 — rozvahové → 702.100 (po Z2 přibyl pohyb na 431)
        z3_id, z3_castka = self._vystavit_z3(rok, datum, ucty, vh)

        return UzaverkaResult(
            rok=rok,
            z1_doklad_id=z1_id,
            z2_doklad_id=z2_id,
            z3_doklad_id=z3_id,
            vh=vh,
            z1_castka=z1_castka,
            z3_castka=z3_castka,
        )

    def _zajistit_ucty(self) -> None:
        uow = self._uow_factory()
        with uow:
            uow.connection.execute(
                "INSERT OR IGNORE INTO uctova_osnova "
                "(cislo, nazev, typ, parent_kod, je_aktivni) "
                "VALUES ('702.100', 'Konečný účet rozvažný', 'Z', '702', 1)"
            )
            uow.connection.execute(
                "INSERT OR IGNORE INTO uctova_osnova "
                "(cislo, nazev, typ, parent_kod, je_aktivni) "
                "VALUES ('710.100', 'Účet zisku a ztráty', 'Z', '710', 1)"
            )
            uow.connection.execute(
                "INSERT OR IGNORE INTO uctova_osnova "
                "(cislo, nazev, typ, parent_kod, je_aktivni) "
                "VALUES ('431.100', "
                "'Výsledek hospodaření ve schvalovacím řízení', "
                "'P', '431', 1)"
            )
            uow.commit()

    def _vystavit_z1(
        self, rok: int, datum: date, ucty: dict,
    ) -> tuple[int, Money, Money]:
        """Z1: 5xx → MD 710.100 / DAL 5xx, 6xx → MD 6xx / DAL 710.100.

        Vrátí (doklad_id, castka_celkem dokladu, VH).
        """
        zaznamy_md_dal: list[tuple[str, str, int]] = []
        naklady_celkem = 0
        vynosy_celkem = 0

        for cislo, data in sorted(ucty.items()):
            md = data["obrat_md"]
            dal = data["obrat_dal"]
            typ = data["typ"]
            if typ == "N":
                saldo = md - dal
                if saldo == 0:
                    continue
                naklady_celkem += saldo
                if saldo > 0:
                    zaznamy_md_dal.append((UCET_710, cislo, saldo))
                else:
                    # Záporný saldo nákladu (anomálie) — opačně
                    zaznamy_md_dal.append((cislo, UCET_710, -saldo))
            elif typ == "V":
                saldo = dal - md
                if saldo == 0:
                    continue
                vynosy_celkem += saldo
                if saldo > 0:
                    zaznamy_md_dal.append((cislo, UCET_710, saldo))
                else:
                    zaznamy_md_dal.append((UCET_710, cislo, -saldo))

        vh = Money(vynosy_celkem - naklady_celkem)
        castka_celkem_hal = sum(hal for _, _, hal in zaznamy_md_dal)

        return (
            self._vystavit_doklad(
                rok=rok, suffix="Z1", datum=datum,
                castka_celkem_hal=castka_celkem_hal,
                popis=(
                    f"Uzavírací doklad výsledkových účtů k 31.12.{rok}. "
                    f"Převod nákladů a výnosů na účet 710.100 "
                    f"(Účet zisku a ztráty)."
                ),
                zaznamy_md_dal=zaznamy_md_dal,
                zapis_popis="Uzavření výsledkovky",
            ),
            Money(castka_celkem_hal),
            vh,
        )

    def _vystavit_z2(self, rok: int, datum: date, vh: Money) -> int:
        """Z2: VH 710.100 → 431.100. Ztráta = MD 431/DAL 710, zisk opačně."""
        if vh.is_zero:
            # Edge case: rok bez nákladů ani výnosů — Z2 je no-op
            # ale musí existovat pro idempotence řetězec
            zaznamy_md_dal = []
            popis = f"Převod VH za rok {rok} (0 Kč — bez výnosů a nákladů)."
        elif vh.is_positive:  # zisk
            zaznamy_md_dal = [(UCET_710, UCET_431, vh.to_halire())]
            popis = (
                f"Převod hospodářského výsledku {rok} z 710.100 na 431.100. "
                f"Zisk {vh.format_cz()}. Zápis MD 710.100 / DAL 431.100."
            )
        else:  # ztráta
            zaznamy_md_dal = [(UCET_431, UCET_710, abs(vh).to_halire())]
            popis = (
                f"Převod hospodářského výsledku {rok} z 710.100 na 431.100. "
                f"Ztráta {abs(vh).format_cz()}. "
                f"Zápis MD 431.100 / DAL 710.100."
            )

        castka_hal = abs(vh).to_halire() if zaznamy_md_dal else 0
        return self._vystavit_doklad(
            rok=rok, suffix="Z2", datum=datum,
            castka_celkem_hal=castka_hal,
            popis=popis,
            zaznamy_md_dal=zaznamy_md_dal,
            zapis_popis="Převod VH na 431",
        )

    def _vystavit_z3(
        self, rok: int, datum: date, ucty: dict, vh: Money,
    ) -> tuple[int, Money]:
        """Z3: rozvahové A/P → 702.100. Včetně 431.100 po Z2.

        Konstrukce zápisů:
        - A účet kladné MD-DAL (běžný stav): MD 702 / DAL A
        - A účet záporné MD-DAL (anomálie): MD A / DAL 702
        - P účet kladné DAL-MD (běžný stav): MD P / DAL 702
        - P účet záporné DAL-MD (anomálie): MD 702 / DAL P
        - 431 po Z2:
            * zisk vh>0: 431 má DAL → uzavřít: MD 431 / DAL 702
            * ztráta vh<0: 431 má MD → uzavřít: MD 702 / DAL 431
        """
        zaznamy_md_dal: list[tuple[str, str, int]] = []
        suma_md = 0
        suma_dal = 0

        for cislo, data in sorted(ucty.items()):
            md = data["obrat_md"]
            dal = data["obrat_dal"]
            typ = data["typ"]
            if cislo == UCET_431:
                # 431 řešíme samostatně níže (po Z2)
                continue
            if typ == "A":
                saldo = md - dal
                if saldo == 0:
                    continue
                if saldo > 0:
                    zaznamy_md_dal.append((UCET_702, cislo, saldo))
                    suma_md += saldo
                else:
                    zaznamy_md_dal.append((cislo, UCET_702, -saldo))
                    suma_dal += -saldo
            elif typ == "P":
                saldo = dal - md
                if saldo == 0:
                    continue
                if saldo > 0:
                    zaznamy_md_dal.append((cislo, UCET_702, saldo))
                    suma_dal += saldo
                else:
                    zaznamy_md_dal.append((UCET_702, cislo, -saldo))
                    suma_md += -saldo

        # 431.100 po Z2:
        # suma_md a suma_dal sledují strany 702: kolik MD 702 (vyrovná aktiva)
        # vs DAL 702 (vyrovná pasiva). Pro 431 platí:
        # - zisk: (MD 431, DAL 702) → 702 dostává DAL → suma_dal += x
        # - ztráta: (MD 702, DAL 431) → 702 dostává MD → suma_md += x
        if not vh.is_zero:
            castka_431 = abs(vh).to_halire()
            if vh.is_positive:
                # zisk: 431 má DAL zůstatek → uzavírací: MD 431 / DAL 702
                zaznamy_md_dal.append((UCET_431, UCET_702, castka_431))
                suma_dal += castka_431
            else:
                # ztráta: 431 má MD zůstatek → uzavírací: MD 702 / DAL 431
                zaznamy_md_dal.append((UCET_702, UCET_431, castka_431))
                suma_md += castka_431

        if suma_md != suma_dal:
            from domain.shared.errors import ValidationError
            raise ValidationError(
                f"Z3 nebilancuje: MD {suma_md/100:.2f} ≠ "
                f"DAL {suma_dal/100:.2f}"
            )

        castka_celkem_hal = suma_md + suma_dal
        return (
            self._vystavit_doklad(
                rok=rok, suffix="Z3", datum=datum,
                castka_celkem_hal=castka_celkem_hal,
                popis=(
                    f"Uzavírací doklad rozvahových účtů k 31.12.{rok} na "
                    f"702.100 (Konečný účet rozvažný). Aktiva, pasiva "
                    f"vč. 431.100 po převodu VH."
                ),
                zaznamy_md_dal=zaznamy_md_dal,
                zapis_popis="Uzavření rozvahy",
            ),
            Money(suma_md),
        )

    def _vystavit_doklad(
        self,
        rok: int,
        suffix: str,
        datum: date,
        castka_celkem_hal: int,
        popis: str,
        zaznamy_md_dal: list[tuple[str, str, int]],
        zapis_popis: str,
    ) -> int:
        """Vytvoří ID-{rok}-{suffix} doklad s je_zaverka=True a zápisy."""
        cislo = f"ID-{rok}-{suffix}"
        # Doklad.popis limit 500
        popis = popis[:500]

        uow = self._uow_factory()
        with uow:
            drepo = SqliteDokladyRepository(uow)
            doklad = Doklad(
                cislo=cislo,
                typ=TypDokladu.INTERNI_DOKLAD,
                datum_vystaveni=datum,
                castka_celkem=Money(castka_celkem_hal),
                popis=popis,
                je_zaverka=True,
            )
            drepo.add(doklad)
            loaded = drepo.get_by_cislo(cislo)

            if zaznamy_md_dal:
                denik = SqliteUcetniDenikRepository(uow)
                zaznamy = tuple(
                    UcetniZaznam(
                        doklad_id=loaded.id, datum=datum,
                        md_ucet=md, dal_ucet=dal, castka=Money(hal),
                        popis=zapis_popis,
                    )
                    for md, dal, hal in zaznamy_md_dal
                )
                denik.zauctuj(UctovyPredpis(
                    doklad_id=loaded.id, zaznamy=zaznamy,
                ))

            loaded.zauctuj()
            drepo.update(loaded)
            uow.commit()
            return loaded.id
