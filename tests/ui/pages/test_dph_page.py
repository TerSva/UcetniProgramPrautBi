"""Testy DPH stránky."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from domain.shared.money import Money
from services.queries.dph_prehled import DphMesicItem
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


def _make_vm(mesice=None):
    prehled_q = MagicMock()
    detail_q = MagicMock()
    podani_cmd = MagicMock()
    vm = DphViewModel(prehled_q, detail_q, podani_cmd)
    if mesice:
        prehled_q.execute.return_value = mesice
    else:
        prehled_q.execute.return_value = _make_mesice()
    return vm


class TestDphPage:

    def test_empty_year(self, qtbot):
        vm = _make_vm()
        page = DphPage(vm)
        qtbot.addWidget(page)
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
