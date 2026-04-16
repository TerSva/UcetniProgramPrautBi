"""PartneriRepository — abstraktní interface pro persistenci partnerů.

Definováno v doménové vrstvě. Implementaci dodá infrastruktura.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.partneri.partner import KategoriePartnera, Partner


class PartneriRepository(ABC):
    """Repository pro entitu Partner."""

    @abstractmethod
    def add(self, partner: Partner) -> Partner:
        """Uloží nového partnera. Vrátí Partner s naplněným id."""

    @abstractmethod
    def update(self, partner: Partner) -> None:
        """Aktualizuje existujícího partnera."""

    @abstractmethod
    def get_by_id(self, partner_id: int) -> Partner:
        """Vrátí partnera. Raise NotFoundError pokud neexistuje."""

    @abstractmethod
    def get_by_ico(self, ico: str) -> Partner | None:
        """Vrátí partnera podle IČO nebo None."""

    @abstractmethod
    def list_all(
        self,
        kategorie: KategoriePartnera | None = None,
        jen_aktivni: bool = True,
    ) -> list[Partner]:
        """Seznam partnerů s volitelným filtrem."""

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[Partner]:
        """Fulltext search v nazev + ico pro typeahead dropdown."""

    @abstractmethod
    def list_spolecnici(self) -> list[Partner]:
        """Vrátí jen společníky."""
