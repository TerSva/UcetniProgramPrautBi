"""ChartOfAccountsQuery — strom účtové osnovy pro UI.

Vrací list syntetických účtů seskupených podle tříd, každý se seznamem
svých analytik. Výstup je immutable DTO ``ChartOfAccountsItem``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from domain.ucetnictvi.repository import UctovaOsnovaRepository
from domain.ucetnictvi.typy import TypUctu
from domain.ucetnictvi.ucet import Ucet
from infrastructure.database.unit_of_work import SqliteUnitOfWork


#: Názvy tříd účtů (index = číslo třídy).
TRIDA_NAZVY: dict[int, str] = {
    0: "Dlouhodobý majetek",
    1: "Zásoby",
    2: "Krátkodobý finanční majetek a peněžní prostředky",
    3: "Zúčtovací vztahy",
    4: "Kapitálové účty a dlouhodobé závazky",
    5: "Náklady",
    6: "Výnosy",
    7: "Závěrkové a podrozvahové",
}


@dataclass(frozen=True)
class ChartOfAccountsItem:
    """Jeden účet v osnově (syntetický nebo analytika)."""

    cislo: str
    nazev: str
    typ: TypUctu
    is_active: bool
    is_analytic: bool
    parent_kod: str | None
    popis: str | None
    analytiky: tuple["ChartOfAccountsItem", ...] = field(default_factory=tuple)

    @classmethod
    def from_ucet(
        cls,
        ucet: Ucet,
        analytiky: tuple["ChartOfAccountsItem", ...] = (),
    ) -> "ChartOfAccountsItem":
        return cls(
            cislo=ucet.cislo,
            nazev=ucet.nazev,
            typ=ucet.typ,
            is_active=ucet.je_aktivni,
            is_analytic=ucet.is_analytic,
            parent_kod=ucet.parent_kod,
            popis=ucet.popis,
            analytiky=analytiky,
        )


@dataclass(frozen=True)
class TridaGroup:
    """Skupina účtů jedné třídy (0-7)."""

    trida: int
    nazev: str
    ucty: tuple[ChartOfAccountsItem, ...]
    active_count: int
    total_count: int


class ChartOfAccountsQuery:
    """Vrátí účtovou osnovu jako strom seskupený podle tříd."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        osnova_repo_factory: Callable[
            [SqliteUnitOfWork], UctovaOsnovaRepository
        ],
    ) -> None:
        self._uow_factory = uow_factory
        self._osnova_repo_factory = osnova_repo_factory

    def execute(self, show_inactive: bool = True) -> list[TridaGroup]:
        """Vrátí seznam tříd, každá s účty + analytiky.

        Args:
            show_inactive: True = všechny účty, False = jen aktivní.
        """
        uow = self._uow_factory()
        with uow:
            repo = self._osnova_repo_factory(uow)
            all_ucty = repo.list_all(jen_aktivni=False)

        # Rozděl na syntetické a analytiky
        synteticke: list[Ucet] = []
        analytiky_by_parent: dict[str, list[Ucet]] = {}
        for u in all_ucty:
            if u.is_analytic:
                analytiky_by_parent.setdefault(u.parent_kod, []).append(u)
            else:
                synteticke.append(u)

        # Seskup syntetické podle třídy
        tridy_map: dict[int, list[Ucet]] = {}
        for u in synteticke:
            trida = int(u.cislo[0])
            tridy_map.setdefault(trida, []).append(u)

        result: list[TridaGroup] = []
        for trida_num in sorted(tridy_map.keys()):
            ucty_in_trida = tridy_map[trida_num]
            items: list[ChartOfAccountsItem] = []
            active_count = 0
            total_count = 0

            for u in ucty_in_trida:
                # Získej analytiky pro tento syntetický účet
                child_analytiky = analytiky_by_parent.get(u.cislo, [])
                analytic_items = tuple(
                    ChartOfAccountsItem.from_ucet(a) for a in child_analytiky
                )

                if not show_inactive and not u.je_aktivni and not any(
                    a.is_active for a in analytic_items
                ):
                    continue

                item = ChartOfAccountsItem.from_ucet(u, analytic_items)
                items.append(item)
                total_count += 1
                if u.je_aktivni:
                    active_count += 1

            if items:
                result.append(TridaGroup(
                    trida=trida_num,
                    nazev=TRIDA_NAZVY.get(trida_num, f"Třída {trida_num}"),
                    ucty=tuple(items),
                    active_count=active_count,
                    total_count=total_count,
                ))

        return result
