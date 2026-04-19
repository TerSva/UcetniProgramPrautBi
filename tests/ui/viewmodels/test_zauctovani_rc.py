"""Testy reverse charge logiky v ZauctovaniViewModel."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from domain.doklady.typy import DphRezim, StavDokladu, TypDokladu
from domain.shared.money import Money
from domain.ucetnictvi.typy import TypUctu
from services.queries.doklady_list import DokladyListItem
from services.queries.uctova_osnova import UcetItem
from ui.viewmodels.zauctovani_vm import (
    RC_DAL_UCET,
    RC_MD_UCET,
    ZauctovaniViewModel,
)


def _make_item(typ=TypDokladu.FAKTURA_PRIJATA, castka=Money(4400)):
    return DokladyListItem(
        id=1, cislo="FP-001", typ=typ,
        datum_vystaveni=date(2025, 4, 23), datum_splatnosti=None,
        partner_id=None, partner_nazev=None,
        castka_celkem=castka, stav=StavDokladu.NOVY,
        k_doreseni=False, poznamka_doreseni=None, popis=None,
    )


def _make_ucty():
    return [
        UcetItem(cislo="321", nazev="Dodavatelé", typ=TypUctu.PASIVA),
        UcetItem(cislo="343.100", nazev="DPH vstup", typ=TypUctu.PASIVA),
        UcetItem(cislo="343.200", nazev="DPH výstup", typ=TypUctu.PASIVA),
        UcetItem(cislo="518", nazev="Ostatní služby", typ=TypUctu.NAKLADY),
    ]


def _make_vm(item=None):
    osnova = MagicMock()
    osnova.execute.return_value = _make_ucty()
    cmd = MagicMock()
    vm = ZauctovaniViewModel(item or _make_item(), osnova, cmd)
    vm.load()
    return vm


class TestReverseCharge:

    def test_show_rc_only_for_fp(self):
        vm_fp = _make_vm(_make_item(typ=TypDokladu.FAKTURA_PRIJATA))
        assert vm_fp.show_reverse_charge is True

        vm_fv = _make_vm(_make_item(typ=TypDokladu.FAKTURA_VYDANA))
        assert vm_fv.show_reverse_charge is False

        vm_pd = _make_vm(_make_item(typ=TypDokladu.POKLADNI_DOKLAD))
        assert vm_pd.show_reverse_charge is False

    def test_rc_off_by_default(self):
        vm = _make_vm()
        assert vm.reverse_charge is False
        assert len(vm.radky) == 1

    def test_rc_on_adds_dph_row(self):
        vm = _make_vm()
        vm.set_reverse_charge(True)
        assert vm.reverse_charge is True
        assert len(vm.radky) == 2
        dph_row = vm.radky[1]
        assert dph_row.md_ucet == RC_MD_UCET
        assert dph_row.dal_ucet == RC_DAL_UCET
        assert dph_row.popis == "DPH reverse charge"

    def test_rc_off_removes_dph_row(self):
        vm = _make_vm()
        vm.set_reverse_charge(True)
        assert len(vm.radky) == 2
        vm.set_reverse_charge(False)
        assert len(vm.radky) == 1
        assert vm.reverse_charge is False

    def test_dph_calculation_21pct(self):
        # 44 Kč = 4400 haléřů, 21% = 924 haléřů = 9,24 Kč
        vm = _make_vm()
        vm.set_reverse_charge(True)
        assert vm.dph_castka == Money(924)
        assert vm.radky[1].castka == Money(924)

    def test_dph_calculation_different_sazba(self):
        vm = _make_vm()
        vm.set_reverse_charge(True)
        vm.set_dph_sazba(Decimal("15"))
        # 4400 * 15 / 100 = 660
        assert vm.dph_castka == Money(660)
        assert vm.radky[1].castka == Money(660)

    def test_dph_row_excluded_from_rozdil(self):
        vm = _make_vm()
        vm.update_row(0, md_ucet="518", dal_ucet="321", castka=Money(4400))
        assert vm.je_podvojne is True
        vm.set_reverse_charge(True)
        # DPH row adds 924, but rozdil should still be 0
        assert vm.rozdil == Money.zero()
        assert vm.je_podvojne is True
        assert vm.soucet_radku == Money(4400 + 924)
        assert vm.soucet_zakladnich == Money(4400)


class TestRCAutoPrefill:
    """Auto-prefill pro doklady s dph_rezim=REVERSE_CHARGE."""

    def test_rc_doklad_prefills_4_rows(self):
        """RC doklad → load() vytvoří 2 řádky: základ + DPH."""
        item = _make_item()
        # Replace with RC version
        item = DokladyListItem(
            id=1, cislo="FP-001", typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2025, 4, 23), datum_splatnosti=None,
            partner_id=None, partner_nazev=None,
            castka_celkem=Money(4400), stav=StavDokladu.NOVY,
            k_doreseni=False, poznamka_doreseni=None, popis=None,
            dph_rezim=DphRezim.REVERSE_CHARGE,
        )
        osnova = MagicMock()
        osnova.execute.return_value = _make_ucty()
        cmd = MagicMock()
        vm = ZauctovaniViewModel(item, osnova, cmd)
        vm.load()

        assert len(vm.radky) == 2
        # Základ: MD 518.200 / Dal 321.002
        assert vm.radky[0].md_ucet == "518.200"
        assert vm.radky[0].dal_ucet == "321.002"
        assert vm.radky[0].castka == Money(4400)
        # DPH: MD 343.100 / Dal 343.200
        assert vm.radky[1].md_ucet == RC_MD_UCET
        assert vm.radky[1].dal_ucet == RC_DAL_UCET
        assert vm.radky[1].castka == Money(924)  # 21% z 4400
        # RC flag je zapnutý
        assert vm.reverse_charge is True

    def test_tuzemsko_doklad_no_prefill(self):
        """TUZEMSKO doklad → standardní 1 řádek."""
        item = _make_item()
        vm = _make_vm(item)
        assert len(vm.radky) == 1
        assert vm.reverse_charge is False

    def test_rc_prefill_je_podvojne(self):
        """RC prefill splňuje podvojnost (základ = castka_celkem)."""
        item = DokladyListItem(
            id=1, cislo="FP-001", typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2025, 4, 23), datum_splatnosti=None,
            partner_id=None, partner_nazev=None,
            castka_celkem=Money(4400), stav=StavDokladu.NOVY,
            k_doreseni=False, poznamka_doreseni=None, popis=None,
            dph_rezim=DphRezim.REVERSE_CHARGE,
        )
        osnova = MagicMock()
        osnova.execute.return_value = _make_ucty()
        cmd = MagicMock()
        vm = ZauctovaniViewModel(item, osnova, cmd)
        vm.load()
        vm.update_row(0, md_ucet="518.200", dal_ucet="321.002")
        assert vm.je_podvojne is True
