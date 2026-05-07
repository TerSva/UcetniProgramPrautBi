"""Testy pro DashboardDataQuery — KPI snapshot pro Dashboard."""

from datetime import date
from decimal import Decimal

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from services.queries.dashboard import (
    DPPO_SAZBA,
    UCET_POHLEDAVKY,
    UCET_ZAVAZKY,
    DashboardData,
    DashboardDataQuery,
)
from services.zauctovani_service import ZauctovaniDokladuService


# ──────────────────────────────────────────────────────────────────────
# Konstanty
# ──────────────────────────────────────────────────────────────────────


class TestKonstanty:

    def test_dppo_sazba_je_19_procent(self):
        assert DPPO_SAZBA == Decimal("0.19")

    def test_ucty_jsou_311_a_321(self):
        assert UCET_POHLEDAVKY == "311"
        assert UCET_ZAVAZKY == "321"


# ──────────────────────────────────────────────────────────────────────
# DashboardData DTO
# ──────────────────────────────────────────────────────────────────────


def _empty_data(**overrides) -> DashboardData:
    base = dict(
        doklady_celkem=0,
        doklady_k_zauctovani=0,
        doklady_k_doreseni=0,
        pohledavky=Money.zero(),
        zavazky=Money.zero(),
        rok=2026,
        vynosy=Money.zero(),
        naklady=Money.zero(),
        hruby_zisk=Money.zero(),
        odhad_dane=Money.zero(),
    )
    base.update(overrides)
    return DashboardData(**base)


class TestDashboardDataDto:

    def test_je_frozen(self):
        data = _empty_data()
        with pytest.raises(Exception):
            data.doklady_celkem = 999  # type: ignore[misc]

    def test_je_ve_ztrate_true_pokud_zaporny_zisk(self):
        data = _empty_data(hruby_zisk=Money.from_koruny("-100"))
        assert data.je_ve_ztrate is True

    def test_je_ve_ztrate_false_pri_nule(self):
        data = _empty_data(hruby_zisk=Money.zero())
        assert data.je_ve_ztrate is False

    def test_je_ve_ztrate_false_pri_kladnem_zisku(self):
        data = _empty_data(hruby_zisk=Money.from_koruny("100"))
        assert data.je_ve_ztrate is False

    def test_ma_doklady_k_doreseni_true(self):
        data = _empty_data(doklady_k_doreseni=3)
        assert data.ma_doklady_k_doreseni is True

    def test_ma_doklady_k_doreseni_false_pri_nule(self):
        data = _empty_data(doklady_k_doreseni=0)
        assert data.ma_doklady_k_doreseni is False


# ──────────────────────────────────────────────────────────────────────
# Query — fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def dashboard_query(service_factories):
    return DashboardDataQuery(
        uow_factory=service_factories["uow"],
        doklady_repo_factory=service_factories["doklady"],
        denik_repo_factory=service_factories["denik"],
        osnova_repo_factory=service_factories["osnova"],
    )


@pytest.fixture
def zauctovani(service_factories):
    return ZauctovaniDokladuService(
        uow_factory=service_factories["uow"],
        doklady_repo_factory=service_factories["doklady"],
        denik_repo_factory=service_factories["denik"],
    )


def _add_doklad(
    service_factories,
    cislo: str,
    typ: TypDokladu,
    datum: date,
    castka_kc: str,
    k_doreseni: bool = False,
    poznamka: str | None = None,
) -> int:
    uow = service_factories["uow"]()
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(
            cislo=cislo,
            typ=typ,
            datum_vystaveni=datum,
            castka_celkem=Money.from_koruny(castka_kc),
            k_doreseni=k_doreseni,
            poznamka_doreseni=poznamka,
        ))
        uow.commit()
    return d.id


# ──────────────────────────────────────────────────────────────────────
# Prázdná DB
# ──────────────────────────────────────────────────────────────────────


class TestPrazdnaDb:

    def test_vsechny_kpi_nuly(self, dashboard_query):
        data = dashboard_query.execute(today=date(2026, 4, 13))
        assert data.doklady_celkem == 0
        assert data.doklady_k_zauctovani == 0
        assert data.doklady_k_doreseni == 0
        assert data.pohledavky == Money.zero()
        assert data.zavazky == Money.zero()
        assert data.vynosy == Money.zero()
        assert data.naklady == Money.zero()
        assert data.hruby_zisk == Money.zero()
        assert data.odhad_dane == Money.zero()

    def test_rok_default_z_today(self, dashboard_query):
        data = dashboard_query.execute(today=date(2026, 4, 13))
        assert data.rok == 2026

    def test_rok_z_zisk_rok_parametru(self, dashboard_query):
        data = dashboard_query.execute(today=date(2026, 4, 13), zisk_rok=2025)
        assert data.rok == 2025

    def test_today_default_je_dnesni_datum(self, dashboard_query):
        data = dashboard_query.execute()
        assert data.rok == date.today().year


