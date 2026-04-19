"""PrilohaRepository — abstraktní interface pro persistenci příloh.

Definováno v doménové vrstvě. Implementaci dodá infrastruktura.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.doklady.priloha import PrilohaDokladu


class PrilohaRepository(ABC):
    """Repository pro entitu PrilohaDokladu."""

    @abstractmethod
    def add(self, priloha: PrilohaDokladu) -> PrilohaDokladu:
        """Uloží novou přílohu. Vrátí instanci s naplněným id."""

    @abstractmethod
    def list_by_doklad(self, doklad_id: int) -> list[PrilohaDokladu]:
        """Seznam příloh daného dokladu."""

    @abstractmethod
    def get_by_id(self, id: int) -> PrilohaDokladu | None:
        """Vrátí přílohu podle id, nebo None."""

    @abstractmethod
    def delete(self, id: int) -> None:
        """Smaže přílohu z DB."""
