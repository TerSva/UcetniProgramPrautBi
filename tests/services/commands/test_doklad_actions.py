"""Integration testy pro DokladActionsCommand."""

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import ValidationError
from domain.shared.money import Money
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.commands.doklad_actions import DokladActionsCommand
from services.commands.zauctovat_doklad import (
    ZauctovatDokladCommand,
    ZauctovatDokladInput,
    ZauctovatRadek,
)
from services.zauctovani_service import ZauctovaniDokladuService


def _seed(
    db_factory,
    cislo: str = "FV-2026-001",
    castka: str = "1000",
    k_doreseni: bool = False,
    poznamka: str | None = None,
    splatnost: date | None = None,
    popis: str | None = None,
) -> int:
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(
            cislo=cislo,
            typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2026, 3, 1),
            castka_celkem=Money.from_koruny(castka),
            datum_splatnosti=splatnost,
            popis=popis,
            k_doreseni=k_doreseni,
            poznamka_doreseni=poznamka,
        ))
        uow.commit()
    return d.id  # type: ignore[return-value]


def _zauctuj(db_factory, doklad_id: int, castka: str) -> None:
    cmd = ZauctovatDokladCommand(
        uow_factory=lambda: SqliteUnitOfWork(db_factory),
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
        denik_repo_factory=lambda uow: SqliteUcetniDenikRepository(uow),
    )
    cmd.execute(ZauctovatDokladInput(
        doklad_id=doklad_id,
        datum=date(2026, 3, 1),
        radky=[ZauctovatRadek(
            md_ucet="311", dal_ucet="601",
            castka=Money.from_koruny(castka),
        )],
    ))


def _build_actions(db_factory) -> DokladActionsCommand:
    """Helper pro sestavení DokladActionsCommand s novou signaturou (Fáze 6.5).

    DokladActionsCommand si vezme ZauctovaniDokladuService, který je potřeba
    pro ``stornovat()`` (protizápisy přes opravný účetní předpis).
    """
    uow_factory = lambda: SqliteUnitOfWork(db_factory)  # noqa: E731
    doklady_repo_factory = lambda uow: SqliteDokladyRepository(uow)  # noqa: E731
    denik_repo_factory = lambda uow: SqliteUcetniDenikRepository(uow)  # noqa: E731
    zauctovani_service = ZauctovaniDokladuService(
        uow_factory=uow_factory,
        doklady_repo_factory=doklady_repo_factory,
        denik_repo_factory=denik_repo_factory,
    )
    return DokladActionsCommand(
        uow_factory=uow_factory,
        doklady_repo_factory=doklady_repo_factory,
        zauctovani_service=zauctovani_service,
    )


# Zpětně kompatibilní alias — zachovává existující call-sites
_build = _build_actions


class TestStornovat:
    """Fáze 6.5: stornovat() deleguje na ZauctovaniDokladuService.

    Pro NOVY doklad (bez zápisů) je storno zakázáno — uživatelka má použít
    Smazat. Pro ZAUCTOVANY/CASTECNE_UHRAZENY vznikne protizápis + stav
    se změní na STORNOVANY.
    """

    def test_nelze_stornovat_novy_doklad(self, db_factory):
        doklad_id = _seed(db_factory)
        cmd = _build(db_factory)
        with pytest.raises(ValidationError, match="NOVY"):
            cmd.stornovat(doklad_id)

    def test_stornuje_zauctovany_doklad(self, db_factory):
        doklad_id = _seed(db_factory, castka="500")
        _zauctuj(db_factory, doklad_id, "500")
        cmd = _build(db_factory)
        item = cmd.stornovat(doklad_id)
        assert item.stav == StavDokladu.STORNOVANY

    def test_storno_vycisti_k_doreseni(self, db_factory):
        """Po stornu zaúčtovaného k_doreseni flagu se flag vyčistí."""
        doklad_id = _seed(
            db_factory, castka="500",
            k_doreseni=True, poznamka="chybí IČO",
        )
        _zauctuj(db_factory, doklad_id, "500")
        # Znovu nastav k_doreseni (zauctuj ho nemaže)
        from domain.doklady.typy import StavDokladu as _S  # noqa: F401
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            d = repo.get_by_id(doklad_id)
            d.oznac_k_doreseni("chybí IČO")
            repo.update(d)
            uow.commit()

        cmd = _build(db_factory)
        item = cmd.stornovat(doklad_id)
        assert item.stav == StavDokladu.STORNOVANY
        assert item.k_doreseni is False
        assert item.poznamka_doreseni is None


class TestSmazat:

    def test_smaze_novy_doklad(self, db_factory):
        doklad_id = _seed(db_factory)
        cmd = _build(db_factory)
        cmd.smazat(doklad_id)
        # Ověř, že je pryč
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            assert repo.existuje_cislo("FV-2026-001") is False

    def test_nelze_smazat_zauctovany(self, db_factory):
        doklad_id = _seed(db_factory, castka="500")
        _zauctuj(db_factory, doklad_id, "500")
        cmd = _build(db_factory)
        with pytest.raises(ValidationError):
            cmd.smazat(doklad_id)


class TestKDoreseni:

    def test_oznaci_k_doreseni(self, db_factory):
        doklad_id = _seed(db_factory)
        cmd = _build(db_factory)
        item = cmd.oznac_k_doreseni(doklad_id, poznamka="chybí partner")
        assert item.k_doreseni is True
        assert item.poznamka_doreseni == "chybí partner"

    def test_dores_vycisti_flag(self, db_factory):
        doklad_id = _seed(db_factory, k_doreseni=True, poznamka="něco")
        cmd = _build(db_factory)
        item = cmd.dores(doklad_id)
        assert item.k_doreseni is False
        assert item.poznamka_doreseni is None

    def test_dores_idempotentni(self, db_factory):
        doklad_id = _seed(db_factory)
        cmd = _build(db_factory)
        item = cmd.dores(doklad_id)  # flag byl False
        assert item.k_doreseni is False


