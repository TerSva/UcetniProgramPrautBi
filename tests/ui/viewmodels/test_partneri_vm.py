"""Testy PartneriViewModel."""

from decimal import Decimal

import pytest

from domain.partneri.partner import KategoriePartnera
from infrastructure.database.repositories.partneri_repository import (
    SqlitePartneriRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.commands.manage_partneri import ManagePartneriCommand
from services.queries.partneri_list import PartneriListQuery
from ui.dialogs.partner_dialog import PartnerDialogResult
from ui.viewmodels.partneri_vm import PartneriViewModel

from tests.infrastructure.database.repositories.conftest import (  # noqa: F401
    db_factory,
    uow,
)


@pytest.fixture
def vm(db_factory):
    uow_factory = lambda: SqliteUnitOfWork(db_factory)
    repo_factory = lambda uow: SqlitePartneriRepository(uow)
    query = PartneriListQuery(
        uow_factory=uow_factory,
        partneri_repo_factory=repo_factory,
    )
    command = ManagePartneriCommand(
        uow_factory=uow_factory,
        partneri_repo_factory=repo_factory,
    )
    return PartneriViewModel(query, command)


class TestPartneriVM:

    def test_load_empty(self, vm):
        vm.load()
        assert vm.items == []
        assert vm.error is None

    def test_create_and_load(self, vm):
        result = PartnerDialogResult(
            nazev="Test s.r.o.",
            kategorie=KategoriePartnera.DODAVATEL,
        )
        assert vm.create(result)
        vm.load()
        assert len(vm.items) == 1
        assert vm.items[0].nazev == "Test s.r.o."

    def test_update(self, vm):
        vm.create(PartnerDialogResult(
            nazev="Old", kategorie=KategoriePartnera.DODAVATEL,
        ))
        vm.load()
        pid = vm.items[0].id

        vm.update(pid, PartnerDialogResult(
            nazev="New", kategorie=KategoriePartnera.DODAVATEL,
        ))
        vm.load()
        assert vm.items[0].nazev == "New"

    def test_deactivate(self, vm):
        vm.create(PartnerDialogResult(
            nazev="ToDelete", kategorie=KategoriePartnera.DODAVATEL,
        ))
        vm.load()
        pid = vm.items[0].id

        vm.deactivate(pid)
        vm.load()
        assert len(vm.items) == 0  # jen_aktivni=True default
