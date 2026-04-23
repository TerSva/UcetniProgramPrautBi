"""Testy pro PredvahaQuery — obratová předvaha."""

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from services.queries.predvaha import PredvahaQuery
from services.zauctovani_service import ZauctovaniDokladuService


@pytest.fixture
def zauctovani(service_factories):
    return ZauctovaniDokladuService(
        uow_factory=service_factories["uow"],
        doklady_repo_factory=service_factories["doklady"],
        denik_repo_factory=service_factories["denik"],
    )


@pytest.fixture
def predvaha_query(service_factories):
    return PredvahaQuery(
        uow_factory=service_factories["uow"],
        denik_repo_factory=service_factories["denik"],
        osnova_repo_factory=service_factories["osnova"],
    )


def _vytvor_doklad(service_factories, cislo, typ, datum, castka_kc):
    """Helper: vytvoří doklad v DB a vrátí id."""
    from infrastructure.database.repositories.doklady_repository import (
        SqliteDokladyRepository,
    )

    uow = service_factories["uow"]()
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(
            cislo=cislo, typ=typ, datum_vystaveni=datum,
            castka_celkem=Money.from_koruny(castka_kc),
        ))
        uow.commit()
    return d.id


@pytest.fixture
def tri_zauctovane_doklady(service_factories, zauctovani):
    """Setup: 3 zaúčtované doklady.

    FV-001: 12 100 Kč (MD 311 / Dal 601: 10000, MD 311 / Dal 343: 2100) — 2026-04-01
    FP-001:  6 050 Kč (MD 501 / Dal 321: 5000, MD 343 / Dal 321: 1050) — 2026-04-10
    FV-002: 24 200 Kč (MD 311 / Dal 602: 20000, MD 311 / Dal 343: 4200) — 2026-04-20
    """
    d1 = _vytvor_doklad(
        service_factories, "FV-001", TypDokladu.FAKTURA_VYDANA,
        date(2026, 4, 1), "12100",
    )
    zauctovani.zauctuj_doklad(d1, UctovyPredpis(
        doklad_id=d1,
        zaznamy=(
            UcetniZaznam(
                doklad_id=d1, datum=date(2026, 4, 1),
                md_ucet="311", dal_ucet="601", castka=Money.from_koruny("10000"),
            ),
            UcetniZaznam(
                doklad_id=d1, datum=date(2026, 4, 1),
                md_ucet="311", dal_ucet="343", castka=Money.from_koruny("2100"),
            ),
        ),
    ))

    d2 = _vytvor_doklad(
        service_factories, "FP-001", TypDokladu.FAKTURA_PRIJATA,
        date(2026, 4, 10), "6050",
    )
    zauctovani.zauctuj_doklad(d2, UctovyPredpis(
        doklad_id=d2,
        zaznamy=(
            UcetniZaznam(
                doklad_id=d2, datum=date(2026, 4, 10),
                md_ucet="501", dal_ucet="321", castka=Money.from_koruny("5000"),
            ),
            UcetniZaznam(
                doklad_id=d2, datum=date(2026, 4, 10),
                md_ucet="343", dal_ucet="321", castka=Money.from_koruny("1050"),
            ),
        ),
    ))

    d3 = _vytvor_doklad(
        service_factories, "FV-002", TypDokladu.FAKTURA_VYDANA,
        date(2026, 4, 20), "24200",
    )
    zauctovani.zauctuj_doklad(d3, UctovyPredpis(
        doklad_id=d3,
        zaznamy=(
            UcetniZaznam(
                doklad_id=d3, datum=date(2026, 4, 20),
                md_ucet="311", dal_ucet="602", castka=Money.from_koruny("20000"),
            ),
            UcetniZaznam(
                doklad_id=d3, datum=date(2026, 4, 20),
                md_ucet="311", dal_ucet="343", castka=Money.from_koruny("4200"),
            ),
        ),
    ))

    return d1, d2, d3


