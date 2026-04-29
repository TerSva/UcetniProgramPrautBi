"""Testy DPH stránky — 3 záložky, měsíční filter."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from domain.shared.money import Money
from services.queries.dph_prehled import DphMesicItem, ViesItem
from ui.pages.dph_page import DphPage
from ui.viewmodels.dph_vm import DphViewModel


def _make_mesice(april_data=None):
    """12 měsíců, duben volitelně s daty."""
    result = []
    for m in range(1, 13):
        if m == 4 and april_data:
            result.append(april_data)
        else:
            result.append(DphMesicItem(
                rok=2025, mesic=m,
                zaklad_celkem=Money.zero(),
                dph_celkem=Money.zero(),
                pocet_transakci=0,
                je_podane=False,
            ))
    return result


def _make_vm(mesice=None, vies=None):
    prehled_q = MagicMock()
    detail_q = MagicMock()
    podani_cmd = MagicMock()
    priznani_q = MagicMock()
    vies_q = MagicMock()
    if mesice is not None:
        prehled_q.execute.return_value = mesice
    else:
        prehled_q.execute.return_value = _make_mesice()
    vies_q.execute.return_value = vies if vies is not None else []
    return DphViewModel(
        prehled_query=prehled_q,
        detail_query=detail_q,
        podani_command=podani_cmd,
        priznani_query=priznani_q,
        vies_query=vies_q,
    )


class TestDphPageTabs:

    def test_three_tabs(self, qtbot):
        vm = _make_vm()
        page = DphPage(vm)
        qtbot.addWidget(page)
        assert page._tabs_widget.count() == 3
        assert page._tabs_widget.tabText(0) == "Přiznání k DPH"
        assert page._tabs_widget.tabText(1) == "Souhrnné hlášení"
        assert page._tabs_widget.tabText(2) == "Kontrolní hlášení"


class TestDphPagePriznani:

    def test_empty_year(self, qtbot):
        vm = _make_vm()
        page = DphPage(vm)
        qtbot.addWidget(page)
        # Without filter all 12 months
        assert page._table_widget.rowCount() == 12
        # April cell should show "Bez transakcí"
        cell = page._table_widget.item(3, 3)
        assert "Bez transakcí" in cell.text()

    def test_month_with_transactions(self, qtbot):
        april = DphMesicItem(
            rok=2025, mesic=4,
            zaklad_celkem=Money(105000),
            dph_celkem=Money(22050),
            pocet_transakci=9,
            je_podane=False,
        )
        vm = _make_vm(_make_mesice(april))
        page = DphPage(vm)
        qtbot.addWidget(page)
        cell = page._table_widget.item(3, 3)
        assert "K podání" in cell.text()

    def test_month_podane(self, qtbot):
        april = DphMesicItem(
            rok=2025, mesic=4,
            zaklad_celkem=Money(105000),
            dph_celkem=Money(22050),
            pocet_transakci=9,
            je_podane=True,
        )
        vm = _make_vm(_make_mesice(april))
        page = DphPage(vm)
        qtbot.addWidget(page)
        cell = page._table_widget.item(3, 3)
        assert "Podáno" in cell.text()

    def test_mesic_filter_shows_only_one_month(self, qtbot):
        april = DphMesicItem(
            rok=2025, mesic=4,
            zaklad_celkem=Money(105000),
            dph_celkem=Money(22050),
            pocet_transakci=9,
            je_podane=False,
        )
        vm = _make_vm(_make_mesice(april))
        page = DphPage(vm)
        qtbot.addWidget(page)
        # Apply filter for April (value 4)
        page._mesic_combo_widget.set_value(4)
        # Table should now have 1 row
        assert page._table_widget.rowCount() == 1
        assert "Duben" in page._table_widget.item(0, 0).text()


class TestDphPageVies:

    def test_vies_empty(self, qtbot):
        vm = _make_vm()
        page = DphPage(vm)
        qtbot.addWidget(page)
        # Switch to VIES tab to trigger load
        page._tabs_widget.setCurrentIndex(1)
        # Empty label not hidden, table is hidden (visible state set via setVisible)
        assert not page._vies_empty_label_widget.isHidden()
        assert page._vies_table_widget.isHidden()

    def test_vies_with_records(self, qtbot):
        vies = [
            ViesItem(
                doklad_cislo="FV-2025-010",
                doklad_datum=date(2025, 5, 12),
                partner_nazev="ACME GmbH",
                partner_dic="DE123456789",
                zaklad=Money(50000),
            ),
        ]
        vm = _make_vm(vies=vies)
        page = DphPage(vm)
        qtbot.addWidget(page)
        page._tabs_widget.setCurrentIndex(1)
        # Table not hidden, empty label hidden
        assert page._vies_empty_label_widget.isHidden()
        assert not page._vies_table_widget.isHidden()
        assert page._vies_table_widget.rowCount() == 1
        assert page._vies_table_widget.item(0, 1).text() == "FV-2025-010"
        assert page._vies_table_widget.item(0, 2).text() == "DE123456789"


class TestDphPageKontrolniHlaseni:

    def test_kh_tab_has_blocking_text(self, qtbot):
        """KH záložka musí obsahovat text vysvětlující, že KH se nepodává."""
        vm = _make_vm()
        page = DphPage(vm)
        qtbot.addWidget(page)
        kh_widget = page._tabs_widget.widget(2)
        from PyQt6.QtWidgets import QLabel
        labels = kh_widget.findChildren(QLabel)
        text_combined = " ".join(lbl.text() for lbl in labels)
        assert "NEPODÁVÁ" in text_combined
        assert "identifikovaná osoba" in text_combined.lower()
