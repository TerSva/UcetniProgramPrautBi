"""Testy pro ZauctovaniDokladuService."""

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import DphRezim, StavDokladu, TypDokladu
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


class TestStornujDoklad:
    """Fáze 6.5: storno přes opravný účetní předpis."""

    def test_stornuje_zauctovany_doklad(
        self, service, fv_v_db, service_factories,
    ):
        """Po stornu: stav=STORNOVANY + 2 protizápisy se správně zapsanými flagy."""
        doklad_id = fv_v_db
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))

        doklad, protizapisy = service.stornuj_doklad(
            doklad_id, datum=date(2026, 4, 20),
        )

        assert doklad.stav == StavDokladu.STORNOVANY
        assert len(protizapisy) == 2
        for p in protizapisy:
            assert p.je_storno is True
            assert p.stornuje_zaznam_id is not None
            assert p.datum == date(2026, 4, 20)

    def test_protizapisy_maji_prohozene_strany(
        self, service, fv_v_db, service_factories,
    ):
        doklad_id = fv_v_db
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))

        _, protizapisy = service.stornuj_doklad(
            doklad_id, datum=date(2026, 4, 20),
        )

        # Originály: 311/601 (základ), 311/343 (DPH)
        # Protizápisy: 601/311, 343/311
        pary = {(p.md_ucet, p.dal_ucet) for p in protizapisy}
        assert pary == {("601", "311"), ("343", "311")}

    def test_castky_zachovane_kladne(
        self, service, fv_v_db, service_factories,
    ):
        doklad_id = fv_v_db
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))

        _, protizapisy = service.stornuj_doklad(doklad_id)

        castky = sorted(p.castka for p in protizapisy)
        assert castky == sorted([
            Money.from_koruny("10000"),
            Money.from_koruny("2100"),
        ])
        # Všechny kladné (Varianta A — ne červený zápis)
        assert all(p.castka.is_positive for p in protizapisy)

    def test_nelze_stornovat_novy(self, service, fv_v_db):
        """NOVY doklad — nemá co reversovat, použij Smazat."""
        with pytest.raises(ValidationError, match="NOVY"):
            service.stornuj_doklad(fv_v_db)

    def test_nelze_stornovat_uhrazeny(
        self, service, fv_v_db, service_factories,
    ):
        doklad_id = fv_v_db
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))
        # Ručně nastav UHRAZENY (přes doklad entity)
        uow = service_factories["uow"]()
        with uow:
            repo = SqliteDokladyRepository(uow)
            d = repo.get_by_id(doklad_id)
            d.oznac_uhrazeny()
            repo.update(d)
            uow.commit()

        with pytest.raises(ValidationError, match="UHRAZENY"):
            service.stornuj_doklad(doklad_id)

    def test_nonexistent_doklad(self, service):
        with pytest.raises(NotFoundError):
            service.stornuj_doklad(99999)

    def test_idempotentni_pri_stornovanem(
        self, service, fv_v_db, service_factories,
    ):
        """Druhé volání na už stornovaném dokladu = no-op, vrátí stav."""
        doklad_id = fv_v_db
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))
        service.stornuj_doklad(doklad_id, datum=date(2026, 4, 20))

        # Druhé zavolání — žádný nový zápis, žádná výjimka
        doklad2, protizapisy2 = service.stornuj_doklad(doklad_id)
        assert doklad2.stav == StavDokladu.STORNOVANY
        # Vrátí existující protizápisy (idempotence)
        assert len(protizapisy2) == 2

        # V DB stále jen 2 protizápisy (ne 4)
        uow = service_factories["uow"]()
        with uow:
            zz = SqliteUcetniDenikRepository(uow).list_by_doklad(doklad_id)
            storno_count = sum(1 for z in zz if z.je_storno)
            assert storno_count == 2

    def test_atomicita_rollback_pri_chybe(
        self, service, fv_v_db, service_factories,
    ):
        """Když deaktivujeme účet během storna, rollback: stav zůstane ZAUCTOVANY."""
        doklad_id = fv_v_db
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))

        # Deaktivuj 601 — storno `601/311` selže na validaci „deaktivované"
        uow = service_factories["uow"]()
        with uow:
            osnova = SqliteUctovaOsnovaRepository(uow)
            u = osnova.get_by_cislo("601")
            u.deaktivuj()
            osnova.update(u)
            uow.commit()

        with pytest.raises(ValidationError, match="deaktivované"):
            service.stornuj_doklad(doklad_id)

        # Doklad pořád ZAUCTOVANY
        uow2 = service_factories["uow"]()
        with uow2:
            d = SqliteDokladyRepository(uow2).get_by_id(doklad_id)
            assert d.stav == StavDokladu.ZAUCTOVANY
            # Žádné protizápisy
            zz = SqliteUcetniDenikRepository(uow2).list_by_doklad(doklad_id)
            assert all(not z.je_storno for z in zz)

    def test_default_datum_je_datum_vystaveni(
        self, service, fv_v_db, service_factories,
    ):
        """Bez explicitního data → použije se datum_vystaveni originálu.

        Důvod: storno musí spadnout do stejného účetního období jako
        původní doklad. Dnešní datum (date.today()) by mohlo být v jiném
        roce a způsobilo by neopravitelnou účetní chybu — viz bug
        s ID-2025-003 stornováným v dubnu 2026 mimo rok 2025.
        """
        doklad_id = fv_v_db   # datum_vystaveni = 2026-04-11
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))

        _, protizapisy = service.stornuj_doklad(doklad_id)

        for p in protizapisy:
            assert p.datum == date(2026, 4, 11)

    def test_explicitni_datum_prebije_default(
        self, service, fv_v_db, service_factories,
    ):
        """Když UI předá datum, použije se to (ne datum_vystaveni)."""
        doklad_id = fv_v_db
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))

        _, protizapisy = service.stornuj_doklad(
            doklad_id, datum=date(2026, 12, 31),
        )

        for p in protizapisy:
            assert p.datum == date(2026, 12, 31)

    def test_poznamka_se_ulozi_do_popisu_storna(
        self, service, fv_v_db, service_factories,
    ):
        """Uživatelská poznámka se promítne do popisu storno zápisů."""
        doklad_id = fv_v_db
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))

        _, protizapisy = service.stornuj_doklad(
            doklad_id, poznamka="Duplicitní zaúčtování ZK",
        )

        for p in protizapisy:
            assert p.popis == "Storno: Duplicitní zaúčtování ZK"

    def test_bez_poznamky_zachova_default_popis(
        self, service, fv_v_db, service_factories,
    ):
        """Bez poznámky zůstává původní 'Storno: {orig.popis}' chování."""
        doklad_id = fv_v_db
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))

        _, protizapisy = service.stornuj_doklad(doklad_id)

        popisy = {p.popis for p in protizapisy}
        assert popisy == {"Storno: Tržba", "Storno: DPH 21%"}

    def test_dvoji_storno_idempotence_soucet_nula(
        self, service, fv_v_db, service_factories,
    ):
        """Po stornu: soucet castky originalu + protizapisy = 2*castka.

        Matematický smysl: v hlavní knize se obě strany vzájemně ruší
        (MD 311 +12100 z originálu, Dal 311 +12100 z protizápisu → 0 na 311).
        Sumárně se tedy všechny částky VIDÍ, ale netto dopad = 0.
        """
        doklad_id = fv_v_db
        service.zauctuj_doklad(doklad_id, _predpis_fv(doklad_id))
        service.stornuj_doklad(doklad_id)

        uow = service_factories["uow"]()
        with uow:
            zz = SqliteUcetniDenikRepository(uow).list_by_doklad(doklad_id)
            # Netto pro 311 (MD): originály mají 311 na MD, protizápisy na Dal
            md_311 = sum(
                (z.castka.to_halire() for z in zz if z.md_ucet == "311"),
                start=0,
            )
            dal_311 = sum(
                (z.castka.to_halire() for z in zz if z.dal_ucet == "311"),
                start=0,
            )
            assert md_311 == dal_311  # anulace


