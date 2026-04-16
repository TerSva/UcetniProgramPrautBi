"""Repository interfaces pro účetnictví.

Definováno v doménové vrstvě. Implementaci dodá infrastruktura.
Žádný import z infrastructure/ — inverze závislostí.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from domain.ucetnictvi.typy import TypUctu
from domain.ucetnictvi.ucet import Ucet
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis


class UctovaOsnovaRepository(ABC):
    """Abstraktní repository pro účtovou osnovu."""

    @abstractmethod
    def add(self, ucet: Ucet) -> Ucet:
        """Uloží nový účet. Vrátí Ucet (cislo je PK).

        Raise ConflictError pokud cislo už existuje.
        """

    @abstractmethod
    def update(self, ucet: Ucet) -> None:
        """Aktualizuje existující účet (nazev, je_aktivni).

        Raise NotFoundError pokud cislo neexistuje.
        """

    @abstractmethod
    def get_by_cislo(self, cislo: str) -> Ucet:
        """Vrátí účet. Raise NotFoundError pokud neexistuje."""

    @abstractmethod
    def existuje(self, cislo: str) -> bool:
        """True pokud účet s daným číslem existuje."""

    @abstractmethod
    def list_all(self, jen_aktivni: bool = True) -> list[Ucet]:
        """Seznam všech účtů, volitelně jen aktivních."""

    @abstractmethod
    def list_by_typ(self, typ: TypUctu, jen_aktivni: bool = True) -> list[Ucet]:
        """Seznam účtů daného typu."""

    @abstractmethod
    def get_analytiky(self, parent_kod: str) -> list[Ucet]:
        """Vrátí analytiky daného syntetického účtu (všechny, i neaktivní)."""


class UcetniDenikRepository(ABC):
    """Abstraktní repository pro účetní deník.

    Žádný update() — účetní zápisy jsou immutable.
    Žádný delete() — storno přes opravný doklad.
    """

    @abstractmethod
    def zauctuj(self, predpis: UctovyPredpis) -> tuple[UcetniZaznam, ...]:
        """Atomicky uloží všechny zápisy z předpisu. Vrátí záznamy s id.

        Validuje, že md_ucet a dal_ucet existují v osnově a jsou aktivní.
        Validuje, že doklad_id existuje.
        Raise NotFoundError pokud účet/doklad neexistuje.
        Raise ValidationError pokud účet je deaktivovaný.
        """

    @abstractmethod
    def get_by_id(self, zaznam_id: int) -> UcetniZaznam:
        """Vrátí záznam. Raise NotFoundError pokud neexistuje."""

    @abstractmethod
    def list_by_doklad(self, doklad_id: int) -> tuple[UcetniZaznam, ...]:
        """Všechny zápisy daného dokladu, seřazené podle id."""

    @abstractmethod
    def list_by_obdobi(
        self, od: date, do: date, limit: int = 1000, offset: int = 0
    ) -> tuple[UcetniZaznam, ...]:
        """Zápisy v období [od, do], seřazené podle datum, id."""

    @abstractmethod
    def list_by_ucet(
        self, ucet_cislo: str, od: date, do: date
    ) -> tuple[UcetniZaznam, ...]:
        """Zápisy kde se účet vyskytuje na MD nebo Dal. Seřazené podle datum."""
