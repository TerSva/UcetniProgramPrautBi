"""E2E integration testy pro Fázi 6.5 — storno přes opravný účetní předpis.

Prochází celým workflow: vytvoř doklad → zaúčtuj → stornuj → ověř, že:
  1. Protizápisy existují v deníku s správnými flagy a prohozenými stranami.
  2. Předvaha sečte netto 0 na všech účtech dotčených stornovaným dokladem.
  3. Hlavní kniha ukazuje originál i storno zápisy.
  4. Dashboard KPI se aktualizují (výnosy, pohledávky, hrubý zisk, odhad daně).
"""

from __future__ import annotations

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.repositories.uctova_osnova_repository import (
    SqliteUctovaOsnovaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.dashboard import DashboardDataQuery
from services.queries.hlavni_kniha import HlavniKnihaQuery
from services.queries.predvaha import PredvahaQuery
from services.zauctovani_service import ZauctovaniDokladuService


@pytest.fixture
def service(service_factories):
    return ZauctovaniDokladuService(
        uow_factory=service_factories["uow"],
        doklady_repo_factory=service_factories["doklady"],
        denik_repo_factory=service_factories["denik"],
    )


def _seed_fv(db_factory, cislo: str, castka: str = "12100") -> int:
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(
            cislo=cislo,
            typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2026, 4, 1),
            datum_splatnosti=date(2026, 4, 15),
            castka_celkem=Money.from_koruny(castka),
        ))
        uow.commit()
    return d.id  # type: ignore[return-value]


def _predpis_fv(doklad_id: int, datum: date = date(2026, 4, 1)) -> UctovyPredpis:
    """Předpis pro FV 12 100 Kč: základ 10 000 + DPH 2 100."""
    return UctovyPredpis(
        doklad_id=doklad_id,
        zaznamy=(
            UcetniZaznam(
                doklad_id=doklad_id, datum=datum,
                md_ucet="311", dal_ucet="601",
                castka=Money.from_koruny("10000"),
                popis="Tržba",
            ),
            UcetniZaznam(
                doklad_id=doklad_id, datum=datum,
                md_ucet="311", dal_ucet="343",
                castka=Money.from_koruny("2100"),
                popis="DPH 21%",
            ),
        ),
    )


class TestStornoE2E:

    def test_storno_workflow_vytvori_protizapisy(
        self, service, service_factories,
    ):
        """Storno vytvoří 2 protizápisy odpovídající 2 originálním zápisům."""
        doklad_id = _seed_fv(service_factories["db_factory"], "FV-STORNO-1")
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))

        doklad, protizapisy = service.stornuj_doklad(
            doklad_id, datum=date(2026, 4, 20),
        )

        assert doklad.stav == StavDokladu.STORNOVANY
        assert len(protizapisy) == 2

        # Ověř v DB
        uow = service_factories["uow"]()
        with uow:
            denik = SqliteUcetniDenikRepository(uow)
            zaznamy = denik.list_by_doklad(doklad_id)
            assert len(zaznamy) == 4  # 2 originály + 2 protizápisy
            originaly = [z for z in zaznamy if not z.je_storno]
            storna = [z for z in zaznamy if z.je_storno]
            assert len(originaly) == 2
            assert len(storna) == 2
            for s in storna:
                assert s.stornuje_zaznam_id in {o.id for o in originaly}

    def test_storno_predvaha_netto_nula(self, service, service_factories):
        """Po stornu: Předvaha musí ukazovat netto 0 na všech dotčených účtech."""
        doklad_id = _seed_fv(service_factories["db_factory"], "FV-STORNO-2")
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))
        service.stornuj_doklad(doklad_id, datum=date(2026, 4, 20))

        q = PredvahaQuery(
            uow_factory=service_factories["uow"],
            denik_repo_factory=service_factories["denik"],
            osnova_repo_factory=service_factories["osnova"],
        )
        predvaha = q.execute(od=date(2026, 1, 1), do=date(2026, 12, 31))

        # Pro každý dotčený účet: MD total == Dal total → netto 0
        by_ucet = {r.ucet_cislo: r for r in predvaha.radky}
        for cislo in ("311", "601", "343"):
            if cislo in by_ucet:
                r = by_ucet[cislo]
                assert r.obrat_md == r.obrat_dal, (
                    f"Účet {cislo}: MD {r.obrat_md} != Dal {r.obrat_dal} "
                    f"— storno neanulovalo originál."
                )

    def test_storno_hlavni_kniha_ma_obe_sady(
        self, service, service_factories,
    ):
        """Hlavní kniha pro 601 obsahuje originál (Dal) i storno (MD)."""
        doklad_id = _seed_fv(service_factories["db_factory"], "FV-STORNO-3")
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))
        service.stornuj_doklad(doklad_id, datum=date(2026, 4, 20))

        q = HlavniKnihaQuery(
            uow_factory=service_factories["uow"],
            denik_repo_factory=service_factories["denik"],
            osnova_repo_factory=service_factories["osnova"],
            doklady_repo_factory=service_factories["doklady"],
        )
        vypis = q.execute(
            ucet_cislo="601",
            od=date(2026, 1, 1), do=date(2026, 12, 31),
        )
        # 2 zápisy: originál (Dal strana) + storno (MD strana)
        assert len(vypis.radky) == 2
        # Součty MD == Dal (anulace)
        assert vypis.obrat_md == vypis.obrat_dal

    def test_storno_dashboard_kpi_se_aktualizuji(
        self, service, service_factories,
    ):
        """Po stornu Dashboard KPI reflektují anulaci.

        Před stornem FV 12 100 Kč (10k základ + 2,1k DPH):
          výnosy=10k, pohledávky=12,1k, hrubý zisk=10k, odhad daně=1900
        Po stornu: vše na 0 (netto dopad storna = anulace originálu).
        """
        doklad_id = _seed_fv(service_factories["db_factory"], "FV-KPI")
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))

        q = DashboardDataQuery(
            uow_factory=service_factories["uow"],
            doklady_repo_factory=service_factories["doklady"],
            denik_repo_factory=service_factories["denik"],
            osnova_repo_factory=service_factories["osnova"],
        )

        # Fixujeme "today" — storno se děje 2026-04-20, takže YTD okno
        # musí sahat aspoň do konce dubna (jinak by protizápisy vypadly).
        today = date(2026, 4, 30)

        # KPI PŘED stornem
        before = q.execute(today=today)
        assert before.vynosy == Money.from_koruny("10000")
        assert before.pohledavky == Money.from_koruny("12100")
        assert before.hruby_zisk == Money.from_koruny("10000")

        # Stornuj
        service.stornuj_doklad(doklad_id, datum=date(2026, 4, 20))

        # KPI PO stornu — netto 0 (anulace)
        after = q.execute(today=today)
        assert after.vynosy == Money.zero()
        assert after.pohledavky == Money.zero()
        assert after.hruby_zisk == Money.zero()
        assert after.odhad_dane == Money.zero()
