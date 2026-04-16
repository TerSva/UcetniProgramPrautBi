"""Integration testy pro DashboardPage — VM napojený na reálnou (prázdnou) DB.

`dashboard_vm` fixture pochází z `tests/ui/conftest.py` a používá tempfile DB.
"""

from __future__ import annotations

from datetime import date

import pytest

from domain.shared.money import Money
from services.queries.dashboard import DashboardData
from ui.pages.dashboard_page import DashboardPage, _format_date_cz
from ui.viewmodels.dashboard_vm import DashboardViewModel


# ──────────────────────────────────────────────────────────────────────
# Czech date formatter
# ──────────────────────────────────────────────────────────────────────


def test_format_date_cz():
    assert _format_date_cz(date(2026, 4, 13)) == "Pondělí, 13. dubna 2026"
    assert _format_date_cz(date(2026, 1, 1)) == "Čtvrtek, 1. ledna 2026"
    assert _format_date_cz(date(2026, 12, 31)) == "Čtvrtek, 31. prosince 2026"


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _data(**overrides) -> DashboardData:
    base = dict(
        doklady_celkem=0,
        doklady_k_zauctovani=0,
        doklady_k_doreseni=0,
        pohledavky=Money.zero(),
        zavazky=Money.zero(),
        rok=2026,
        vynosy=Money.zero(),
        naklady=Money.zero(),
        hruby_zisk=Money.zero(),
        odhad_dane=Money.zero(),
    )
    base.update(overrides)
    return DashboardData(**base)


class _StubQuery:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class _ErrorQuery:
    def __init__(self, exc):
        self.exc = exc

    def execute(self):
        raise self.exc


@pytest.fixture
def page_factory(qtbot):
    def _make(vm):
        page = DashboardPage(vm)
        qtbot.addWidget(page)
        return page
    return _make


# ──────────────────────────────────────────────────────────────────────
# Reálný VM (prázdná DB)
# ──────────────────────────────────────────────────────────────────────


class TestSReálnouPrazdnouDb:

    def test_page_se_postavi_a_nacte_data(self, dashboard_vm, page_factory):
        page = page_factory(dashboard_vm)
        # Po refresh() v __init__ má VM data z prázdné DB
        assert dashboard_vm.has_data is True
        assert dashboard_vm.error is None
        assert page.card_doklady.value_widget.text() == "0"

    def test_pohledavky_a_zavazky_jsou_nula_v_prazdne_db(
        self, dashboard_vm, page_factory,
    ):
        page = page_factory(dashboard_vm)
        assert "0,00" in page.card_pohledavky.value_widget.text()
        assert "0,00" in page.card_zavazky.value_widget.text()

    def test_error_label_je_skryty_pri_uspechu(
        self, dashboard_vm, page_factory,
    ):
        page = page_factory(dashboard_vm)
        assert page.error_label.isVisibleTo(page) is False


# ──────────────────────────────────────────────────────────────────────
# Render se stub daty
# ──────────────────────────────────────────────────────────────────────


