"""DokladByIdQuery — načtení jednoho dokladu jako DTO.

Slouží pro detail dialog a pro refresh UI po mutaci (edit, storno, dořeš).
Vrací stejné ``DokladyListItem`` DTO, jaké používá list, aby UI mohlo
konzistentně pracovat se snapshoty bez ohledu na zdroj.
"""

from __future__ import annotations

from typing import Callable

from domain.doklady.repository import DokladyRepository
from domain.doklady.typy import StavDokladu
from domain.ucetnictvi.repository import UcetniDenikRepository
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.doklady_list import DokladyListItem


class DokladByIdQuery:
    """Read-only query: načte doklad podle id a vrátí DTO.

    Fáze 6.5: Pro STORNOVANY doklad doplní ``datum_storna`` z deníku
    (pokud je injektovaný ``denik_repo_factory``).
    """

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
        denik_repo_factory: Callable[
            [SqliteUnitOfWork], UcetniDenikRepository
        ] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._doklady_repo_factory = doklady_repo_factory
        self._denik_repo_factory = denik_repo_factory

    def execute(self, doklad_id: int) -> DokladyListItem:
        """Vrátí DTO pro doklad s daným id.

        Raises:
            NotFoundError: pokud doklad neexistuje (propagováno z repository).
        """
        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            doklad = repo.get_by_id(doklad_id)

            datum_storna = None
            if (
                self._denik_repo_factory is not None
                and doklad.stav == StavDokladu.STORNOVANY
            ):
                denik = self._denik_repo_factory(uow)
                zaznamy = denik.list_by_doklad(doklad_id)
                storno = next(
                    (z for z in zaznamy if z.je_storno), None,
                )
                datum_storna = storno.datum if storno is not None else None

        return DokladyListItem.from_domain(doklad, datum_storna=datum_storna)