# ──────────────────────────────────────────────────────────────────────
# Doklady — počty
# ──────────────────────────────────────────────────────────────────────


class TestDokladyPocty:

    def test_pocita_vsechny_doklady(self, dashboard_query, service_factories):
        # 2 letošní (2026), 1 loňský (2025) — všechny se počítají
        _add_doklad(service_factories, "FV-26-1", TypDokladu.FAKTURA_VYDANA,
                    date(2026, 1, 5), "1000")
        _add_doklad(service_factories, "FV-26-2", TypDokladu.FAKTURA_VYDANA,
                    date(2026, 3, 15), "2000")
        _add_doklad(service_factories, "FV-25", TypDokladu.FAKTURA_VYDANA,
                    date(2025, 12, 30), "5000")

        data = dashboard_query.execute(today=date(2026, 4, 13))
        assert data.doklady_celkem == 3

    def test_doklady_k_zauctovani_jen_novy(
        self, dashboard_query, service_factories, zauctovani,
    ):
        d_novy = _add_doklad(
            service_factories, "FV-A", TypDokladu.FAKTURA_VYDANA,
            date(2026, 4, 1), "1000",
        )
        d_zauct = _add_doklad(
            service_factories, "FV-B", TypDokladu.FAKTURA_VYDANA,
            date(2026, 4, 2), "1000",
        )
        zauctovani.zauctuj_doklad(d_zauct, UctovyPredpis(
            doklad_id=d_zauct,
            zaznamy=(UcetniZaznam(
                doklad_id=d_zauct, datum=date(2026, 4, 2),
                md_ucet="311", dal_ucet="601", castka=Money.from_koruny("1000"),
            ),),
        ))

        data = dashboard_query.execute(today=date(2026, 4, 13))
        assert data.doklady_celkem == 2
        assert data.doklady_k_zauctovani == 1
        assert d_novy != d_zauct  # sanity

    def test_k_zauctovani_ignoruje_bv_zf_pd_id(
        self, dashboard_query, service_factories,
    ):
        """K zaúčtování patří jen FP/FV v NOVY. BV/ZF/PD/ID se neúčtují
        manuálně (BV: spárování/auto, ZF: jen úhrada, PD/ID: rovnou
        ZAUCTOVANY) — nesmí se počítat."""
        _add_doklad(
            service_factories, "FP-X", TypDokladu.FAKTURA_PRIJATA,
            date(2026, 4, 1), "1000",
        )
        _add_doklad(
            service_factories, "BV-X", TypDokladu.BANKOVNI_VYPIS,
            date(2026, 4, 1), "0",
        )
        _add_doklad(
            service_factories, "PD-X", TypDokladu.POKLADNI_DOKLAD,
            date(2026, 4, 1), "1000",
        )
        _add_doklad(
            service_factories, "ID-X", TypDokladu.INTERNI_DOKLAD,
            date(2026, 4, 1), "1000",
        )

        data = dashboard_query.execute(today=date(2026, 4, 13))
        assert data.doklady_celkem == 4
        # Pouze FP-X spadá do NOVY FP/FV
        assert data.doklady_k_zauctovani == 1

    def test_k_doreseni_pocet_pres_repository(
        self, dashboard_query, service_factories,
    ):
        _add_doklad(
            service_factories, "FV-FLAG-1", TypDokladu.FAKTURA_VYDANA,
            date(2026, 4, 1), "1000", k_doreseni=True, poznamka="prověřit",
        )
        _add_doklad(
            service_factories, "FV-FLAG-2", TypDokladu.FAKTURA_VYDANA,
            date(2026, 4, 2), "1000", k_doreseni=True,
        )
        _add_doklad(
            service_factories, "FV-OK", TypDokladu.FAKTURA_VYDANA,
            date(2026, 4, 3), "1000",
        )

        data = dashboard_query.execute(today=date(2026, 4, 13))
        assert data.doklady_k_doreseni == 2


# ──────────────────────────────────────────────────────────────────────
# Saldokonto
# ──────────────────────────────────────────────────────────────────────


