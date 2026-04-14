"""Testy pro FilterBar widget."""

from datetime import date

from domain.doklady.typy import StavDokladu, TypDokladu
from services.queries.doklady_list import DokladyFilter, KDoreseniFilter
from ui.widgets.filter_bar import FilterBar


class TestFilterBarDefault:

    def test_vychozi_current_filter_je_default(self, qtbot):
        bar = FilterBar()
        qtbot.addWidget(bar)
        assert bar.current_filter() == DokladyFilter()

    def test_rok_combo_ma_vsechny_roky_jako_prvni(self, qtbot):
        bar = FilterBar()
        qtbot.addWidget(bar)
        combo = bar._combo_rok_widget
        assert combo.itemText(0) == "Všechny roky"
        assert combo.itemData(0) is None

    def test_rok_combo_obsahuje_aktualni_rok(self, qtbot):
        bar = FilterBar()
        qtbot.addWidget(bar)
        combo = bar._combo_rok_widget
        current = date.today().year
        data_list = [combo.itemData(i) for i in range(combo.count())]
        assert current in data_list

    def test_typ_combo_ma_vsechny_typy_plus_prazdny(self, qtbot):
        bar = FilterBar()
        qtbot.addWidget(bar)
        combo = bar._combo_typ_widget
        # +1 za "Všechny typy"
        assert combo.count() == len(list(TypDokladu)) + 1
        assert combo.itemData(0) is None

    def test_stav_combo_ma_vsechny_stavy_plus_prazdny(self, qtbot):
        bar = FilterBar()
        qtbot.addWidget(bar)
        combo = bar._combo_stav_widget
        assert combo.count() == len(list(StavDokladu)) + 1
        assert combo.itemData(0) is None

    def test_doreseni_combo_ma_tri_hodnoty(self, qtbot):
        bar = FilterBar()
        qtbot.addWidget(bar)
        combo = bar._combo_doreseni_widget
        assert combo.count() == 3
        assert combo.itemData(0) == KDoreseniFilter.SKRYT
        assert combo.itemData(1) == KDoreseniFilter.VSE
        assert combo.itemData(2) == KDoreseniFilter.POUZE


class TestFilterBarSetFilter:

    def test_set_filter_naplni_combo(self, qtbot):
        bar = FilterBar()
        qtbot.addWidget(bar)
        f = DokladyFilter(
            rok=date.today().year,
            typ=TypDokladu.FAKTURA_VYDANA,
            stav=StavDokladu.ZAUCTOVANY,
            k_doreseni=KDoreseniFilter.POUZE,
        )
        bar.set_filter(f)
        assert bar.current_filter() == f

    def test_set_filter_neemituje_signal(self, qtbot):
        bar = FilterBar()
        qtbot.addWidget(bar)
        received = []
        bar.filters_changed.connect(
            lambda r, t, s, k: received.append((r, t, s, k))
        )
        bar.set_filter(DokladyFilter(typ=TypDokladu.FAKTURA_VYDANA))
        assert received == []


class TestFilterBarSignaly:

    def test_zmena_typu_emituje_filters_changed(self, qtbot):
        bar = FilterBar()
        qtbot.addWidget(bar)
        received = []
        bar.filters_changed.connect(
            lambda r, t, s, k: received.append((r, t, s, k))
        )
        combo = bar._combo_typ_widget
        # Najdi index pro FAKTURA_VYDANA
        for i in range(combo.count()):
            if combo.itemData(i) == TypDokladu.FAKTURA_VYDANA:
                combo.setCurrentIndex(i)
                break
        assert len(received) == 1
        rok, typ, stav, k = received[0]
        assert typ == TypDokladu.FAKTURA_VYDANA
        assert stav is None
        assert k == KDoreseniFilter.SKRYT

    def test_clear_button_emituje_clear_requested(self, qtbot):
        bar = FilterBar()
        qtbot.addWidget(bar)
        received = []
        bar.clear_requested.connect(lambda: received.append(True))
        # Nastav něco, pak stiskni clear
        bar.set_filter(DokladyFilter(typ=TypDokladu.FAKTURA_VYDANA))
        bar._clear_button_widget.click()
        assert received == [True]

    def test_reset_vrati_combo_na_default(self, qtbot):
        bar = FilterBar()
        qtbot.addWidget(bar)
        bar.set_filter(DokladyFilter(
            rok=date.today().year, typ=TypDokladu.FAKTURA_VYDANA,
        ))
        bar.reset()
        assert bar.current_filter() == DokladyFilter()
