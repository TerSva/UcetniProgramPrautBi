"""Testy pro SqliteUcetniDenikRepository — zaúčtování, round-trip, atomicita."""

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import NotFoundError, ValidationError
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


@pytest.fixture
def doklad_v_db(db_factory):
    """Vytvoří validní doklad pro účtování. Vrátí (doklad_id, db_factory)."""
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(
            cislo="FV-2026-TEST-001",
            typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2026, 4, 1),
            castka_celkem=Money.from_koruny("12100"),
        ))
        uow.commit()
    return d.id


@pytest.fixture
def druhy_doklad_v_db(db_factory):
    """Druhý doklad pro testy, kde potřebujeme dva."""
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(
            cislo="FP-2026-TEST-001",
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2026, 4, 5),
            castka_celkem=Money.from_koruny("5000"),
        ))
        uow.commit()
    return d.id


class TestZauctuj:

    def test_happy_path_fv_s_dph(self, db_factory, doklad_v_db):
        """FV 12 100 Kč: základ 10 000 + DPH 2 100."""
        doklad_id = doklad_v_db
        predpis = UctovyPredpis(
            doklad_id=doklad_id,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=doklad_id, datum=date(2026, 4, 1),
                    md_ucet="311", dal_ucet="601", castka=Money(1000000),
                    popis="Tržba za výrobky",
                ),
                UcetniZaznam(
                    doklad_id=doklad_id, datum=date(2026, 4, 1),
                    md_ucet="311", dal_ucet="343", castka=Money(210000),
                    popis="DPH 21%",
                ),
            ),
        )
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUcetniDenikRepository(uow)
            result = repo.zauctuj(predpis)
            assert len(result) == 2
            assert all(z.id is not None for z in result)
            assert result[0].castka == Money(1000000)
            assert result[1].castka == Money(210000)
            uow.commit()

        # Ověření v nové UoW
        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUcetniDenikRepository(uow2)
            zaznamy = repo2.list_by_doklad(doklad_id)
            assert len(zaznamy) == 2
            assert zaznamy[0].md_ucet == "311"
            assert zaznamy[0].dal_ucet == "601"
            assert zaznamy[1].dal_ucet == "343"

    def test_round_trip_money(self, db_factory, doklad_v_db):
        """Částky se vrátí přesně — halíře se neztrácí."""
        doklad_id = doklad_v_db
        predpis = UctovyPredpis.jednoduchy(
            doklad_id=doklad_id, datum=date(2026, 4, 1),
            md_ucet="311", dal_ucet="602", castka=Money(123456789),
        )
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUcetniDenikRepository(uow)
            repo.zauctuj(predpis)
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUcetniDenikRepository(uow2)
            zaznamy = repo2.list_by_doklad(doklad_id)
            assert zaznamy[0].castka == Money(123456789)

    def test_round_trip_none_popis(self, db_factory, doklad_v_db):
        doklad_id = doklad_v_db
        predpis = UctovyPredpis.jednoduchy(
            doklad_id=doklad_id, datum=date(2026, 4, 1),
            md_ucet="311", dal_ucet="601", castka=Money(100),
        )
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUcetniDenikRepository(uow)
            repo.zauctuj(predpis)
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUcetniDenikRepository(uow2)
            z = repo2.list_by_doklad(doklad_id)
            assert z[0].popis is None


class TestValidaceZauctuj:

    def test_ucet_neexistuje(self, db_factory, doklad_v_db):
        doklad_id = doklad_v_db
        predpis = UctovyPredpis.jednoduchy(
            doklad_id=doklad_id, datum=date(2026, 4, 1),
            md_ucet="999", dal_ucet="601", castka=Money(100),
        )
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUcetniDenikRepository(uow)
            with pytest.raises(NotFoundError, match="999"):
                repo.zauctuj(predpis)

    def test_ucet_deaktivovany(self, db_factory, doklad_v_db):
        doklad_id = doklad_v_db
        # Deaktivuj 311
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            osnova = SqliteUctovaOsnovaRepository(uow)
            u = osnova.get_by_cislo("311")
            u.deaktivuj()
            osnova.update(u)
            uow.commit()

        # Teď zkus zaúčtovat s 311
        predpis = UctovyPredpis.jednoduchy(
            doklad_id=doklad_id, datum=date(2026, 4, 1),
            md_ucet="311", dal_ucet="601", castka=Money(100),
        )
        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo = SqliteUcetniDenikRepository(uow2)
            with pytest.raises(ValidationError, match="deaktivované"):
                repo.zauctuj(predpis)

    def test_doklad_neexistuje(self, db_factory):
        predpis = UctovyPredpis.jednoduchy(
            doklad_id=99999, datum=date(2026, 4, 1),
            md_ucet="311", dal_ucet="601", castka=Money(100),
        )
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUcetniDenikRepository(uow)
            with pytest.raises(NotFoundError, match="99999"):
                repo.zauctuj(predpis)


