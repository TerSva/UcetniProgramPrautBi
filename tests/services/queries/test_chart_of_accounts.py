"""Testy pro ChartOfAccountsQuery — Fáze 7."""

from domain.ucetnictvi.typy import TypUctu
from domain.ucetnictvi.ucet import Ucet
from infrastructure.database.repositories.uctova_osnova_repository import (
    SqliteUctovaOsnovaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.chart_of_accounts import ChartOfAccountsQuery


def _build_query(db_factory):
    return ChartOfAccountsQuery(
        uow_factory=lambda: SqliteUnitOfWork(db_factory),
        osnova_repo_factory=lambda uow: SqliteUctovaOsnovaRepository(uow),
    )


def _seed_analytiky(db_factory):
    """Přidá analytiky pro testování stromové struktury."""
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteUctovaOsnovaRepository(uow)
        repo.add(Ucet("501.100", "Kancelář", TypUctu.NAKLADY, parent_kod="501"))
        repo.add(Ucet("501.200", "Služby", TypUctu.NAKLADY, parent_kod="501"))
        uow.commit()


class TestChartOfAccountsQuery:

    def test_returns_trida_groups(self, db_factory):
        """Query vrátí non-empty list tříd z migrace (seed 9 účtů)."""
        query = _build_query(db_factory)
        result = query.execute(show_inactive=True)
        assert len(result) > 0
        # Migrace seeduje účty v třídách 2, 3, 5, 6
        trida_nums = {t.trida for t in result}
        assert 3 in trida_nums  # 311 pohledávky
        assert 5 in trida_nums  # 501, 518

    def test_tree_structure_with_analytiky(self, db_factory):
        """Analytiky se zobrazí vnořeně pod syntetickým účtem."""
        _seed_analytiky(db_factory)
        query = _build_query(db_factory)
        result = query.execute(show_inactive=True)

        # Najdi třídu 5
        trida_5 = next(t for t in result if t.trida == 5)
        ucet_501 = next(u for u in trida_5.ucty if u.cislo == "501")
        assert len(ucet_501.analytiky) == 2
        cisla = {a.cislo for a in ucet_501.analytiky}
        assert cisla == {"501.100", "501.200"}

    def test_active_count(self, db_factory):
        """active_count počítá jen aktivní syntetické účty."""
        query = _build_query(db_factory)
        result = query.execute(show_inactive=True)
        for trida in result:
            computed = sum(1 for u in trida.ucty if u.is_active)
            assert trida.active_count == computed

    def test_filter_inactive(self, db_factory):
        """show_inactive=False skryje neaktivní účty."""
        # Deaktivuj účet 501
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            u = repo.get_by_cislo("501")
            u.deaktivuj()
            repo.update(u)
            uow.commit()

        query = _build_query(db_factory)

        # S neaktivními
        all_result = query.execute(show_inactive=True)
        trida_5_all = next(t for t in all_result if t.trida == 5)
        cisla_all = {u.cislo for u in trida_5_all.ucty}
        assert "501" in cisla_all

        # Bez neaktivních
        active_result = query.execute(show_inactive=False)
        trida_5_active = next(
            (t for t in active_result if t.trida == 5), None,
        )
        if trida_5_active:
            cisla_active = {u.cislo for u in trida_5_active.ucty}
            assert "501" not in cisla_active

    def test_trida_nazev(self, db_factory):
        """Každá třída má správný český název."""
        query = _build_query(db_factory)
        result = query.execute(show_inactive=True)
        for trida in result:
            assert trida.nazev  # non-empty
            assert isinstance(trida.nazev, str)