class TestUpravitPopisASplatnost:

    def test_upravi_oboje_na_novem(self, db_factory):
        doklad_id = _seed(db_factory, splatnost=date(2026, 3, 10),
                          popis="původní")
        cmd = _build(db_factory)
        item = cmd.upravit_popis_a_splatnost(
            doklad_id,
            popis="nový popis",
            splatnost=date(2026, 3, 20),
        )
        assert item.popis == "nový popis"
        assert item.datum_splatnosti == date(2026, 3, 20)

    def test_upravi_jen_popis_na_zauctovanem(self, db_factory):
        doklad_id = _seed(db_factory, castka="500",
                          splatnost=date(2026, 3, 15), popis="a")
        _zauctuj(db_factory, doklad_id, "500")
        cmd = _build(db_factory)
        # Splatnost se nezmění — předáváme stejnou hodnotu.
        item = cmd.upravit_popis_a_splatnost(
            doklad_id,
            popis="b",
            splatnost=date(2026, 3, 15),
        )
        assert item.popis == "b"
        assert item.stav == StavDokladu.ZAUCTOVANY

    def test_zmena_splatnosti_na_zauctovanem_vyhodi(self, db_factory):
        doklad_id = _seed(db_factory, castka="500",
                          splatnost=date(2026, 3, 15))
        _zauctuj(db_factory, doklad_id, "500")
        cmd = _build(db_factory)
        with pytest.raises(ValidationError):
            cmd.upravit_popis_a_splatnost(
                doklad_id,
                popis="x",
                splatnost=date(2026, 3, 25),  # jiná splatnost → ne-NOVY fail
            )

    def test_popis_na_stornovanem_vyhodi(self, db_factory):
        # Seed + zauctuj + stornuj (storno vyžaduje ZAUCTOVANY)
        doklad_id = _seed(db_factory, castka="500")
        _zauctuj(db_factory, doklad_id, "500")
        _build(db_factory).stornovat(doklad_id)
        cmd = _build(db_factory)
        with pytest.raises(ValidationError):
            cmd.upravit_popis_a_splatnost(
                doklad_id, popis="x", splatnost=None,
            )

    def test_popis_nastavi_none(self, db_factory):
        doklad_id = _seed(db_factory, popis="původní")
        cmd = _build(db_factory)
        item = cmd.upravit_popis_a_splatnost(
            doklad_id, popis=None, splatnost=None,
        )
        assert item.popis is None


class TestUpravitPoleNovyDokladu:
    """Fáze 6.7: kompletní edit NOVY dokladu (popis+splatnost+flag+poznámka)."""

    def test_upravi_vsechna_pole_naraz(self, db_factory):
        doklad_id = _seed(db_factory, splatnost=date(2026, 3, 10),
                          popis="původní")
        cmd = _build(db_factory)
        item = cmd.upravit_pole_novy_dokladu(
            doklad_id,
            popis="nový popis",
            splatnost=date(2026, 3, 25),
            k_doreseni=True,
            poznamka_doreseni="zkontrolovat IČO",
        )
        assert item.popis == "nový popis"
        assert item.datum_splatnosti == date(2026, 3, 25)
        assert item.k_doreseni is True
        assert item.poznamka_doreseni == "zkontrolovat IČO"

    def test_zrusi_flag_kdyz_k_doreseni_false(self, db_factory):
        doklad_id = _seed(db_factory, k_doreseni=True, poznamka="něco")
        cmd = _build(db_factory)
        item = cmd.upravit_pole_novy_dokladu(
            doklad_id,
            popis=None,
            splatnost=None,
            k_doreseni=False,
            poznamka_doreseni=None,
        )
        assert item.k_doreseni is False
        assert item.poznamka_doreseni is None

    def test_flag_bez_poznamky(self, db_factory):
        doklad_id = _seed(db_factory)
        cmd = _build(db_factory)
        item = cmd.upravit_pole_novy_dokladu(
            doklad_id,
            popis="x",
            splatnost=None,
            k_doreseni=True,
            poznamka_doreseni=None,
        )
        assert item.k_doreseni is True
        assert item.poznamka_doreseni is None

    def test_update_poznamky_na_jiz_flagnutem(self, db_factory):
        doklad_id = _seed(db_factory, k_doreseni=True, poznamka="staré")
        cmd = _build(db_factory)
        item = cmd.upravit_pole_novy_dokladu(
            doklad_id,
            popis=None,
            splatnost=None,
            k_doreseni=True,
            poznamka_doreseni="nové",
        )
        assert item.k_doreseni is True
        assert item.poznamka_doreseni == "nové"

    def test_splatnost_vyhodi_na_zauctovanem(self, db_factory):
        """Defenzivní: když UI pustí call pro ne-NOVY se splatností."""
        doklad_id = _seed(db_factory, castka="500",
                          splatnost=date(2026, 3, 15))
        _zauctuj(db_factory, doklad_id, "500")
        cmd = _build(db_factory)
        with pytest.raises(ValidationError):
            cmd.upravit_pole_novy_dokladu(
                doklad_id,
                popis="x",
                splatnost=date(2026, 3, 30),
                k_doreseni=False,
                poznamka_doreseni=None,
            )
