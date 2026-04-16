"""Integration testy pro CountAllDokladyQuery."""

from datetime import date

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.count_all_doklady import CountAllDokladyQuery


def _add(
    db_factory,
    cislo: str,
    typ: TypDokladu = TypDokladu.FAKTURA_VYDANA,
    stav: StavDokladu = StavDokladu.NOVY,
) -> None:
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        repo.add(Doklad(
            cislo=cislo,
            typ=typ,
            datum_vystaveni=date(2026, 2, 1),
            castka_celkem=Money.from_koruny("1000"),
            stav=stav,
        ))
        uow.commit()


def _build_query(db_factory) -> CountAllDokladyQuery:
    return CountAllDokladyQuery(
        uow_factory=lambda: SqliteUnitOfWork(db_factory),
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
    )


class TestCountAllDokladyQuery:
    """count_all query — triviální helper pro status bar."""

    def test_empty_db_vraci_nula(self, db_factory):
        q = _build_query(db_factory)
        assert q.execute() == 0

    def test_scita_vsechny_bez_ohledu_na_typ_a_stav(self, db_factory):
        _add(db_factory, "FV-001", TypDokladu.FAKTURA_VYDANA)
        _add(db_factory, "FV-002", TypDokladu.FAKTURA_VYDANA,
             stav=StavDokladu.ZAUCTOVANY)
        _add(db_factory, "FP-001", TypDokladu.FAKTURA_PRIJATA)

        q = _build_query(db_factory)
        assert q.execute() == 3
