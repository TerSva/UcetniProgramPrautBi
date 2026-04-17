"""Testy DphDetailDialog."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from domain.shared.money import Money
from services.queries.dph_prehled import DphMesicItem, DphTransakceItem
from ui.dialogs.dph_detail_dialog import DphDetailDialog
from ui.viewmodels.dph_vm import DphViewModel


def _make_vm():
    return DphViewModel(MagicMock(), MagicMock(), MagicMock())


def _make_mesic_item(je_podane=False):
    return DphMesicItem(
        rok=2025, mesic=4,
        zaklad_celkem=Money(105000),
        dph_celkem=Money(22050),
        pocet_transakci=3,
        je_podane=je_podane,
    )


def _make_transakce():
    return [
        DphTransakceItem(
            doklad_cislo="FP-2025-001",
            doklad_datum=date(2025, 4, 10),
            partner_nazev="Meta Platforms",
            zaklad=Money(4400),
            dph=Money(924),
            sazba=Decimal("21.0"),
        ),
        DphTransakceItem(
            doklad_cislo="FP-2025-002",
            doklad_datum=date(2025, 4, 15),
            partner_nazev="Meta Platforms",
            zaklad=Money(4400),
            dph=Money(924),
            sazba=Decimal("21.0"),
        ),
    ]


class TestDphDetailDialog:

    def test_table_rows(self, qtbot):
        vm = _make_vm()
        transakce = _make_transakce()
        d = DphDetailDialog(vm, 4, _make_mesic_item(), transakce)
        qtbot.addWidget(d)
        # 2 transakce + 1 CELKEM row
        assert d._table_widget.rowCount() == 3
        assert d._table_widget.item(2, 0).text() == "CELKEM"

    def test_epo_section(self, qtbot):
        vm = _make_vm()
        transakce = _make_transakce()
        d = DphDetailDialog(vm, 4, _make_mesic_item(), transakce)
        qtbot.addWidget(d)
        text = d._epo_label_widget.text()
        assert "služby z EU" in text
        assert "DPH" in text

    def test_podano_checkbox(self, qtbot):
        vm = _make_vm()
        d = DphDetailDialog(
            vm, 4, _make_mesic_item(je_podane=True), _make_transakce(),
        )
        qtbot.addWidget(d)
        assert d._podano_check_widget.isChecked()
