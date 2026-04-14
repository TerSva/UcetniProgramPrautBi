"""Testy pro DokladyPage — integrace VM + FilterBar + Table."""

from datetime import date

import pytest

from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from services.queries.doklady_list import (
    DokladyFilter,
    DokladyListItem,
    KDoreseniFilter,
)
from ui.pages.doklady_page import DokladyPage
from ui.viewmodels.doklady_list_vm import DokladyListViewModel


def _item(
    id: int = 1,
    cislo: str = "A",
    k_doreseni: bool = False,
    poznamka: str | None = None,
) -> DokladyListItem:
    return DokladyListItem(
        id=id,
        cislo=cislo,
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 2, 1),
        datum_splatnosti=None,
        partner_nazev=None,
        castka_celkem=Money.from_koruny("1000"),
        stav=StavDokladu.NOVY,
        k_doreseni=k_doreseni,
        poznamka_doreseni=poznamka,
        popis=None,
    )


class _StubQuery:
    def __init__(self, items):
        self.items = items
        self.last_filter: DokladyFilter | None = None

    def execute(self, f: DokladyFilter):
        self.last_filter = f
        # Filter doma aspoň k_doreseni, aby empty-state rozlišení fungovalo
        if f.k_doreseni == KDoreseniFilter.POUZE:
            return [i for i in self.items if i.k_doreseni]
        if f.k_doreseni == KDoreseniFilter.SKRYT:
            return [i for i in self.items if not i.k_doreseni]
        return list(self.items)


class _ErrorQuery:
    def execute(self, f):
        raise RuntimeError("DB fail")


@pytest.fixture
def page_factory(qtbot):
    def _make(items_or_query):
        if isinstance(items_or_query, list):
            query = _StubQuery(items_or_query)
        else:
            query = items_or_query
        vm = DokladyListViewModel(query)
        page = DokladyPage(vm)
        qtbot.addWidget(page)
        return page, vm, query
    return _make


# ──────────────────────────────────────────────────────────────────────
# Render
# ──────────────────────────────────────────────────────────────────────


class TestRender:

    def test_title_je_doklady(self, page_factory):
        page, _, _ = page_factory([])
        assert page._title_widget.text() == "Doklady"

    def test_novy_button_je_disabled(self, page_factory):
        page, _, _ = page_factory([])
        assert page._novy_button.isEnabled() is False

    def test_filter_bar_je_pritomny(self, page_factory):
        page, _, _ = page_factory([])
        assert page._filter_bar_widget is not None

    def test_table_obsahuje_items(self, page_factory):
        page, _, _ = page_factory([
            _item(id=1, cislo="A"),
            _item(id=2, cislo="B"),
        ])
        assert page._table_widget._model_adapter.rowCount() == 2


# ──────────────────────────────────────────────────────────────────────
# Empty state
# ──────────────────────────────────────────────────────────────────────


class TestEmptyState:

    def test_prazdna_db_info_o_pridani(self, page_factory):
        page, _, _ = page_factory([])
        page.show()
        assert page._empty_widget.isVisibleTo(page) is True
        assert "nejsou" in page._empty_label_widget.text().lower()

    def test_filter_bez_vysledku_nabidne_vymazat(self, page_factory):
        page, vm, _ = page_factory([])
        page.show()
        # Aktivuj filter → is_empty_because_of_filter = True
        vm.apply_filters(DokladyFilter(rok=2026))
        page._sync_ui_with_vm()
        assert "neodpovídají" in page._empty_label_widget.text().lower()


# ──────────────────────────────────────────────────────────────────────
# Error state
# ──────────────────────────────────────────────────────────────────────


class TestErrorState:

    def test_error_label_viditelny(self, page_factory):
        page, _, _ = page_factory(_ErrorQuery())
        page.show()
        assert page._error_label_widget.isVisibleTo(page) is True
        assert "DB fail" in page._error_label_widget.text()


# ──────────────────────────────────────────────────────────────────────
# apply_k_doreseni_filter (Dashboard drill)
# ──────────────────────────────────────────────────────────────────────


class TestApplyKDoreseniFilter:

    def test_aplikuje_filter_pouze(self, page_factory):
        page, vm, _ = page_factory([
            _item(id=1, cislo="N", k_doreseni=False),
            _item(id=2, cislo="F", k_doreseni=True, poznamka="p"),
        ])
        page.apply_k_doreseni_filter()
        assert vm.filter.k_doreseni == KDoreseniFilter.POUZE
        assert len(vm.items) == 1
        assert vm.items[0].cislo == "F"

    def test_synclne_filter_bar(self, page_factory):
        page, _, _ = page_factory([])
        page.apply_k_doreseni_filter()
        assert page._filter_bar_widget.current_filter().k_doreseni == \
            KDoreseniFilter.POUZE
