"""Testy ViesQuery — souhrnné hlášení pro identifikovanou osobu."""

from datetime import date
from pathlib import Path
import tempfile

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import DphRezim, TypDokladu
from domain.shared.money import Money
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.dph_prehled import ViesQuery


@pytest.fixture()
def factory():
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "test.db"
    f = ConnectionFactory(db_path)
    migrations_dir = Path("infrastructure/database/migrations/sql")
    MigrationRunner(f, migrations_dir).migrate()
    return f


def _seed_partner(factory, nazev: str, dic: str | None) -> int:
    uow = SqliteUnitOfWork(factory)
    with uow:
        conn = uow.connection
        conn.execute(
            "INSERT INTO partneri (nazev, kategorie, dic, je_aktivni) "
            "VALUES (?, 'odberatel', ?, 1)",
            (nazev, dic),
        )
        row = conn.execute(
            "SELECT id FROM partneri WHERE nazev = ?", (nazev,),
        ).fetchone()
        uow.commit()
        return row["id"]


def _seed_fv_rc(
    factory,
    cislo: str,
    datum: date,
    castka_hal: int,
    partner_id: int,
):
    """Seed FV s dph_rezim=REVERSE_CHARGE a stavem zauctovany."""
    uow = SqliteUnitOfWork(factory)
    with uow:
        drepo = SqliteDokladyRepository(uow)
        d = Doklad(
            cislo=cislo,
            typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=datum,
            castka_celkem=Money(castka_hal),
            partner_id=partner_id,
            dph_rezim=DphRezim.REVERSE_CHARGE,
        )
        drepo.add(d)
        # Mark as posted
        loaded = drepo.get_by_cislo(cislo)
        loaded.zauctuj()
        drepo.update(loaded)
        uow.commit()


class TestViesQuery:

    def test_empty_when_no_rc_fv(self, factory):
        q = ViesQuery(lambda: SqliteUnitOfWork(factory))
        assert q.execute(2025) == []

    def test_lists_rc_faktury_vydane(self, factory):
        partner_id = _seed_partner(factory, "ACME GmbH", "DE123456789")
        _seed_fv_rc(factory, "FV-2025-001", date(2025, 5, 12), 50000, partner_id)
        q = ViesQuery(lambda: SqliteUnitOfWork(factory))
        result = q.execute(2025)
        assert len(result) == 1
        v = result[0]
        assert v.doklad_cislo == "FV-2025-001"
        assert v.partner_dic == "DE123456789"
        assert v.partner_nazev == "ACME GmbH"
        assert v.zaklad == Money(50000)

    def test_excludes_other_year(self, factory):
        partner_id = _seed_partner(factory, "ACME", "DE123")
        _seed_fv_rc(factory, "FV-2024-001", date(2024, 6, 1), 10000, partner_id)
        _seed_fv_rc(factory, "FV-2025-001", date(2025, 6, 1), 20000, partner_id)
        q = ViesQuery(lambda: SqliteUnitOfWork(factory))
        result = q.execute(2025)
        assert len(result) == 1
        assert result[0].doklad_cislo == "FV-2025-001"