class TestAtomicita:

    def test_rollback_pri_selhani(self, db_factory, doklad_v_db):
        """Po selhání žádný záznam z předpisu není v DB."""
        doklad_id = doklad_v_db

        # Deaktivuj 343 — druhý zápis selže
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            osnova = SqliteUctovaOsnovaRepository(uow)
            u = osnova.get_by_cislo("343")
            u.deaktivuj()
            osnova.update(u)
            uow.commit()

        predpis = UctovyPredpis(
            doklad_id=doklad_id,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=doklad_id, datum=date(2026, 4, 1),
                    md_ucet="311", dal_ucet="601", castka=Money(1000000),
                ),
                UcetniZaznam(
                    doklad_id=doklad_id, datum=date(2026, 4, 1),
                    md_ucet="311", dal_ucet="343", castka=Money(210000),
                ),
            ),
        )

        # zauctuj selže na deaktivovaném 343 — validace proběhne PŘED insertem
        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo = SqliteUcetniDenikRepository(uow2)
            with pytest.raises(ValidationError, match="deaktivované"):
                repo.zauctuj(predpis)

        # Ověř, že ŽÁDNÝ záznam z předpisu není v DB
        uow3 = SqliteUnitOfWork(db_factory)
        with uow3:
            repo3 = SqliteUcetniDenikRepository(uow3)
            zaznamy = repo3.list_by_doklad(doklad_id)
            assert len(zaznamy) == 0


class TestGetById:

    def test_nalezeno(self, db_factory, doklad_v_db):
        doklad_id = doklad_v_db
        predpis = UctovyPredpis.jednoduchy(
            doklad_id=doklad_id, datum=date(2026, 4, 1),
            md_ucet="311", dal_ucet="601", castka=Money(100),
        )
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUcetniDenikRepository(uow)
            result = repo.zauctuj(predpis)
            zaznam_id = result[0].id
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUcetniDenikRepository(uow2)
            z = repo2.get_by_id(zaznam_id)
            assert z.md_ucet == "311"
            assert z.castka == Money(100)

    def test_nenalezeno(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUcetniDenikRepository(uow)
            with pytest.raises(NotFoundError):
                repo.get_by_id(99999)


class TestListByDoklad:

    def test_jen_dany_doklad(self, db_factory, doklad_v_db, druhy_doklad_v_db):
        d1 = doklad_v_db
        d2 = druhy_doklad_v_db

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUcetniDenikRepository(uow)
            p1 = UctovyPredpis.jednoduchy(
                doklad_id=d1, datum=date(2026, 4, 1),
                md_ucet="311", dal_ucet="601", castka=Money(100),
            )
            p2 = UctovyPredpis.jednoduchy(
                doklad_id=d2, datum=date(2026, 4, 5),
                md_ucet="518", dal_ucet="321", castka=Money(200),
            )
            repo.zauctuj(p1)
            repo.zauctuj(p2)
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUcetniDenikRepository(uow2)
            zaznamy_d1 = repo2.list_by_doklad(d1)
            assert len(zaznamy_d1) == 1
            assert zaznamy_d1[0].md_ucet == "311"

    def test_serazeno_podle_id(self, db_factory, doklad_v_db):
        doklad_id = doklad_v_db
        predpis = UctovyPredpis(
            doklad_id=doklad_id,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=doklad_id, datum=date(2026, 4, 1),
                    md_ucet="311", dal_ucet="601", castka=Money(100),
                    popis="První",
                ),
                UcetniZaznam(
                    doklad_id=doklad_id, datum=date(2026, 4, 1),
                    md_ucet="311", dal_ucet="343", castka=Money(200),
                    popis="Druhý",
                ),
            ),
        )
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUcetniDenikRepository(uow)
            repo.zauctuj(predpis)
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUcetniDenikRepository(uow2)
            zaznamy = repo2.list_by_doklad(doklad_id)
            assert zaznamy[0].id < zaznamy[1].id


