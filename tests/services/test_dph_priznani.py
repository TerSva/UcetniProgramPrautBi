"""Testy DphPriznaniRadky — výpočet 11 řádků EPO + zaokrouhlení."""

from datetime import date
from decimal import Decimal

import pytest

from domain.shared.money import Money
from services.queries.dph_prehled import (
    DphPriznaniRadky,
    DphTransakceItem,
)


def _t(zaklad_hal: int, dph_hal: int, sazba: str) -> DphTransakceItem:
    return DphTransakceItem(
        doklad_cislo="FP-X",
        doklad_datum=date(2025, 4, 15),
        partner_nazev="X",
        zaklad=Money(zaklad_hal),
        dph=Money(dph_hal),
        sazba=Decimal(sazba),
    )


class TestDphPriznaniRadky:

    def test_empty_month_all_zero(self):
        p = DphPriznaniRadky.from_transakce(2025, 3, [])
        assert p.radek_9_sluzby_jcs == Money.zero()
        assert p.radek_44_dph_21 == Money.zero()
        assert p.radek_62_celkova_dan == Money.zero()
        assert p.radek_64_odpocet == Money.zero()
        assert p.radek_66_dan_povinnost == Money.zero()

    def test_single_21_pct_transakce(self):
        # 4400 hal základ + 924 hal DPH (21 %)
        p = DphPriznaniRadky.from_transakce(2025, 4, [_t(4400, 924, "21.0")])
        assert p.radek_9_sluzby_jcs == Money(4400)
        assert p.radek_10_sluzby_21 == Money(4400)
        assert p.radek_11_sluzby_12 == Money.zero()
        assert p.radek_43_zaklad_21 == Money(4400)
        assert p.radek_44_dph_21 == Money(924)
        assert p.radek_47_zaklad_12 == Money.zero()
        assert p.radek_48_dph_12 == Money.zero()
        assert p.radek_62_celkova_dan == Money(924)
        assert p.radek_66_dan_povinnost == Money(924)

    def test_mixed_21_and_12_pct(self):
        # 21%: 1000+210, 12%: 500+60
        p = DphPriznaniRadky.from_transakce(2025, 4, [
            _t(100000, 21000, "21.0"),
            _t(50000, 6000, "12.0"),
        ])
        assert p.radek_9_sluzby_jcs == Money(150000)  # součet obou základů
        assert p.radek_10_sluzby_21 == Money(100000)
        assert p.radek_11_sluzby_12 == Money(50000)
        assert p.radek_43_zaklad_21 == Money(100000)
        assert p.radek_44_dph_21 == Money(21000)
        assert p.radek_47_zaklad_12 == Money(50000)
        assert p.radek_48_dph_12 == Money(6000)
        assert p.radek_62_celkova_dan == Money(27000)
        assert p.radek_66_dan_povinnost == Money(27000)

    def test_identifikovana_osoba_nema_odpocet(self):
        """Řádek 64 (odpočet) musí být VŽDY 0 — to je celá podstata
        identifikované osoby (na rozdíl od plátce DPH)."""
        p = DphPriznaniRadky.from_transakce(2025, 4, [_t(100000, 21000, "21.0")])
        assert p.radek_64_odpocet == Money.zero()
        # Daňová povinnost = celková daň − odpočet = celková daň
        assert p.radek_66_dan_povinnost == p.radek_62_celkova_dan

    def test_radek_7_zbozi_vzdy_nula(self):
        """Pro identifikovanou osobu používající jen služby — ř. 7 = 0."""
        p = DphPriznaniRadky.from_transakce(2025, 4, [_t(4400, 924, "21.0")])
        assert p.radek_7_zbozi_jcs == Money.zero()


class TestEpoZaokrouhleni:
    """EPO formulář vyžaduje celé Kč. Test: 18.48 → 18, 18.50 → 19, 18.51 → 19."""

    def test_round_half_up_below_half(self):
        # 1848 hal = 18.48 Kč → 18 Kč
        p = DphPriznaniRadky.from_transakce(2025, 4, [_t(8800, 1848, "21.0")])
        text = p.to_epo_text()
        assert "Řádek 44: 18" in text

    def test_round_half_up_at_half(self):
        # 1850 hal = 18.50 Kč → 19 Kč (ROUND_HALF_UP)
        p = DphPriznaniRadky.from_transakce(2025, 4, [_t(8810, 1850, "21.0")])
        text = p.to_epo_text()
        assert "Řádek 44: 19" in text

    def test_zero_lines_omitted(self):
        """Nulové řádky se v EPO textu vynechají, kromě ř. 64 a 66."""
        p = DphPriznaniRadky.from_transakce(2025, 3, [])
        text = p.to_epo_text()
        # Ř. 7, 9, 10, 11, 43, 44, 47, 48, 62 — vše 0, vynecháno
        assert "Řádek 7" not in text
        assert "Řádek 9" not in text
        assert "Řádek 44" not in text
        # Ř. 64 a 66 vždy
        assert "Řádek 64: 0" in text
        assert "Řádek 66: 0" in text

    def test_only_relevant_lines_for_21pct_only(self):
        """Pokud jen 21% — vynechat 11, 47, 48 (12 % řádky)."""
        p = DphPriznaniRadky.from_transakce(2025, 4, [_t(100000, 21000, "21.0")])
        text = p.to_epo_text()
        assert "Řádek 11" not in text
        assert "Řádek 47" not in text
        assert "Řádek 48" not in text
        assert "Řádek 9" in text
        assert "Řádek 10" in text
        assert "Řádek 44" in text
