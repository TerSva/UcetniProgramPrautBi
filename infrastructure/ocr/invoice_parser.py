"""InvoiceParser — parsuje OCR text do strukturovaných dat české faktury.

Specifické parsery pro Meta Platforms, iStyle a Google.
Generický parser pro české faktury (IČO, DIČ, částky, datum).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from domain.doklady.typy import Mena, TypDokladu
from domain.shared.money import Money


@dataclass(frozen=True)
class ParsedInvoice:
    """Výsledek parsování faktury z OCR textu."""

    typ_dokladu: TypDokladu | None = None
    dodavatel_nazev: str | None = None
    dodavatel_ico: str | None = None
    dodavatel_dic: str | None = None
    odberatel_nazev: str | None = None
    odberatel_ico: str | None = None
    cislo_dokladu: str | None = None
    datum_vystaveni: date | None = None
    datum_uzp: date | None = None
    datum_splatnosti: date | None = None
    castka_celkem: Money | None = None
    castka_bez_dph: Money | None = None
    dph_castka: Money | None = None
    dph_sazba: Decimal | None = None
    mena: Mena = Mena.CZK
    castka_mena: Money | None = None
    kurz: Decimal | None = None
    is_reverse_charge: bool = False
    is_pytlovani: bool = False
    pytlovani_jmeno: str | None = None
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializace pro uložení do DB jako JSON."""
        d: dict[str, Any] = {}
        if self.typ_dokladu:
            d["typ_dokladu"] = self.typ_dokladu.value
        if self.dodavatel_nazev:
            d["dodavatel_nazev"] = self.dodavatel_nazev
        if self.dodavatel_ico:
            d["dodavatel_ico"] = self.dodavatel_ico
        if self.dodavatel_dic:
            d["dodavatel_dic"] = self.dodavatel_dic
        if self.odberatel_nazev:
            d["odberatel_nazev"] = self.odberatel_nazev
        if self.odberatel_ico:
            d["odberatel_ico"] = self.odberatel_ico
        if self.cislo_dokladu:
            d["cislo_dokladu"] = self.cislo_dokladu
        if self.datum_vystaveni:
            d["datum_vystaveni"] = self.datum_vystaveni.isoformat()
        if self.datum_uzp:
            d["datum_uzp"] = self.datum_uzp.isoformat()
        if self.datum_splatnosti:
            d["datum_splatnosti"] = self.datum_splatnosti.isoformat()
        if self.castka_celkem:
            d["castka_celkem"] = self.castka_celkem.to_halire()
        if self.castka_bez_dph:
            d["castka_bez_dph"] = self.castka_bez_dph.to_halire()
        if self.dph_castka:
            d["dph_castka"] = self.dph_castka.to_halire()
        if self.dph_sazba is not None:
            d["dph_sazba"] = str(self.dph_sazba)
        d["mena"] = self.mena.value
        if self.castka_mena:
            d["castka_mena"] = self.castka_mena.to_halire()
        if self.kurz is not None:
            d["kurz"] = str(self.kurz)
        d["is_reverse_charge"] = self.is_reverse_charge
        d["is_pytlovani"] = self.is_pytlovani
        if self.pytlovani_jmeno:
            d["pytlovani_jmeno"] = self.pytlovani_jmeno
        return d

    @staticmethod
    def from_dict(d: dict[str, Any], raw_text: str = "") -> ParsedInvoice:
        """Deserializace z DB JSON."""
        typ = None
        if "typ_dokladu" in d:
            try:
                typ = TypDokladu(d["typ_dokladu"])
            except ValueError:
                pass

        castka_celkem = Money(d["castka_celkem"]) if d.get("castka_celkem") else None
        castka_bez_dph = Money(d["castka_bez_dph"]) if d.get("castka_bez_dph") else None
        dph_castka = Money(d["dph_castka"]) if d.get("dph_castka") else None
        castka_mena = Money(d["castka_mena"]) if d.get("castka_mena") else None

        dph_sazba = None
        if d.get("dph_sazba"):
            try:
                dph_sazba = Decimal(d["dph_sazba"])
            except (InvalidOperation, ValueError):
                pass

        kurz = None
        if d.get("kurz"):
            try:
                kurz = Decimal(d["kurz"])
            except (InvalidOperation, ValueError):
                pass

        mena = Mena.CZK
        if d.get("mena"):
            try:
                mena = Mena(d["mena"])
            except ValueError:
                pass

        datum_vystaveni = None
        if d.get("datum_vystaveni"):
            try:
                datum_vystaveni = date.fromisoformat(d["datum_vystaveni"])
            except ValueError:
                pass

        datum_uzp = None
        if d.get("datum_uzp"):
            try:
                datum_uzp = date.fromisoformat(d["datum_uzp"])
            except ValueError:
                pass

        datum_splatnosti = None
        if d.get("datum_splatnosti"):
            try:
                datum_splatnosti = date.fromisoformat(d["datum_splatnosti"])
            except ValueError:
                pass

        return ParsedInvoice(
            typ_dokladu=typ,
            dodavatel_nazev=d.get("dodavatel_nazev"),
            dodavatel_ico=d.get("dodavatel_ico"),
            dodavatel_dic=d.get("dodavatel_dic"),
            odberatel_nazev=d.get("odberatel_nazev"),
            odberatel_ico=d.get("odberatel_ico"),
            cislo_dokladu=d.get("cislo_dokladu"),
            datum_vystaveni=datum_vystaveni,
            datum_uzp=datum_uzp,
            datum_splatnosti=datum_splatnosti,
            castka_celkem=castka_celkem,
            castka_bez_dph=castka_bez_dph,
            dph_castka=dph_castka,
            dph_sazba=dph_sazba,
            mena=mena,
            castka_mena=castka_mena,
            kurz=kurz,
            is_reverse_charge=d.get("is_reverse_charge", False),
            is_pytlovani=d.get("is_pytlovani", False),
            pytlovani_jmeno=d.get("pytlovani_jmeno"),
            raw_text=raw_text,
        )


