"""PredvahaQuery — obratová předvaha za období."""

from __future__ import annotations

from datetime import date
from typing import Callable

from domain.shared.money import Money
from domain.ucetnictvi.repository import UcetniDenikRepository, UctovaOsnovaRepository
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.dto import Predvaha, RadekPredvahy


class PredvahaQuery:
    """Spočítá obratovou předvahu za období [od, do]."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        denik_repo_factory: Callable[[SqliteUnitOfWork], UcetniDenikRepository],
        osnova_repo_factory: Callable[[SqliteUnitOfWork], UctovaOsnovaRepository],
    ) -> None:
        self._uow_factory = uow_factory
        self._denik_repo_factory = denik_repo_factory
        self._osnova_repo_factory = osnova_repo_factory

    def execute(
        self, od: date, do: date, jen_dotcene_ucty: bool = True
    ) -> Predvaha:
        uow = self._uow_factory()
        with uow:
            denik_repo = self._denik_repo_factory(uow)
            osnova_repo = self._osnova_repo_factory(uow)

            zaznamy = denik_repo.list_by_obdobi(od, do, limit=100_000)

            # Agregace obratů
            obrat_md: dict[str, Money] = {}
            obrat_dal: dict[str, Money] = {}
            for z in zaznamy:
                obrat_md[z.md_ucet] = (
                    obrat_md.get(z.md_ucet, Money.zero()) + z.castka
                )
                obrat_dal[z.dal_ucet] = (
                    obrat_dal.get(z.dal_ucet, Money.zero()) + z.castka
                )

            dotcene_cisla = set(obrat_md.keys()) | set(obrat_dal.keys())

            # Načti metadata účtů
            if jen_dotcene_ucty:
                ucty_cache = {}
                for cislo in sorted(dotcene_cisla):
                    ucty_cache[cislo] = osnova_repo.get_by_cislo(cislo)
                ucty_pro_radky = ucty_cache
            else:
                vsechny = osnova_repo.list_all(jen_aktivni=True)
                ucty_pro_radky = {u.cislo: u for u in vsechny}

            # Sestav řádky
            radky = []
            for cislo in sorted(ucty_pro_radky.keys()):
                ucet = ucty_pro_radky[cislo]
                radky.append(RadekPredvahy(
                    ucet_cislo=ucet.cislo,
                    ucet_nazev=ucet.nazev,
                    ucet_typ=ucet.typ,
                    obrat_md=obrat_md.get(cislo, Money.zero()),
                    obrat_dal=obrat_dal.get(cislo, Money.zero()),
                ))

        return Predvaha(od=od, do=do, radky=tuple(radky))
