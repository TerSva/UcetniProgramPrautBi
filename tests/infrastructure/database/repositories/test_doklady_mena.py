"""Testy persistence cizoměnových dokladů."""

from datetime import date
from decimal import Decimal

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import Mena, TypDokladu
from domain.shared.money import Money
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork

from tests.infrastructure.database.repositories.conftest import (  # noqa: F401
    db_factory,
    uow,
)


class TestDokladyMenaPersistence:

    def test_roundtrip_eur(self, db_factory, uow):
        with uow:
            repo = SqliteDokladyRepository(uow)
            d = Doklad(
                cislo="FP-EUR-001",
                typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2026, 4, 10),
                castka_celkem=Money(25100),
                mena=Mena.EUR,
                castka_mena=Money(1000),
                kurz=Decimal("25.10"),
            )
            saved = repo.add(d)
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteDokladyRepository(uow2)
            loaded = repo2.get_by_id(saved.id)

        assert loaded.mena == Mena.EUR
        assert loaded.castka_mena == Money(1000)
        assert loaded.kurz == Decimal("25.10")
        assert loaded.castka_celkem == Money(25100)

    def test_roundtrip_czk_null_fields(self, db_factory, uow):
        with uow:
            repo = SqliteDokladyRepository(uow)
            d = Doklad(
                cislo="FV-CZK-001",
                typ=TypDokladu.FAKTURA_VYDANA,
                datum_vystaveni=date(2026, 4, 10),
                castka_celkem=Money(100000),
            )
            saved = repo.add(d)
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteDokladyRepository(uow2)
            loaded = repo2.get_by_id(saved.id)

        assert loaded.mena == Mena.CZK
        assert loaded.castka_mena is None
        assert loaded.kurz is None

    def test_update_eur_doklad(self, db_factory, uow):
        with uow:
            repo = SqliteDokladyRepository(uow)
            d = Doklad(
                cislo="FP-EUR-002",
                typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2026, 4, 10),
                castka_celkem=Money(50200),
                mena=Mena.EUR,
                castka_mena=Money(2000),
                kurz=Decimal("25.10"),
            )
            saved = repo.add(d)
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteDokladyRepository(uow2)
            loaded = repo2.get_by_id(saved.id)
            repo2.update(loaded)
            uow2.commit()

    def test_migration_007_columns_exist(self, db_factory):
        """Ověř, že migrace 007 přidala sloupce."""
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            cursor = uow.connection.execute(
                "PRAGMA table_info(doklady)"
            )
            columns = {row["name"] for row in cursor.fetchall()}
        assert "castka_mena" in columns
        assert "kurz" in columns
        assert "mena" in columns
