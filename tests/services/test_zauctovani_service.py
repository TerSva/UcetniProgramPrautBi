"""Testy pro ZauctovaniDokladuService."""

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import NotFoundError, PodvojnostError, ValidationError
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
from services.zauctovani_service import ZauctovaniDokladuService


@pytest.fixture
def service(service_factories):
    return ZauctovaniDokladuService(
        uow_factory=service_factories["uow"],
        doklady_repo_factory=service_factories["doklady"],
        denik_repo_factory=service_factories["denik"],
    )


@pytest.fixture
def fv_v_db(service_factories):
    """FV 12 100 Kč v DB, vrací doklad_id."""
    uow = service_factories["uow"]()
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(
            cislo="FV-2026-001",
            typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2026, 4, 11),
            datum_splatnosti=date(2026, 4, 25),
            castka_celkem=Money.from_koruny("12100"),
            popis="Testovací FV",
        ))
        uow.commit()
    return d.id


def _predpis_fv(doklad_id: int) -> UctovyPredpis:
    """Předpis pro FV 12 100 Kč: základ 10 000 + DPH 2 100."""
    return UctovyPredpis(
        doklad_id=doklad_id,
        zaznamy=(
            UcetniZaznam(
                doklad_id=doklad_id, datum=date(2026, 4, 11),
                md_ucet="311", dal_ucet="601", castka=Money.from_koruny("10000"),
                popis="Tržba",
            ),
            UcetniZaznam(
                doklad_id=doklad_id, datum=date(2026, 4, 11),
                md_ucet="311", dal_ucet="343", castka=Money.from_koruny("2100"),
                popis="DPH 21%",
            ),
        ),
    )


class TestHappyPath:

    def test_zauctuj_fv_s_dph(self, service, fv_v_db, service_factories):
        doklad_id = fv_v_db
        predpis = _predpis_fv(doklad_id)

        doklad, zaznamy = service.zauctuj_doklad(doklad_id, predpis)

        assert doklad.stav == StavDokladu.ZAUCTOVANY
        assert len(zaznamy) == 2
        assert all(z.id is not None for z in zaznamy)
        assert zaznamy[0].castka == Money.from_koruny("10000")
        assert zaznamy[1].castka == Money.from_koruny("2100")

        # Ověř v DB
        uow = service_factories["uow"]()
        with uow:
            d = SqliteDokladyRepository(uow).get_by_id(doklad_id)
            assert d.stav == StavDokladu.ZAUCTOVANY
            zz = SqliteUcetniDenikRepository(uow).list_by_doklad(doklad_id)
            assert len(zz) == 2

    def test_returned_doklad_is_detached_snapshot(
        self, service, fv_v_db, service_factories
    ):
        doklad_id = fv_v_db
        doklad, zaznamy = service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))

        # In-memory snapshot po uzavřené UoW
        assert doklad.stav == StavDokladu.ZAUCTOVANY
        assert doklad.cislo == "FV-2026-001"
        assert doklad.castka_celkem == Money.from_koruny("12100")

        # Nezávisle načtený doklad taky ZAUCTOVANY
        uow = service_factories["uow"]()
        with uow:
            fresh = SqliteDokladyRepository(uow).get_by_id(doklad_id)
        assert fresh.stav == StavDokladu.ZAUCTOVANY


class TestValidace:

    def test_konzistence_id_v_predpisu(self, service, fv_v_db):
        predpis = _predpis_fv(99999)  # jiný doklad_id
        with pytest.raises(ValidationError, match="odkazuje na doklad"):
            service.zauctuj_doklad(fv_v_db, predpis)

    def test_doklad_neexistuje(self, service):
        predpis = _predpis_fv(99999)
        with pytest.raises(NotFoundError):
            service.zauctuj_doklad(99999, predpis)

    def test_doklad_neni_novy(self, service, fv_v_db, service_factories):
        doklad_id = fv_v_db
        # Zaúčtuj poprvé
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))
        # Podruhé → ValidationError z doklad.zauctuj()
        with pytest.raises(ValidationError, match="zauctovany"):
            service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))

    def test_predpis_nesouhlasi_s_castkou(self, service, fv_v_db):
        doklad_id = fv_v_db
        # Předpis jen 12 000, ale doklad je 12 100
        predpis = UctovyPredpis.jednoduchy(
            doklad_id=doklad_id, datum=date(2026, 4, 11),
            md_ucet="311", dal_ucet="601", castka=Money.from_koruny("12000"),
        )
        with pytest.raises(PodvojnostError, match="nesouhlasí"):
            service.zauctuj_doklad(doklad_id, predpis)

    def test_ucet_neexistuje(self, service, fv_v_db):
        doklad_id = fv_v_db
        predpis = UctovyPredpis.jednoduchy(
            doklad_id=doklad_id, datum=date(2026, 4, 11),
            md_ucet="999", dal_ucet="601", castka=Money.from_koruny("12100"),
        )
        with pytest.raises(NotFoundError, match="999"):
            service.zauctuj_doklad(doklad_id, predpis)

    def test_ucet_deaktivovany(self, service, fv_v_db, service_factories):
        # Deaktivuj 311
        uow = service_factories["uow"]()
        with uow:
            osnova = SqliteUctovaOsnovaRepository(uow)
            u = osnova.get_by_cislo("311")
            u.deaktivuj()
            osnova.update(u)
            uow.commit()

        predpis = _predpis_fv(fv_v_db)
        with pytest.raises(ValidationError, match="deaktivované"):
            service.zauctuj_doklad(fv_v_db, predpis)


class TestAtomicita:

    def test_selhani_zachova_doklad_novy(self, service, fv_v_db, service_factories):
        """Po selhání zaúčtování: doklad stále NOVY, deník prázdný."""
        doklad_id = fv_v_db
        # Předpis s neexistujícím účtem → selže v denik_repo.zauctuj()
        predpis = UctovyPredpis(
            doklad_id=doklad_id,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=doklad_id, datum=date(2026, 4, 11),
                    md_ucet="311", dal_ucet="601",
                    castka=Money.from_koruny("10000"),
                ),
                UcetniZaznam(
                    doklad_id=doklad_id, datum=date(2026, 4, 11),
                    md_ucet="999", dal_ucet="343",  # 999 neexistuje
                    castka=Money.from_koruny("2100"),
                ),
            ),
        )
        with pytest.raises(NotFoundError):
            service.zauctuj_doklad(doklad_id, predpis)

        # Doklad stále NOVY
        uow = service_factories["uow"]()
        with uow:
            d = SqliteDokladyRepository(uow).get_by_id(doklad_id)
            assert d.stav == StavDokladu.NOVY

        # Deník prázdný
        uow2 = service_factories["uow"]()
        with uow2:
            zz = SqliteUcetniDenikRepository(uow2).list_by_doklad(doklad_id)
            assert len(zz) == 0
