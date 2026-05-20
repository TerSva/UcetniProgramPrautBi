"""Testy parametru vcetne_zaverky napříč VykazyQuery."""

from __future__ import annotations

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
from scripts.seed_chart_of_accounts import seed_chart_of_accounts
from services.queries.vykazy_query import VykazyQuery


MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "infrastructure" / "database" / "migrations" / "sql"
)


@pytest.fixture
def factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    f = ConnectionFactory(db_path)
    MigrationRunner(f, MIGRATIONS_SQL_DIR).migrate()
    seed_chart_of_accounts(f)
    # Ensure 702, 710, 431 analytics exist (used in closing entries)
    conn = f.create()
    conn.execute(
        "INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, parent_kod, je_aktivni) "
        "VALUES ('702.100', 'Konečný účet rozvažný', 'Z', '702', 1)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, parent_kod, je_aktivni) "
        "VALUES ('710.100', 'Účet zisku a ztráty', 'Z', '710', 1)"
    )
    conn.commit()
    conn.close()
    return f


_CITAC = [0]


def _zauctuj(
    factory: ConnectionFactory,
    cislo: str,
    datum: date,
    zapisy: list[tuple[str, str, int]],
    je_zaverka: bool = False,
) -> None:
    """Vystaví ID doklad a zaúčtuje zápisy."""
    _CITAC[0] += 1
    uow = SqliteUnitOfWork(factory)
    with uow:
        drepo = SqliteDokladyRepository(uow)
        celkem = Money.zero()
        for _, _, hal in zapisy:
            celkem = celkem + Money(hal)
        doklad = Doklad(
            cislo=cislo,
            typ=TypDokladu.INTERNI_DOKLAD,
            datum_vystaveni=datum,
            castka_celkem=celkem,
            je_zaverka=je_zaverka,
        )
        drepo.add(doklad)
        loaded = drepo.get_by_cislo(cislo)
        denik = SqliteUcetniDenikRepository(uow)
        zaznamy_tuple = tuple(
            UcetniZaznam(
                doklad_id=loaded.id, datum=datum,
                md_ucet=md, dal_ucet=dal, castka=Money(hal),
            )
            for md, dal, hal in zapisy
        )
        denik.zauctuj(UctovyPredpis(doklad_id=loaded.id, zaznamy=zaznamy_tuple))
        loaded.zauctuj()
        drepo.update(loaded)
        uow.commit()


class TestVcetneZaverky:

    def test_default_false_vylouci_zaverkove(self, factory):
        # Běžný zápis na výnos
        _zauctuj(factory, "ID-1", date(2025, 6, 1),
                 [("311", "602", 100000)])  # 1000 Kč výnos
        # Uzavírací doklad
        _zauctuj(factory, "ID-Z1", date(2025, 12, 31),
                 [("602", "710.100", 100000)], je_zaverka=True)

        vq = VykazyQuery(lambda: SqliteUnitOfWork(factory))

        # Default False: 602 má jen pohyb z ID-1 (DAL +1000)
        data = vq._nacti_obraty_a_ps(2025)
        assert data["602"]["obrat_dal"] == 100000
        assert data["602"]["obrat_md"] == 0

        # vcetne_zaverky=True: 602 má i pohyb ze Z1 (MD +1000) → vyrovnáno
        data2 = vq._nacti_obraty_a_ps(2025, vcetne_zaverky=True)
        assert data2["602"]["obrat_dal"] == 100000
        assert data2["602"]["obrat_md"] == 100000

    def test_get_rozvaha_default_bez_zaverkovych(self, factory):
        _zauctuj(factory, "ID-1", date(2025, 6, 1),
                 [("211", "411", 50000)])
        _zauctuj(factory, "ID-Z3", date(2025, 12, 31),
                 [("411", "702.100", 50000), ("702.100", "211", 50000)],
                 je_zaverka=True)

        vq = VykazyQuery(lambda: SqliteUnitOfWork(factory))

        # Default — vidí stav před uzávěrkou: 211 = 500 MD, 411 = 500 DAL
        a, p = vq.get_bilancni_kontrola(2025)
        assert a == Money(50000)
        assert p == Money(50000)

        # vcetne_zaverky=True — po uzávěrce vše = 0
        a2, p2 = vq.get_bilancni_kontrola(2025, vcetne_zaverky=True)
        assert a2 == Money.zero()
        assert p2 == Money.zero()

    def test_get_vzz_default_bez_zaverkovych(self, factory):
        _zauctuj(factory, "ID-1", date(2025, 6, 1),
                 [("311", "602", 100000)])
        _zauctuj(factory, "ID-Z1", date(2025, 12, 31),
                 [("602", "710.100", 100000)], je_zaverka=True)

        vq = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        data = vq._nacti_obraty_a_ps(2025)
        vh = sum(
            d["obrat_dal"] - d["obrat_md"]
            for d in data.values() if d["typ"] == "V"
        )
        assert vh == 100000  # 1000 Kč zisk

    def test_get_hlavni_kniha_default_true(self, factory):
        _zauctuj(factory, "ID-1", date(2025, 6, 1),
                 [("211", "411", 50000)])
        _zauctuj(factory, "ID-Z", date(2025, 12, 31),
                 [("411", "702.100", 50000)], je_zaverka=True)

        vq = VykazyQuery(lambda: SqliteUnitOfWork(factory))

        # Default True — vidí všechny pohyby na 411 (i závěrkové)
        hk = vq.get_hlavni_kniha("411", 2025)
        assert len(hk.radky) == 2  # běžný + uzavírací

        # vcetne_zaverky=False — jen běžný
        hk2 = vq.get_hlavni_kniha("411", 2025, vcetne_zaverky=False)
        assert len(hk2.radky) == 1

    def test_pokladni_kniha_default_bez_zaverkovych(self, factory):
        _zauctuj(factory, "PD-1", date(2025, 6, 1),
                 [("211", "411", 50000)])
        _zauctuj(factory, "ID-Z", date(2025, 12, 31),
                 [("702.100", "211", 50000)], je_zaverka=True)

        vq = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        pk = vq.get_pokladni_kniha(2025)
        assert pk.koncovy_stav == Money(50000)  # uzavírací ignorován

        pk2 = vq.get_pokladni_kniha(2025, vcetne_zaverky=True)
        assert pk2.koncovy_stav == Money.zero()  # vyrovnáno uzávěrkou

    def test_drilldown_vzz_default_true(self, factory):
        _zauctuj(factory, "ID-1", date(2025, 6, 1),
                 [("311", "602", 100000)])
        _zauctuj(factory, "ID-Z1", date(2025, 12, 31),
                 [("602", "710.100", 100000)], je_zaverka=True)

        vq = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        # Default True — drilldown ukáže oba zápisy (audit)
        zap = vq.get_vzz_drilldown(2025, "I.")
        assert len(zap) == 2

        zap2 = vq.get_vzz_drilldown(2025, "I.", vcetne_zaverky=False)
        assert len(zap2) == 1
