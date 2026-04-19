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
        partner_id=None, partner_nazev=None,
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


# ──────────────────────────────────────────────────────────────────────
# Fáze 6.7 — apply_typ_filter (Dashboard drill Pohledávky/Závazky)
# ──────────────────────────────────────────────────────────────────────


class TestApplyTypFilter:

    def test_aplikuje_filter_na_typ(self, page_factory):
        page, vm, _ = page_factory([])
        page.apply_typ_filter(TypDokladu.FAKTURA_VYDANA)
        assert vm.filter.typ == TypDokladu.FAKTURA_VYDANA
        assert vm.filter.rok is None

    def test_synclne_filter_bar(self, page_factory):
        page, _, _ = page_factory([])
        page.apply_typ_filter(TypDokladu.FAKTURA_PRIJATA)
        assert page._filter_bar_widget.current_filter().typ == \
            TypDokladu.FAKTURA_PRIJATA

    def test_resetuje_jine_filtry(self, page_factory):
        page, vm, _ = page_factory([])
        # Nejdřív aktivuj rok a k_doreseni
        page._vm.apply_filters(DokladyFilter(
            rok=2025, k_doreseni=KDoreseniFilter.POUZE,
        ))
        # Pak drill
        page.apply_typ_filter(TypDokladu.FAKTURA_VYDANA)
        assert vm.filter.rok is None
        assert vm.filter.k_doreseni == KDoreseniFilter.VSE
        assert vm.filter.typ == TypDokladu.FAKTURA_VYDANA


# ──────────────────────────────────────────────────────────────────────
# Fáze 6.7 — status bar „Zobrazeno X z Y · N filtrů aktivní"
# ──────────────────────────────────────────────────────────────────────


class _CountQueryStub:
    def __init__(self, total: int) -> None:
        self._total = total

    def execute(self) -> int:
        return self._total


@pytest.fixture
def page_with_count(qtbot):
    def _make(items: list, total: int):
        query = _StubQuery(items)
        vm = DokladyListViewModel(query, count_query=_CountQueryStub(total))
        page = DokladyPage(vm)
        qtbot.addWidget(page)
        return page, vm, query
    return _make


class TestStatusBar:

    def test_skryty_bez_count_query(self, page_factory):
        page, _, _ = page_factory([_item(cislo="A")])
        page.show()
        assert page._status_bar_widget.isVisibleTo(page) is False

    def test_zobrazeno_x_z_y(self, page_with_count):
        page, _, _ = page_with_count([_item(cislo="A"), _item(cislo="B")], 5)
        page.show()
        assert page._status_bar_widget.isVisibleTo(page) is True
        text = page._status_bar_widget.text()
        assert "Zobrazeno 2 z 5" in text
        assert "dokladů" in text

    def test_bez_filtru_nezobrazuje_pocet_filtru(self, page_with_count):
        page, _, _ = page_with_count([_item(cislo="A")], 3)
        assert "filtr" not in page._status_bar_widget.text()

    def test_s_jednim_filtrem_zobrazuje_1_filtr(self, page_with_count):
        page, vm, _ = page_with_count([_item(cislo="A")], 3)
        page._filter_bar_widget.set_filter(DokladyFilter(rok=2026))
        vm.apply_filters(DokladyFilter(rok=2026))
        page._sync_ui_with_vm()
        text = page._status_bar_widget.text()
        assert "1 filtr aktivní" in text

    def test_se_dvema_filtry_zobrazuje_2_filtry(self, page_with_count):
        page, vm, _ = page_with_count([_item(cislo="A")], 3)
        f = DokladyFilter(rok=2026, typ=TypDokladu.FAKTURA_VYDANA)
        page._filter_bar_widget.set_filter(f)
        vm.apply_filters(f)
        page._sync_ui_with_vm()
        text = page._status_bar_widget.text()
        assert "2 filtry aktivní" in text

    def test_se_ctyrmi_filtry_zobrazuje_4_filtry(self, page_with_count):
        page, vm, _ = page_with_count([_item(cislo="A", k_doreseni=True)], 3)
        f = DokladyFilter(
            rok=2026,
            typ=TypDokladu.FAKTURA_VYDANA,
            stav=StavDokladu.NOVY,
            k_doreseni=KDoreseniFilter.POUZE,
        )
        page._filter_bar_widget.set_filter(f)
        vm.apply_filters(f)
        page._sync_ui_with_vm()
        text = page._status_bar_widget.text()
        assert "4 filtry aktivní" in text

    def test_status_bar_skryty_pri_prazdne_db(self, page_with_count):
        page, _, _ = page_with_count([], 0)
        page.show()
        assert page._status_bar_widget.isVisibleTo(page) is False

    def test_status_bar_skryty_pri_chybe(self, page_factory):
        page, _, _ = page_factory(_ErrorQuery())
        page.show()
        assert page._status_bar_widget.isVisibleTo(page) is False


class TestCzechPlural:

    def test_plural_filtry(self):
        from ui.pages.doklady_page import _czech_plural_filtry
        assert _czech_plural_filtry(0) == "0 filtrů aktivní"
        assert _czech_plural_filtry(1) == "1 filtr aktivní"
        assert _czech_plural_filtry(2) == "2 filtry aktivní"
        assert _czech_plural_filtry(3) == "3 filtry aktivní"
        assert _czech_plural_filtry(4) == "4 filtry aktivní"
        assert _czech_plural_filtry(5) == "5 filtrů aktivní"


# ──────────────────────────────────────────────────────────────────────
# Fáze 8 — preset_typ (typová stránka Doklady)
# ──────────────────────────────────────────────────────────────────────


class TestPresetTyp:

    def test_fv_page_has_preset_typ(self, qtbot):
        query = _StubQuery([])
        vm = DokladyListViewModel(query)
        page = DokladyPage(
            vm,
            preset_typ=TypDokladu.FAKTURA_VYDANA,
            preset_title="Vydané faktury",
        )
        qtbot.addWidget(page)
        assert page._title_widget.text() == "Vydané faktury"

    def test_fp_page_has_preset_typ(self, qtbot):
        query = _StubQuery([])
        vm = DokladyListViewModel(query)
        page = DokladyPage(
            vm,
            preset_typ=TypDokladu.FAKTURA_PRIJATA,
            preset_title="Přijaté faktury",
        )
        qtbot.addWidget(page)
        assert page._title_widget.text() == "Přijaté faktury"

    def test_typ_dropdown_hidden_when_preset(self, qtbot):
        query = _StubQuery([])
        vm = DokladyListViewModel(query)
        page = DokladyPage(
            vm,
            preset_typ=TypDokladu.FAKTURA_VYDANA,
            preset_title="Vydané faktury",
        )
        qtbot.addWidget(page)
        assert page._filter_bar_widget._typ_hidden is True

    def test_default_title_without_preset(self, qtbot):
        query = _StubQuery([])
        vm = DokladyListViewModel(query)
        page = DokladyPage(vm)
        qtbot.addWidget(page)
        assert page._title_widget.text() == "Doklady"
