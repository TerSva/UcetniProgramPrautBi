"""Testy UI switche 'Včetně závěrkových zápisů' na Výkazy stránce."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from domain.shared.money import Money
from services.queries.vykazy_query import (
    HlavniKnihaUctu,
)


@pytest.fixture
def mock_query():
    q = MagicMock()
    q.get_rozvaha.return_value = (tuple(), tuple())
    q.get_vzz.return_value = tuple()
    q.get_predvaha.return_value = tuple()
    q.get_hlavni_kniha.return_value = HlavniKnihaUctu(
        ucet="211", nazev="Pokladna", typ="A",
        pocatecni_stav=Money.zero(),
        obrat_md=Money.zero(), obrat_dal=Money.zero(),
        radky=tuple(),
    )
    q.get_zaverkove_saldo.return_value = Money.zero()
    q.get_ucty_s_pohybem.return_value = (("211", "Pokladna"),)
    q.get_bilancni_kontrola.return_value = (Money.zero(), Money.zero())
    q.get_saldokonto.return_value = (tuple(), tuple())
    q.get_saldokonto_per_ucet.return_value = (
        type("S", (), {"radky": tuple(), "celkem": Money.zero()})(),
        type("S", (), {"radky": tuple(), "celkem": Money.zero()})(),
        type("S", (), {"radky": tuple(), "celkem": Money.zero()})(),
        type("S", (), {"radky": tuple(), "celkem": Money.zero()})(),
    )
    from services.queries.vykazy_query import DphPrehled
    q.get_dph_prehled.return_value = DphPrehled(
        rok=2025, obdobi_od=date(2025, 1, 1), obdobi_do=date(2025, 12, 31),
        vstup_celkem=Money.zero(), vstup_rc=Money.zero(),
        vystup_celkem=Money.zero(), vystup_rc=Money.zero(),
        doklady=tuple(),
    )
    from services.queries.vykazy_query import PokladniKniha
    q.get_pokladni_kniha.return_value = PokladniKniha(
        rok=2025, pocatecni_stav=Money.zero(),
        radky=tuple(), pouzita=False,
    )
    from services.queries.vykazy_query import NedanoveNaklady
    q.get_nedanove_naklady.return_value = NedanoveNaklady(
        rok=2025, radky=tuple(), celkem=Money.zero(),
    )
    return q


@pytest.fixture
def page(qtbot, mock_query):
    from ui.pages.vykazy_page import VykazyPage
    p = VykazyPage(mock_query, rok_default=2025)
    qtbot.addWidget(p)
    return p


class TestZaverkaSwitchDefaults:

    def test_rozvaha_switch_default_off(self, page):
        assert page._rozvaha_zaverka_check.isChecked() is False
        assert "závěrkových" in page._rozvaha_zaverka_check.text()

    def test_vzz_switch_default_off(self, page):
        assert page._vzz_zaverka_check.isChecked() is False

    def test_predvaha_switch_default_off(self, page):
        assert page._predvaha_zaverka_check.isChecked() is False

    def test_kniha_switch_default_on(self, page):
        assert page._kniha_zaverka_check.isChecked() is True


class TestZaverkaSwitchPropaguje:

    def test_rozvaha_off_passes_false(self, page, mock_query):
        page._rozvaha_zaverka_check.setChecked(False)
        mock_query.get_rozvaha.reset_mock()
        page._load_rozvaha()
        mock_query.get_rozvaha.assert_called_with(
            2025, vcetne_zaverky=False,
        )

    def test_rozvaha_on_passes_true(self, page, mock_query):
        mock_query.get_rozvaha.reset_mock()
        page._rozvaha_zaverka_check.setChecked(True)
        mock_query.get_rozvaha.assert_called_with(
            2025, vcetne_zaverky=True,
        )

    def test_vzz_on_passes_true(self, page, mock_query):
        mock_query.get_vzz.reset_mock()
        page._vzz_zaverka_check.setChecked(True)
        mock_query.get_vzz.assert_called_with(
            2025, vcetne_zaverky=True,
        )

    def test_predvaha_on_passes_true(self, page, mock_query):
        mock_query.get_predvaha.reset_mock()
        page._predvaha_zaverka_check.setChecked(True)
        # předvaha se loaduje s jen_s_pohybem=True (default checkbox off)
        mock_query.get_predvaha.assert_called_with(
            2025, jen_s_pohybem=True, vcetne_zaverky=True,
        )

    def test_kniha_off_passes_false(self, page, mock_query):
        # Default je ON, switch off → False
        # Nejdřív naplnit combo (jinak setChecked nezavolá load — combo prázdný)
        page._load_kniha()
        mock_query.get_hlavni_kniha.reset_mock()
        page._kniha_zaverka_check.setChecked(False)
        mock_query.get_hlavni_kniha.assert_called_with(
            "211", 2025, vcetne_zaverky=False,
        )

    def test_kniha_default_on_passes_true(self, page, mock_query):
        # Klik na účet při default ON → musí být True
        page._load_kniha()
        mock_query.get_hlavni_kniha.reset_mock()
        page._load_kniha_detail()
        mock_query.get_hlavni_kniha.assert_called_with(
            "211", 2025, vcetne_zaverky=True,
        )
