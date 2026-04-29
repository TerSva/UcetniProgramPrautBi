"""Testy DphDetailDialog — řádky EPO + clipboard + transakce."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from domain.shared.money import Money
from services.queries.dph_prehled import (
    DphMesicItem,
    DphPriznaniRadky,
    DphTransakceItem,
)
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


def _make_priznani(transakce=None):
    if transakce is None:
        transakce = _make_transakce()
    return DphPriznaniRadky.from_transakce(2025, 4, transakce)


class TestDphDetailDialog:

    def test_transakce_table_rows(self, qtbot):
        vm = _make_vm()
        transakce = _make_transakce()
        d = DphDetailDialog(
            vm, 4, _make_mesic_item(), transakce, _make_priznani(transakce),
        )
        qtbot.addWidget(d)
        # 2 transakce + 1 CELKEM
        assert d._transakce_table_widget.rowCount() == 3
        assert d._transakce_table_widget.item(2, 0).text() == "CELKEM"

    def test_epo_table_eleven_rows(self, qtbot):
        """Tabulka EPO musí mít přesně 11 řádků (ř. 7, 9, 10, 11, 43, 44,
        47, 48, 62, 64, 66)."""
        vm = _make_vm()
        d = DphDetailDialog(
            vm, 4, _make_mesic_item(), _make_transakce(), _make_priznani(),
        )
        qtbot.addWidget(d)
        assert d._epo_table_widget.rowCount() == 11

    def test_epo_clipboard_format_lines(self, qtbot):
        """Clipboard text musí mít formát 'Řádek X: Y' na samostatných řádcích."""
        vm = _make_vm()
        d = DphDetailDialog(
            vm, 4, _make_mesic_item(), _make_transakce(), _make_priznani(),
        )
        qtbot.addWidget(d)
        text = d._epo_clipboard_text()
        assert "Řádek 9: 88" in text  # 4400+4400 hal = 88 Kč
        assert "Řádek 10: 88" in text
        assert "Řádek 43: 88" in text
        assert "Řádek 44: 18" in text  # 924+924 hal = 18.48 → 18 Kč
        assert "Řádek 62: 18" in text
        # Ř. 64 a 66 vždy zobrazené
        assert "Řádek 64: 0" in text
        assert "Řádek 66: 18" in text

    def test_podano_checkbox(self, qtbot):
        vm = _make_vm()
        d = DphDetailDialog(
            vm, 4, _make_mesic_item(je_podane=True), _make_transakce(),
            _make_priznani(),
        )
        qtbot.addWidget(d)
        assert d._podano_check_widget.isChecked()