class TestRenderHodnot:

    def test_doklady_celkem_v_value(self, page_factory):
        vm = DashboardViewModel(_StubQuery(_data(doklady_celkem=7)))
        page = page_factory(vm)
        assert page.card_doklady.value_widget.text() == "7"

    def test_subtitle_dokladu_jen_k_zauctovani_kdyz_zadne_doreseni(
        self, page_factory,
    ):
        vm = DashboardViewModel(_StubQuery(
            _data(doklady_celkem=5, doklady_k_zauctovani=2,
                  doklady_k_doreseni=0)
        ))
        page = page_factory(vm)
        sub = page.card_doklady.subtitle_widget.text()
        assert "2 k zaúčtování" in sub
        assert "k dořešení" not in sub

    def test_subtitle_dokladu_obsahuje_doreseni_kdyz_existuji(
        self, page_factory,
    ):
        vm = DashboardViewModel(_StubQuery(
            _data(doklady_celkem=5, doklady_k_zauctovani=2,
                  doklady_k_doreseni=3)
        ))
        page = page_factory(vm)
        sub = page.card_doklady.subtitle_widget.text()
        assert "2 k zaúčtování" in sub
        assert "3 k dořešení" in sub

    def test_pohledavky_format_cz(self, page_factory):
        vm = DashboardViewModel(_StubQuery(
            _data(pohledavky=Money.from_koruny("12345"))
        ))
        page = page_factory(vm)
        # 12 345,00 Kč (nb-space)
        text = page.card_pohledavky.value_widget.text()
        assert "12" in text and "345,00" in text and "Kč" in text

    def test_zisk_positive_kdyz_kladny(self, page_factory):
        vm = DashboardViewModel(_StubQuery(
            _data(
                vynosy=Money.from_koruny("100000"),
                naklady=Money.from_koruny("60000"),
                hruby_zisk=Money.from_koruny("40000"),
                odhad_dane=Money.from_koruny("7600"),
            )
        ))
        page = page_factory(vm)
        assert page.card_zisk.property("positive") == "true"

    def test_zisk_neni_positive_pri_ztrate(self, page_factory):
        vm = DashboardViewModel(_StubQuery(
            _data(
                naklady=Money.from_koruny("3000"),
                hruby_zisk=Money.from_koruny("-3000"),
            )
        ))
        page = page_factory(vm)
        assert page.card_zisk.property("positive") == "false"

    def test_zisk_subtitle_obsahuje_vynosy_naklady_dan(self, page_factory):
        vm = DashboardViewModel(_StubQuery(
            _data(
                rok=2026,
                vynosy=Money.from_koruny("10000"),
                naklady=Money.from_koruny("4000"),
                hruby_zisk=Money.from_koruny("6000"),
                odhad_dane=Money.from_koruny("1140"),
            )
        ))
        page = page_factory(vm)
        sub = page.card_zisk.subtitle_widget.text()
        assert "2026" in sub
        assert "výnosy" in sub
        assert "náklady" in sub
        assert "odhad daně" in sub


# ──────────────────────────────────────────────────────────────────────
# Chybový stav
# ──────────────────────────────────────────────────────────────────────


class TestChybovyStav:

    def test_error_label_se_zobrazi(self, page_factory):
        vm = DashboardViewModel(_ErrorQuery(RuntimeError("DB read fail")))
        page = page_factory(vm)
        page.show()
        assert page.error_label.isVisibleTo(page) is True
        assert "DB read fail" in page.error_label.text()

    def test_karty_maji_pomlcku_pri_chybe(self, page_factory):
        vm = DashboardViewModel(_ErrorQuery(RuntimeError("boom")))
        page = page_factory(vm)
        assert page.card_doklady.value_widget.text() == "—"
        assert page.card_pohledavky.value_widget.text() == "—"
        assert page.card_zavazky.value_widget.text() == "—"
        assert page.card_zisk.value_widget.text() == "—"


# ──────────────────────────────────────────────────────────────────────
# Refresh
# ──────────────────────────────────────────────────────────────────────


class TestRefresh:

    def test_refresh_nacte_nova_data(self, page_factory):
        # Mutable stub: měníme result mezi voláními
        class _Mut:
            def __init__(self):
                self.calls = 0
                self.results = [_data(doklady_celkem=1), _data(doklady_celkem=99)]

            def execute(self):
                r = self.results[self.calls]
                self.calls += 1
                return r

        q = _Mut()
        vm = DashboardViewModel(q)
        page = page_factory(vm)
        assert page.card_doklady.value_widget.text() == "1"

        page.refresh()
        assert page.card_doklady.value_widget.text() == "99"

    def test_show_po_skryti_refreshuje_data(self, page_factory):
        """Když je stránka skrytá (QStackedWidget přepne na jinou) a pak
        znovu zobrazená, musí se data načíst znovu — jinak Dashboard
        pojede se starými hodnotami po transakcích v jiných stránkách."""
        class _Mut:
            def __init__(self):
                self.calls = 0
                self.results = [
                    _data(doklady_celkem=1),
                    _data(doklady_celkem=42),
                ]

            def execute(self):
                r = self.results[min(self.calls, len(self.results) - 1)]
                self.calls += 1
                return r

        q = _Mut()
        vm = DashboardViewModel(q)
        page = page_factory(vm)
        # Ctor refresh: calls=1, value=1
        assert page.card_doklady.value_widget.text() == "1"
        # První show (mount) nesmí refresh znovu — kdyby ano, vidíme 42
        page.show()
        assert page.card_doklady.value_widget.text() == "1"
        # Simuluj skrytí (přepnutí na jinou stránku) a návrat
        page.hide()
        page.show()
        assert page.card_doklady.value_widget.text() == "42"

    def test_refresh_z_chyby_do_uspechu_skryje_error(self, page_factory):
        class _Toggle:
            def __init__(self):
                self.first = True

            def execute(self):
                if self.first:
                    self.first = False
                    raise RuntimeError("temp")
                return _data(doklady_celkem=3)

        vm = DashboardViewModel(_Toggle())
        page = page_factory(vm)
        page.show()
        assert page.error_label.isVisibleTo(page) is True

        page.refresh()
        assert page.error_label.isVisibleTo(page) is False
        assert page.card_doklady.value_widget.text() == "3"