class TestListByObdobi:

    def test_inkluzivni_hranice(self, db_factory, doklad_v_db, druhy_doklad_v_db):
        d1 = doklad_v_db   # datum 2026-04-01
        d2 = druhy_doklad_v_db  # datum 2026-04-05

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUcetniDenikRepository(uow)
            repo.zauctuj(UctovyPredpis.jednoduchy(
                doklad_id=d1, datum=date(2026, 4, 1),
                md_ucet="311", dal_ucet="601", castka=Money(100),
            ))
            repo.zauctuj(UctovyPredpis.jednoduchy(
                doklad_id=d2, datum=date(2026, 4, 5),
                md_ucet="518", dal_ucet="321", castka=Money(200),
            ))
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUcetniDenikRepository(uow2)
            # Celé období
            all_z = repo2.list_by_obdobi(date(2026, 4, 1), date(2026, 4, 5))
            assert len(all_z) == 2
            # Jen první den
            den1 = repo2.list_by_obdobi(date(2026, 4, 1), date(2026, 4, 1))
            assert len(den1) == 1
            assert den1[0].md_ucet == "311"


class TestListByUcet:

    def test_md_i_dal(self, db_factory, doklad_v_db, druhy_doklad_v_db):
        d1 = doklad_v_db
        d2 = druhy_doklad_v_db

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUcetniDenikRepository(uow)
            # 311 na MD
            repo.zauctuj(UctovyPredpis.jednoduchy(
                doklad_id=d1, datum=date(2026, 4, 1),
                md_ucet="311", dal_ucet="601", castka=Money(100),
            ))
            # 311 na Dal (úhrada)
            repo.zauctuj(UctovyPredpis.jednoduchy(
                doklad_id=d2, datum=date(2026, 4, 5),
                md_ucet="221", dal_ucet="311", castka=Money(100),
            ))
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUcetniDenikRepository(uow2)
            zaznamy_311 = repo2.list_by_ucet("311", date(2026, 4, 1), date(2026, 4, 30))
            assert len(zaznamy_311) == 2
            # Jeden kde 311 je MD, druhý kde je Dal
            md_ucty = {z.md_ucet for z in zaznamy_311}
            dal_ucty = {z.dal_ucet for z in zaznamy_311}
            assert "311" in md_ucty
            assert "311" in dal_ucty


class TestStornoZapisyRoundTrip:
    """Fáze 6.5: round-trip je_storno + stornuje_zaznam_id."""

    def test_original_zaznam_ma_je_storno_false(self, db_factory, doklad_v_db):
        doklad_id = doklad_v_db
        predpis = UctovyPredpis.jednoduchy(
            doklad_id=doklad_id, datum=date(2026, 4, 1),
            md_ucet="311", dal_ucet="601", castka=Money(100000),
        )
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUcetniDenikRepository(uow)
            repo.zauctuj(predpis)
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUcetniDenikRepository(uow2)
            zaznamy = repo2.list_by_doklad(doklad_id)
            assert zaznamy[0].je_storno is False
            assert zaznamy[0].stornuje_zaznam_id is None

    def test_storno_zaznam_round_trip(self, db_factory, doklad_v_db):
        doklad_id = doklad_v_db

        # 1. Původní zápis
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUcetniDenikRepository(uow)
            original = repo.zauctuj(UctovyPredpis.jednoduchy(
                doklad_id=doklad_id, datum=date(2026, 4, 1),
                md_ucet="311", dal_ucet="601", castka=Money(100000),
            ))
            original_id = original[0].id
            uow.commit()

        # 2. Opravný (storno) zápis — prohozené MD/Dal, odkazuje na original
        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUcetniDenikRepository(uow2)
            storno_predpis = UctovyPredpis(
                doklad_id=doklad_id,
                zaznamy=(UcetniZaznam(
                    doklad_id=doklad_id, datum=date(2026, 4, 10),
                    md_ucet="601", dal_ucet="311", castka=Money(100000),
                    popis="Storno — opravný zápis",
                    je_storno=True, stornuje_zaznam_id=original_id,
                ),),
            )
            repo2.zauctuj(storno_predpis)
            uow2.commit()

        # 3. Round-trip: flag + FK čteme správně
        uow3 = SqliteUnitOfWork(db_factory)
        with uow3:
            repo3 = SqliteUcetniDenikRepository(uow3)
            zaznamy = repo3.list_by_doklad(doklad_id)
            assert len(zaznamy) == 2
            orig, storno = zaznamy[0], zaznamy[1]
            assert orig.je_storno is False
            assert orig.stornuje_zaznam_id is None
            assert storno.je_storno is True
            assert storno.stornuje_zaznam_id == orig.id
            assert storno.md_ucet == "601"
            assert storno.dal_ucet == "311"


class TestZadnyUpdateDelete:

    def test_nema_update(self):
        """UcetniDenikRepository NEMÁ update() metodu."""
        assert not hasattr(SqliteUcetniDenikRepository, "update")

    def test_nema_delete(self):
        """UcetniDenikRepository NEMÁ delete() metodu."""
        assert not hasattr(SqliteUcetniDenikRepository, "delete")
