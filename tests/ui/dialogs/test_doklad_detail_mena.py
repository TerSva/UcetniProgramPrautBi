"""Testy zobrazení cizoměnových údajů v DokladDetailDialog."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from domain.doklady.typy import Mena, StavDokladu, TypDokladu
from domain.shared.money import Money
from services.queries.doklady_list import DokladyListItem
from ui.dialogs.doklad_detail_dialog import DokladDetailDialog
from ui.viewmodels.doklad_detail_vm import DokladDetailViewModel


def _make_item(mena=Mena.CZK, castka_mena=None, kurz=None):
    return DokladyListItem(
        id=1, cislo="FP-2026-001", typ=TypDokladu.FAKTURA_PRIJATA,
        datum_vystaveni=date(2026, 4, 10), datum_splatnosti=None,
        partner_id=None, partner_nazev=None,
        castka_celkem=Money(25100), stav=StavDokladu.NOVY,
        k_doreseni=False, poznamka_doreseni=None, popis=None,
        mena=mena, castka_mena=castka_mena, kurz=kurz,
    )


def _make_vm(item):
    actions = MagicMock()
    return DokladDetailViewModel(item, actions)


class TestDetailMenaDisplay:

    def test_czk_hides_foreign_row(self, qtbot):
        item = _make_item()
        vm = _make_vm(item)
        d = DokladDetailDialog(vm)
        qtbot.addWidget(d)
        assert d._foreign_label.isHidden()
        assert d._foreign_value.isHidden()

    def test_eur_shows_foreign_row(self, qtbot):
        item = _make_item(
            mena=Mena.EUR,
            castka_mena=Money(1000),
            kurz=Decimal("25.10"),
        )
        vm = _make_vm(item)
        d = DokladDetailDialog(vm)
        qtbot.addWidget(d)
        assert not d._foreign_label.isHidden()
        assert not d._foreign_value.isHidden()
        text = d._foreign_value.text()
        assert "EUR" in text
        assert "25" in text