# ── Regex patterns ──

_ICO_RE = re.compile(r"IČ[O]?\s*:?\s*(\d{8})", re.IGNORECASE)
_DIC_RE = re.compile(r"DIČ\s*:?\s*(CZ\d{8,10}|[A-Z]{2}\d{6,10}\w*)", re.IGNORECASE)
_VS_RE = re.compile(r"(?:VS|Variabilní\s+symbol|var\.?\s*sym\.?)\s*:?\s*(\d{4,20})", re.IGNORECASE)
_CISLO_FV_RE = re.compile(
    r"(?:Číslo\s+faktury|Faktura\s+(?:č(?:íslo)?\.?)|Invoice\s+No\.?|Invoice\s+number|Invoice)\s*:?\s*([A-Za-z0-9\-/]+)",
    re.IGNORECASE,
)
_FBADS_RE = re.compile(r"FBADS-\d{3}-\d{5,}", re.IGNORECASE)
_DATE_CZ_RE = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})")
_DATE_ISO_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_CASTKA_CZ_RE = re.compile(
    r"(?:Celkem|Total|K úhradě|Amount due|Částka)\s*:?\s*"
    r"([\d\s,.]+)\s*(?:Kč|CZK|EUR|USD)?",
    re.IGNORECASE,
)
_CASTKA_EUR_RE = re.compile(
    r"(?:Total|Amount|Celkem)\s*:?\s*€?\s*([\d\s,.]+)\s*(?:EUR)?",
    re.IGNORECASE,
)

# Společníci PRAUT s.r.o. — pro detekci pytlování
_PRAUT_ICO = "22545107"
_SPOLECNICI = ["Martin Švanda", "Tomáš Hůf"]


