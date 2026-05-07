"""Integration testy pro UctovaOsnovaQuery + UcetItem DTO."""

from infrastructure.database.repositories.uctova_osnova_repository import (
    SqliteUctovaOsnovaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from domain.ucetnictvi.typy import TypUctu
from domain.ucetnictvi.ucet import Ucet
from services.queries.uctova_osnova import UcetItem, UctovaOsnovaQuery


def _build_query(db_factory) -> UctovaOsnovaQuery:
    return UctovaOsnovaQuery(
        uow_factory=lambda: SqliteUnitOfWork(db_factory),
        osnova_repo_factory=lambda uow: SqliteUctovaOsnovaRepository(uow),
    )


def _deaktivuj(db_factory, cislo: str) -> None:
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteUctovaOsnovaRepository(uow)
        u = repo.get_by_cislo(cislo)
        u.deaktivuj()
        repo.update(u)
        uow.commit()


class TestUcetItem:

    def test_display_format(self):
        item = UcetItem(cislo="311", nazev="Odběratelé", typ=TypUctu.AKTIVA)
        # pomlčka je U+2013 (en-dash)
        assert item.display == "311 \u2013 Odběratelé"

    def test_from_domain(self):
        ucet = Ucet(
            cislo="311", nazev="Odběratelé", typ=TypUctu.AKTIVA,
        )
        item = UcetItem.from_domain(ucet)
        assert item.cislo == "311"
        assert item.nazev == "Odběratelé"
        assert item.typ == TypUctu.AKTIVA

    def test_je_frozen(self):
        item = UcetItem(cislo="311", nazev="Odběratelé", typ=TypUctu.AKTIVA)
        import pytest
        with pytest.raises(Exception):
            item.cislo = "321"  # type: ignore[misc]


class TestUctovaOsnovaQuery:

    def test_vrati_seed_ucty(self, db_factory):
        q = _build_query(db_factory)
        items = q.execute()
        # All migrations: 82 + 1 z 027 (479) + 1 z 028 (562)
        assert len(items) == 84
        cisla = {i.cislo for i in items}
        assert "211" in cisla
        assert "311" in cisla
        assert "602" in cisla
        # 022_je_danovy seeded analytiky pro daňové/nedaňové
        assert "543.200" in cisla  # nedaňové dary
        assert "545" in cisla       # ostatní pokuty (nedaňový syntetický)

    def test_typy_sedi(self, db_factory):
        q = _build_query(db_factory)
        items = q.execute()
        by_cislo = {i.cislo: i for i in items}
        assert by_cislo["211"].typ == TypUctu.AKTIVA
        assert by_cislo["321"].typ == TypUctu.PASIVA
        assert by_cislo["501"].typ == TypUctu.NAKLADY
        assert by_cislo["601"].typ == TypUctu.VYNOSY

    def test_default_skryva_neaktivni(self, db_factory):
        _deaktivuj(db_factory, "602")
        q = _build_query(db_factory)
        items = q.execute()
        cisla = {i.cislo for i in items}
        assert "602" not in cisla
        assert len(items) == 83  # 84 - 1 deaktivovaný

    def test_jen_aktivni_false_vrati_i_neaktivni(self, db_factory):
        _deaktivuj(db_factory, "602")
        q = _build_query(db_factory)
        items = q.execute(jen_aktivni=False)
        assert len(items) == 84

    def test_display_u_jednoho_uctu(self, db_factory):
        q = _build_query(db_factory)
        items = q.execute()
        by_cislo = {i.cislo: i for i in items}
        assert by_cislo["311"].display == (
            "311 \u2013 Pohledávky z obchodních vztahů"
        )