class TestSaldokonto:

    def test_pohledavky_jsou_311_md_minus_dal(
        self, dashboard_query, service_factories, zauctovani,
    ):
        # FV: 311 MD 12 100 (10000 + 2100 DPH), pak částečná úhrada 311 Dal 5000
        d1 = _add_doklad(
            service_factories, "FV-1", TypDokladu.FAKTURA_VYDANA,
            date(2026, 4, 1), "12100",
        )
        zauctovani.zauctuj_doklad(d1, UctovyPredpis(
            doklad_id=d1,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=d1, datum=date(2026, 4, 1),
                    md_ucet="311", dal_ucet="601",
                    castka=Money.from_koruny("10000"),
                ),
                UcetniZaznam(
                    doklad_id=d1, datum=date(2026, 4, 1),
                    md_ucet="311", dal_ucet="343",
                    castka=Money.from_koruny("2100"),
                ),
            ),
        ))

        d2 = _add_doklad(
            service_factories, "BV-1", TypDokladu.BANKOVNI_VYPIS,
            date(2026, 4, 5), "5000",
        )
        zauctovani.zauctuj_doklad(d2, UctovyPredpis(
            doklad_id=d2,
            zaznamy=(UcetniZaznam(
                doklad_id=d2, datum=date(2026, 4, 5),
                md_ucet="221", dal_ucet="311",
                castka=Money.from_koruny("5000"),
            ),),
        ))

        data = dashboard_query.execute(today=date(2026, 4, 13))
        # 12 100 - 5 000 = 7 100
        assert data.pohledavky == Money.from_koruny("7100")

    def test_zavazky_jsou_321_dal_minus_md(
        self, dashboard_query, service_factories, zauctovani,
    ):
        # FP: 321 Dal 6 050 (5000 + 1050 DPH), úhrada 321 MD 4000
        d1 = _add_doklad(
            service_factories, "FP-1", TypDokladu.FAKTURA_PRIJATA,
            date(2026, 3, 10), "6050",
        )
        zauctovani.zauctuj_doklad(d1, UctovyPredpis(
            doklad_id=d1,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=d1, datum=date(2026, 3, 10),
                    md_ucet="501", dal_ucet="321",
                    castka=Money.from_koruny("5000"),
                ),
                UcetniZaznam(
                    doklad_id=d1, datum=date(2026, 3, 10),
                    md_ucet="343", dal_ucet="321",
                    castka=Money.from_koruny("1050"),
                ),
            ),
        ))

        d2 = _add_doklad(
            service_factories, "BV-2", TypDokladu.BANKOVNI_VYPIS,
            date(2026, 4, 1), "4000",
        )
        zauctovani.zauctuj_doklad(d2, UctovyPredpis(
            doklad_id=d2,
            zaznamy=(UcetniZaznam(
                doklad_id=d2, datum=date(2026, 4, 1),
                md_ucet="321", dal_ucet="221",
                castka=Money.from_koruny("4000"),
            ),),
        ))

        data = dashboard_query.execute(today=date(2026, 4, 13))
        # 6 050 - 4 000 = 2 050
        assert data.zavazky == Money.from_koruny("2050")

    def test_saldokonto_je_all_time_ne_jen_ytd(
        self, dashboard_query, service_factories, zauctovani,
    ):
        """Loňská otevřená pohledávka se musí započítat."""
        d = _add_doklad(
            service_factories, "FV-LONI", TypDokladu.FAKTURA_VYDANA,
            date(2025, 11, 1), "1000",
        )
        zauctovani.zauctuj_doklad(d, UctovyPredpis(
            doklad_id=d,
            zaznamy=(UcetniZaznam(
                doklad_id=d, datum=date(2025, 11, 1),
                md_ucet="311", dal_ucet="601",
                castka=Money.from_koruny("1000"),
            ),),
        ))

        data = dashboard_query.execute(today=date(2026, 4, 13))
        assert data.pohledavky == Money.from_koruny("1000")


# ──────────────────────────────────────────────────────────────────────
# Hospodářský výsledek + daň
# ──────────────────────────────────────────────────────────────────────


