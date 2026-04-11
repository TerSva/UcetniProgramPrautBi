"""ZauctovaniDokladuService — orchestrace zaúčtování dokladu.

Tenká service vrstva: ví JAK věci skládat dohromady.
Doménové entity ví JAK věci BÝT (validace, stav, invarianty).
"""

from __future__ import annotations

from typing import Callable, Tuple

from domain.doklady.doklad import Doklad
from domain.doklady.repository import DokladyRepository
from domain.shared.errors import PodvojnostError, ValidationError
from domain.ucetnictvi.repository import UcetniDenikRepository
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class ZauctovaniDokladuService:
    """Atomické zaúčtování dokladu — jedna transakce, vše nebo nic."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
        denik_repo_factory: Callable[[SqliteUnitOfWork], UcetniDenikRepository],
    ) -> None:
        self._uow_factory = uow_factory
        self._doklady_repo_factory = doklady_repo_factory
        self._denik_repo_factory = denik_repo_factory

    def zauctuj_doklad(
        self,
        doklad_id: int,
        predpis: UctovyPredpis,
    ) -> Tuple[Doklad, tuple[UcetniZaznam, ...]]:
        """Atomicky zaúčtuje doklad.

        Raises:
            ValidationError — predpis.doklad_id != doklad_id, nebo špatný stav
            NotFoundError — doklad/účet neexistuje
            PodvojnostError — celková částka předpisu != castka_celkem dokladu
        """
        if predpis.doklad_id != doklad_id:
            raise ValidationError(
                f"Předpis odkazuje na doklad {predpis.doklad_id}, "
                f"ale zaúčtováváme {doklad_id}"
            )

        uow = self._uow_factory()
        with uow:
            doklady_repo = self._doklady_repo_factory(uow)
            denik_repo = self._denik_repo_factory(uow)

            doklad = doklady_repo.get_by_id(doklad_id)

            if doklad.castka_celkem != predpis.celkova_castka:
                raise PodvojnostError(
                    f"Předpis ({predpis.celkova_castka}) nesouhlasí "
                    f"s celkovou částkou dokladu ({doklad.castka_celkem})"
                )

            doklad.zauctuj()

            ulozene = denik_repo.zauctuj(predpis)
            doklady_repo.update(doklad)

            uow.commit()

        return doklad, ulozene
