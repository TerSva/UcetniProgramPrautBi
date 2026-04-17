"""Testy RC checkbox v ZauctovaniDialog."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from domain.ucetnictvi.typy import TypUctu
from services.queries.doklady_list import DokladyListItem
from services.queries.uctova_osnova import UcetItem
from ui.dialogs.zauctovani_dialog import ZauctovaniDialog
from ui.viewmodels.zauctovani_vm import ZauctovaniViewModel


def _make_item(typ=TypDokladu.FAKTURA_PRIJATA):
    return DokladyListItem(
        id=1, cislo="FP-001", typ=typ,
        datum_vystaveni=date(2025, 4, 23), datum_splatnosti=None,
        partner_id=None, partner_nazev=None,
        castka_celkem=Money(4400), stav=StavDokladu.NOVY,
        k_doreseni=False, poznamka_doreseni=None, popis=None,
    )


def _make_ucty():
    return [
        UcetItem(cislo="321", nazev="Dodavatelé", typ=TypUctu.PASIVA),
        UcetItem(cislo="343.100", nazev="DPH vstup", typ=TypUctu.PASIVA),
        UcetItem(cislo="343.200", nazev="DPH výstup", typ=TypUctu.PASIVA),
        UcetItem(cislo="518", nazev="Ostatní služby", typ=TypUctu.NAKLADY),
    ]


def _make_dialog(item=None, qtbot=None):
    osnova = MagicMock()
    osnova.execute.return_value = _make_ucty()
    cmd = MagicMock()
    vm = ZauctovaniViewModel(item or _make_item(), osnova, cmd)
    d = ZauctovaniDialog(vm)
    if qtbot:
        qtbot.addWidget(d)
    return d, vm


class TestRcCheckbox:

    def test_rc_visible_for_fp(self, qtbot):
        d, _ = _make_dialog(qtbot=qtbot)
        assert not d._rc_section_widget.isHidden()

    def test_rc_hidden_for_fv(self, qtbot):
        d, _ = _make_dialog(
            item=_make_item(typ=TypDokladu.FAKTURA_VYDANA), qtbot=qtbot,
        )
        assert d._rc_section_widget.isHidden()

    def test_rc_check_adds_dph_row(self, qtbot):
        d, vm = _make_dialog(qtbot=qtbot)
        assert len(d._rows_list) == 1
        d._rc_check_widget.setChecked(True)
        assert len(d._rows_list) == 2
        assert vm.reverse_charge is True

    def test_rc_uncheck_removes_dph_row(self, qtbot):
        d, vm = _make_dialog(qtbot=qtbot)
        d._rc_check_widget.setChecked(True)
        d._rc_check_widget.setChecked(False)
        assert len(d._rows_list) == 1
        assert vm.reverse_charge is False
