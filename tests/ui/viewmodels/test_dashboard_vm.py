"""Testy pro DashboardViewModel — pure Python, bez Qt."""

from __future__ import annotations

import pytest

from domain.shared.money import Money
from services.queries.dashboard import DashboardData
from ui.viewmodels.dashboard_vm import DashboardViewModel


# ──────────────────────────────────────────────────────────────────────
# Mock query
# ──────────────────────────────────────────────────────────────────────


def _sample_data() -> DashboardData:
    return DashboardData(
        doklady_celkem=5,
        doklady_k_zauctovani=2,
        doklady_k_doreseni=1,
        pohledavky=Money.from_koruny("12000"),
        zavazky=Money.from_koruny("4000"),
        rok=2026,
        vynosy=Money.from_koruny("100000"),
        naklady=Money.from_koruny("60000"),
        hruby_zisk=Money.from_koruny("40000"),
        odhad_dane=Money.from_koruny("7600"),
    )


class _StubQuery:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def execute(self):
        self.calls += 1
        return self.result


class _ErrorQuery:
    def __init__(self, exc):
        self.exc = exc
        self.calls = 0

    def execute(self):
        self.calls += 1
        raise self.exc


# ──────────────────────────────────────────────────────────────────────
# Initial state
# ──────────────────────────────────────────────────────────────────────


class TestPocatecniStav:

    def test_data_je_none_pred_load(self):
        vm = DashboardViewModel(_StubQuery(_sample_data()))
        assert vm.data is None

    def test_error_je_none_pred_load(self):
        vm = DashboardViewModel(_StubQuery(_sample_data()))
        assert vm.error is None

    def test_has_data_je_false_pred_load(self):
        vm = DashboardViewModel(_StubQuery(_sample_data()))
        assert vm.has_data is False


# ──────────────────────────────────────────────────────────────────────
# Úspěšný load
# ──────────────────────────────────────────────────────────────────────


class TestUspesnyLoad:

    def test_load_zavola_query(self):
        q = _StubQuery(_sample_data())
        vm = DashboardViewModel(q)
        vm.load()
        assert q.calls == 1

    def test_load_naplni_data(self):
        data = _sample_data()
        vm = DashboardViewModel(_StubQuery(data))
        vm.load()
        assert vm.data is data

    def test_load_resetuje_error(self):
        # Nejdřív chyba
        err_q = _ErrorQuery(RuntimeError("boom"))
        vm = DashboardViewModel(err_q)
        vm.load()
        assert vm.error == "boom"
        # Pak úspěch — error musí zmizet
        vm._query = _StubQuery(_sample_data())  # type: ignore[attr-defined]
        vm.load()
        assert vm.error is None
        assert vm.has_data is True

    def test_load_je_volatelne_opakovane(self):
        q = _StubQuery(_sample_data())
        vm = DashboardViewModel(q)
        vm.load()
        vm.load()
        vm.load()
        assert q.calls == 3
        assert vm.has_data is True


# ──────────────────────────────────────────────────────────────────────
# Chybový load
# ──────────────────────────────────────────────────────────────────────


class TestChybovyLoad:

    def test_vyjimka_se_zachyti(self):
        vm = DashboardViewModel(_ErrorQuery(RuntimeError("DB nedostupná")))
        vm.load()  # nesmí padnout
        assert vm.error == "DB nedostupná"

    def test_data_zustane_none_pri_chybe(self):
        vm = DashboardViewModel(_ErrorQuery(ValueError("x")))
        vm.load()
        assert vm.data is None
        assert vm.has_data is False

    def test_prazdna_zprava_fallback_na_typ(self):
        vm = DashboardViewModel(_ErrorQuery(RuntimeError("")))
        vm.load()
        assert vm.error == "RuntimeError"

    def test_chyba_smaze_predchozi_data(self):
        # Nejdřív úspěch
        vm = DashboardViewModel(_StubQuery(_sample_data()))
        vm.load()
        assert vm.has_data is True
        # Pak chyba
        vm._query = _ErrorQuery(RuntimeError("network"))  # type: ignore[attr-defined]
        vm.load()
        assert vm.data is None
        assert vm.error == "network"