class TestReverseChargeValidation:
    """RC doklady: DPH řádky (343/343) neblokují validaci částky."""

    @pytest.fixture
    def rc_doklad(self, service_factories):
        """FP 44 Kč s dph_rezim=REVERSE_CHARGE."""
        uow = service_factories["uow"]()
        with uow:
            repo = SqliteDokladyRepository(uow)
            d = repo.add(Doklad(
                cislo="FP-RC-001",
                typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2025, 4, 23),
                castka_celkem=Money(4400),
                dph_rezim=DphRezim.REVERSE_CHARGE,
            ))
            uow.commit()
        return d.id

    def test_rc_zauctovani_projde(self, service, rc_doklad):
        """RC doklad 44 Kč + DPH 9,24 Kč → součet 53,24 → projde."""
        predpis = UctovyPredpis(
            doklad_id=rc_doklad,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=rc_doklad, datum=date(2025, 4, 23),
                    md_ucet="518.200", dal_ucet="321.002",
                    castka=Money(4400),
                ),
                UcetniZaznam(
                    doklad_id=rc_doklad, datum=date(2025, 4, 23),
                    md_ucet="343.100", dal_ucet="343.200",
                    castka=Money(924),
                ),
            ),
        )
        doklad, zapisy = service.zauctuj_doklad(rc_doklad, predpis)
        assert doklad.stav == StavDokladu.ZAUCTOVANY
        assert len(zapisy) == 2

    def test_rc_zaklad_nesouhlasi_selze(self, service, rc_doklad):
        """RC doklad 44 Kč, základ 40 Kč → selže (základ != castka_celkem)."""
        predpis = UctovyPredpis(
            doklad_id=rc_doklad,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=rc_doklad, datum=date(2025, 4, 23),
                    md_ucet="518.200", dal_ucet="321.002",
                    castka=Money(4000),  # 40 Kč, ne 44
                ),
                UcetniZaznam(
                    doklad_id=rc_doklad, datum=date(2025, 4, 23),
                    md_ucet="343.100", dal_ucet="343.200",
                    castka=Money(840),
                ),
            ),
        )
        with pytest.raises(PodvojnostError, match="nesouhlasí"):
            service.zauctuj_doklad(rc_doklad, predpis)

    def test_tuzemsky_s_dph_343_343_detekovan_jako_rc(self, service, fv_v_db):
        """Tuzemský doklad + 343/343 v předpisu → service detekuje RC.

        User mohl ručně zaškrtnout RC checkbox v dialogu; service to musí
        respektovat: porovná jen základ (ne-DPH řádky) s castka_celkem
        a doklad.dph_rezim dorovná na REVERSE_CHARGE.
        """
        predpis = UctovyPredpis(
            doklad_id=fv_v_db,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=fv_v_db, datum=date(2026, 4, 11),
                    md_ucet="311", dal_ucet="601",
                    castka=Money.from_koruny("12100"),
                ),
                UcetniZaznam(
                    doklad_id=fv_v_db, datum=date(2026, 4, 11),
                    md_ucet="343.100", dal_ucet="343.200",
                    castka=Money.from_koruny("2541"),
                ),
            ),
        )
        doklad, _ = service.zauctuj_doklad(fv_v_db, predpis)
        assert doklad.dph_rezim == DphRezim.REVERSE_CHARGE
        assert doklad.stav == StavDokladu.ZAUCTOVANY

    def test_eur_doklad_s_rc_v_dialogu(self, service, service_factories):
        """EUR doklad TUZEMSKO → user ručně zaškrtne RC → správně se zaúčtuje."""
        from decimal import Decimal as _D
        from domain.doklady.typy import Mena

        # Vytvoř EUR fakturu jako TUZEMSKO (OCR ji neoznačilo jako RC)
        uow = service_factories["uow"]()
        with uow:
            repo = SqliteDokladyRepository(uow)
            d = repo.add(Doklad(
                cislo="FP-EUR-RC-001",
                typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2025, 5, 1),
                castka_celkem=Money(250000),  # 2 500 CZK (přepočet)
                mena=Mena.EUR,
                castka_mena=Money(10000),     # 100 EUR
                kurz=_D("25.00"),
                dph_rezim=DphRezim.TUZEMSKO,  # ← OCR neoznačilo RC
            ))
            uow.commit()
        doklad_id = d.id

        # Předpis se zaškrtnutým RC v dialogu (518.200/321.002 + 343/343)
        predpis = UctovyPredpis(
            doklad_id=doklad_id,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=doklad_id, datum=date(2025, 5, 1),
                    md_ucet="518.200", dal_ucet="321.002",
                    castka=Money(250000),
                ),
                UcetniZaznam(
                    doklad_id=doklad_id, datum=date(2025, 5, 1),
                    md_ucet="343.100", dal_ucet="343.200",
                    castka=Money(52500),  # 21% z 2 500
                ),
            ),
        )
        doklad, zapisy = service.zauctuj_doklad(doklad_id, predpis)
        assert doklad.stav == StavDokladu.ZAUCTOVANY
        assert doklad.dph_rezim == DphRezim.REVERSE_CHARGE  # auto-dorovnán
        assert len(zapisy) == 2

    def test_tuzemsky_s_dph_zaklad_nesouhlasi_selze(self, service, fv_v_db):
        """Tuzemský doklad + 343/343 ale základ != castka_celkem → selže."""
        predpis = UctovyPredpis(
            doklad_id=fv_v_db,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=fv_v_db, datum=date(2026, 4, 11),
                    md_ucet="311", dal_ucet="601",
                    castka=Money.from_koruny("10000"),  # ne 12100
                ),
                UcetniZaznam(
                    doklad_id=fv_v_db, datum=date(2026, 4, 11),
                    md_ucet="343.100", dal_ucet="343.200",
                    castka=Money.from_koruny("2100"),
                ),
            ),
        )
        with pytest.raises(PodvojnostError, match="nesouhlasí"):
            service.zauctuj_doklad(fv_v_db, predpis)


