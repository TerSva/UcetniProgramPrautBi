"""Testy pro BankovniVypis entity."""

from __future__ import annotations

import pytest

from domain.banka.bankovni_vypis import BankovniVypis
from domain.shared.errors import ValidationError
from domain.shared.money import Money


def _make_vypis(**kwargs) -> BankovniVypis:
    defaults = dict(
        bankovni_ucet_id=1,
        rok=2025,
        mesic=3,
        pocatecni_stav=Money(100_000_00),
        konecny_stav=Money(120_000_00),
        pdf_path="/uploads/banka/221_001_2025_03.pdf",
        bv_doklad_id=1,
    )
    defaults.update(kwargs)
    return BankovniVypis(**defaults)


class TestBankovniVypis:

    def test_create_valid(self):
        v = _make_vypis()
        assert v.rok == 2025
        assert v.mesic == 3
        assert v.pocatecni_stav == Money(100_000_00)

    def test_mesic_below_1_raises(self):
        with pytest.raises(ValidationError, match="1–12"):
            _make_vypis(mesic=0)

    def test_mesic_above_12_raises(self):
        with pytest.raises(ValidationError, match="1–12"):
            _make_vypis(mesic=13)

    def test_rok_below_2000_raises(self):
        with pytest.raises(ValidationError, match="rok"):
            _make_vypis(rok=1999)

    def test_rok_above_2099_raises(self):
        with pytest.raises(ValidationError, match="rok"):
            _make_vypis(rok=2100)

    def test_empty_pdf_path_raises(self):
        with pytest.raises(ValidationError, match="PDF"):
            _make_vypis(pdf_path="")
