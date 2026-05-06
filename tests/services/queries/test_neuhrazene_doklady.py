"""Testy NeuhrazeneDokladyQuery — kandidáti pro spárování platby."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.neuhrazene_doklady import NeuhrazeneDokladyQuery


@pytest.fixture
def factory():
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "test.db"
    f = ConnectionFactory(db_path)
    runner = MigrationRunner(
        f, Path("infrastructure/database/migrations/sql"),
    )
    runner.migrate()
    return f


def _add(factory, **kwargs):
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(**kwargs))
        uow.commit()
    return d.id


def _q(factory) -> NeuhrazeneDokladyQuery:
    return NeuhrazeneDokladyQuery(lambda: SqliteUnitOfWork(factory))


class TestNeuhrazeneDoklady:

    def test_fv_zauctovany_je_kandidat(self, factory):
        _add(
            factory, cislo="FV-001", typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2025, 5, 1),
            castka_celkem=Money(100000),
            stav=StavDokladu.ZAUCTOVANY,
        )
        result = _q(factory).execute()
        assert len(result) == 1
        assert result[0].cislo == "FV-001"

    def test_fv_novy_neni_kandidat(self, factory):
        """FV ve stavu NOVY se nesmí párovat — musí být zaúčtovaná."""
        _add(
            factory, cislo="FV-002", typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2025, 5, 1),
            castka_celkem=Money(100000),
            stav=StavDokladu.NOVY,
        )
        assert _q(factory).execute() == []

    def test_zf_novy_je_kandidat(self, factory):
        """ZF v NOVY se ZÁROVEŇ párují — neúčtují se samostatně."""
        _add(
            factory, cislo="ZF-2025-001", typ=TypDokladu.ZALOHA_FAKTURA,
            datum_vystaveni=date(2025, 5, 1),
            castka_celkem=Money(50000),
            stav=StavDokladu.NOVY,
            je_vystavena=True,
        )
        result = _q(factory).execute()
        assert len(result) == 1
        assert result[0].cislo == "ZF-2025-001"
        assert result[0].typ == TypDokladu.ZALOHA_FAKTURA

    def test_zf_prijata_novy_je_kandidat(self, factory):
        _add(
            factory, cislo="ZF-PRIJATA-001",
            typ=TypDokladu.ZALOHA_FAKTURA,
            datum_vystaveni=date(2025, 5, 1),
            castka_celkem=Money(20000),
            stav=StavDokladu.NOVY,
            je_vystavena=False,
        )
        result = _q(factory).execute()
        assert len(result) == 1

    def test_zf_uhrazeny_neni_kandidat(self, factory):
        _add(
            factory, cislo="ZF-OK", typ=TypDokladu.ZALOHA_FAKTURA,
            datum_vystaveni=date(2025, 5, 1),
            castka_celkem=Money(10000),
            stav=StavDokladu.UHRAZENY,
            je_vystavena=True,
        )
        assert _q(factory).execute() == []

    def test_id_pd_nejsou_kandidati(self, factory):
        _add(
            factory, cislo="ID-1", typ=TypDokladu.INTERNI_DOKLAD,
            datum_vystaveni=date(2025, 5, 1),
            castka_celkem=Money(1000),
            stav=StavDokladu.ZAUCTOVANY,
        )
        assert _q(factory).execute() == []
