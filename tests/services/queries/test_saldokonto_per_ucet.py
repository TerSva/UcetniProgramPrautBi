"""Testy get_saldokonto_per_ucet — 311/321/355/365 sekce."""

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
from services.queries.vykazy_query import (
    SaldokontoRadek,
    SaldoUcetRadek,
    VykazyQuery,
)


@pytest.fixture()
def factory():
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "test.db"
    f = ConnectionFactory(db_path)
    migrations_dir = Path("infrastructure/database/migrations/sql")
    MigrationRunner(f, migrations_dir).migrate()
    # Seed required accounts
    conn = f.create()
    conn.execute(
        "INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES "
        "('311', 'Odběratelé', 'A', 1),"
        "('321', 'Dodavatelé', 'P', 1),"
        "('355', 'Pohledávky za společníky', 'A', 1),"
        "('365', 'Závazky vůči společníkům', 'P', 1),"
        "('221', 'Bankovní účet', 'A', 1)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO uctova_osnova "
        "(cislo, nazev, typ, je_aktivni, parent_kod) VALUES "
        "('355.001', 'Půjčka společníkovi A', 'A', 1, '355'),"
        "('365.001', 'Půjčka od společníka A', 'P', 1, '365')"
    )
    conn.commit()
    conn.close()
    return f


def _zauctuj(factory, datum, md, dal, castka_hal, doklad_cislo, doklad_typ):
    """Helper: vytvoří doklad + zaúčtuje 1 zápis MD/Dal."""
    uow = SqliteUnitOfWork(factory)
    with uow:
        drepo = SqliteDokladyRepository(uow)
        d = Doklad(
            cislo=doklad_cislo,
            typ=doklad_typ,
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
                    md_ucet=md,
                    dal_ucet=dal,
                    castka=Money(castka_hal),
                ),
            ),
        ))
        loaded.zauctuj()
        drepo2.update(loaded)
        uow2.commit()


class TestSaldokontoPerUcet355:

    def test_empty_355(self, factory):
        q = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        sekce = q.get_saldokonto_per_ucet(2025)
        # 4 sekce: 311, 321, 355, 365
        # 6 sekcí: 311, 321, 314, 324, 355, 365
        assert len(sekce) == 6
        sekce_355 = next(s for s in sekce if s.ucet == "355")
        assert sekce_355.je_pohledavka is True
        assert sekce_355.celkem == Money.zero()
        assert sekce_355.radky == ()

    def test_355_pohledavka_z_uctu(self, factory):
        # Půjčka společníkovi: MD 355.001 / Dal 221 (banka), 100 000 Kč
        _zauctuj(
            factory,
            date(2025, 3, 15),
            md="355.001",
            dal="221",
            castka_hal=10000000,
            doklad_cislo="ID-2025-001",
            doklad_typ=TypDokladu.INTERNI_DOKLAD,
        )
        q = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        sekce = q.get_saldokonto_per_ucet(2025)
        sekce_355 = next(s for s in sekce if s.ucet == "355")
        assert sekce_355.celkem == Money(10000000)
        assert len(sekce_355.radky) == 1
        r = sekce_355.radky[0]
        assert isinstance(r, SaldoUcetRadek)
        assert r.ucet == "355.001"
        assert r.saldo == Money(10000000)


class TestSaldokontoPerUcet365:

    def test_365_zavazek_je_kladny(self, factory):
        # Půjčka od společníka: MD 221 / Dal 365.001, 50 000 Kč
        _zauctuj(
            factory,
            date(2025, 4, 1),
            md="221",
            dal="365.001",
            castka_hal=5000000,
            doklad_cislo="ID-2025-002",
            doklad_typ=TypDokladu.INTERNI_DOKLAD,
        )
        q = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        sekce = q.get_saldokonto_per_ucet(2025)
        sekce_365 = next(s for s in sekce if s.ucet == "365")
        # Pasivní účet: závazek se zobrazuje jako kladné saldo
        assert sekce_365.je_pohledavka is False
        assert sekce_365.celkem == Money(5000000)
        assert len(sekce_365.radky) == 1


class TestSaldokontoPerUcet311_321:

    def test_311_321_pouzije_existujici_saldokonto(self, factory):
        """311 a 321 se sestaví ze stejných FV/FP jako get_saldokonto."""
        q = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        sekce = q.get_saldokonto_per_ucet(2025)
        sekce_311 = next(s for s in sekce if s.ucet == "311")
        sekce_321 = next(s for s in sekce if s.ucet == "321")
        # Bez FV/FP musí být prázdné
        assert sekce_311.radky == ()
        assert sekce_321.radky == ()
        assert sekce_311.celkem == Money.zero()
        assert sekce_321.celkem == Money.zero()
