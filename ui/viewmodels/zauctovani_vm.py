"""ZauctovaniViewModel — prezentační stav pro dialog „Zaúčtovat".

Pure Python, žádný Qt import. Spravuje seznam řádků předpisu
(MD, Dal, castka, popis) a počítá:

* ``soucet_radku`` — Money sum(radky.castka)
* ``rozdil`` — doklad.castka_celkem − soucet_radku
* ``je_podvojne`` — rozdil == 0 (nutná podmínka pro enablované „Zaúčtovat")

Dialog při otevření volá ``load()`` — VM si stáhne účtovou osnovu
(``ucty``) a pre-fillne jeden výchozí řádek s celkovou částkou.

``submit()`` zavolá ``ZauctovatDokladCommand`` a při úspěchu uloží
aktualizovaný DTO do ``posted_item``.

Fáze 11: Reverse charge — checkbox přidá auto DPH řádek 343.100/343.200.
DPH řádky se nepočítají do rozdílu (jsou "navíc" oproti částce dokladu).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Protocol

from domain.doklady.typy import DphRezim, TypDokladu
from domain.shared.money import Money
from services.commands.zauctovat_doklad import (
    ZauctovatDokladInput,
    ZauctovatRadek,
)
from services.queries.doklady_list import DokladyListItem
from services.queries.uctova_osnova import UcetItem

#: Výchozí sazba DPH pro reverse charge.
DEFAULT_DPH_SAZBA = Decimal("21")

#: Dostupné sazby DPH.
DPH_SAZBY: tuple[Decimal, ...] = (
    Decimal("21"), Decimal("15"), Decimal("10"), Decimal("0"),
)

#: Účty pro RC DPH.
RC_MD_UCET = "343.100"
RC_DAL_UCET = "343.200"


@dataclass(frozen=True)
class PredpisRadek:
    """Jeden řádek v UI. Mutace přes ``update_row`` (vytvoří novou instanci).

    ``md_ucet`` / ``dal_ucet`` — prázdný string = ještě nevybráno.
    """

    md_ucet: str = ""
    dal_ucet: str = ""
    castka: Money = Money.zero()
    popis: str = ""


class _UctovaOsnovaQuery(Protocol):
    def execute(self, jen_aktivni: bool = True) -> list[UcetItem]: ...


class _ZauctovatCommand(Protocol):
    def execute(self, data: ZauctovatDokladInput) -> DokladyListItem: ...


class ZauctovaniViewModel:
    """ViewModel pro zaúčtování dialog."""

    def __init__(
        self,
        doklad: DokladyListItem,
        uctova_osnova_query: _UctovaOsnovaQuery,
        zauctovat_command: _ZauctovatCommand,
        prefill_dal_ucet: str | None = None,
    ) -> None:
        self._doklad = doklad
        self._osnova_query = uctova_osnova_query
        self._zauctovat_cmd = zauctovat_command
        self._prefill_dal_ucet = prefill_dal_ucet

        self._ucty: list[UcetItem] = []
        self._radky: list[PredpisRadek] = []
        self._datum: date = doklad.datum_vystaveni
        self._posted_item: DokladyListItem | None = None
        self._error: str | None = None
        self._loaded: bool = False
        self._reverse_charge: bool = False
        self._dph_sazba: Decimal = DEFAULT_DPH_SAZBA

    # ─── Read-only state ──────────────────────────────────────────────

    @property
    def doklad(self) -> DokladyListItem:
        return self._doklad

    @property
    def ucty(self) -> list[UcetItem]:
        """Aktivní účty osnovy (seřazené ASC)."""
        return self._ucty

    @property
    def radky(self) -> list[PredpisRadek]:
        """Aktuální seznam řádků předpisu."""
        return list(self._radky)

    @property
    def datum(self) -> date:
        """Datum účetního případu. Default = datum_vystaveni dokladu."""
        return self._datum

    @property
    def posted_item(self) -> DokladyListItem | None:
        return self._posted_item

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def reverse_charge(self) -> bool:
        return self._reverse_charge

    @property
    def dph_sazba(self) -> Decimal:
        return self._dph_sazba

    @property
    def show_reverse_charge(self) -> bool:
        """RC checkbox viditelný jen pro FP."""
        return self._doklad.typ == TypDokladu.FAKTURA_PRIJATA

    @property
    def dph_castka(self) -> Money:
        """Vypočtená DPH z castka_celkem dokladu."""
        if self._dph_sazba == Decimal("0"):
            return Money.zero()
        halire = self._doklad.castka_celkem.to_halire()
        dph_halire = round(halire * int(self._dph_sazba) / 100)
        return Money(dph_halire)

    # ─── Computed ─────────────────────────────────────────────────────

    @staticmethod
    def _is_dph_row(radek: PredpisRadek) -> bool:
        """True pokud řádek je DPH (oba účty na 343)."""
        return radek.md_ucet.startswith("343") and radek.dal_ucet.startswith("343")

    @property
    def soucet_radku(self) -> Money:
        total = Money.zero()
        for r in self._radky:
            total = total + r.castka
        return total

    @property
    def soucet_zakladnich(self) -> Money:
        """Součet řádků bez DPH (pro podvojnost)."""
        total = Money.zero()
        for r in self._radky:
            if not self._is_dph_row(r):
                total = total + r.castka
        return total

    @property
    def rozdil(self) -> Money:
        """Kolik chybí (kladné) nebo přebývá (záporné) oproti dokladu."""
        return self._doklad.castka_celkem - self.soucet_zakladnich

    @property
    def je_podvojne(self) -> bool:
        return self.soucet_zakladnich == self._doklad.castka_celkem

    @property
    def je_validni(self) -> bool:
        """Všechny podmínky pro umožnění tlačítka „Zaúčtovat"."""
        if not self._radky:
            return False
        if not self.je_podvojne:
            return False
        for r in self._radky:
            if not r.md_ucet or not r.dal_ucet:
                return False
            if r.castka <= Money.zero():
                return False
        return True

    # ─── Commands ─────────────────────────────────────────────────────

    def load(self) -> None:
        """Načti účtovou osnovu a pre-fill jeden řádek s celkovou částkou."""
        try:
            self._ucty = self._osnova_query.execute(jen_aktivni=True)
            self._error = None
        except Exception as exc:  # noqa: BLE001
            self._ucty = []
            self._error = str(exc) or exc.__class__.__name__
        # Pre-fill: jeden prázdný řádek s celkovou částkou (Q4 rozhodnutí).
        if not self._radky:
            if self._doklad.dph_rezim == DphRezim.REVERSE_CHARGE:
                self._prefill_reverse_charge()
            else:
                self._radky.append(PredpisRadek(
                    castka=self._doklad.castka_celkem,
                    dal_ucet=self._prefill_dal_ucet or "",
                ))
        self._loaded = True

    def _prefill_reverse_charge(self) -> None:
        """Pre-fill 4 řádky pro reverse charge doklad (FP z EU)."""
        castka = self._doklad.castka_celkem
        # MD 518.200 (IT služby) / Dal 321.002 (závazky EUR)
        self._radky.append(PredpisRadek(
            md_ucet="518.200",
            dal_ucet="321.002",
            castka=castka,
            popis="Služby z EU (reverse charge)",
        ))
        # Zapnout RC → přidá DPH řádek 343.100/343.200
        self._reverse_charge = True
        self._add_dph_row()

    def set_datum(self, datum: date) -> None:
        self._datum = datum

    def set_reverse_charge(self, enabled: bool) -> None:
        """Zapne/vypne reverse charge — přidá/odebere DPH řádek."""
        if enabled == self._reverse_charge:
            return
        self._reverse_charge = enabled
        if enabled:
            self._add_dph_row()
        else:
            self._remove_dph_row()

    def is_doklad_rc(self) -> bool:
        """Vrací True, pokud doklad má režim DPH = REVERSE_CHARGE.

        Používá se pro varování v UI, když uživatel odškrtne RC checkbox
        u dokladu, který je RC-flaggovaný.
        """
        return self._doklad.dph_rezim == DphRezim.REVERSE_CHARGE

    def set_dph_sazba(self, sazba: Decimal) -> None:
        """Změní sazbu DPH a přepočítá DPH řádek."""
        self._dph_sazba = sazba
        if self._reverse_charge:
            self._update_dph_row_castka()

    def _add_dph_row(self) -> None:
        """Přidá RC DPH řádek na konec."""
        self._radky.append(PredpisRadek(
            md_ucet=RC_MD_UCET,
            dal_ucet=RC_DAL_UCET,
            castka=self.dph_castka,
            popis="DPH reverse charge",
        ))

    def _remove_dph_row(self) -> None:
        """Odebere RC DPH řádek (hledá oba účty 343)."""
        for i in range(len(self._radky) - 1, -1, -1):
            if self._is_dph_row(self._radky[i]):
                self._radky.pop(i)
                break

    def _update_dph_row_castka(self) -> None:
        """Přepočítá částku DPH řádku po změně sazby."""
        for i, r in enumerate(self._radky):
            if self._is_dph_row(r):
                self._radky[i] = replace(r, castka=self.dph_castka)
                break

    def add_row(self) -> None:
        """Přidá nový prázdný řádek s částkou rovnou aktuálnímu rozdílu.

        Když je doklad podvojný, dostane řádek Money.zero() — uživatelka
        ručně upraví.
        """
        castka = self.rozdil if self.rozdil > Money.zero() else Money.zero()
        self._radky.append(PredpisRadek(castka=castka))

    def remove_row(self, index: int) -> None:
        if 0 <= index < len(self._radky):
            self._radky.pop(index)

    def update_row(
        self,
        index: int,
        *,
        md_ucet: str | None = None,
        dal_ucet: str | None = None,
        castka: Money | None = None,
        popis: str | None = None,
    ) -> None:
        """Nahraď řádek novou immutable instancí (jen změněná pole)."""
        if not (0 <= index < len(self._radky)):
            return
        current = self._radky[index]
        kwargs: dict[str, object] = {}
        if md_ucet is not None:
            kwargs["md_ucet"] = md_ucet
        if dal_ucet is not None:
            kwargs["dal_ucet"] = dal_ucet
        if castka is not None:
            kwargs["castka"] = castka
        if popis is not None:
            kwargs["popis"] = popis
        self._radky[index] = replace(current, **kwargs)

    def submit(self) -> DokladyListItem | None:
        """Zaúčtuje doklad. Vrátí DTO nebo None při chybě."""
        if not self.je_validni:
            self._error = "Předpis není validní."
            return None
        try:
            radky = tuple(
                ZauctovatRadek(
                    md_ucet=r.md_ucet,
                    dal_ucet=r.dal_ucet,
                    castka=r.castka,
                    popis=r.popis or None,
                )
                for r in self._radky
            )
            item = self._zauctovat_cmd.execute(ZauctovatDokladInput(
                doklad_id=self._doklad.id,
                datum=self._datum,
                radky=radky,
            ))
            self._posted_item = item
            self._error = None
            return item
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
            return None