class TestPredvahaZaObdobi:

    def test_obraty_po_uctech(self, predvaha_query, tri_zauctovane_doklady):
        p = predvaha_query.execute(date(2026, 4, 1), date(2026, 4, 30))

        radky = {r.ucet_cislo: r for r in p.radky}

        # 311: MD = 12100 + 24200 = 36300, Dal = 0
        assert radky["311"].obrat_md == Money.from_koruny("36300")
        assert radky["311"].obrat_dal == Money.zero()

        # 321: MD = 0, Dal = 5000 + 1050 = 6050
        assert radky["321"].obrat_md == Money.zero()
        assert radky["321"].obrat_dal == Money.from_koruny("6050")

        # 343: MD = 1050, Dal = 2100 + 4200 = 6300
        assert radky["343"].obrat_md == Money.from_koruny("1050")
        assert radky["343"].obrat_dal == Money.from_koruny("6300")

        # 501: MD = 5000, Dal = 0
        assert radky["501"].obrat_md == Money.from_koruny("5000")
        assert radky["501"].obrat_dal == Money.zero()

        # 601: MD = 0, Dal = 10000
        assert radky["601"].obrat_md == Money.zero()
        assert radky["601"].obrat_dal == Money.from_koruny("10000")

        # 602: MD = 0, Dal = 20000
        assert radky["602"].obrat_md == Money.zero()
        assert radky["602"].obrat_dal == Money.from_koruny("20000")

        assert p.je_vyvazena

    def test_vyvazenost(self, predvaha_query, tri_zauctovane_doklady):
        p = predvaha_query.execute(date(2026, 4, 1), date(2026, 4, 30))
        # celkem MD = 36300 + 1050 + 5000 = 42350
        # celkem Dal = 6050 + 6300 + 10000 + 20000 = 42350
        assert p.celkem_md == Money.from_koruny("42350")
        assert p.celkem_dal == Money.from_koruny("42350")
        assert p.je_vyvazena

    def test_filtr_obdobi(self, predvaha_query, tri_zauctovane_doklady):
        """Jen první polovina dubna — jen FV-001."""
        p = predvaha_query.execute(date(2026, 4, 1), date(2026, 4, 9))
        radky = {r.ucet_cislo: r for r in p.radky}
        assert "311" in radky
        assert radky["311"].obrat_md == Money.from_koruny("12100")
        assert "501" not in radky  # FP-001 je 10. dubna
        assert p.je_vyvazena


class TestDotceneUcty:

    def test_jen_dotcene_default(self, predvaha_query, tri_zauctovane_doklady):
        p = predvaha_query.execute(date(2026, 4, 1), date(2026, 4, 30))
        cisla = {r.ucet_cislo for r in p.radky}
        # 211, 221, 518 nemají žádné zápisy
        assert "211" not in cisla
        assert "221" not in cisla
        assert "518" not in cisla
        assert p.je_vyvazena

    def test_vsechny_ucty_z_osnovy(self, predvaha_query, tri_zauctovane_doklady):
        p = predvaha_query.execute(
            date(2026, 4, 1), date(2026, 4, 30), jen_dotcene_ucty=False
        )
        assert len(p.radky) == 68  # all accounts after seed 020
        # Nedotčené mají nulové obraty
        radky = {r.ucet_cislo: r for r in p.radky}
        assert radky["211"].obrat_md == Money.zero()
        assert radky["211"].obrat_dal == Money.zero()
        assert radky["211"].saldo == Money.zero()
        assert p.je_vyvazena


class TestPrazdneObdobi:

    def test_zadne_zapisy(self, predvaha_query):
        """Období bez zápisů — prázdné řádky, vyvážená (0 == 0)."""
        p = predvaha_query.execute(date(2025, 1, 1), date(2025, 12, 31))
        assert len(p.radky) == 0
        assert p.je_vyvazena
        assert p.celkem_md == Money.zero()


class TestSaldo:

    def test_saldo_311_kladne(self, predvaha_query, tri_zauctovane_doklady):
        p = predvaha_query.execute(date(2026, 4, 1), date(2026, 4, 30))
        radky = {r.ucet_cislo: r for r in p.radky}
        # 311: MD 36300 - Dal 0 = +36300
        assert radky["311"].saldo == Money.from_koruny("36300")

    def test_saldo_601_zaporne(self, predvaha_query, tri_zauctovane_doklady):
        p = predvaha_query.execute(date(2026, 4, 1), date(2026, 4, 30))
        radky = {r.ucet_cislo: r for r in p.radky}
        # 601: MD 0 - Dal 10000 = -10000
        assert radky["601"].saldo == Money.from_koruny("-10000")
        assert p.je_vyvazena


class TestRazeni:

    def test_lexikograficke_razeni(self, predvaha_query, tri_zauctovane_doklady):
        p = predvaha_query.execute(date(2026, 4, 1), date(2026, 4, 30))
        cisla = [r.ucet_cislo for r in p.radky]
        assert cisla == sorted(cisla)
        assert p.je_vyvazena
