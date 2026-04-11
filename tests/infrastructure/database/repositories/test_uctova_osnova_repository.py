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
            assert len(ucty) == 9

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
            assert len(naklady) == 2
            cisla = {u.cislo for u in naklady}
            assert cisla == {"501", "518"}

    def test_vynosy(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            vynosy = repo.list_by_typ(TypUctu.VYNOSY)
            assert len(vynosy) == 2

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
            ucet = Ucet(cislo="411", nazev="Základní kapitál", typ=TypUctu.PASIVA)
            result = repo.add(ucet)
            assert result.cislo == "411"
            uow.commit()

        # ověření v nové UoW
        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo2 = SqliteUctovaOsnovaRepository(uow2)
            u = repo2.get_by_cislo("411")
            assert u.nazev == "Základní kapitál"

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
