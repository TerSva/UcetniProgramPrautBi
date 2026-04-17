"""Testy pro domain/firma/firma.py — Firma entita."""

from __future__ import annotations

from datetime import date

import pytest

from domain.firma.firma import Firma
from domain.shared.errors import ValidationError
from domain.shared.money import Money


def test_firma_basic_create():
    f = Firma(nazev="PRAUT s.r.o.")
    assert f.nazev == "PRAUT s.r.o."
    assert f.pravni_forma == "s.r.o."
    assert f.kategorie_uj == "mikro"
    assert f.je_identifikovana_osoba_dph is True
    assert f.je_platce_dph is False


def test_firma_full_create():
    f = Firma(
        nazev="PRAUT s.r.o.",
        ico="22545107",
        dic="CZ22545107",
        sidlo="Tršnice 36, 35134 Skalná",
        pravni_forma="s.r.o.",
        datum_zalozeni=date(2025, 1, 1),
        rok_zacatku_uctovani=2025,
        zakladni_kapital=Money(20000000),
        kategorie_uj="mikro",
        je_identifikovana_osoba_dph=True,
        je_platce_dph=False,
        bankovni_ucet_1="221.001",
        bankovni_ucet_2="221.002",
    )
    assert f.ico == "22545107"
    assert f.zakladni_kapital == Money(20000000)
    assert f.bankovni_ucet_1 == "221.001"


def test_firma_empty_nazev_raises():
    with pytest.raises(ValidationError, match="Název firmy"):
        Firma(nazev="")


def test_firma_whitespace_nazev_raises():
    with pytest.raises(ValidationError, match="Název firmy"):
        Firma(nazev="   ")


def test_firma_invalid_ico_raises():
    with pytest.raises(ValidationError, match="IČO"):
        Firma(nazev="Test", ico="123")


def test_firma_valid_ico():
    f = Firma(nazev="Test", ico="12345678")
    assert f.ico == "12345678"


def test_firma_none_ico_is_ok():
    f = Firma(nazev="Test", ico=None)
    assert f.ico is None
