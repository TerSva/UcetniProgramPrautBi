"""ZauctovatDokladCommand — thin wrapper nad ZauctovaniDokladuService.

Důvod samostatné třídy: UI dialog dostává seznam řádků (MD, Dal, castka,
popis), ne hotový ``UctovyPredpis``. Command ho sestaví a předá servisu.

Vrací ``DokladyListItem`` DTO po úspěšném zaúčtování — stejný tvar jako
``DokladByIdQuery``, aby UI mohlo jednou logikou obnovit detail.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Sequence

from domain.doklady.repository import DokladyRepository
from domain.shared.money import Money
from domain.ucetnictvi.repository import UcetniDenikRepository
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.doklady_list import DokladyListItem
from services.zauctovani_service import ZauctovaniDokladuService


@dataclass(frozen=True)
class ZauctovatRadek:
    """Jeden řádek účtování v UI — předchůdce UcetniZaznam.

    UI pracuje s ``md_ucet`` + ``dal_ucet`` jako string "311", "601" —
    až command z nich sestaví doménový objekt.
    """

    md_ucet: str
    dal_ucet: str
    castka: Money
    popis: str | None = None


@dataclass(frozen=True)
class ZauctovatDokladInput:
    """Input DTO pro zaúčtování dokladu."""

    doklad_id: int
    datum: date
    radky: Sequence[ZauctovatRadek]


class ZauctovatDokladCommand:
    """Sestaví UctovyPredpis a deleguje na ZauctovaniDokladuService."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
        denik_repo_factory: Callable[[SqliteUnitOfWork], UcetniDenikRepository],
    ) -> None:
        # Znovuvyrobitelná service (stateless) — držet factory je zbytečné,
        # postačí vytvořit přímo.
        self._service = ZauctovaniDokladuService(
            uow_factory=uow_factory,
            doklady_repo_factory=doklady_repo_factory,
            denik_repo_factory=denik_repo_factory,
        )
        self._uow_factory = uow_factory
        self._doklady_repo_factory = doklady_repo_factory

    def execute(self, data: ZauctovatDokladInput) -> DokladyListItem:
        """Zaúčtuje doklad. Vrátí aktuální DTO po změně stavu.

        Raises:
            ValidationError, NotFoundError, PodvojnostError (z service).
        """
        zaznamy = tuple(
            UcetniZaznam(
                doklad_id=data.doklad_id,
                datum=data.datum,
                md_ucet=r.md_ucet,
                dal_ucet=r.dal_ucet,
                castka=r.castka,
                popis=r.popis,
            )
            for r in data.radky
        )
        predpis = UctovyPredpis(doklad_id=data.doklad_id, zaznamy=zaznamy)

        doklad, _zapisy = self._service.zauctuj_doklad(
            doklad_id=data.doklad_id,
            predpis=predpis,
        )
        return DokladyListItem.from_domain(doklad)
