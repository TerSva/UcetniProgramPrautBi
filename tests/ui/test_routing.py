"""Testy pro MainWindow routing — Fáze 8.

Ověřuje navigaci mezi stránkami, dashboard drill-down
a placeholder stránky.
"""

from __future__ import annotations

from ui.pages.placeholder_page import PlaceholderPage


class TestRouting:

    def test_all_pages_have_index(self, main_window):
        """Každá stránka má index v page_index dict."""
        pi = main_window.page_index
        expected_keys = [
            "dashboard",
            "doklady_fv", "doklady_fp", "doklady_pd",
            "doklady_id", "doklady_od",
            "osnova",
            "nahrat_doklady", "banka_import", "banka_vypisy",
            "ucetni_denik",
            "partneri", "vykazy", "dph", "saldokonto",
            "nastaveni",
            "_doklady_all",
        ]
        for key in expected_keys:
            assert key in pi, f"Missing page: {key}"

    def test_navigate_to_placeholder(self, main_window, qtbot):
        """Klik na placeholder stránku zobrazí PlaceholderPage."""
        main_window.sidebar._buttons["ucetni_denik"].click()
        idx = main_window.page_index["ucetni_denik"]
        assert main_window.stack.currentIndex() == idx
        page = main_window.stack.widget(idx)
        assert isinstance(page, PlaceholderPage)

    def test_navigate_to_doklady_fv(self, main_window, qtbot):
        """Klik na Vydané faktury přepne na typovou stránku."""
        # Expand sub-menu
        main_window.sidebar._parent_buttons["doklady"].click()
        main_window.sidebar._buttons["doklady_fv"].click()
        idx = main_window.page_index["doklady_fv"]
        assert main_window.stack.currentIndex() == idx


class TestDashboardDrillDown:

    def test_pohledavky_navigates_to_fv(self, main_window, qtbot):
        """Dashboard Pohledávky karta naviguje na doklady_fv."""
        from domain.doklady.typy import TypDokladu
        main_window._on_navigate_with_typ(TypDokladu.FAKTURA_VYDANA)
        idx = main_window.page_index["doklady_fv"]
        assert main_window.stack.currentIndex() == idx

    def test_zavazky_navigates_to_fp(self, main_window, qtbot):
        """Dashboard Závazky karta naviguje na doklady_fp."""
        from domain.doklady.typy import TypDokladu
        main_window._on_navigate_with_typ(TypDokladu.FAKTURA_PRIJATA)
        idx = main_window.page_index["doklady_fp"]
        assert main_window.stack.currentIndex() == idx

    def test_k_doreseni_navigates_to_all_doklady(self, main_window, qtbot):
        """Dashboard k dořešení naviguje na all-doklady page."""
        main_window._on_navigate_k_doreseni()
        idx = main_window.page_index["_doklady_all"]
        assert main_window.stack.currentIndex() == idx
