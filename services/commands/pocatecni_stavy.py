"""PocatecniStavyCommand — správa počátečních stavů + generování ID dokladu 701."""

from __future__ import annotations

from datetime import date
from typing import Callable

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.firma.pocatecni_stav import PocatecniStav
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.pocatecni_stavy_repository import (
    SqlitePocatecniStavyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class PocatecniStavyCommand:
    """Přidání/smazání počátečních stavů + generování ID dokladu."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def pridat(
        self,
        rok: int,
        ucet_kod: str,
        castka: Money,
        strana: str,
        poznamka: str | None = None,
    ) -> PocatecniStav:
        stav = PocatecniStav(
            ucet_kod=ucet_kod,
            castka=castka,
            strana=strana,
            rok=rok,
            poznamka=poznamka,
        )
        uow = self._uow_factory()
        with uow:
            repo = SqlitePocatecniStavyRepository(uow)
            result = repo.add(stav)
            uow.commit()
        return result

    def smazat(self, stav_id: int) -> None:
        uow = self._uow_factory()
        with uow:
            repo = SqlitePocatecniStavyRepository(uow)
            repo.delete(stav_id)
            uow.commit()

    def list_by_rok(self, rok: int) -> list[PocatecniStav]:
        uow = self._uow_factory()
        with uow:
            repo = SqlitePocatecniStavyRepository(uow)
            return repo.list_by_rok(rok)

    def generovat_id_doklad(
        self,
        rok: int,
        datum: date | None = None,
    ) -> int | None:
        """Vytvoří ID doklad 701 (Počáteční účet rozvažný).

        Vrátí ID vytvořeného dokladu nebo None pokud žádné stavy.
        """
        if datum is None:
            datum = date(rok, 1, 1)

        uow = self._uow_factory()
        with uow:
            ps_repo = SqlitePocatecniStavyRepository(uow)
            stavy = ps_repo.list_by_rok(rok)

            if not stavy:
                return None

            drepo = SqliteDokladyRepository(uow)
            denik = SqliteUcetniDenikRepository(uow)

            # Součet pro doklad
            celkem = Money.zero()
            for s in stavy:
                celkem = celkem + s.castka

            cislo = f"ID-{rok}-PS"
            if drepo.existuje_cislo(cislo):
                return None

            doklad = Doklad(
                cislo=cislo,
                typ=TypDokladu.INTERNI_DOKLAD,
                datum_vystaveni=datum,
                castka_celkem=celkem,
                popis=f"Počáteční stavy účtů — rok {rok}",
            )
            drepo.add(doklad)
            loaded = drepo.get_by_cislo(cislo)

            # Účetní zápisy: MD strana → MD účet / Dal 701
            #                 DAL strana → MD 701 / Dal účet
            zaznamy = []
            for s in stavy:
                if s.strana == "MD":
                    zaznamy.append(UcetniZaznam(
                        doklad_id=loaded.id,
                        datum=datum,
                        md_ucet=s.ucet_kod,
                        dal_ucet="701",
                        castka=s.castka,
                        popis=s.poznamka,
                    ))
                else:
                    zaznamy.append(UcetniZaznam(
                        doklad_id=loaded.id,
                        datum=datum,
                        md_ucet="701",
                        dal_ucet=s.ucet_kod,
                        castka=s.castka,
                        popis=s.poznamka,
                    ))

            predpis = UctovyPredpis(
                doklad_id=loaded.id,
                zaznamy=tuple(zaznamy),
            )
            denik.zauctuj(predpis)
            loaded.zauctuj()
            drepo.update(loaded)
            uow.commit()
            return loaded.id
