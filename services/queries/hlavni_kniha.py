"""HlavniKnihaQuery — hlavní kniha pro jeden účet za období."""

from __future__ import annotations

from datetime import date
from typing import Callable

from domain.doklady.doklad import Doklad
from domain.doklady.repository import DokladyRepository
from domain.shared.money import Money
from domain.ucetnictvi.repository import UcetniDenikRepository, UctovaOsnovaRepository
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.dto import HlavniKniha, RadekHlavniKnihy, StranaUctu


class HlavniKnihaQuery:
    """Hlavní kniha pro jeden účet za období [od, do]."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        denik_repo_factory: Callable[[SqliteUnitOfWork], UcetniDenikRepository],
        osnova_repo_factory: Callable[[SqliteUnitOfWork], UctovaOsnovaRepository],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
    ) -> None:
        self._uow_factory = uow_factory
        self._denik_repo_factory = denik_repo_factory
        self._osnova_repo_factory = osnova_repo_factory
        self._doklady_repo_factory = doklady_repo_factory

    def execute(self, ucet_cislo: str, od: date, do: date) -> HlavniKniha:
        uow = self._uow_factory()
        with uow:
            osnova_repo = self._osnova_repo_factory(uow)
            denik_repo = self._denik_repo_factory(uow)
            doklady_repo = self._doklady_repo_factory(uow)

            ucet = osnova_repo.get_by_cislo(ucet_cislo)

            zaznamy = denik_repo.list_by_ucet(ucet_cislo, od, do)

            # Lazy cache pro doklady
            doklady_cache: dict[int, Doklad] = {}

            def get_doklad(doklad_id: int) -> Doklad:
                if doklad_id not in doklady_cache:
                    doklady_cache[doklad_id] = doklady_repo.get_by_id(doklad_id)
                return doklady_cache[doklad_id]

            zustatek = Money.zero()
            radky = []
            for z in zaznamy:
                doklad = get_doklad(z.doklad_id)

                if z.md_ucet == ucet_cislo:
                    strana = StranaUctu.MD
                    protiucet = z.dal_ucet
                    zustatek = zustatek + z.castka
                else:
                    strana = StranaUctu.DAL
                    protiucet = z.md_ucet
                    zustatek = zustatek - z.castka

                radky.append(RadekHlavniKnihy(
                    datum=z.datum,
                    doklad_cislo=doklad.cislo,
                    doklad_typ=doklad.typ.value,
                    protiucet=protiucet,
                    strana=strana,
                    castka=z.castka,
                    popis=z.popis,
                    zustatek=zustatek,
                ))

        return HlavniKniha(
            ucet_cislo=ucet.cislo,
            ucet_nazev=ucet.nazev,
            ucet_typ=ucet.typ,
            od=od,
            do=do,
            pocatecni_zustatek=Money.zero(),
            radky=tuple(radky),
        )
