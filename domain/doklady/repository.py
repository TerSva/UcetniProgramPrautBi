"""DokladyRepository — abstraktní interface pro persistenci dokladů.

Definováno v doménové vrstvě. Implementaci dodá infrastruktura.
Žádný import z infrastructure/ — inverze závislostí.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu


class DokladyRepository(ABC):
    """Abstraktní repository pro doklady.

    Žádné delete() — účetní data se NIKDY nemažou.
    Storno přes stavový stroj entity.
    """

    @abstractmethod
    def add(self, doklad: Doklad) -> Doklad:
        """Uloží nový doklad. Vrátí Doklad s naplněným id.

        Raise ConflictError pokud cislo už existuje.
        Raise ValidationError pokud doklad už má id.
        """

    @abstractmethod
    def update(self, doklad: Doklad) -> None:
        """Aktualizuje existující doklad.

        Raise ValidationError pokud doklad nemá id.
        Raise NotFoundError pokud id neexistuje v DB.
        """

    @abstractmethod
    def get_by_id(self, doklad_id: int) -> Doklad:
        """Vrátí doklad. Raise NotFoundError pokud neexistuje."""

    @abstractmethod
    def get_by_cislo(self, cislo: str) -> Doklad:
        """Vrátí doklad podle čísla. Raise NotFoundError pokud neexistuje."""

    @abstractmethod
    def existuje_cislo(self, cislo: str) -> bool:
        """True pokud doklad s daným číslem už existuje."""

    @abstractmethod
    def list_by_typ(
        self, typ: TypDokladu, limit: int = 100, offset: int = 0
    ) -> list[Doklad]:
        """Seznam dokladů daného typu, sestupně podle datum_vystaveni."""

    @abstractmethod
    def list_by_stav(
        self, stav: StavDokladu, limit: int = 100, offset: int = 0
    ) -> list[Doklad]:
        """Seznam dokladů v daném stavu, sestupně podle datum_vystaveni."""

    @abstractmethod
    def list_by_obdobi(
        self, od: date, do: date, limit: int = 1000, offset: int = 0
    ) -> list[Doklad]:
        """Doklady s datum_vystaveni v intervalu [od, do], sestupně."""
