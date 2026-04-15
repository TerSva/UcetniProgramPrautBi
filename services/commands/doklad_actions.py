"""DokladActionsCommand — sada akcí nad existujícím dokladem.

Jedna třída sdružuje mutace, které UI volá z detailu nebo kontextového menu:

* ``stornovat(doklad_id)`` — doménové ``Doklad.stornuj()``.
* ``smazat(doklad_id)`` — repository ``delete()`` (jen NOVY + bez zápisů).
* ``oznac_k_doreseni(doklad_id, poznamka)`` — ``Doklad.oznac_k_doreseni``.
* ``dores(doklad_id)`` — ``Doklad.dores()``.
* ``upravit_popis_a_splatnost(doklad_id, popis, splatnost)`` —
  atomická úprava dvou polí, která entita povoluje (popis kdykoli
  kromě STORNOVANY, splatnost jen NOVY).

Každá metoda běží v jedné transakci. Vrací ``DokladyListItem`` DTO
(kromě ``smazat``, které vrací ``None``).
"""

from __future__ import annotations

from datetime import date
from typing import Callable

from domain.doklady.repository import DokladyRepository
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.doklady_list import DokladyListItem


class DokladActionsCommand:
    """Sada write operací nad existujícím dokladem."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
    ) -> None:
        self._uow_factory = uow_factory
        self._doklady_repo_factory = doklady_repo_factory

    # ── State transitions ──────────────────────────────────────────────

    def stornovat(self, doklad_id: int) -> DokladyListItem:
        """Stornuje doklad (auto-clear k_doreseni). Raises ValidationError."""
        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            doklad = repo.get_by_id(doklad_id)
            doklad.stornuj()
            repo.update(doklad)
            uow.commit()
        return DokladyListItem.from_domain(doklad)

    def smazat(self, doklad_id: int) -> None:
        """Smaže doklad (jen NOVY + bez zápisů). Raises ValidationError."""
        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            repo.delete(doklad_id)
            uow.commit()

    # ── Flag "k dořešení" ──────────────────────────────────────────────

    def oznac_k_doreseni(
        self, doklad_id: int, poznamka: str | None = None
    ) -> DokladyListItem:
        """Nastaví flag k_doreseni=True + volitelnou poznámku."""
        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            doklad = repo.get_by_id(doklad_id)
            doklad.oznac_k_doreseni(poznamka)
            repo.update(doklad)
            uow.commit()
        return DokladyListItem.from_domain(doklad)

    def dores(self, doklad_id: int) -> DokladyListItem:
        """Odznačí flag. Idempotentní."""
        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            doklad = repo.get_by_id(doklad_id)
            doklad.dores()
            repo.update(doklad)
            uow.commit()
        return DokladyListItem.from_domain(doklad)

    # ── Editace ────────────────────────────────────────────────────────

    def upravit_popis_a_splatnost(
        self,
        doklad_id: int,
        popis: str | None,
        splatnost: date | None,
    ) -> DokladyListItem:
        """Atomicky upraví popis + splatnost.

        Popis — povoleno kdykoli kromě STORNOVANY.
        Splatnost — povoleno jen ve stavu NOVY.

        Když je splatnost stejná jako stávající, ``uprav_splatnost`` se
        nezavolá — editovatelné pole u jiného než NOVY stavu je tak bezpečné
        (UI dialog splatnost disabluje, ale double-check je levný).

        Raises:
            ValidationError: popis přes limit, splatnost < datum vystavení,
                doklad STORNOVANY, splatnost měněna ne-NOVY dokladu.
            NotFoundError: doklad neexistuje.
        """
        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            doklad = repo.get_by_id(doklad_id)

            # Popis — vždy aplikuj, entita si hlídá STORNOVANY a délku.
            doklad.uprav_popis(popis)

            # Splatnost — přeskočit no-op, jinak entita zkusí změnit i na
            # stejnou hodnotu a u ne-NOVY dokladu by vyhodila.
            if splatnost != doklad.datum_splatnosti:
                doklad.uprav_splatnost(splatnost)

            repo.update(doklad)
            uow.commit()
        return DokladyListItem.from_domain(doklad)
