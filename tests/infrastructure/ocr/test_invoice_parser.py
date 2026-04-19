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
    assert result.variabilni_symbol == "12345"


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


# ── Meta VS extraction ──


class TestMetaVSExtraction:
    """VS z FBADS čísla — poslední číselný blok, max 10 číslic."""

    def test_standard_fbads(self, parser):
        text = "Meta Platforms\nFBADS-404-104441208\nTotal: 50,00 CZK"
        result = parser.parse(text)
        assert result.variabilni_symbol == "104441208"

    def test_long_last_block_truncated(self, parser):
        text = "Meta Platforms\nFBADS-001-99999999999\nTotal: 10,00 CZK"
        result = parser.parse(text)
        assert result.variabilni_symbol == "9999999999"

    def test_single_block(self, parser):
        """FBADS s jedním blokem (NNN-NNNNN) — VS = poslední blok."""
        text = "Meta Platforms\nFBADS-001-12345\nTotal: 10,00 CZK"
        result = parser.parse(text)
        assert result.variabilni_symbol == "12345"

    def test_no_fbads_no_vs(self, parser):
        text = "Meta Platforms\nInvoice something\nTotal: 10,00 CZK"
        result = parser.parse(text)
        assert result.variabilni_symbol is None


# ── Meta castka fallback ──


class TestMetaCastkaFallback:
    """Meta faktury s „Zaplaceno" / „ve výši" vzorem."""

    def test_ve_vysi_pattern(self, parser):
        text = (
            "Meta Platforms\nFBADS-404-123\n"
            "dosáhli jste limitu ve výši 44,00 Kč.\n"
        )
        result = parser.parse(text)
        assert result.castka_celkem == Money(4400)

    def test_bare_kc_pattern(self, parser):
        text = (
            "Meta Platforms\nFBADS-404-123\n"
            "Kampaň reklama\n44,00 Kč\n"
        )
        result = parser.parse(text)
        assert result.castka_celkem == Money(4400)


# ── Meta real PDF ──


class TestMetaRealPDF:
    """Test s reálným Meta PDF z OCR inboxu."""

    @pytest.fixture
    def meta_parsed(self, parser):
        from pathlib import Path
        from infrastructure.ocr.ocr_engine import OcrEngine
        pdf = Path(__file__).resolve().parent.parent.parent / "fixtures" / "ocr" / "meta_sample.pdf"
        if not pdf.exists():
            pytest.skip("Meta sample PDF not found")
        engine = OcrEngine()
        result = engine.extract_text(pdf)
        return parser.parse(result.text)

    def test_dodavatel(self, meta_parsed):
        assert meta_parsed.dodavatel_nazev == "Meta Platforms Ireland Limited"

    def test_cislo(self, meta_parsed):
        assert meta_parsed.cislo_dokladu == "FBADS-404-104441208"

    def test_castka(self, meta_parsed):
        assert meta_parsed.castka_celkem == Money(4400)

    def test_mena(self, meta_parsed):
        assert meta_parsed.mena == Mena.CZK

    def test_datum(self, meta_parsed):
        assert meta_parsed.datum_vystaveni == date(2025, 4, 23)

    def test_vs(self, meta_parsed):
        assert meta_parsed.variabilni_symbol == "104441208"

    def test_reverse_charge(self, meta_parsed):
        assert meta_parsed.is_reverse_charge is True
