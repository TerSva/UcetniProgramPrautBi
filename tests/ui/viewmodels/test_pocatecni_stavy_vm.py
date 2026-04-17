"""Testy pro PocatecniStavyViewModel."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.shared.money import Money
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from scripts.seed_chart_of_accounts import seed_chart_of_accounts
from services.commands.pocatecni_stavy import PocatecniStavyCommand
from services.commands.vklad_zk import VkladZKCommand
from ui.viewmodels.pocatecni_stavy_vm import PocatecniStavyViewModel


MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "infrastructure" / "database" / "migrations" / "sql"
)


@pytest.fixture
def factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    f = ConnectionFactory(db_path)
    MigrationRunner(f, MIGRATIONS_SQL_DIR).migrate()
    seed_chart_of_accounts(f)
    return f


@pytest.fixture
def vm(factory) -> PocatecniStavyViewModel:
    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    ps_cmd = PocatecniStavyCommand(uow_factory=uow_factory)
    vklad_cmd = VkladZKCommand(uow_factory=uow_factory)
    return PocatecniStavyViewModel(
        pocatecni_cmd=ps_cmd,
        vklad_zk_cmd=vklad_cmd,
        firma_loader=lambda: None,
    )


def test_initial_state(vm):
    assert vm.rok == 2025
    assert vm.stavy == []
    assert vm.error is None


def test_load_empty(vm):
    vm.load()
    assert vm.stavy == []
    assert vm.soucet_md == Money.zero()
    assert vm.soucet_dal == Money.zero()
    assert vm.bilance_souhlasi is True


def test_pridat_stav(vm):
    vm.pridat_stav("221", Money(100000), "MD")
    assert len(vm.stavy) == 1
    assert vm.soucet_md == Money(100000)
    assert vm.soucet_dal == Money.zero()
    assert vm.bilance_souhlasi is False


def test_bilance_souhlasi(vm):
    vm.pridat_stav("221", Money(100000), "MD")
    vm.pridat_stav("411", Money(100000), "DAL")
    assert vm.bilance_souhlasi is True
    assert vm.soucet_md == vm.soucet_dal


def test_smazat_stav(vm):
    vm.pridat_stav("221", Money(100000), "MD")
    stav_id = vm.stavy[0].id
    vm.smazat_stav(stav_id)
    assert vm.stavy == []


def test_set_rok(vm):
    vm.pridat_stav("221", Money(100000), "MD")
    assert len(vm.stavy) == 1

    vm.set_rok(2026)
    vm.load()
    assert vm.stavy == []
    assert vm.rok == 2026


def test_generovat_doklad(vm):
    vm.pridat_stav("221", Money(100000), "MD")
    vm.pridat_stav("411", Money(100000), "DAL")
    result = vm.generovat_doklad()
    assert result is not None
    assert vm.error is None
