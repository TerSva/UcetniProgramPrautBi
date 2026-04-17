"""Testy pro InvoiceParser — parsování českých faktur z OCR textu."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from domain.doklady.typy import Mena, TypDokladu
from domain.shared.money import Money
from infrastructure.ocr.invoice_parser import InvoiceParser, ParsedInvoice


@pytest.fixture
def parser() -> InvoiceParser:
    return InvoiceParser()


# ── Meta Platforms ──

META_TEXT = """
Meta Platforms Ireland Limited
4 Grand Canal Square, Grand Canal Harbour
Dublin 2, Ireland

Tax Identification: IE9692928F

Invoice: FBADS-404-12345
Date: 23.04.2025

Advertiser: PRAUT s.r.o.
Martin Švanda

Total: 44,00 CZK
"""


def test_parse_meta(parser):
    result = parser.parse(META_TEXT)
    assert result.typ_dokladu == TypDokladu.FAKTURA_PRIJATA
    assert result.dodavatel_nazev == "Meta Platforms Ireland Limited"
    assert result.dodavatel_dic == "IE9692928F"
    assert result.cislo_dokladu == "FBADS-404-12345"
    assert result.datum_vystaveni == date(2025, 4, 23)
    assert result.castka_celkem == Money(4400)
    assert result.is_reverse_charge is True


def test_parse_meta_detects_pytlovani(parser):
    result = parser.parse(META_TEXT)
    assert result.is_pytlovani is True
    assert result.pytlovani_jmeno == "Martin Švanda"


# ── iStyle ──

ISTYLE_TEXT = """
iStyle CZ, s.r.o.
IČ: 27583368
DIČ: CZ27583368

Faktura č. FA-2025-001
Datum vystavení: 28.03.2025
Datum splatnosti: 11.04.2025

Odběratel:
Martin Švanda
Tršnice 36, 35134 Skalná

MacBook Pro 16" M4 Max
Celkem: 79 990,00 Kč
"""


def test_parse_istyle(parser):
    result = parser.parse(ISTYLE_TEXT)
    assert result.typ_dokladu == TypDokladu.FAKTURA_PRIJATA
    assert result.dodavatel_nazev == "iStyle CZ, s.r.o."
    assert result.dodavatel_ico == "27583368"
    assert result.dodavatel_dic == "CZ27583368"
    assert result.datum_vystaveni == date(2025, 3, 28)
    assert result.castka_celkem == Money(7999000)


def test_parse_istyle_detects_pytlovani(parser):
    result = parser.parse(ISTYLE_TEXT)
    assert result.is_pytlovani is True
    assert result.pytlovani_jmeno == "Martin Švanda"


# ── Generic CZ ──

GENERIC_CZ_TEXT = """
Firma XYZ s.r.o.
IČO: 12345678
DIČ: CZ12345678

Faktura číslo: FV-2025-042
Datum: 15.05.2025
VS: 2025042

Odběratel: PRAUT s.r.o.
IČ: 22545107

Celkem: 1 500,00 Kč
"""


def test_parse_generic_cz(parser):
    result = parser.parse(GENERIC_CZ_TEXT)
    assert result.dodavatel_ico == "12345678"
    assert result.dodavatel_dic == "CZ12345678"
    assert result.cislo_dokladu == "FV-2025-042"
    assert result.datum_vystaveni == date(2025, 5, 15)
    assert result.castka_celkem == Money(150000)
    assert result.typ_dokladu == TypDokladu.FAKTURA_PRIJATA


def test_parse_generic_no_pytlovani(parser):
    result = parser.parse(GENERIC_CZ_TEXT)
    assert result.is_pytlovani is False


# ── Empty text ──

def test_parse_empty(parser):
    result = parser.parse("")
    assert result.typ_dokladu is None
    assert result.castka_celkem is None


# ── Serialization ──

def test_to_dict_and_from_dict():
    original = ParsedInvoice(
        typ_dokladu=TypDokladu.FAKTURA_PRIJATA,
        dodavatel_nazev="Meta Platforms Ireland Limited",
        dodavatel_dic="IE9692928F",
        cislo_dokladu="FBADS-404-12345",
        datum_vystaveni=date(2025, 4, 23),
        castka_celkem=Money(4400),
        is_reverse_charge=True,
        is_pytlovani=True,
        pytlovani_jmeno="Martin Švanda",
    )
    d = original.to_dict()
    restored = ParsedInvoice.from_dict(d)
    assert restored.typ_dokladu == original.typ_dokladu
    assert restored.dodavatel_nazev == original.dodavatel_nazev
    assert restored.castka_celkem == original.castka_celkem
    assert restored.is_reverse_charge is True
    assert restored.is_pytlovani is True
    assert restored.pytlovani_jmeno == "Martin Švanda"


def test_from_dict_empty():
    restored = ParsedInvoice.from_dict({})
    assert restored.typ_dokladu is None
    assert restored.mena == Mena.CZK
