"""PartneriListQuery + PartneriSearchQuery — seznam a vyhledávání partnerů."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from domain.partneri.partner import KategoriePartnera, Partner
from domain.partneri.repository import PartneriRepository
from infrastructure.database.unit_of_work import SqliteUnitOfWork


@dataclass(frozen=True)
class PartneriListItem:
    """Read-only DTO partnera pro UI."""

    id: int
    nazev: str
    kategorie: KategoriePartnera
    ico: str | None
    dic: str | None
    adresa: str | None
    je_aktivni: bool
    podil_procent: Decimal | None
    bankovni_ucet: str | None = None
    email: str | None = None
    telefon: str | None = None
    poznamka: str | None = None
    ucet_pohledavka: str | None = None
    ucet_zavazek: str | None = None

    @classmethod
    def from_domain(cls, p: Partner) -> PartneriListItem:
        assert p.id is not None
        return cls(
            id=p.id,
            nazev=p.nazev,
            kategorie=p.kategorie,
            ico=p.ico,
            dic=p.dic,
            adresa=p.adresa,
            je_aktivni=p.je_aktivni,
            podil_procent=p.podil_procent,
            bankovni_ucet=p.bankovni_ucet,
            email=p.email,
            telefon=p.telefon,
            poznamka=p.poznamka,
            ucet_pohledavka=p.ucet_pohledavka,
            ucet_zavazek=p.ucet_zavazek,
        )


class PartneriListQuery:
    """Seznam partnerů s volitelným filtrem na kategorii."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        partneri_repo_factory: Callable[[SqliteUnitOfWork], PartneriRepository],
    ) -> None:
        self._uow_factory = uow_factory
        self._partneri_repo_factory = partneri_repo_factory

    def execute(
        self,
        kategorie: KategoriePartnera | None = None,
        jen_aktivni: bool = True,
    ) -> list[PartneriListItem]:
        uow = self._uow_factory()
        with uow:
            repo = self._partneri_repo_factory(uow)
            partneri = repo.list_all(
                kategorie=kategorie, jen_aktivni=jen_aktivni,
            )
        return [PartneriListItem.from_domain(p) for p in partneri]


class PartneriSearchQuery:
    """Pro typeahead dropdown — rychlý search v nazev + ico."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        partneri_repo_factory: Callable[[SqliteUnitOfWork], PartneriRepository],
    ) -> None:
        self._uow_factory = uow_factory
        self._partneri_repo_factory = partneri_repo_factory

    def execute(self, query: str, limit: int = 10) -> list[PartneriListItem]:
        if len(query) < 2:
            return []
        uow = self._uow_factory()
        with uow:
            repo = self._partneri_repo_factory(uow)
            partneri = repo.search(query, limit=limit)
        return [PartneriListItem.from_domain(p) for p in partneri]
