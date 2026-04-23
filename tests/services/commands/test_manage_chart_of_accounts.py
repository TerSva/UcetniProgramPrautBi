"""Testy pro ManageChartOfAccountsCommand — Fáze 7."""

import pytest

from domain.shared.errors import ConflictError, NotFoundError, ValidationError
from domain.ucetnictvi.typy import TypUctu
from domain.ucetnictvi.ucet import Ucet
from infrastructure.database.repositories.uctova_osnova_repository import (
    SqliteUctovaOsnovaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.commands.manage_chart_of_accounts import (
    ManageChartOfAccountsCommand,
)


def _build_cmd(db_factory):
    return ManageChartOfAccountsCommand(
        uow_factory=lambda: SqliteUnitOfWork(db_factory),
        osnova_repo_factory=lambda uow: SqliteUctovaOsnovaRepository(uow),
    )


class TestActivateDeactivate:

    def test_deactivate_ucet(self, db_factory):
        cmd = _build_cmd(db_factory)
        cmd.deactivate_ucet("502")

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            u = repo.get_by_cislo("502")
            assert u.je_aktivni is False

    def test_activate_ucet(self, db_factory):
        cmd = _build_cmd(db_factory)
        cmd.deactivate_ucet("502")
        cmd.activate_ucet("502")

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            u = repo.get_by_cislo("502")
            assert u.je_aktivni is True

    def test_deactivate_nonexistent(self, db_factory):
        cmd = _build_cmd(db_factory)
        with pytest.raises(NotFoundError):
            cmd.deactivate_ucet("999")

    def test_deactivate_blocked_by_active_analytiky(self, db_factory):
        """Nelze deaktivovat syntetiku s aktivními analytikami."""
        cmd = _build_cmd(db_factory)
        # 501.100 already exists from seed migration 020
        with pytest.raises(ValidationError, match="aktivní analytiky"):
            cmd.deactivate_ucet("501")


class TestAddAnalytika:

    def test_add_analytika(self, db_factory):
        cmd = _build_cmd(db_factory)
        result = cmd.add_analytika("502", "200", "Plyn", popis="Plyn kancelář")
        assert result.cislo == "502.200"
        assert result.nazev == "Plyn"
        assert result.popis == "Plyn kancelář"
        assert result.is_analytic is True

    def test_add_analytika_activates_parent(self, db_factory):
        """Přidání analytiky automaticky aktivuje neaktivního parenta."""
        cmd = _build_cmd(db_factory)
        cmd.deactivate_ucet("502")
        cmd.add_analytika("502", "100", "Elektřina")

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            parent = repo.get_by_cislo("502")
            assert parent.je_aktivni is True

    def test_add_analytika_nonexistent_parent(self, db_factory):
        cmd = _build_cmd(db_factory)
        with pytest.raises(NotFoundError):
            cmd.add_analytika("999", "100", "Neexistuje")

    def test_add_duplicate_analytika(self, db_factory):
        cmd = _build_cmd(db_factory)
        # 501.100 already exists from seed
        with pytest.raises(ConflictError):
            cmd.add_analytika("501", "100", "Duplikát")


class TestUpdateAnalytika:

    def test_update_analytika(self, db_factory):
        cmd = _build_cmd(db_factory)
        # 501.100 exists from seed
        cmd.update_analytika("501.100", "Nový název", popis="Nový popis")

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            u = repo.get_by_cislo("501.100")
            assert u.nazev == "Nový název"
            assert u.popis == "Nový popis"

    def test_update_syntetic_raises(self, db_factory):
        """Update analytiky na syntetickém účtu vyhodí ValidationError."""
        cmd = _build_cmd(db_factory)
        with pytest.raises(ValidationError, match="není analytika"):
            cmd.update_analytika("501", "Nový název")