class TestHospodarskyVysledek:

    def test_zisk_a_dan_19_procent(
        self, dashboard_query, service_factories, zauctovani,
    ):
        # Výnosy YTD: 10 000 (601) + 5 000 (602) = 15 000
        # Náklady YTD: 5 000 (501) = 5 000
        # Hrubý zisk = 10 000 → daň = 1 900
        d1 = _add_doklad(
            service_factories, "FV-1", TypDokladu.FAKTURA_VYDANA,
            date(2026, 2, 1), "10000",
        )
        zauctovani.zauctuj_doklad(d1, UctovyPredpis(
            doklad_id=d1,
            zaznamy=(UcetniZaznam(
                doklad_id=d1, datum=date(2026, 2, 1),
                md_ucet="311", dal_ucet="601",
                castka=Money.from_koruny("10000"),
            ),),
        ))
        d2 = _add_doklad(
            service_factories, "FV-2", TypDokladu.FAKTURA_VYDANA,
            date(2026, 3, 1), "5000",
        )
        zauctovani.zauctuj_doklad(d2, UctovyPredpis(
            doklad_id=d2,
            zaznamy=(UcetniZaznam(
                doklad_id=d2, datum=date(2026, 3, 1),
                md_ucet="311", dal_ucet="602",
                castka=Money.from_koruny("5000"),
            ),),
        ))
        d3 = _add_doklad(
            service_factories, "FP-1", TypDokladu.FAKTURA_PRIJATA,
            date(2026, 3, 5), "5000",
        )
        zauctovani.zauctuj_doklad(d3, UctovyPredpis(
            doklad_id=d3,
            zaznamy=(UcetniZaznam(
                doklad_id=d3, datum=date(2026, 3, 5),
                md_ucet="501", dal_ucet="321",
                castka=Money.from_koruny("5000"),
            ),),
        ))

        data = dashboard_query.execute(today=date(2026, 4, 13))
        assert data.vynosy == Money.from_koruny("15000")
        assert data.naklady == Money.from_koruny("5000")
        assert data.hruby_zisk == Money.from_koruny("10000")
        assert data.odhad_dane == Money.from_koruny("1900")
        assert data.je_ve_ztrate is False

    def test_ztrata_dan_je_nula(
        self, dashboard_query, service_factories, zauctovani,
    ):
        # Jen náklad → ztráta → daň = 0
        d = _add_doklad(
            service_factories, "FP-LOSS", TypDokladu.FAKTURA_PRIJATA,
            date(2026, 2, 1), "3000",
        )
        zauctovani.zauctuj_doklad(d, UctovyPredpis(
            doklad_id=d,
            zaznamy=(UcetniZaznam(
                doklad_id=d, datum=date(2026, 2, 1),
                md_ucet="501", dal_ucet="321",
                castka=Money.from_koruny("3000"),
            ),),
        ))

        data = dashboard_query.execute(today=date(2026, 4, 13))
        assert data.naklady == Money.from_koruny("3000")
        assert data.vynosy == Money.zero()
        assert data.hruby_zisk == Money.from_koruny("-3000")
        assert data.odhad_dane == Money.zero()
        assert data.je_ve_ztrate is True

    def test_hv_jen_vybrany_rok_default(
        self, dashboard_query, service_factories, zauctovani,
    ):
        """Loňský výnos se nezapočte do zisku za 2026 (default)."""
        d = _add_doklad(
            service_factories, "FV-LONI", TypDokladu.FAKTURA_VYDANA,
            date(2025, 11, 1), "9999",
        )
        zauctovani.zauctuj_doklad(d, UctovyPredpis(
            doklad_id=d,
            zaznamy=(UcetniZaznam(
                doklad_id=d, datum=date(2025, 11, 1),
                md_ucet="311", dal_ucet="601",
                castka=Money.from_koruny("9999"),
            ),),
        ))

        data = dashboard_query.execute(today=date(2026, 4, 13))
        assert data.vynosy == Money.zero()
        assert data.hruby_zisk == Money.zero()

    def test_hv_za_vybrany_rok_2025(
        self, dashboard_query, service_factories, zauctovani,
    ):
        """S zisk_rok=2025 se loňský výnos započte."""
        d = _add_doklad(
            service_factories, "FV-LONI", TypDokladu.FAKTURA_VYDANA,
            date(2025, 11, 1), "9999",
        )
        zauctovani.zauctuj_doklad(d, UctovyPredpis(
            doklad_id=d,
            zaznamy=(UcetniZaznam(
                doklad_id=d, datum=date(2025, 11, 1),
                md_ucet="311", dal_ucet="601",
                castka=Money.from_koruny("9999"),
            ),),
        ))

        data = dashboard_query.execute(today=date(2026, 4, 13), zisk_rok=2025)
        assert data.rok == 2025
        assert data.vynosy == Money.from_koruny("9999")
        assert data.hruby_zisk == Money.from_koruny("9999")