class InvoiceParser:
    """Parsuje text z OCR do strukturovaných dat."""

    def parse(self, text: str) -> ParsedInvoice:
        """Hlavní parsovací metoda — detekuje formát a parsuje."""
        if not text or not text.strip():
            return ParsedInvoice(raw_text=text)

        # Specifické formáty
        if "FBADS-" in text or "Meta Platforms" in text:
            return self._parse_meta(text)
        if "Google" in text and ("Ireland" in text or "Google Ads" in text):
            return self._parse_google(text)
        if "iStyle" in text or "27583368" in text:
            return self._parse_istyle(text)

        # Generický český parser
        return self._parse_generic_cz(text)

    def _parse_meta(self, text: str) -> ParsedInvoice:
        """Meta/Facebook Ads invoices."""
        cislo = None
        m = _FBADS_RE.search(text)
        if m:
            cislo = m.group(0)

        datum = self._extract_first_date(text)
        castka = self._extract_castka(text)

        # Meta faktury z EU jsou reverse charge
        dic = self._extract_dic(text)

        # Detekce měny
        mena = Mena.CZK
        castka_mena = None
        if "EUR" in text or "€" in text:
            mena = Mena.EUR
            castka_mena = castka
        if "USD" in text or "$" in text:
            mena = Mena.USD
            castka_mena = castka

        # Detekce pytlování — faktura na společníka
        is_pytlovani, pytl_jmeno = self._detect_pytlovani(text)

        return ParsedInvoice(
            typ_dokladu=TypDokladu.FAKTURA_PRIJATA,
            dodavatel_nazev="Meta Platforms Ireland Limited",
            dodavatel_dic=dic or "IE9692928F",
            cislo_dokladu=cislo,
            datum_vystaveni=datum,
            castka_celkem=castka,
            mena=mena,
            castka_mena=castka_mena,
            is_reverse_charge=True,
            is_pytlovani=is_pytlovani,
            pytlovani_jmeno=pytl_jmeno,
            raw_text=text,
        )

    def _parse_google(self, text: str) -> ParsedInvoice:
        """Google Ads invoices."""
        cislo_m = _CISLO_FV_RE.search(text)
        cislo = cislo_m.group(1) if cislo_m else None

        datum = self._extract_first_date(text)
        castka = self._extract_castka(text)
        dic = self._extract_dic(text)

        is_pytlovani, pytl_jmeno = self._detect_pytlovani(text)

        return ParsedInvoice(
            typ_dokladu=TypDokladu.FAKTURA_PRIJATA,
            dodavatel_nazev="Google Ireland Limited",
            dodavatel_dic=dic or "IE6388047V",
            cislo_dokladu=cislo,
            datum_vystaveni=datum,
            castka_celkem=castka,
            is_reverse_charge=True,
            is_pytlovani=is_pytlovani,
            pytlovani_jmeno=pytl_jmeno,
            raw_text=text,
        )

    def _parse_istyle(self, text: str) -> ParsedInvoice:
        """iStyle CZ faktury."""
        ico = "27583368"
        dic = self._extract_dic(text) or "CZ27583368"
        cislo_m = _CISLO_FV_RE.search(text)
        cislo = cislo_m.group(1) if cislo_m else self._extract_vs(text)

        datum = self._extract_first_date(text)
        castka = self._extract_castka(text)

        is_pytlovani, pytl_jmeno = self._detect_pytlovani(text)

        return ParsedInvoice(
            typ_dokladu=TypDokladu.FAKTURA_PRIJATA,
            dodavatel_nazev="iStyle CZ, s.r.o.",
            dodavatel_ico=ico,
            dodavatel_dic=dic,
            cislo_dokladu=cislo,
            datum_vystaveni=datum,
            castka_celkem=castka,
            is_pytlovani=is_pytlovani,
            pytlovani_jmeno=pytl_jmeno,
            raw_text=text,
        )

    def _parse_generic_cz(self, text: str) -> ParsedInvoice:
        """Obecný parser pro české faktury."""
        ico = self._extract_ico(text)
        dic = self._extract_dic(text)
        cislo = self._extract_cislo_faktury(text) or self._extract_vs(text)
        datum = self._extract_first_date(text)
        castka = self._extract_castka(text)

        # Heuristika pro typ dokladu
        typ = None
        text_lower = text.lower()
        if "faktura" in text_lower or "invoice" in text_lower:
            # Pokud odběratel je PRAUT → FP, jinak FV
            if _PRAUT_ICO in text:
                typ = TypDokladu.FAKTURA_PRIJATA
            else:
                typ = TypDokladu.FAKTURA_VYDANA

        is_pytlovani, pytl_jmeno = self._detect_pytlovani(text)

        return ParsedInvoice(
            typ_dokladu=typ,
            dodavatel_ico=ico,
            dodavatel_dic=dic,
            cislo_dokladu=cislo,
            datum_vystaveni=datum,
            castka_celkem=castka,
            is_pytlovani=is_pytlovani,
            pytlovani_jmeno=pytl_jmeno,
            raw_text=text,
        )

    # ── Extraction helpers ──

    def _extract_ico(self, text: str) -> str | None:
        m = _ICO_RE.search(text)
        return m.group(1) if m else None

    def _extract_dic(self, text: str) -> str | None:
        m = _DIC_RE.search(text)
        return m.group(1) if m else None

    def _extract_vs(self, text: str) -> str | None:
        m = _VS_RE.search(text)
        return m.group(1) if m else None

    def _extract_cislo_faktury(self, text: str) -> str | None:
        m = _CISLO_FV_RE.search(text)
        return m.group(1) if m else None

    def _extract_first_date(self, text: str) -> date | None:
        """Extrahuje první rozpoznané datum z textu."""
        # CZ formát: dd.mm.yyyy
        m = _DATE_CZ_RE.search(text)
        if m:
            try:
                return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass
        # ISO formát: yyyy-mm-dd
        m = _DATE_ISO_RE.search(text)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        return None

    def _extract_castka(self, text: str) -> Money | None:
        """Extrahuje částku z textu."""
        for pattern in (_CASTKA_CZ_RE, _CASTKA_EUR_RE):
            m = pattern.search(text)
            if m:
                raw = m.group(1).strip()
                return self._parse_money(raw)
        return None

    @staticmethod
    def _parse_money(raw: str) -> Money | None:
        """Parsuje textovou částku na Money."""
        normalized = raw.replace(" ", "").replace("\u00A0", "")
        normalized = normalized.replace(",", ".")
        # Pokud je více teček (tisícové oddělovače), nech jen poslední
        parts = normalized.split(".")
        if len(parts) > 2:
            normalized = "".join(parts[:-1]) + "." + parts[-1]
        try:
            dec = Decimal(normalized)
            return Money.from_koruny(str(dec))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _detect_pytlovani(text: str) -> tuple[bool, str | None]:
        """Detekce pytlování — faktura vystavená na společníka."""
        text_lower = text.lower()
        for jmeno in _SPOLECNICI:
            if jmeno.lower() in text_lower:
                # Ověř, že odběratel NENÍ PRAUT (IČO firmy)
                # Pokud text obsahuje jméno společníka, je to pytlování
                return True, jmeno
        return False, None
