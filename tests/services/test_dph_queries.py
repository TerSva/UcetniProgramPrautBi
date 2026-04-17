"""Testy DPH queries — měsíční přehled a detail."""

from datetime import date
from decimal import Decimal
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
from services.queries.dph_prehled import DphMesicDetailQuery, DphPrehledQuery


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
        "('518', 'Ostatní služby', 'N', 1),"
        "('321', 'Dodavatelé', 'P', 1),"
        "('343', 'DPH', 'P', 1)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni, parent_kod) VALUES "
        "('343.100', 'DPH vstup', 'P', 1, '343'),"
        "('343.200', 'DPH výstup', 'P', 1, '343'),"
        "('518.100', 'Reklama', 'N', 1, '518'),"
        "('321.002', 'Meta Platforms', 'P', 1, '321')"
    )
    conn.commit()
    conn.close()
    return f


def _seed_rc_doklad(factory, cislo, datum, castka_halire, partner_nazev=None):
    """Seed doklad + zaúčtování s RC."""
    uow = SqliteUnitOfWork(factory)
    with uow:
        drepo = SqliteDokladyRepository(uow)

        # Seed partner if needed
        partner_id = None
        if partner_nazev:
            conn = uow.connection
            conn.execute(
                "INSERT OR IGNORE INTO partneri (nazev, kategorie, je_aktivni) "
                "VALUES (?, 'dodavatel', 1)",
                (partner_nazev,),
            )
            row = conn.execute(
                "SELECT id FROM partneri WHERE nazev = ?", (partner_nazev,),
            ).fetchone()
            partner_id = row["id"]

        doklad = Doklad(
            cislo=cislo,
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=datum,
            castka_celkem=Money(castka_halire),
            partner_id=partner_id,
        )
        drepo.add(doklad)
        uow.commit()

    # Get doklad id
    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        drepo2 = SqliteDokladyRepository(uow2)
        loaded = drepo2.get_by_cislo(cislo)
        doklad_id = loaded.id

        # Zaúčtovat: base row + RC DPH row
        dph_halire = round(castka_halire * 21 / 100)
        predpis = UctovyPredpis(
            doklad_id=doklad_id,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=doklad_id,
                    datum=datum,
                    md_ucet="518.100",
                    dal_ucet="321.002",
                    castka=Money(castka_halire),
                ),
                UcetniZaznam(
                    doklad_id=doklad_id,
                    datum=datum,
                    md_ucet="343.100",
                    dal_ucet="343.200",
                    castka=Money(dph_halire),
                ),
            ),
        )
        denik = SqliteUcetniDenikRepository(uow2)
        denik.zauctuj(predpis)

        # Mark as posted
        loaded.zauctuj()
        drepo2.update(loaded)
        uow2.commit()


class TestDphPrehledQuery:

    def test_empty_year(self, factory):
        q = DphPrehledQuery(lambda: SqliteUnitOfWork(factory))
        result = q.execute(2025)
        assert len(result) == 12
        for item in result:
            assert item.pocet_transakci == 0
            assert item.je_podane is False

    def test_one_rc_doklad(self, factory):
        _seed_rc_doklad(factory, "FP-2025-001", date(2025, 4, 23), 4400)
        q = DphPrehledQuery(lambda: SqliteUnitOfWork(factory))
        result = q.execute(2025)
        april = result[3]  # index 3 = April
        assert april.mesic == 4
        assert april.pocet_transakci == 1
        assert april.dph_celkem == Money(924)  # 4400 * 21%
        assert april.zaklad_celkem == Money(4400)

    def test_multiple_doklady_same_month(self, factory):
        _seed_rc_doklad(factory, "FP-2025-001", date(2025, 4, 10), 4400)
        _seed_rc_doklad(factory, "FP-2025-002", date(2025, 4, 15), 4400)
        q = DphPrehledQuery(lambda: SqliteUnitOfWork(factory))
        result = q.execute(2025)
        april = result[3]
        assert april.pocet_transakci == 2
        assert april.dph_celkem == Money(1848)
        assert april.zaklad_celkem == Money(8800)

    def test_different_months(self, factory):
        _seed_rc_doklad(factory, "FP-2025-001", date(2025, 3, 15), 4400)
        _seed_rc_doklad(factory, "FP-2025-002", date(2025, 4, 10), 6000)
        q = DphPrehledQuery(lambda: SqliteUnitOfWork(factory))
        result = q.execute(2025)
        march = result[2]
        assert march.pocet_transakci == 1
        april = result[3]
        assert april.pocet_transakci == 1
        assert april.dph_celkem == Money(1260)


class TestDphMesicDetailQuery:

    def test_detail_transakce(self, factory):
        _seed_rc_doklad(
            factory, "FP-2025-001", date(2025, 4, 23), 4400,
            partner_nazev="Meta Platforms",
        )
        q = DphMesicDetailQuery(lambda: SqliteUnitOfWork(factory))
        result = q.execute(2025, 4)
        assert len(result) == 1
        t = result[0]
        assert t.doklad_cislo == "FP-2025-001"
        assert t.partner_nazev == "Meta Platforms"
        assert t.zaklad == Money(4400)
        assert t.dph == Money(924)

    def test_empty_month(self, factory):
        q = DphMesicDetailQuery(lambda: SqliteUnitOfWork(factory))
        result = q.execute(2025, 4)
        assert result == []

    def test_multiple_transakce(self, factory):
        _seed_rc_doklad(factory, "FP-2025-001", date(2025, 4, 10), 4400)
        _seed_rc_doklad(factory, "FP-2025-002", date(2025, 4, 15), 6000)
        q = DphMesicDetailQuery(lambda: SqliteUnitOfWork(factory))
        result = q.execute(2025, 4)
        assert len(result) == 2
