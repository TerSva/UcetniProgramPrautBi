"""PDF parser pro bankovní výpisy — extrakce PS/KS a transakcí.

Používá pdfplumber pro text-layer extraction. Regex-based parsing
pro bankovní výpisy (MONETA, Česká spořitelna, obecný layout).

Pravidla:
- Transakce začíná řádkem s datem DD.MM.YYYY
- Částka musí být ve formátu s čárkou (X XXX,XX) — NE s tečkou (27.00 EUR)
- Cizoměnové řádky (EUR, USD, KURZ) se přeskakují
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from domain.banka.bankovni_ucet import FormatCsv
from domain.shared.money import Money

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedPdfTransaction:
    """Jedna transakce extrahovaná z PDF výpisu."""

    datum_transakce: date
    datum_zauctovani: date | None
    castka: Money
    variabilni_symbol: str | None
    popis: str | None


@dataclass(frozen=True)
class ParsedStatement:
    """Výsledek parsování PDF bankovního výpisu."""

    pocatecni_stav: Money | None
    konecny_stav: Money | None
    cislo_vypisu: str | None = None
    datum_od: date | None = None
    datum_do: date | None = None
    transakce: list[ParsedPdfTransaction] = field(default_factory=list)
    chyby: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# Regex patterns
# ═══════════════════════════════════════════════════════════════════

# Datum ve formátu dd.mm.yyyy
_DATE_CZ_RE = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})")

# Částka v českém formátu — číslo s ČÁRKOU jako desetinný oddělovač
# Matchuje: -1 500,00 | 25 000,00 | -8 447,00 | 700,21
# Nematchuje: 27.00 (tečka = cizoměnový formát), 25.9337 (kurz)
_CASTKA_CZ_RE = re.compile(
    r"(-)\s*"                           # znaménko mínus (debetní obrat)
    r"(\d{1,3}(?:[\s\u00A0]\d{3})*"     # celá část s tisícovými mezerami
    r",\d{2})"                          # čárka + přesně 2 desetinná místa
    r"(?!\d)"                           # nesmí pokračovat další číslicí
)

# Kreditní částka (bez znaménka)
# Nesmí navazovat na delší číslo (VS, kód transakce) —
# lookbehind: před první cifrou nesmí být cifra ani digit+separator
_CASTKA_KREDIT_RE = re.compile(
    r"(?<!\d)"                          # nesmí předcházet cifra (jinak je to VS)
    r"(?<!\d[.,])"                      # nesmí předcházet digit+separator
    r"(\d{1,3}(?:[\s\u00A0]\d{3})*"     # celá část
    r",\d{2})"                          # čárka + 2 desetinná místa
    r"(?!\d)"                           # nesmí pokračovat další číslicí
)

# Cizoměnové řádky — přeskočit
_CURRENCY_LINE_RE = re.compile(
    r"\b(?:EUR|USD|GBP|CHF|PLN|HUF|SEK|NOK|DKK|CAD|AUD|JPY)\b"
    r"|KURZ\s+\d"
    r"|KI:\s*KURZ"
    r"|Směnný\s+kurz",
    re.IGNORECASE,
)

# PS/KS — různé formáty bankovních výpisů
# Čárka (Moneta): 127 315,91 | -51,48
# Tečka (ČS):     127315.91  | -51.48
_AMOUNT_CZ_PAT = r"[-+]?\s*[\d\s\u00A0]+,\d{2}"
_AMOUNT_DOT_PAT = r"-?\d[\d\s\u00A0]*\.\d{2}"
_PS_LABEL = (
    r"(?:Počáteční\s+zůstatek|Počáteční\s+stav|PS|"
    r"Zůstatek\s+na\s+počátku|Stav\s+na\s+počátku|"
    r"Předchozí\s+zůstatek|Počáteční\s+bilance)"
)
_KS_LABEL = (
    r"(?:Konečný\s+zůstatek|Konečný\s+stav|KS|"
    r"Zůstatek\s+na\s+konci|Stav\s+na\s+konci|"
    r"Nový\s+zůstatek|Konečná\s+bilance)"
)
_PS_PATTERNS = [
    re.compile(rf"{_PS_LABEL}\s*:?\s*({_AMOUNT_CZ_PAT})", re.IGNORECASE),
    re.compile(rf"{_PS_LABEL}\s*:?\s*({_AMOUNT_DOT_PAT})", re.IGNORECASE),
    re.compile(r"PS\s*:?\s*([-+]?\s*[\d\s\u00A0]+,\d{2})(?:\s*Kč|\s*CZK|\s*$)", re.IGNORECASE),
]

_KS_PATTERNS = [
    re.compile(rf"{_KS_LABEL}\s*:?\s*({_AMOUNT_CZ_PAT})", re.IGNORECASE),
    re.compile(rf"{_KS_LABEL}\s*:?\s*({_AMOUNT_DOT_PAT})", re.IGNORECASE),
    re.compile(r"KS\s*:?\s*([-+]?\s*[\d\s\u00A0]+,\d{2})(?:\s*Kč|\s*CZK|\s*$)", re.IGNORECASE),
]

_VS_RE = re.compile(r"VS\s*:?\s*(\d{4,20})", re.IGNORECASE)

# Celkový počet transakcí (validace)
_CELKOVY_POCET_RE = re.compile(
    r"Celkový\s+počet\s+transakcí\s*:\s*(\d+)", re.IGNORECASE,
)

# Metadata výpisu
# Moneta: "Číslo výpisu: 2025/3", ČS: "Číslo výpisu: 001"
_CISLO_VYPISU_RE = re.compile(
    r"Číslo\s+výpisu\s*:\s*(\d{4}/\d+|\d{1,4})", re.IGNORECASE,
)
# Moneta: "Výpis ze dne: 30.04.2025"
_VYPIS_ZE_DNE_RE = re.compile(
    r"Výpis\s+ze\s+dne\s*:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", re.IGNORECASE,
)
# Moneta: "Předchozí výpis ze dne: 31.03.2025"
_PREDCHOZI_VYPIS_RE = re.compile(
    r"Předchozí\s+výpis\s+ze\s+dne\s*:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})",
    re.IGNORECASE,
)
# ČS: "Období: 28.05.2025 - 31.05.2025"
_OBDOBI_RE = re.compile(
    r"Období\s*:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*-\s*(\d{1,2})\.(\d{1,2})\.(\d{4})",
    re.IGNORECASE,
)


class PdfStatementParser:
    """Extrahuje transakce a PS/KS z PDF bankovního výpisu."""

    def parse(
        self, pdf_path: Path, format_banky: FormatCsv,
    ) -> ParsedStatement:
        # ČS má vlastní parser (tabulkový layout)
        if format_banky == FormatCsv.CESKA_SPORITELNA:
            from infrastructure.banka.pdf.cs_parser import CeskaSporitelnaParser
            return CeskaSporitelnaParser().parse(pdf_path)

        if not pdf_path.exists():
            return ParsedStatement(
                pocatecni_stav=None,
                konecny_stav=None,
                chyby=[f"Soubor neexistuje: {pdf_path}"],
            )

        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            return ParsedStatement(
                pocatecni_stav=None,
                konecny_stav=None,
                chyby=["pdfplumber není nainstalován"],
            )

        try:
            text = self._extract_text(pdf_path)
        except Exception as exc:  # noqa: BLE001
            return ParsedStatement(
                pocatecni_stav=None,
                konecny_stav=None,
                chyby=[f"Chyba čtení PDF: {exc}"],
            )

        if not text.strip():
            return ParsedStatement(
                pocatecni_stav=None,
                konecny_stav=None,
                chyby=["PDF neobsahuje žádný text"],
            )

        logger.debug("PDF text (first 2000 chars):\n%s", text[:2000])

        ps = self._extract_stav(text, _PS_PATTERNS)
        ks = self._extract_stav(text, _KS_PATTERNS)

        logger.debug("PS: %s, KS: %s", ps, ks)

        # Metadata výpisu
        cislo_vypisu = self._extract_cislo_vypisu(text)
        datum_od, datum_do = self._extract_obdobi(text)

        transakce = self._extract_transakce(text)

        # Validační kontrola — porovnání s celkovým počtem
        expected_m = _CELKOVY_POCET_RE.search(text)
        chyby: list[str] = []
        if expected_m:
            expected = int(expected_m.group(1))
            actual = len(transakce)
            if actual != expected:
                msg = (
                    f"PDF uvádí {expected} transakcí, parser nalezl {actual}"
                )
                logger.warning(msg)
                chyby.append(msg)

        logger.debug("Nalezeno %d transakcí v PDF", len(transakce))
        for i, tx in enumerate(transakce):
            logger.debug(
                "  TX[%d]: datum=%s castka=%s vs=%s popis=%s",
                i, tx.datum_transakce, tx.castka, tx.variabilni_symbol,
                (tx.popis or "")[:60],
            )

        return ParsedStatement(
            pocatecni_stav=ps,
            konecny_stav=ks,
            cislo_vypisu=cislo_vypisu,
            datum_od=datum_od,
            datum_do=datum_do,
            transakce=transakce,
            chyby=chyby,
        )

    @staticmethod
    def _extract_text(pdf_path: Path) -> str:
        import pdfplumber

        pages_text: list[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
        return "\n".join(pages_text)

    @staticmethod
    def _extract_stav(text: str, patterns: list[re.Pattern]) -> Money | None:
        for pattern in patterns:
            m = pattern.search(text)
            if not m:
                continue
            raw = m.group(1).strip()
            logger.debug("Stav raw match: %r", raw)
            # Normalize: remove spaces, convert comma to dot
            normalized = raw.replace(" ", "").replace("\u00A0", "")
            normalized = normalized.replace(",", ".")
            # Should now be a simple decimal like "127315.91"
            # Remove trailing junk
            normalized = re.sub(r"[^0-9.+-].*$", "", normalized)
            if not normalized:
                continue
            try:
                dec = Decimal(normalized)
                return Money.from_koruny(str(dec))
            except (InvalidOperation, ValueError):
                continue
        return None

    @staticmethod
    def _extract_cislo_vypisu(text: str) -> str | None:
        m = _CISLO_VYPISU_RE.search(text)
        return m.group(1) if m else None

    @staticmethod
    def _extract_obdobi(text: str) -> tuple[date | None, date | None]:
        """Extrahuje datum_od a datum_do z PDF hlavičky.

        Moneta: datum_do = "Výpis ze dne", datum_od = den po "Předchozí výpis ze dne"
        ČS:     "Období: DD.MM.YYYY - DD.MM.YYYY"
        """
        datum_do: date | None = None
        datum_od: date | None = None

        # ČS formát: "Období: 28.05.2025 - 31.05.2025"
        m_obdobi = _OBDOBI_RE.search(text)
        if m_obdobi:
            try:
                datum_od = date(
                    int(m_obdobi.group(3)), int(m_obdobi.group(2)),
                    int(m_obdobi.group(1)),
                )
                datum_do = date(
                    int(m_obdobi.group(6)), int(m_obdobi.group(5)),
                    int(m_obdobi.group(4)),
                )
                return datum_od, datum_do
            except ValueError:
                pass

        # Moneta formát
        m_do = _VYPIS_ZE_DNE_RE.search(text)
        if m_do:
            try:
                datum_do = date(
                    int(m_do.group(3)), int(m_do.group(2)), int(m_do.group(1)),
                )
            except ValueError:
                pass

        m_od = _PREDCHOZI_VYPIS_RE.search(text)
        if m_od:
            try:
                pred = date(
                    int(m_od.group(3)), int(m_od.group(2)), int(m_od.group(1)),
                )
                from datetime import timedelta
                datum_od = pred + timedelta(days=1)
            except ValueError:
                pass

        return datum_od, datum_do

    def _extract_transakce(self, text: str) -> list[ParsedPdfTransaction]:
        """Extrahuje transakce z textu PDF.

        Strategie:
        1. Najdi řádky s datem (dd.mm.yyyy) na začátku
        2. Přeskoč cizoměnové řádky (EUR, USD, KURZ)
        3. Hledej pouze české formáty částek (s čárkou)
        4. Debetní obrat = se znaménkem mínus
        """
        results: list[ParsedPdfTransaction] = []
        lines = text.split("\n")

        for line in lines:
            tx = self._parse_tx_line(line)
            if tx is not None:
                results.append(tx)

        return results

    def _parse_tx_line(self, line: str) -> ParsedPdfTransaction | None:
        # Řádek musí začínat datem
        date_m = _DATE_CZ_RE.match(line.strip())
        if not date_m:
            return None

        try:
            datum = date(
                int(date_m.group(3)),
                int(date_m.group(2)),
                int(date_m.group(1)),
            )
        except ValueError:
            return None

        # Přeskoč cizoměnové řádky
        if _CURRENCY_LINE_RE.search(line):
            logger.debug("Přeskakuji cizoměnový řádek: %s", line.strip()[:80])
            return None

        # Odstraň všechny datumy z řádku, aby se nepletly s částkami
        line_no_dates = _DATE_CZ_RE.sub("", line)

        # Hledej debetní částku (se znaménkem -)
        castka = self._extract_cz_amount(line_no_dates)
        if castka is None:
            return None

        # Odmítni absurdně malé částky (< 1 Kč)
        if abs(castka.to_halire()) < 100:
            logger.debug(
                "Odmítám příliš malou částku %s na řádku: %s",
                castka, line.strip()[:80],
            )
            return None

        # VS
        vs_m = _VS_RE.search(line)
        vs = vs_m.group(1) if vs_m else None

        # Popis — celý řádek
        popis = line.strip()

        return ParsedPdfTransaction(
            datum_transakce=datum,
            datum_zauctovani=None,
            castka=castka,
            variabilni_symbol=vs,
            popis=popis,
        )

    @staticmethod
    def _extract_cz_amount(text: str) -> Money | None:
        """Extrahuje částku v českém formátu (s čárkou).

        Hledá debetní obrat (- X XXX,XX) nebo kreditní (X XXX,XX).
        Ignoruje cizoměnové formáty s tečkou (27.00, 25.9337).
        """
        # Nejprve zkus debetní (záporná)
        debet_m = _CASTKA_CZ_RE.search(text)
        if debet_m:
            sign = debet_m.group(1)  # "-"
            amount_raw = debet_m.group(2)
            return _parse_cz_money(sign + amount_raw)

        # Kreditní (kladná) — poslední match
        kredit_matches = list(_CASTKA_KREDIT_RE.finditer(text))
        if kredit_matches:
            amount_raw = kredit_matches[-1].group(1)
            return _parse_cz_money(amount_raw)

        return None


def _parse_cz_money(raw: str) -> Money | None:
    """Parse Czech money format: -1 500,00 → Money(-150000)."""
    normalized = raw.strip().replace(" ", "").replace("\u00A0", "")
    normalized = normalized.replace(",", ".")
    try:
        dec = Decimal(normalized)
        return Money.from_koruny(str(dec))
    except (InvalidOperation, ValueError):
        return None
