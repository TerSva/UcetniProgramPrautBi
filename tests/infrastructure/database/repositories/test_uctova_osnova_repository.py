"""Testy pro SqliteUctovaOsnovaRepository — round-trip + seed."""

import pytest

from domain.shared.errors import ConflictError, NotFoundError
from domain.ucetnictvi.typy import TypUctu
from domain.ucetnictvi.ucet import Ucet
from infrastructure.database.repositories.uctova_osnova_repository import (
    SqliteUctovaOsnovaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class TestSeedOsnovy:

    def test_po_migraci_9_uctu(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            ucty = repo.list_all(jen_aktivni=False)
            # 82 + 1 z 027 (479)
            assert len(ucty) == 83

    def test_pohledavky_311(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            u = repo.get_by_cislo("311")
            assert u.nazev == "Pohledávky z obchodních vztahů"
            assert u.typ == TypUctu.AKTIVA
            assert u.je_aktivni is True


class TestListByTyp:

    def test_naklady(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            naklady = repo.list_by_typ(TypUctu.NAKLADY)
            # 23 + 9 z 022_je_danovy + 1 z 024 (563.100, V už tam je)
            assert len(naklady) == 33
            cisla = {u.cislo for u in naklady}
            assert "501" in cisla
            assert "518" in cisla
            assert "568" in cisla
            assert "591" in cisla

    def test_vynosy(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            vynosy = repo.list_by_typ(TypUctu.VYNOSY)
            # 6 base + 1 z 024 (663.100 kurzové zisky bankovní)
            assert len(vynosy) == 7

    def test_serazeno_podle_cisla(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            ucty = repo.list_all()
            cisla = [u.cislo for u in ucty]
            assert cisla == sorted(cisla)


class TestAdd:

    def test_novy_ucet(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            ucet = Ucet(cislo="461", nazev="Bankovní úvěry", typ=TypUctu.PASIVA)
            result = repo.add(ucet)
            assert result.cislo == "461"
            uow.commit()

        # ověření v nové UoW
        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUctovaOsnovaRepository(uow2)
            u = repo2.get_by_cislo("461")
            assert u.nazev == "Bankovní úvěry"

    def test_duplicitni_cislo(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            ucet = Ucet(cislo="311", nazev="Duplikát", typ=TypUctu.AKTIVA)
            with pytest.raises(ConflictError, match="311"):
                repo.add(ucet)


class TestUpdate:

    def test_deaktivace(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            u = repo.get_by_cislo("501")
            u.deaktivuj()
            repo.update(u)
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUctovaOsnovaRepository(uow2)
            # jen_aktivni=True ho přeskočí
            aktivni = repo2.list_all(jen_aktivni=True)
            cisla_aktivni = {u.cislo for u in aktivni}
            assert "501" not in cisla_aktivni
            # jen_aktivni=False ho najde
            vsechny = repo2.list_all(jen_aktivni=False)
            cisla_vsechny = {u.cislo for u in vsechny}
            assert "501" in cisla_vsechny

    def test_neexistujici(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            ucet = Ucet(cislo="999", nazev="Neexistuje", typ=TypUctu.AKTIVA)
            with pytest.raises(NotFoundError):
                repo.update(ucet)


class TestExistuje:

    def test_existuje(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            assert repo.existuje("311") is True

    def test_neexistuje(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            assert repo.existuje("999") is False


class TestGetByCislo:

    def test_nenalezeno(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            with pytest.raises(NotFoundError, match="999"):
                repo.get_by_cislo("999")


class TestAnalytikaRoundTrip:
    """Fáze 7: analytické účty — persistence."""

    def test_add_analytika_roundtrip(self, db_factory):
        """Přidání analytiky a zpětné čtení."""
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            analytika = Ucet(
                cislo="502.100",
                nazev="Elektřina",
                typ=TypUctu.NAKLADY,
                parent_kod="502",
                popis="Elektrická energie",
            )
            repo.add(analytika)
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUctovaOsnovaRepository(uow2)
            loaded = repo2.get_by_cislo("502.100")
            assert loaded.cislo == "502.100"
            assert loaded.nazev == "Elektřina"
            assert loaded.typ == TypUctu.NAKLADY
            assert loaded.parent_kod == "502"
            assert loaded.popis == "Elektrická energie"
            assert loaded.is_analytic is True

    def test_get_analytiky(self, db_factory):
        """get_analytiky vrátí jen analytiky daného syntetického účtu."""
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            # 501.100 already exists from seed, add 501.200
            repo.add(Ucet("501.200", "Služby", TypUctu.NAKLADY, parent_kod="501"))
            uow.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUctovaOsnovaRepository(uow2)
            analytiky_501 = repo2.get_analytiky("501")
            assert len(analytiky_501) == 2
            assert {a.cislo for a in analytiky_501} == {"501.100", "501.200"}

            analytiky_518 = repo2.get_analytiky("518")
            # 518.100, 518.200 from migrations + 518.300, 518.400 from seed 020
            assert len(analytiky_518) == 4

            analytiky_314 = repo2.get_analytiky("314")
            # 314.001 přidána v 026_zalohove_faktury (Poskytnuté zálohy CZK)
            assert len(analytiky_314) == 1
            assert analytiky_314[0].cislo == "314.001"

    def test_update_popis(self, db_factory):
        """Update analytiky — popis se uloží."""
        # 501.100 already exists from seed migration

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUctovaOsnovaRepository(uow2)
            u = repo2.get_by_cislo("501.100")
            u.uprav_popis("Nový popis")
            u.uprav_nazev("Nový název")
            repo2.update(u)
            uow2.commit()

        uow3 = SqliteUnitOfWork(db_factory)
        with uow3:
            repo3 = SqliteUctovaOsnovaRepository(uow3)
            u2 = repo3.get_by_cislo("501.100")
            assert u2.popis == "Nový popis"
            assert u2.nazev == "Nový název"

    def test_deaktivace_analytiky(self, db_factory):
        """Deaktivace analytiky se správně persistuje."""
        # 501.100 already exists from seed

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUctovaOsnovaRepository(uow2)
            u = repo2.get_by_cislo("501.100")
            u.deaktivuj()
            repo2.update(u)
            uow2.commit()

        uow3 = SqliteUnitOfWork(db_factory)
        with uow3:
            repo3 = SqliteUctovaOsnovaRepository(uow3)
            u2 = repo3.get_by_cislo("501.100")
            assert u2.je_aktivni is False

    def test_duplicitni_analytika(self, db_factory):
        """Pokus o přidání duplicitní analytiky vyhodí ConflictError."""
        # 501.100 already exists from seed
        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUctovaOsnovaRepository(uow2)
            with pytest.raises(ConflictError, match="501.100"):
                repo2.add(Ucet("501.100", "Duplicita", TypUctu.NAKLADY, parent_kod="501"))

    def test_list_all_includes_analytiky(self, db_factory):
        """list_all vrátí i analytické účty."""
        # 501.100 already exists from seed
        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUctovaOsnovaRepository(uow2)
            all_ucty = repo2.list_all(jen_aktivni=False)
            cisla = {u.cislo for u in all_ucty}
            assert "501.100" in cisla
