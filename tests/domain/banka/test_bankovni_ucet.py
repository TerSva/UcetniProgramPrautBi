"""Testy pro BankovniUcet entity."""

from __future__ import annotations

import pytest

from domain.banka.bankovni_ucet import BankovniUcet, FormatCsv
from domain.doklady.typy import Mena
from domain.shared.errors import ValidationError


class TestBankovniUcet:

    def test_create_valid(self):
        ucet = BankovniUcet(
            nazev="Money Banka",
            cislo_uctu="670100-2213456789/6210",
            ucet_kod="221.001",
            format_csv=FormatCsv.MONEY_BANKA,
        )
        assert ucet.nazev == "Money Banka"
        assert ucet.ucet_kod == "221.001"
        assert ucet.format_csv == FormatCsv.MONEY_BANKA
        assert ucet.mena == Mena.CZK
        assert ucet.je_aktivni is True
        assert ucet.id is None

    def test_empty_nazev_raises(self):
        with pytest.raises(ValidationError, match="Název"):
            BankovniUcet(nazev="", cislo_uctu="123/0100", ucet_kod="221")

    def test_empty_cislo_uctu_raises(self):
        with pytest.raises(ValidationError, match="Číslo"):
            BankovniUcet(nazev="Test", cislo_uctu="", ucet_kod="221")

    def test_empty_ucet_kod_raises(self):
        with pytest.raises(ValidationError, match="Kód"):
            BankovniUcet(nazev="Test", cislo_uctu="123/0100", ucet_kod="")

    def test_format_csv_enum_values(self):
        assert FormatCsv.MONEY_BANKA.value == "money_banka"
        assert FormatCsv.CESKA_SPORITELNA.value == "ceska_sporitelna"
        assert FormatCsv.OBECNY.value == "obecny"