class TestZuctovaniZalohy:
    """Konečná FV/FP s odečtem zálohy — auto-UHRAZENÍ + označení ZF."""

    def _make_doklady(
        self, service_factories, finalni_castka_kc: str,
    ) -> tuple[int, str, str]:
        """Vytvoř ZF (UHRAZENY) + finální FV (ZAUCTOVANY-ready).

        Vrací (finalni_id, finalni_cislo, zf_cislo).
        """
        from domain.doklady.typy import Mena
        uow = service_factories["uow"]()
        with uow:
            repo = SqliteDokladyRepository(uow)
            zf = repo.add(Doklad(
                cislo="ZF-2025-001",
                typ=TypDokladu.ZALOHA_FAKTURA,
                datum_vystaveni=date(2025, 4, 1),
                castka_celkem=Money.from_koruny(finalni_castka_kc),
                stav=StavDokladu.UHRAZENY,
                je_vystavena=True,
            ))
            fv = repo.add(Doklad(
                cislo="FV-FINAL-001",
                typ=TypDokladu.FAKTURA_VYDANA,
                datum_vystaveni=date(2025, 4, 30),
                castka_celkem=Money.from_koruny(finalni_castka_kc),
            ))
            uow.commit()
        return fv.id, fv.cislo, zf.cislo

    def test_zauctovani_se_zalohou_oznaci_doklad_uhrazeny(
        self, service, service_factories,
    ):
        """Finální FV 50000 + odečet 50000 ze zálohy → stav UHRAZENY."""
        fv_id, fv_cislo, zf_cislo = self._make_doklady(
            service_factories, "50000",
        )
        predpis = UctovyPredpis(
            doklad_id=fv_id,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=fv_id, datum=date(2025, 4, 30),
                    md_ucet="311", dal_ucet="601",
                    castka=Money.from_koruny("50000"),
                ),
                UcetniZaznam(
                    doklad_id=fv_id, datum=date(2025, 4, 30),
                    md_ucet="324.001", dal_ucet="311",
                    castka=Money.from_koruny("50000"),
                    popis=f"Odečet zálohy {zf_cislo}",
                ),
            ),
        )
        doklad, _ = service.zauctuj_doklad(fv_id, predpis)
        # Auto-UHRAZENO: záloha pokrývá celou pohledávku
        assert doklad.stav == StavDokladu.UHRAZENY

    def test_zauctovani_castecny_odecet_zustava_zauctovany(
        self, service, service_factories,
    ):
        """FV 50000 + odečet 30000 → ZAUCTOVANY (zbývá 20000 doplatit)."""
        fv_id, fv_cislo, zf_cislo = self._make_doklady(
            service_factories, "50000",
        )
        predpis = UctovyPredpis(
            doklad_id=fv_id,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=fv_id, datum=date(2025, 4, 30),
                    md_ucet="311", dal_ucet="601",
                    castka=Money.from_koruny("50000"),
                ),
                UcetniZaznam(
                    doklad_id=fv_id, datum=date(2025, 4, 30),
                    md_ucet="324.001", dal_ucet="311",
                    castka=Money.from_koruny("30000"),
                    popis=f"Odečet zálohy {zf_cislo}",
                ),
            ),
        )
        doklad, _ = service.zauctuj_doklad(fv_id, predpis)
        # Záloha nepokryla celou částku → klasický ZAUCTOVANY,
        # zbývá 20000 doplatit přes banku
        assert doklad.stav == StavDokladu.ZAUCTOVANY

    def test_zaloha_oznacena_v_popisu_finalni_doklad(
        self, service, service_factories,
    ):
        """Po zaúčtování finální FV se ZF doklad označí v popisu."""
        fv_id, fv_cislo, zf_cislo = self._make_doklady(
            service_factories, "50000",
        )
        predpis = UctovyPredpis(
            doklad_id=fv_id,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=fv_id, datum=date(2025, 4, 30),
                    md_ucet="311", dal_ucet="601",
                    castka=Money.from_koruny("50000"),
                ),
                UcetniZaznam(
                    doklad_id=fv_id, datum=date(2025, 4, 30),
                    md_ucet="324.001", dal_ucet="311",
                    castka=Money.from_koruny("50000"),
                    popis=f"Odečet zálohy {zf_cislo}",
                ),
            ),
        )
        service.zauctuj_doklad(fv_id, predpis)

        # Najdi ZF a zkontroluj popis
        uow = service_factories["uow"]()
        with uow:
            repo = SqliteDokladyRepository(uow)
            zf = repo.get_by_cislo(zf_cislo)
            assert zf.popis is not None
            assert f"Zúčtováno s {fv_cislo}" in zf.popis
