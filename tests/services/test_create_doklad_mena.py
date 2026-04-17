"""Testy CreateDokladCommand s cizoměnovými poli."""

from datetime import date
from decimal import Decimal

import pytest

from domain.doklady.typy import Mena, TypDokladu
from domain.shared.money import Money
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.commands.create_doklad import CreateDokladCommand, CreateDokladInput

from tests.infrastructure.database.repositories.conftest import (  # noqa: F401
    db_factory,
    uow,
)


@pytest.fixture
def cmd(db_factory):
    return CreateDokladCommand(
        uow_factory=lambda: SqliteUnitOfWork(db_factory),
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
    )


class TestCreateDokladMena:

    def test_create_eur_doklad(self, cmd):
        data = CreateDokladInput(
            cislo="FP-EUR-001",
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2026, 4, 10),
            castka_celkem=Money(25100),
            mena=Mena.EUR,
            castka_mena=Money(1000),
            kurz=Decimal("25.10"),
        )
        item = cmd.execute(data)
        assert item.mena == Mena.EUR
        assert item.castka_mena == Money(1000)
        assert item.kurz == Decimal("25.10")

    def test_create_czk_doklad_default(self, cmd):
        data = CreateDokladInput(
            cislo="FV-CZK-001",
            typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2026, 4, 10),
            castka_celkem=Money(100000),
        )
        item = cmd.execute(data)
        assert item.mena == Mena.CZK
        assert item.castka_mena is None
        assert item.kurz is None

    def test_doklady_list_item_mena_field(self, cmd):
        data = CreateDokladInput(
            cislo="FP-USD-001",
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2026, 4, 10),
            castka_celkem=Money(250000),
            mena=Mena.USD,
            castka_mena=Money(10000),
            kurz=Decimal("25.00"),
        )
        item = cmd.execute(data)
        assert item.mena == Mena.USD

    def test_create_eur_without_kurz_fails(self, cmd):
        data = CreateDokladInput(
            cislo="FP-BAD-001",
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2026, 4, 10),
            castka_celkem=Money(25100),
            mena=Mena.EUR,
            castka_mena=Money(1000),
            # kurz missing
        )
        with pytest.raises(Exception, match="kurz"):
            cmd.execute(data)
