"""Testy pro DokladyListViewModel — pure Python, bez Qt."""

from datetime import date

import pytest

from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from services.queries.doklady_list import (
    DokladyFilter,
    DokladyListItem,
    KDoreseniFilter,
)
from ui.viewmodels.doklady_list_vm import DokladyListViewModel


def _item(cislo: str = "A", k_doreseni: bool = False) -> DokladyListItem:
    return DokladyListItem(
        id=1,
        cislo=cislo,
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 2, 1),
        datum_splatnosti=None,
        partner_id=None, partner_nazev=None,
        castka_celkem=Money.from_koruny("100"),
        stav=StavDokladu.NOVY,
        k_doreseni=k_doreseni,
        poznamka_doreseni=None,
        popis=None,
    )


class _StubQuery:
    def __init__(self, result):
        self.result = result
        self.calls: list[DokladyFilter] = []

    def execute(self, f: DokladyFilter):
        self.calls.append(f)
        return self.result


class _ErrorQuery:
    def __init__(self, exc):
        self.exc = exc

    def execute(self, f: DokladyFilter):
        raise self.exc


# ──────────────────────────────────────────────────────────────────────
# Initial state
# ──────────────────────────────────────────────────────────────────────


class TestPocatecniStav:

    def test_items_je_prazdny(self):
        vm = DokladyListViewModel(_StubQuery([]))
        assert vm.items == []

    def test_filter_je_defaultni(self):
        vm = DokladyListViewModel(_StubQuery([]))
        assert vm.filter == DokladyFilter()

    def test_error_je_none(self):
        vm = DokladyListViewModel(_StubQuery([]))
        assert vm.error is None

    def test_has_data_false_pred_load(self):
        vm = DokladyListViewModel(_StubQuery([]))
        assert vm.has_data is False

    def test_is_empty_filter_false_pred_load(self):
        vm = DokladyListViewModel(_StubQuery([]))
        assert vm.is_empty_because_of_filter is False


# ──────────────────────────────────────────────────────────────────────
# load()
# ──────────────────────────────────────────────────────────────────────


class TestLoad:

    def test_load_ulozi_items(self):
        items = [_item("A"), _item("B")]
        vm = DokladyListViewModel(_StubQuery(items))
        vm.load()
        assert vm.items == items

    def test_load_nastavi_has_data(self):
        vm = DokladyListViewModel(_StubQuery([]))
        vm.load()
        assert vm.has_data is True

    def test_load_zavola_query_s_current_filtrem(self):
        q = _StubQuery([])
        vm = DokladyListViewModel(q)
        vm.load()
        assert q.calls == [DokladyFilter()]

    def test_load_chyba_nastavi_error(self):
        vm = DokladyListViewModel(_ErrorQuery(RuntimeError("DB fail")))
        vm.load()
        assert vm.error == "DB fail"
        assert vm.items == []

    def test_load_uspech_po_chybe_smaze_error(self):
        vm = DokladyListViewModel(_ErrorQuery(RuntimeError("x")))
        vm.load()
        assert vm.error == "x"
        vm._query = _StubQuery([_item("ok")])  # type: ignore[attr-defined]
        vm.load()
        assert vm.error is None
        assert len(vm.items) == 1


# ──────────────────────────────────────────────────────────────────────
# apply_filters() / clear_filters() / set_k_doreseni_only()
# ──────────────────────────────────────────────────────────────────────


class TestKomandy:

    def test_apply_filters_ulozi_filtr_a_zavola_load(self):
        q = _StubQuery([])
        vm = DokladyListViewModel(q)
        new = DokladyFilter(rok=2026, typ=TypDokladu.FAKTURA_VYDANA)
        vm.apply_filters(new)
        assert vm.filter == new
        assert q.calls == [new]

    def test_clear_filters_vrati_default(self):
        q = _StubQuery([])
        vm = DokladyListViewModel(q)
        vm.apply_filters(DokladyFilter(rok=2026))
        vm.clear_filters()
        assert vm.filter == DokladyFilter()
        assert q.calls[-1] == DokladyFilter()

    def test_set_k_doreseni_only(self):
        q = _StubQuery([])
        vm = DokladyListViewModel(q)
        vm.set_k_doreseni_only()
        assert vm.filter.k_doreseni == KDoreseniFilter.POUZE
        assert vm.filter.rok is None
        assert vm.filter.typ is None

    def test_set_k_doreseni_only_resetuje_jine_filtry(self):
        q = _StubQuery([])
        vm = DokladyListViewModel(q)
        vm.apply_filters(DokladyFilter(
            rok=2025, typ=TypDokladu.FAKTURA_VYDANA,
        ))
        vm.set_k_doreseni_only()
        assert vm.filter.rok is None
        assert vm.filter.typ is None
        assert vm.filter.k_doreseni == KDoreseniFilter.POUZE


