"""Integration testy pro DokladByIdQuery."""

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import NotFoundError
from domain.shared.money import Money
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.doklad_by_id import DokladByIdQuery
from services.queries.doklady_list import DokladyListItem


def _add(
    db_factory,
    cislo: str,
    typ: TypDokladu,
    datum: date,
    castka: str,
    k_doreseni: bool = False,
    poznamka: str | None = None,
) -> int:
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(
            cislo=cislo,
            typ=typ,
            datum_vystaveni=datum,
            castka_celkem=Money.from_koruny(castka),
            k_doreseni=k_doreseni,
            poznamka_doreseni=poznamka,
        ))
        uow.commit()
    return d.id  # type: ignore[return-value]


def _build_query(db_factory) -> DokladByIdQuery:
    return DokladByIdQuery(
        uow_factory=lambda: SqliteUnitOfWork(db_factory),
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
    )


class TestDokladByIdQuery:

    def test_vrati_dto_pro_existujici_doklad(self, db_factory):
        doklad_id = _add(
            db_factory, "FV-2026-001", TypDokladu.FAKTURA_VYDANA,
            date(2026, 2, 1), "1000",
        )

        q = _build_query(db_factory)
        item = q.execute(doklad_id)

        assert isinstance(item, DokladyListItem)
        assert item.id == doklad_id
        assert item.cislo == "FV-2026-001"
        assert item.typ == TypDokladu.FAKTURA_VYDANA
        assert item.datum_vystaveni == date(2026, 2, 1)
        assert item.castka_celkem == Money.from_koruny("1000")
        assert item.stav == StavDokladu.NOVY
        assert item.k_doreseni is False

    def test_zachova_flag_k_doreseni(self, db_factory):
        doklad_id = _add(
            db_factory, "FV-2026-002", TypDokladu.FAKTURA_VYDANA,
            date(2026, 2, 1), "500",
            k_doreseni=True, poznamka="chybí IČO",
        )

        q = _build_query(db_factory)
        item = q.execute(doklad_id)

        assert item.k_doreseni is True
        assert item.poznamka_doreseni == "chybí IČO"

    def test_neexistujici_id_vyhodi_notfound(self, db_factory):
        q = _build_query(db_factory)
        with pytest.raises(NotFoundError):
            q.execute(999)
