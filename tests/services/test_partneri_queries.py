"""Testy PartneriListQuery a PartneriSearchQuery."""

from decimal import Decimal

import pytest

from domain.partneri.partner import KategoriePartnera, Partner
from infrastructure.database.repositories.partneri_repository import (
    SqlitePartneriRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.partneri_list import (
    PartneriListQuery,
    PartneriSearchQuery,
)


@pytest.fixture
def _seed(db_factory):
    """Seed 3 partnery."""
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqlitePartneriRepository(uow)
        repo.add(Partner(
            nazev="iStyle CZ",
            kategorie=KategoriePartnera.DODAVATEL,
            ico="27583368",
        ))
        repo.add(Partner(
            nazev="Martin Švanda",
            kategorie=KategoriePartnera.SPOLECNIK,
            podil_procent=Decimal("90"),
        ))
        repo.add(Partner(
            nazev="Odběratel s.r.o.",
            kategorie=KategoriePartnera.ODBERATEL,
        ))
        uow.commit()


class TestPartneriListQuery:

    def test_list_all(self, db_factory, _seed):
        q = PartneriListQuery(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
            partneri_repo_factory=lambda uow: SqlitePartneriRepository(uow),
        )
        items = q.execute()
        assert len(items) == 3

    def test_list_by_kategorie(self, db_factory, _seed):
        q = PartneriListQuery(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
            partneri_repo_factory=lambda uow: SqlitePartneriRepository(uow),
        )
        items = q.execute(kategorie=KategoriePartnera.DODAVATEL)
        assert len(items) == 1
        assert items[0].nazev == "iStyle CZ"


class TestPartneriSearchQuery:

    def test_search(self, db_factory, _seed):
        q = PartneriSearchQuery(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
            partneri_repo_factory=lambda uow: SqlitePartneriRepository(uow),
        )
        items = q.execute("ist")
        assert len(items) == 1
        assert items[0].nazev == "iStyle CZ"

    def test_search_short(self, db_factory, _seed):
        """Hledání kratší než 2 znaky vrátí prázdný seznam."""
        q = PartneriSearchQuery(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
            partneri_repo_factory=lambda uow: SqlitePartneriRepository(uow),
        )
        assert q.execute("i") == []
