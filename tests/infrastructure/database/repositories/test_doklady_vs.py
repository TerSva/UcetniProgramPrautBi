"""Testy pro variabilní symbol v SqliteDokladyRepository — s reálnou SQLite DB."""

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork


def _doklad(**kwargs) -> Doklad:
    defaults = dict(
        cislo="FV-2026-001",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 1, 15),
        castka_celkem=Money(100000),
    )
    defaults.update(kwargs)
    return Doklad(**defaults)


class TestVSRoundTrip:

    def test_uloz_a_nacti_vs(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            novy = repo.add(_doklad(variabilni_symbol="20250044"))
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteDokladyRepository(uow2)
            loaded = repo2.get_by_id(novy.id)
            assert loaded.variabilni_symbol == "20250044"

    def test_uloz_none_vs(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            novy = repo.add(_doklad(variabilni_symbol=None))
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteDokladyRepository(uow2)
            loaded = repo2.get_by_id(novy.id)
            assert loaded.variabilni_symbol is None

    def test_update_vs(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            novy = repo.add(_doklad(variabilni_symbol="111"))
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteDokladyRepository(uow2)
            loaded = repo2.get_by_id(novy.id)
            assert loaded.variabilni_symbol == "111"


class TestFindByVs:

    def test_najde_doklad_s_vs(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            repo.add(_doklad(cislo="FP-001", variabilni_symbol="12345"))
            repo.add(_doklad(cislo="FP-002", variabilni_symbol="99999"))
            repo.add(_doklad(cislo="FP-003"))  # bez VS
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteDokladyRepository(uow2)
            results = repo2.find_by_vs("12345")
            assert len(results) == 1
            assert results[0].cislo == "FP-001"

    def test_vice_dokladu_se_stejnym_vs(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            repo.add(_doklad(cislo="FP-001", variabilni_symbol="55555"))
            repo.add(_doklad(cislo="FP-002", variabilni_symbol="55555"))
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteDokladyRepository(uow2)
            results = repo2.find_by_vs("55555")
            assert len(results) == 2

    def test_nenajde_nic(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            repo.add(_doklad(cislo="FP-001", variabilni_symbol="111"))
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteDokladyRepository(uow2)
            results = repo2.find_by_vs("999")
            assert results == []

    def test_nevraci_doklady_bez_vs(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            repo.add(_doklad(cislo="FP-001"))  # VS=None
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteDokladyRepository(uow2)
            results = repo2.find_by_vs("12345")
            assert results == []
