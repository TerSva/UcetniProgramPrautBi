"""Testy pro ChartOfAccountsViewModel — Fáze 7.

Pure Python VM, testovatelný bez Qt — mockujeme query + command.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.shared.errors import ValidationError
from domain.ucetnictvi.typy import TypUctu
from services.queries.chart_of_accounts import (
    ChartOfAccountsItem,
    TridaGroup,
)
from ui.viewmodels.chart_of_accounts_vm import ChartOfAccountsViewModel


def _make_item(cislo="501", nazev="Služby", active=True, analytiky=()):
    return ChartOfAccountsItem(
        cislo=cislo,
        nazev=nazev,
        typ=TypUctu.NAKLADY,
        is_active=active,
        is_analytic="." in cislo,
        parent_kod=cislo.split(".")[0] if "." in cislo else None,
        popis=None,
        analytiky=analytiky,
    )


def _make_trida(trida=5, ucty=None):
    items = ucty or (_make_item(),)
    return TridaGroup(
        trida=trida,
        nazev="Náklady",
        ucty=tuple(items),
        active_count=sum(1 for u in items if u.is_active),
        total_count=len(items),
    )


class FakeQuery:
    def __init__(self, tridy=None, error=None):
        self._tridy = tridy or [_make_trida()]
        self._error = error
        self.call_count = 0
        self.last_show_inactive = None

    def execute(self, show_inactive=True):
        self.call_count += 1
        self.last_show_inactive = show_inactive
        if self._error:
            raise self._error
        return self._tridy


class FakeCommand:
    def __init__(self, error=None):
        self._error = error
        self.activated = []
        self.deactivated = []
        self.added = []
        self.updated = []

    def activate_ucet(self, cislo):
        if self._error:
            raise self._error
        self.activated.append(cislo)

    def deactivate_ucet(self, cislo):
        if self._error:
            raise self._error
        self.deactivated.append(cislo)

    def add_analytika(self, syntetic_kod, suffix, nazev, popis=None):
        if self._error:
            raise self._error
        self.added.append((syntetic_kod, suffix, nazev, popis))

    def update_analytika(self, cislo, nazev, popis=None):
        if self._error:
            raise self._error
        self.updated.append((cislo, nazev, popis))


class TestLoad:

    def test_load_populates_tridy(self):
        query = FakeQuery()
        vm = ChartOfAccountsViewModel(query, FakeCommand())
        vm.load()
        assert len(vm.tridy) == 1
        assert vm.error is None

    def test_load_error(self):
        query = FakeQuery(error=RuntimeError("DB fail"))
        vm = ChartOfAccountsViewModel(query, FakeCommand())
        vm.load()
        assert vm.tridy == []
        assert "DB fail" in vm.error


class TestToggleInactive:

    def test_toggle_switches_flag(self):
        query = FakeQuery()
        vm = ChartOfAccountsViewModel(query, FakeCommand())
        assert vm.show_inactive is True
        vm.toggle_show_inactive()
        assert vm.show_inactive is False
        assert query.last_show_inactive is False

    def test_toggle_reloads(self):
        query = FakeQuery()
        vm = ChartOfAccountsViewModel(query, FakeCommand())
        vm.toggle_show_inactive()
        assert query.call_count == 1  # load() called


class TestActivateDeactivate:

    def test_activate_delegates_and_reloads(self):
        query = FakeQuery()
        cmd = FakeCommand()
        vm = ChartOfAccountsViewModel(query, cmd)
        vm.activate_ucet("501")
        assert cmd.activated == ["501"]
        assert query.call_count == 1  # reload

    def test_deactivate_error_reloads_after_failure(self):
        """Command error → reload stále proběhne (error se vyčistí, data se obnoví)."""
        query = FakeQuery()
        cmd = FakeCommand(error=ValidationError("aktivní analytiky"))
        vm = ChartOfAccountsViewModel(query, cmd)
        vm.deactivate_ucet("501")
        # VM volá load() po chybě, load() uspěje → error=None
        assert query.call_count == 1  # reload proběhl
        assert vm.error is None  # load() vyčistil error


class TestAddUpdateAnalytika:

    def test_add_analytika_delegates(self):
        query = FakeQuery()
        cmd = FakeCommand()
        vm = ChartOfAccountsViewModel(query, cmd)
        vm.add_analytika("501", "100", "Kancelář", "popis")
        assert cmd.added == [("501", "100", "Kancelář", "popis")]
        assert query.call_count == 1

    def test_update_analytika_delegates(self):
        query = FakeQuery()
        cmd = FakeCommand()
        vm = ChartOfAccountsViewModel(query, cmd)
        vm.update_analytika("501.100", "Nový", "popis")
        assert cmd.updated == [("501.100", "Nový", "popis")]
        assert query.call_count == 1

    def test_add_error_still_reloads(self):
        """Command error → reload stále proběhne."""
        query = FakeQuery()
        cmd = FakeCommand(error=ValidationError("neplatný formát"))
        vm = ChartOfAccountsViewModel(query, cmd)
        vm.add_analytika("501", "!!!", "Bad")
        # load() po chybě uspěje → error=None
        assert query.call_count == 1
