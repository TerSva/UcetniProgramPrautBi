"""Integration testy pro ZauctovatDokladCommand."""

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import PodvojnostError
from domain.shared.money import Money
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.commands.zauctovat_doklad import (
    ZauctovatDokladCommand,
    ZauctovatDokladInput,
    ZauctovatRadek,
)


def _seed_doklad(db_factory, cislo: str, castka: str) -> int:
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(
            cislo=cislo,
            typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2026, 3, 1),
            castka_celkem=Money.from_koruny(castka),
        ))
        uow.commit()
    return d.id  # type: ignore[return-value]


def _build(db_factory) -> ZauctovatDokladCommand:
    return ZauctovatDokladCommand(
        uow_factory=lambda: SqliteUnitOfWork(db_factory),
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
        denik_repo_factory=lambda uow: SqliteUcetniDenikRepository(uow),
    )


class TestZauctovatDokladCommand:

    def test_zauctuje_fakturu_jeden_radek(self, db_factory):
        doklad_id = _seed_doklad(db_factory, "FV-2026-001", "12100")
        cmd = _build(db_factory)
        item = cmd.execute(ZauctovatDokladInput(
            doklad_id=doklad_id,
            datum=date(2026, 3, 1),
            radky=[ZauctovatRadek(
                md_ucet="311", dal_ucet="601",
                castka=Money.from_koruny("12100"),
                popis="Faktura",
            )],
        ))
        assert item.stav == StavDokladu.ZAUCTOVANY

    def test_zauctuje_s_dph_dva_radky(self, db_factory):
        # Faktura 12 100 = 10 000 základ + 2 100 DPH 21 %
        doklad_id = _seed_doklad(db_factory, "FV-2026-002", "12100")
        cmd = _build(db_factory)
        item = cmd.execute(ZauctovatDokladInput(
            doklad_id=doklad_id,
            datum=date(2026, 3, 1),
            radky=[
                ZauctovatRadek(
                    md_ucet="311", dal_ucet="601",
                    castka=Money.from_koruny("10000"),
                    popis="Základ",
                ),
                ZauctovatRadek(
                    md_ucet="311", dal_ucet="343",
                    castka=Money.from_koruny("2100"),
                    popis="DPH 21 %",
                ),
            ],
        ))
        assert item.stav == StavDokladu.ZAUCTOVANY

    def test_persistuje_zmenu_stavu(self, db_factory):
        doklad_id = _seed_doklad(db_factory, "FV-2026-003", "500")
        cmd = _build(db_factory)
        cmd.execute(ZauctovatDokladInput(
            doklad_id=doklad_id,
            datum=date(2026, 3, 1),
            radky=[ZauctovatRadek(
                md_ucet="311", dal_ucet="601",
                castka=Money.from_koruny("500"),
            )],
        ))
        # Ověř persistenci přes jiný UoW
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            loaded = repo.get_by_id(doklad_id)
        assert loaded.stav == StavDokladu.ZAUCTOVANY

    def test_nesouhlas_castky_vyhodi_podvojnost(self, db_factory):
        doklad_id = _seed_doklad(db_factory, "FV-2026-004", "1000")
        cmd = _build(db_factory)
        with pytest.raises(PodvojnostError):
            cmd.execute(ZauctovatDokladInput(
                doklad_id=doklad_id,
                datum=date(2026, 3, 1),
                radky=[ZauctovatRadek(
                    md_ucet="311", dal_ucet="601",
                    castka=Money.from_koruny("500"),  # < 1000
                )],
            ))
