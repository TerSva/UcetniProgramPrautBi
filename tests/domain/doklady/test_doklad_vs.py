"""Testy pro variabilní symbol na Doklad entitě — pure Python, bez DB."""

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.errors import ValidationError
from domain.shared.money import Money


def _doklad(**kwargs) -> Doklad:
    """Helper: vytvoří validní doklad s defaulty."""
    defaults = dict(
        cislo="FV-2026-001",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 1, 15),
        castka_celkem=Money(100000),
    )
    defaults.update(kwargs)
    return Doklad(**defaults)


class TestVSKonstruktor:

    def test_none_default(self):
        d = _doklad()
        assert d.variabilni_symbol is None

    def test_validni_vs(self):
        d = _doklad(variabilni_symbol="20250044")
        assert d.variabilni_symbol == "20250044"

    def test_jednociferne(self):
        d = _doklad(variabilni_symbol="1")
        assert d.variabilni_symbol == "1"

    def test_max_10_cislic(self):
        d = _doklad(variabilni_symbol="1234567890")
        assert d.variabilni_symbol == "1234567890"

    def test_11_cislic_raises(self):
        with pytest.raises(ValidationError, match="max 10"):
            _doklad(variabilni_symbol="12345678901")

    def test_pismena_raises(self):
        with pytest.raises(ValidationError, match="pouze číslice"):
            _doklad(variabilni_symbol="ABC123")

    def test_pomlcka_raises(self):
        with pytest.raises(ValidationError, match="pouze číslice"):
            _doklad(variabilni_symbol="2025-0044")

    def test_mezery_raises(self):
        with pytest.raises(ValidationError, match="pouze číslice"):
            _doklad(variabilni_symbol="2025 0044")

    def test_prazdny_retezec_raises(self):
        with pytest.raises(ValidationError, match="pouze číslice"):
            _doklad(variabilni_symbol="")

    def test_none_explicitni(self):
        d = _doklad(variabilni_symbol=None)
        assert d.variabilni_symbol is None


class TestVSSKombinace:

    def test_vs_s_k_doreseni(self):
        d = _doklad(variabilni_symbol="123456", k_doreseni=True)
        assert d.variabilni_symbol == "123456"
        assert d.k_doreseni is True

    def test_vs_s_partnerem(self):
        d = _doklad(variabilni_symbol="999", partner_id=5)
        assert d.variabilni_symbol == "999"
        assert d.partner_id == 5

    def test_vs_vsechny_typy_dokladu(self):
        for typ in TypDokladu:
            kwargs = {"typ": typ, "variabilni_symbol": "42"}
            # ZF vyžaduje je_vystavena
            if typ == TypDokladu.ZALOHA_FAKTURA:
                kwargs["je_vystavena"] = True
            d = _doklad(**kwargs)
            assert d.variabilni_symbol == "42"