# ──────────────────────────────────────────────────────────────────────
# is_empty_because_of_filter
# ──────────────────────────────────────────────────────────────────────


class TestIsEmptyBecauseOfFilter:

    def test_false_pri_defaultnim_filtru_bez_dat(self):
        vm = DokladyListViewModel(_StubQuery([]))
        vm.load()
        assert vm.is_empty_because_of_filter is False

    def test_true_pri_aktivnim_filtru_bez_vysledku(self):
        vm = DokladyListViewModel(_StubQuery([]))
        vm.apply_filters(DokladyFilter(rok=2026))
        assert vm.is_empty_because_of_filter is True

    def test_false_pokud_items_nenedovane(self):
        vm = DokladyListViewModel(_StubQuery([_item("A")]))
        vm.apply_filters(DokladyFilter(rok=2026))
        assert vm.is_empty_because_of_filter is False


# ──────────────────────────────────────────────────────────────────────
# Fáze 6.7 — total_count + visible_count + set_typ_filter
# ──────────────────────────────────────────────────────────────────────


class TestTotalCount:
    """Status bar: „Zobrazeno X z Y dokladů"."""

    def test_default_total_count_je_nula(self):
        """Bez count_query je total_count 0."""
        vm = DokladyListViewModel(_StubQuery([]))
        assert vm.total_count == 0

    def test_visible_count_je_len_items(self):
        vm = DokladyListViewModel(_StubQuery([_item("A"), _item("B")]))
        vm.load()
        assert vm.visible_count == 2

    def test_load_refreshne_total_count(self):
        from unittest.mock import MagicMock
        count_q = MagicMock()
        count_q.execute.return_value = 42
        vm = DokladyListViewModel(
            _StubQuery([_item("A")]), count_query=count_q,
        )
        vm.load()
        assert vm.total_count == 42
        count_q.execute.assert_called_once()

    def test_apply_filters_refreshne_total_count(self):
        from unittest.mock import MagicMock
        count_q = MagicMock()
        count_q.execute.side_effect = [10, 10]
        vm = DokladyListViewModel(
            _StubQuery([]), count_query=count_q,
        )
        vm.load()
        vm.apply_filters(DokladyFilter(rok=2026))
        assert count_q.execute.call_count == 2
        assert vm.total_count == 10

    def test_count_query_chyba_je_non_fatal(self):
        """Pokud count_query selže, load stále funguje."""
        from unittest.mock import MagicMock
        count_q = MagicMock()
        count_q.execute.side_effect = RuntimeError("DB")
        vm = DokladyListViewModel(
            _StubQuery([_item("A")]), count_query=count_q,
        )
        vm.load()
        assert vm.error is None  # load neovlivněn
        assert vm.items == [_item("A")]
        assert vm.total_count == 0  # zůstává na defaultu


class TestSetTypFilter:

    def test_set_typ_filter(self):
        q = _StubQuery([])
        vm = DokladyListViewModel(q)
        vm.set_typ_filter(TypDokladu.FAKTURA_VYDANA)
        assert vm.filter.typ == TypDokladu.FAKTURA_VYDANA
        assert vm.filter.rok is None
        assert vm.filter.k_doreseni == KDoreseniFilter.SKRYT

    def test_set_typ_filter_resetuje_jine(self):
        q = _StubQuery([])
        vm = DokladyListViewModel(q)
        vm.apply_filters(DokladyFilter(
            rok=2025, k_doreseni=KDoreseniFilter.POUZE,
        ))
        vm.set_typ_filter(TypDokladu.FAKTURA_PRIJATA)
        assert vm.filter.typ == TypDokladu.FAKTURA_PRIJATA
        assert vm.filter.rok is None
        assert vm.filter.k_doreseni == KDoreseniFilter.SKRYT

    def test_set_typ_filter_zavola_load(self):
        q = _StubQuery([_item("A")])
        vm = DokladyListViewModel(q)
        vm.set_typ_filter(TypDokladu.FAKTURA_VYDANA)
        assert q.calls[-1].typ == TypDokladu.FAKTURA_VYDANA
        assert vm.items == [_item("A")]
