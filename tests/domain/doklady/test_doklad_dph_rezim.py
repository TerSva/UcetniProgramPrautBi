"""Testy pro DPH režim na Doklad entitě — pure Python, bez DB."""

from datetime import date

from domain.doklady.doklad import Doklad
from domain.doklady.typy import DphRezim, TypDokladu
from domain.shared.money import Money


def _doklad(**kwargs) -> Doklad:
    defaults = dict(
        cislo="FP-2025-001",
        typ=TypDokladu.FAKTURA_PRIJATA,
        datum_vystaveni=date(2025, 4, 23),
        castka_celkem=Money(4400),
    )
    defaults.update(kwargs)
    return Doklad(**defaults)


class TestDphRezim:

    def test_default_je_tuzemsko(self):
        d = _doklad()
        assert d.dph_rezim == DphRezim.TUZEMSKO

    def test_reverse_charge(self):
        d = _doklad(dph_rezim=DphRezim.REVERSE_CHARGE)
        assert d.dph_rezim == DphRezim.REVERSE_CHARGE

    def test_osvobozeno(self):
        d = _doklad(dph_rezim=DphRezim.OSVOBOZENO)
        assert d.dph_rezim == DphRezim.OSVOBOZENO

    def test_mimo_dph(self):
        d = _doklad(dph_rezim=DphRezim.MIMO_DPH)
        assert d.dph_rezim == DphRezim.MIMO_DPH

    def test_rc_s_variabilnim_symbolem(self):
        d = _doklad(
            dph_rezim=DphRezim.REVERSE_CHARGE,
            variabilni_symbol="104441208",
        )
        assert d.dph_rezim == DphRezim.REVERSE_CHARGE
        assert d.variabilni_symbol == "104441208"
