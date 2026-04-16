"""Testy ManagePartneriCommand."""

from decimal import Decimal

import pytest

from domain.partneri.partner import KategoriePartnera
from domain.shared.errors import ValidationError
from infrastructure.database.repositories.partneri_repository import (
    SqlitePartneriRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.commands.manage_partneri import ManagePartneriCommand


@pytest.fixture
def cmd(db_factory):
    return ManagePartneriCommand(
        uow_factory=lambda: SqliteUnitOfWork(db_factory),
        partneri_repo_factory=lambda uow: SqlitePartneriRepository(uow),
    )


class TestCreate:

    def test_create_dodavatel(self, cmd):
        p = cmd.create(
            nazev="iStyle CZ",
            kategorie=KategoriePartnera.DODAVATEL,
            ico="27583368",
        )
        assert p.id is not None
        assert p.nazev == "iStyle CZ"

    def test_create_spolecnik(self, cmd):
        p = cmd.create(
            nazev="Martin",
            kategorie=KategoriePartnera.SPOLECNIK,
            podil_procent=Decimal("90"),
        )
        assert p.podil_procent == Decimal("90")

    def test_create_validation_error(self, cmd):
        with pytest.raises(ValidationError):
            cmd.create(nazev="", kategorie=KategoriePartnera.DODAVATEL)


class TestUpdate:

    def test_update(self, cmd):
        p = cmd.create(
            nazev="Old", kategorie=KategoriePartnera.DODAVATEL,
        )
        cmd.update(p.id, nazev="New")
        # Verify through a new create+read cycle
        uow = cmd._uow_factory()
        with uow:
            repo = cmd._partneri_repo_factory(uow)
            updated = repo.get_by_id(p.id)
        assert updated.nazev == "New"


class TestDeactivate:

    def test_deactivate(self, cmd):
        p = cmd.create(
            nazev="Test", kategorie=KategoriePartnera.DODAVATEL,
        )
        cmd.deactivate(p.id)
        uow = cmd._uow_factory()
        with uow:
            repo = cmd._partneri_repo_factory(uow)
            loaded = repo.get_by_id(p.id)
        assert not loaded.je_aktivni

    def test_reactivate(self, cmd):
        p = cmd.create(
            nazev="Test", kategorie=KategoriePartnera.DODAVATEL,
        )
        cmd.deactivate(p.id)
        cmd.reactivate(p.id)
        uow = cmd._uow_factory()
        with uow:
            repo = cmd._partneri_repo_factory(uow)
            loaded = repo.get_by_id(p.id)
        assert loaded.je_aktivni
