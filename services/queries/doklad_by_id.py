"""DokladByIdQuery — načtení jednoho dokladu jako DTO.

Slouží pro detail dialog a pro refresh UI po mutaci (edit, storno, dořeš).
Vrací stejné ``DokladyListItem`` DTO, jaké používá list, aby UI mohlo
konzistentně pracovat se snapshoty bez ohledu na zdroj.
"""

from __future__ import annotations

from typing import Callable

from domain.doklady.repository import DokladyRepository
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.doklady_list import DokladyListItem


class DokladByIdQuery:
    """Read-only query: načte doklad podle id a vrátí DTO."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
    ) -> None:
        self._uow_factory = uow_factory
        self._doklady_repo_factory = doklady_repo_factory

    def execute(self, doklad_id: int) -> DokladyListItem:
        """Vrátí DTO pro doklad s daným id.

        Raises:
            NotFoundError: pokud doklad neexistuje (propagováno z repository).
        """
        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            doklad = repo.get_by_id(doklad_id)

        return DokladyListItem.from_domain(doklad)
