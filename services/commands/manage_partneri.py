"""ManagePartneriCommand — CRUD operace nad partnery."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable

from domain.partneri.partner import KategoriePartnera, Partner
from domain.partneri.repository import PartneriRepository
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class ManagePartneriCommand:
    """Create, update, deactivate, reactivate partnerů."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        partneri_repo_factory: Callable[[SqliteUnitOfWork], PartneriRepository],
    ) -> None:
        self._uow_factory = uow_factory
        self._partneri_repo_factory = partneri_repo_factory

    def create(
        self,
        nazev: str,
        kategorie: KategoriePartnera,
        ico: str | None = None,
        dic: str | None = None,
        adresa: str | None = None,
        bankovni_ucet: str | None = None,
        email: str | None = None,
        telefon: str | None = None,
        poznamka: str | None = None,
        podil_procent: Decimal | None = None,
        ucet_pohledavka: str | None = None,
        ucet_zavazek: str | None = None,
    ) -> Partner:
        """Vytvoří nového partnera. Doménová validace proběhne v konstruktoru."""
        partner = Partner(
            nazev=nazev,
            kategorie=kategorie,
            ico=ico,
            dic=dic,
            adresa=adresa,
            bankovni_ucet=bankovni_ucet,
            email=email,
            telefon=telefon,
            poznamka=poznamka,
            podil_procent=podil_procent,
            ucet_pohledavka=ucet_pohledavka,
            ucet_zavazek=ucet_zavazek,
        )
        uow = self._uow_factory()
        with uow:
            repo = self._partneri_repo_factory(uow)
            saved = repo.add(partner)
            uow.commit()
        return saved

    def update(
        self,
        partner_id: int,
        nazev: str | None = None,
        kategorie: KategoriePartnera | None = None,
        ico: str | None = ...,  # type: ignore[assignment]
        dic: str | None = ...,  # type: ignore[assignment]
        adresa: str | None = ...,  # type: ignore[assignment]
        bankovni_ucet: str | None = ...,  # type: ignore[assignment]
        email: str | None = ...,  # type: ignore[assignment]
        telefon: str | None = ...,  # type: ignore[assignment]
        poznamka: str | None = ...,  # type: ignore[assignment]
        podil_procent: Decimal | None = ...,  # type: ignore[assignment]
        ucet_pohledavka: str | None = ...,  # type: ignore[assignment]
        ucet_zavazek: str | None = ...,  # type: ignore[assignment]
    ) -> None:
        uow = self._uow_factory()
        with uow:
            repo = self._partneri_repo_factory(uow)
            partner = repo.get_by_id(partner_id)
            partner.uprav(
                nazev=nazev,
                kategorie=kategorie,
                ico=ico,
                dic=dic,
                adresa=adresa,
                bankovni_ucet=bankovni_ucet,
                email=email,
                telefon=telefon,
                poznamka=poznamka,
                podil_procent=podil_procent,
                ucet_pohledavka=ucet_pohledavka,
                ucet_zavazek=ucet_zavazek,
            )
            repo.update(partner)
            uow.commit()

    def deactivate(self, partner_id: int) -> None:
        """Soft delete partnera."""
        uow = self._uow_factory()
        with uow:
            repo = self._partneri_repo_factory(uow)
            partner = repo.get_by_id(partner_id)
            partner.deaktivuj()
            repo.update(partner)
            uow.commit()

    def reactivate(self, partner_id: int) -> None:
        uow = self._uow_factory()
        with uow:
            repo = self._partneri_repo_factory(uow)
            partner = repo.get_by_id(partner_id)
            partner.reaktivuj()
            repo.update(partner)
            uow.commit()
