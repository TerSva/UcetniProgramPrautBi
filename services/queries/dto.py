"""Read-side DTO — data structures pro queries (předvaha, hlavní kniha).

Frozen dataclasses, žádný přístup do DB. Properties jsou čisté funkce nad daty.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from domain.shared.money import Money
from domain.ucetnictvi.typy import TypUctu


class StranaUctu:
    """Konstanty pro stranu účtu v zápisech."""

    MD = "MD"
    DAL = "DAL"


@dataclass(frozen=True)
class RadekPredvahy:
    """Jeden řádek obratové předvahy = jeden účet."""

    ucet_cislo: str
    ucet_nazev: str
    ucet_typ: TypUctu
    obrat_md: Money
    obrat_dal: Money

    @property
    def saldo(self) -> Money:
        """MD - Dal."""
        return self.obrat_md - self.obrat_dal


@dataclass(frozen=True)
class Predvaha:
    """Obratová předvaha za období."""

    od: date
    do: date
    radky: tuple[RadekPredvahy, ...]

    @property
    def celkem_md(self) -> Money:
        total = Money.zero()
        for r in self.radky:
            total = total + r.obrat_md
        return total

    @property
    def celkem_dal(self) -> Money:
        total = Money.zero()
        for r in self.radky:
            total = total + r.obrat_dal
        return total

    @property
    def je_vyvazena(self) -> bool:
        """Klíčová kontrola — předvaha musí být vyvážená."""
        return self.celkem_md == self.celkem_dal


@dataclass(frozen=True)
class RadekHlavniKnihy:
    """Jeden řádek hlavní knihy = jeden zápis dotýkající se daného účtu."""

    datum: date
    doklad_cislo: str
    doklad_typ: str
    protiucet: str
    strana: str
    castka: Money
    popis: str | None
    zustatek: Money


@dataclass(frozen=True)
class HlavniKniha:
    """Hlavní kniha pro jeden účet za období."""

    ucet_cislo: str
    ucet_nazev: str
    ucet_typ: TypUctu
    od: date
    do: date
    pocatecni_zustatek: Money
    radky: tuple[RadekHlavniKnihy, ...]

    @property
    def koncovy_zustatek(self) -> Money:
        if self.radky:
            return self.radky[-1].zustatek
        return self.pocatecni_zustatek

    @property
    def obrat_md(self) -> Money:
        total = Money.zero()
        for r in self.radky:
            if r.strana == StranaUctu.MD:
                total = total + r.castka
        return total

    @property
    def obrat_dal(self) -> Money:
        total = Money.zero()
        for r in self.radky:
            if r.strana == StranaUctu.DAL:
                total = total + r.castka
        return total
