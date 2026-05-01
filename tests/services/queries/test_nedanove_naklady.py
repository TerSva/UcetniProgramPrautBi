"""Testy get_nedanove_naklady — souhrn nedaňových N účtů (DPPO ř. 40)."""

from datetime import date
from pathlib import Path
import tempfile

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.vykazy_query import VykazyQuery


@pytest.fixture()
def factory():
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "test.db"
    f = ConnectionFactory(db_path)
    migrations_dir = Path("infrastructure/database/migrations/sql")
    MigrationRunner(f, migrations_dir).migrate()
    return f


def _zauctuj_naklad(
    factory, datum: date, md_ucet: str, castka_hal: int, doklad_cislo: str,
):
    """Pomocník: vytvoří FP doklad + zápis MD <md_ucet> / Dal 321."""
    uow = SqliteUnitOfWork(factory)
    with uow:
        drepo = SqliteDokladyRepository(uow)
        d = Doklad(
            cislo=doklad_cislo,
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=datum,
            castka_celkem=Money(castka_hal),
        )
        drepo.add(d)
        uow.commit()

    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        drepo2 = SqliteDokladyRepository(uow2)
        loaded = drepo2.get_by_cislo(doklad_cislo)
        denik = SqliteUcetniDenikRepository(uow2)
        denik.zauctuj(UctovyPredpis(
            doklad_id=loaded.id,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=loaded.id,
                    datum=datum,
                    md_ucet=md_ucet,
                    dal_ucet="321",
                    castka=Money(castka_hal),
                ),
            ),
        ))
        loaded.zauctuj()
        drepo2.update(loaded)
        uow2.commit()


class TestNedanoveNaklady:

    def test_empty_year_returns_zero(self, factory):
        q = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        data = q.get_nedanove_naklady(2025)
        assert data.je_prazdny
        assert data.celkem == Money.zero()
        assert data.radky == ()

    def test_513_reprezentace_je_nedanovy(self, factory):
        # 513 je seedované jako nedaňové (migrace 022)
        _zauctuj_naklad(
            factory, date(2025, 5, 10), "513", 50000, "FP-2025-001",
        )
        q = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        data = q.get_nedanove_naklady(2025)
        assert not data.je_prazdny
        assert data.celkem == Money(50000)
        # Najít 513 v řádcích
        ucty = {r.ucet for r in data.radky}
        assert "513" in ucty

    def test_545_pokuty_je_nedanovy(self, factory):
        # 545 (Ostatní pokuty a penále) — seedovaný jako nedaňový
        _zauctuj_naklad(
            factory, date(2025, 6, 1), "545", 30000, "FP-2025-002",
        )
        q = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        data = q.get_nedanove_naklady(2025)
        ucty = {r.ucet for r in data.radky}
        assert "545" in ucty

    def test_501_je_danovy_neni_v_souhrnu(self, factory):
        # 501 je daňový — neměl by být v nedaňových
        _zauctuj_naklad(
            factory, date(2025, 5, 10), "501", 100000, "FP-2025-003",
        )
        q = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        data = q.get_nedanove_naklady(2025)
        assert data.je_prazdny

    def test_543_200_dary_nedanove(self, factory):
        # 543.200 (analytika) je nedaňové
        _zauctuj_naklad(
            factory, date(2025, 7, 15), "543.200", 20000, "FP-2025-004",
        )
        q = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        data = q.get_nedanove_naklady(2025)
        assert not data.je_prazdny
        ucty = {r.ucet for r in data.radky}
        assert "543.200" in ucty

    def test_celkem_souhrn_vice_uctu(self, factory):
        _zauctuj_naklad(factory, date(2025, 1, 1), "513", 10000, "FP-A")
        _zauctuj_naklad(factory, date(2025, 2, 1), "545", 20000, "FP-B")
        _zauctuj_naklad(factory, date(2025, 3, 1), "543.200", 30000, "FP-C")
        q = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        data = q.get_nedanove_naklady(2025)
        assert data.celkem == Money(60000)
        assert len(data.radky) == 3

    def test_jiny_rok_se_neztracuje(self, factory):
        _zauctuj_naklad(factory, date(2024, 12, 31), "513", 10000, "FP-OLD")
        _zauctuj_naklad(factory, date(2025, 1, 1), "513", 50000, "FP-NEW")
        q = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        data_2025 = q.get_nedanove_naklady(2025)
        assert data_2025.celkem == Money(50000)
        data_2024 = q.get_nedanove_naklady(2024)
        assert data_2024.celkem == Money(10000)