# ──────────────────────────────────────────────────────────────────────
# Dashboard drill — klik na „k dořešení" subtitle emituje signal
# ──────────────────────────────────────────────────────────────────────


class TestDrillKDoreseni:

    def test_subtitle_clickable_kdyz_jsou_doreseni(self, page_factory):
        vm = DashboardViewModel(_StubQuery(
            _data(doklady_celkem=5, doklady_k_zauctovani=1,
                  doklady_k_doreseni=2)
        ))
        page = page_factory(vm)
        assert page.card_doklady.subtitle_widget.property("clickable") == "true"

    def test_subtitle_neni_clickable_bez_doreseni(self, page_factory):
        vm = DashboardViewModel(_StubQuery(
            _data(doklady_celkem=5, doklady_k_zauctovani=1,
                  doklady_k_doreseni=0)
        ))
        page = page_factory(vm)
        assert page.card_doklady.subtitle_widget.property("clickable") == "false"

    def test_klik_emituje_navigate_signal(self, page_factory):
        from PyQt6.QtCore import QPointF, Qt
        from PyQt6.QtGui import QMouseEvent
        vm = DashboardViewModel(_StubQuery(
            _data(doklady_celkem=5, doklady_k_zauctovani=1,
                  doklady_k_doreseni=2)
        ))
        page = page_factory(vm)
        received = []
        page.navigate_to_doklady_k_doreseni.connect(
            lambda: received.append(True)
        )
        ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(5, 5),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        page.card_doklady.subtitle_widget.mousePressEvent(ev)
        assert received == [True]


# ──────────────────────────────────────────────────────────────────────
# Fáze 6.7 — drill-down z Pohledávky / Závazky na filtr FV / FP
# ──────────────────────────────────────────────────────────────────────


class TestDrillPohledavkyZavazky:

    def test_karta_pohledavky_je_klikatelna(self, page_factory):
        vm = DashboardViewModel(_StubQuery(_data()))
        page = page_factory(vm)
        assert page.card_pohledavky.property("clickable") == "true"

    def test_karta_zavazky_je_klikatelna(self, page_factory):
        vm = DashboardViewModel(_StubQuery(_data()))
        page = page_factory(vm)
        assert page.card_zavazky.property("clickable") == "true"

    def test_klik_na_pohledavky_emituje_fv(self, page_factory):
        from domain.doklady.typy import TypDokladu
        vm = DashboardViewModel(_StubQuery(_data()))
        page = page_factory(vm)
        received: list[object] = []
        page.navigate_to_doklady_with_typ.connect(
            lambda typ: received.append(typ)
        )
        page.card_pohledavky.card_clicked.emit()
        assert received == [TypDokladu.FAKTURA_VYDANA]

    def test_klik_na_zavazky_emituje_fp(self, page_factory):
        from domain.doklady.typy import TypDokladu
        vm = DashboardViewModel(_StubQuery(_data()))
        page = page_factory(vm)
        received: list[object] = []
        page.navigate_to_doklady_with_typ.connect(
            lambda typ: received.append(typ)
        )
        page.card_zavazky.card_clicked.emit()
        assert received == [TypDokladu.FAKTURA_PRIJATA]

    def test_karty_doklady_a_zisk_nejsou_klikatelne(self, page_factory):
        vm = DashboardViewModel(_StubQuery(_data()))
        page = page_factory(vm)
        # Doklady má subtitle-clickable, ne card-clickable
        assert page.card_doklady.property("clickable") == "false"
        assert page.card_zisk.property("clickable") == "false"
