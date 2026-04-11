"""Testy pro HlavniKnihaQuery — hlavní kniha jednoho účtu."""

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.errors import NotFoundError
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from services.queries.dto import StranaUctu
from services.queries.hlavni_kniha import HlavniKnihaQuery
from services.zauctovani_service import ZauctovaniDokladuService


@pytest.fixture
def zauctovani(service_factories):
    return ZauctovaniDokladuService(
        uow_factory=service_factories["uow"],
        doklady_repo_factory=service_factories["doklady"],
        denik_repo_factory=service_factories["denik"],
    )


@pytest.fixture
def hk_query(service_factories):
    return HlavniKnihaQuery(
        uow_factory=service_factories["uow"],
        denik_repo_factory=service_factories["denik"],
        osnova_repo_factory=service_factories["osnova"],
        doklady_repo_factory=service_factories["doklady"],
    )


def _vytvor_doklad(service_factories, cislo, typ, datum, castka_kc):
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
def zauctovane_doklady(service_factories, zauctovani):
    """FV-001: MD 311 / Dal 601: 10000, MD 311 / Dal 343: 2100 (2026-04-01)
       FP-001: MD 501 / Dal 321: 6050 (2026-04-10)
       Uhrada: MD 221 / Dal 311: 12100 (2026-04-15) — úhrada FV pohledávky
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
                popis="Tržba",
            ),
            UcetniZaznam(
                doklad_id=d1, datum=date(2026, 4, 1),
                md_ucet="311", dal_ucet="343", castka=Money.from_koruny("2100"),
                popis="DPH 21%",
            ),
        ),
    ))

    d2 = _vytvor_doklad(
        service_factories, "FP-001", TypDokladu.FAKTURA_PRIJATA,
        date(2026, 4, 10), "6050",
    )
    zauctovani.zauctuj_doklad(d2, UctovyPredpis.jednoduchy(
        doklad_id=d2, datum=date(2026, 4, 10),
        md_ucet="501", dal_ucet="321", castka=Money.from_koruny("6050"),
    ))

    # Bankovní úhrada FV: MD 221 (banka přijme) / Dal 311 (pohledávka zanikne)
    d3 = _vytvor_doklad(
        service_factories, "BV-001", TypDokladu.BANKOVNI_VYPIS,
        date(2026, 4, 15), "12100",
    )
    zauctovani.zauctuj_doklad(d3, UctovyPredpis.jednoduchy(
        doklad_id=d3, datum=date(2026, 4, 15),
        md_ucet="221", dal_ucet="311", castka=Money.from_koruny("12100"),
    ))

    return d1, d2, d3


class TestHlavniKniha311:

    def test_pocet_radku(self, hk_query, zauctovane_doklady):
        """311 má 3 zápisy: 2x MD (FV) + 1x DAL (úhrada)."""
        hk = hk_query.execute("311", date(2026, 4, 1), date(2026, 4, 30))
        assert len(hk.radky) == 3

    def test_kumulativni_zustatek(self, hk_query, zauctovane_doklady):
        hk = hk_query.execute("311", date(2026, 4, 1), date(2026, 4, 30))
        # Zápis 1: MD 311 +10000 → zustatek 10000
        assert hk.radky[0].zustatek == Money.from_koruny("10000")
        # Zápis 2: MD 311 +2100 → zustatek 12100
        assert hk.radky[1].zustatek == Money.from_koruny("12100")
        # Zápis 3: Dal 311 -12100 → zustatek 0
        assert hk.radky[2].zustatek == Money.zero()
        assert hk.koncovy_zustatek == Money.zero()

    def test_strany(self, hk_query, zauctovane_doklady):
        hk = hk_query.execute("311", date(2026, 4, 1), date(2026, 4, 30))
        assert hk.radky[0].strana == StranaUctu.MD
        assert hk.radky[1].strana == StranaUctu.MD
        assert hk.radky[2].strana == StranaUctu.DAL

    def test_protiucty(self, hk_query, zauctovane_doklady):
        hk = hk_query.execute("311", date(2026, 4, 1), date(2026, 4, 30))
        assert hk.radky[0].protiucet == "601"
        assert hk.radky[1].protiucet == "343"
        assert hk.radky[2].protiucet == "221"

    def test_obraty(self, hk_query, zauctovane_doklady):
        hk = hk_query.execute("311", date(2026, 4, 1), date(2026, 4, 30))
        assert hk.obrat_md == Money.from_koruny("12100")
        assert hk.obrat_dal == Money.from_koruny("12100")


class TestUcetJenDal:

    def test_601_jen_dal(self, hk_query, zauctovane_doklady):
        """601 má jen jeden zápis na Dal straně."""
        hk = hk_query.execute("601", date(2026, 4, 1), date(2026, 4, 30))
        assert len(hk.radky) == 1
        assert hk.radky[0].strana == StranaUctu.DAL
        assert hk.radky[0].protiucet == "311"
        # Kumulativní zůstatek: 0 - 10000 = -10000
        assert hk.koncovy_zustatek == Money.from_koruny("-10000")
        assert hk.obrat_md == Money.zero()
        assert hk.obrat_dal == Money.from_koruny("10000")


class TestUcetObeStrany:

    def test_311_md_i_dal(self, hk_query, zauctovane_doklady):
        """311 je na MD (FV) i na DAL (úhrada)."""
        hk = hk_query.execute("311", date(2026, 4, 1), date(2026, 4, 30))
        strany = {r.strana for r in hk.radky}
        assert StranaUctu.MD in strany
        assert StranaUctu.DAL in strany


class TestPrazdneObdobi:

    def test_ucet_bez_zapisu(self, hk_query):
        """Účet existuje, ale nemá žádné zápisy → prázdné řádky."""
        hk = hk_query.execute("211", date(2026, 4, 1), date(2026, 4, 30))
        assert len(hk.radky) == 0
        assert hk.koncovy_zustatek == Money.zero()
        assert hk.pocatecni_zustatek == Money.zero()


class TestUcetNeexistuje:

    def test_not_found(self, hk_query):
        with pytest.raises(NotFoundError, match="999"):
            hk_query.execute("999", date(2026, 4, 1), date(2026, 4, 30))


class TestFiltrObdobi:

    def test_jen_duben_1_az_9(self, hk_query, zauctovane_doklady):
        """Jen FV-001 (1. dubna), ne FP-001 (10.) ani BV-001 (15.)."""
        hk = hk_query.execute("311", date(2026, 4, 1), date(2026, 4, 9))
        assert len(hk.radky) == 2  # dva zápisy z FV-001
        assert hk.koncovy_zustatek == Money.from_koruny("12100")


class TestDokladInfo:

    def test_doklad_cislo_a_typ(self, hk_query, zauctovane_doklady):
        hk = hk_query.execute("311", date(2026, 4, 1), date(2026, 4, 30))
        assert hk.radky[0].doklad_cislo == "FV-001"
        assert hk.radky[0].doklad_typ == "FV"
        assert hk.radky[2].doklad_cislo == "BV-001"
        assert hk.radky[2].doklad_typ == "BV"
