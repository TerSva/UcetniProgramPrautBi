"""UctovaOsnovaQuery — seznam účtů pro dropdowny v UI.

Vrací immutable DTO ``UcetItem`` s display textem ve formátu
``"311 – Odběratelé"``, aby UI nemuselo znát doménovou entitu.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from domain.ucetnictvi.repository import UctovaOsnovaRepository
from domain.ucetnictvi.typy import TypUctu
from domain.ucetnictvi.ucet import Ucet
from infrastructure.database.unit_of_work import SqliteUnitOfWork


@dataclass(frozen=True)
class UcetItem:
    """Jeden řádek účtu — snímek pro UI dropdown."""

    cislo: str
    nazev: str
    typ: TypUctu
    je_danovy: bool | None = None
    popis: str | None = None

    @property
    def display(self) -> str:
        """Formát ``"311 – Odběratelé"`` (pomlčka U+2013).

        Pro nedaňové účty (typ N/V s je_danovy=False) přidá suffix ``(N)``,
        aby uživatelka v dropdownu jasně viděla, že volí nedaňový účet.
        """
        suffix = " (N)" if self.je_danovy is False else ""
        return f"{self.cislo} – {self.nazev}{suffix}"

    @classmethod
    def from_domain(cls, ucet: Ucet) -> "UcetItem":
        return cls(
            cislo=ucet.cislo,
            nazev=ucet.nazev,
            typ=ucet.typ,
            je_danovy=ucet.je_danovy,
            popis=ucet.popis,
        )


class UctovaOsnovaQuery:
    """Read-only query: vrátí aktivní účty účtové osnovy."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        osnova_repo_factory: Callable[
            [SqliteUnitOfWork], UctovaOsnovaRepository
        ],
    ) -> None:
        self._uow_factory = uow_factory
        self._osnova_repo_factory = osnova_repo_factory

    def execute(self, jen_aktivni: bool = True) -> list[UcetItem]:
        """Vrátí seznam účtů setříděný podle čísla (ASC).

        Repository list_all() vrací účty řazené podle čísla — zachováváme.
        """
        uow = self._uow_factory()
        with uow:
            repo = self._osnova_repo_factory(uow)
            ucty = repo.list_all(jen_aktivni=jen_aktivni)

        return [UcetItem.from_domain(u) for u in ucty]
