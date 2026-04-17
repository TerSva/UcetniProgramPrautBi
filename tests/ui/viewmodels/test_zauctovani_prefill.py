"""Testy pre-fill Dal účtu v ZauctovaniViewModel."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from services.queries.doklady_list import DokladyListItem
from domain.ucetnictvi.typy import TypUctu
from services.queries.uctova_osnova import UcetItem
from ui.viewmodels.zauctovani_vm import ZauctovaniViewModel


def _make_item():
    return DokladyListItem(
        id=1, cislo="FP-001", typ=TypDokladu.FAKTURA_PRIJATA,
        datum_vystaveni=date(2026, 4, 10), datum_splatnosti=None,
        partner_id=None, partner_nazev=None,
        castka_celkem=Money(100000), stav=StavDokladu.NOVY,
        k_doreseni=False, poznamka_doreseni=None, popis=None,
    )


def _make_ucty():
    return [
        UcetItem(cislo="321", nazev="Dodavatelé", typ=TypUctu.PASIVA),
        UcetItem(cislo="365.001", nazev="Závazky Martin", typ=TypUctu.PASIVA),
        UcetItem(cislo="518", nazev="Ostatní služby", typ=TypUctu.NAKLADY),
    ]


class TestPrefillDal:

    def test_no_prefill_default(self):
        osnova = MagicMock()
        osnova.execute.return_value = _make_ucty()
        cmd = MagicMock()
        vm = ZauctovaniViewModel(_make_item(), osnova, cmd)
        vm.load()
        assert vm.radky[0].dal_ucet == ""

    def test_prefill_dal_ucet(self):
        osnova = MagicMock()
        osnova.execute.return_value = _make_ucty()
        cmd = MagicMock()
        vm = ZauctovaniViewModel(
            _make_item(), osnova, cmd,
            prefill_dal_ucet="365.001",
        )
        vm.load()
        assert vm.radky[0].dal_ucet == "365.001"
