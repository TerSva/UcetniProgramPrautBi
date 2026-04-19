"""Testy pro SqlitePrilohaRepository."""

from datetime import date, datetime

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.priloha import PrilohaDokladu
from domain.doklady.typy import TypDokladu
from domain.shared.money import Money
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.priloha_repository import (
    SqlitePrilohaRepository,
)


class TestSqlitePrilohaRepository:
    """CRUD operace + cascade delete."""

    def _create_doklad(self, uow, cislo="FP-2025-0001"):
        repo = SqliteDokladyRepository(uow)
        doklad = Doklad(
            cislo=cislo,
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2025, 1, 15),
            castka_celkem=Money(100_00),
        )
        return repo.add(doklad)

    def _make_priloha(self, doklad_id, nazev="faktura.pdf"):
        return PrilohaDokladu(
            id=None,
            doklad_id=doklad_id,
            nazev_souboru=nazev,
            relativni_cesta=f"doklady/2025/FP/{nazev}",
            velikost_bytes=12345,
            mime_type="application/pdf",
            vytvoreno=datetime(2025, 1, 15, 10, 30),
        )

    def test_add_and_get_by_id(self, uow):
        with uow:
            doklad = self._create_doklad(uow)
            repo = SqlitePrilohaRepository(uow)
            priloha = self._make_priloha(doklad.id)
            saved = repo.add(priloha)

            assert saved.id is not None
            assert saved.nazev_souboru == "faktura.pdf"
            assert saved.doklad_id == doklad.id

            loaded = repo.get_by_id(saved.id)
            assert loaded is not None
            assert loaded.nazev_souboru == "faktura.pdf"
            assert loaded.relativni_cesta == "doklady/2025/FP/faktura.pdf"
            uow.commit()

    def test_list_by_doklad(self, uow):
        with uow:
            doklad = self._create_doklad(uow)
            repo = SqlitePrilohaRepository(uow)
            repo.add(self._make_priloha(doklad.id, "a.pdf"))
            repo.add(self._make_priloha(doklad.id, "b.pdf"))

            items = repo.list_by_doklad(doklad.id)
            assert len(items) == 2
            names = [p.nazev_souboru for p in items]
            assert "a.pdf" in names
            assert "b.pdf" in names
            uow.commit()

    def test_list_by_doklad_empty(self, uow):
        with uow:
            doklad = self._create_doklad(uow)
            repo = SqlitePrilohaRepository(uow)
            items = repo.list_by_doklad(doklad.id)
            assert items == []
            uow.commit()

    def test_delete(self, uow):
        with uow:
            doklad = self._create_doklad(uow)
            repo = SqlitePrilohaRepository(uow)
            saved = repo.add(self._make_priloha(doklad.id))
            repo.delete(saved.id)
            assert repo.get_by_id(saved.id) is None
            uow.commit()

    def test_get_nonexistent_returns_none(self, uow):
        with uow:
            repo = SqlitePrilohaRepository(uow)
            assert repo.get_by_id(9999) is None
            uow.commit()

    def test_cascade_delete_doklad_removes_prilohy(self, uow):
        """Smazání dokladu kaskádně smaže přílohy z DB."""
        with uow:
            doklad = self._create_doklad(uow)
            prepo = SqlitePrilohaRepository(uow)
            prepo.add(self._make_priloha(doklad.id, "a.pdf"))
            prepo.add(self._make_priloha(doklad.id, "b.pdf"))

            # Smaž doklad (je ve stavu NOVY, nemá účetní zápisy)
            drepo = SqliteDokladyRepository(uow)
            drepo.delete(doklad.id)

            # Přílohy by měly být pryč (CASCADE)
            assert prepo.list_by_doklad(doklad.id) == []
            uow.commit()
