"""Česká spořitelna PDF parser — extract_tables() strategie.

ČS PDF formát:
- PS/KS v plain textu hlavičky (tečka jako des. oddělovač: -51.48)
- Transakce jako single-cell tabulky (jedna buňka = jedna transakce)
- "Ceny za služby" = jedna buňka s více sub-položkami "Cena za ..."
- "Založení účtu 0.00" — přeskočit (nulová částka)
- Období: "Období: DD.MM.YYYY - DD.MM.YYYY"
- Číslo výpisu: "Číslo výpisu: 001"
"""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from domain.shared.money import Money
from infrastructure.banka.pdf_statement_parser import (
    ParsedPdfTransaction,
    ParsedStatement,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# Regex patterns — ČS specifické
# ═══════════════════════════════════════════════════════════════════

# PS/KS — tečkový formát: "Počáteční zůstatek: -51.48"
_PS_RE = re.compile(
    r"Počáteční\s+zůstatek\s*:\s*([+-]?\s*[\d\s\u00A0]*\.?\d+\.\d{2})",
    re.IGNORECASE,
)
_KS_RE = re.compile(
    r"Konečný\s+zůstatek\s*:\s*([+-]?\s*[\d\s\u00A0]*\.?\d+\.\d{2})",
    re.IGNORECASE,
)

# Období: "Období: 28.05.2025 - 31.05.2025"
_OBDOBI_RE = re.compile(
    r"Období\s*:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*-\s*(\d{1,2})\.(\d{1,2})\.(\d{4})",
)

# Číslo výpisu: "Číslo výpisu: 001"
_CISLO_RE = re.compile(r"Číslo\s+výpisu\s*:\s*(\d+)", re.IGNORECASE)

# Počet položek: "Počet položek na výpise 34 3"
_POCET_RE = re.compile(r"Počet\s+položek\s+na\s+výpise\s+(\d+)\s+(\d+)", re.IGNORECASE)

# Hlavní řádek transakce: datum ... částka
_TX_FIRST_LINE_RE = re.compile(
    r"^(\d{2}\.\d{2}\.\d{4})"       # datum zaúčtování
    r"\s+(.+?)"                       # middle part (popis, protiúčet, VS)
    r"\s+([+-]\s?[\d\s\u00A0]+\.\d{2})"  # částka (ČS tečkový formát)
    r"\s*$",
)

# Sub-položka pod "Ceny za služby": popis začínající velkým písmenem + částka.
# Matchuje "Cena za George Business -350.00" i "Náklady spojené s prodlením -300.00".
# Bezpečné — aplikuje se jen v kontextu _parse_ceny_za_sluzby().
_SUBITEM_RE = re.compile(
    r"^([A-ZÁ-Ž].+?)\s+([+-]?\s?[\d\s\u00A0]+\.\d{2})\s*$",
)


def _parse_cs_amount(raw: str) -> Decimal:
    """ČS formát částky: '+30 000.00' → Decimal('30000.00')."""
    s = raw.strip().replace(" ", "").replace("\u00A0", "")
    return Decimal(s)


def _parse_cs_money(raw: str) -> Money:
    """ČS formát → Money."""
    dec = _parse_cs_amount(raw)
    return Money.from_koruny(str(dec))


def _parse_date_cz(s: str) -> date:
    """DD.MM.YYYY → date."""
    parts = s.strip().split(".")
    return date(int(parts[2]), int(parts[1]), int(parts[0]))


class CeskaSporitelnaParser:
    """Parsuje ČS bankovní výpis z PDF pomocí pdfplumber tables."""

    def parse(self, pdf_path: Path) -> ParsedStatement:
        """Parse ČS PDF — vrací ParsedStatement kompatibilní s existujícím kódem."""
        if not pdf_path.exists():
            return ParsedStatement(
                pocatecni_stav=None,
                konecny_stav=None,
                chyby=[f"Soubor neexistuje: {pdf_path}"],
            )

        try:
            import pdfplumber
        except ImportError:
            return ParsedStatement(
                pocatecni_stav=None,
                konecny_stav=None,
                chyby=["pdfplumber není nainstalován"],
            )

        try:
            text, tables = self._extract_all(pdf_path)
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

        # Metadata z plain textu
        ps = self._extract_stav(text, _PS_RE)
        ks = self._extract_stav(text, _KS_RE)
        cislo = self._extract_cislo(text)
        datum_od, datum_do = self._extract_obdobi(text)

        logger.debug("ČS PS: %s, KS: %s, cislo: %s", ps, ks, cislo)

        # Transakce z tabulek
        transakce = self._extract_transakce(tables)

        # Počet položek check — jen warning, ne hard chyba
        # (ČS počítá i nulové položky jako "Založení účtu 0.00")
        chyby: list[str] = []
        pocet_deklarovany = self._extract_pocet(text)
        if pocet_deklarovany is not None:
            actual = len(transakce)
            if actual != pocet_deklarovany:
                msg = f"PDF uvádí {pocet_deklarovany} položek, parser nalezl {actual}"
                logger.warning(msg)

        # PS + suma == KS check
        if ps is not None and ks is not None and transakce:
            suma = sum(
                tx.castka.to_halire() for tx in transakce
            )
            expected_ks = ps.to_halire() + suma
            if abs(expected_ks - ks.to_halire()) > 1:  # tolerance 1 haléř
                msg = (
                    f"PS + suma transakcí = {Money(expected_ks).format_cz()}, "
                    f"PDF říká KS = {ks.format_cz()}"
                )
                logger.warning(msg)
                chyby.append(msg)

        logger.debug("ČS: nalezeno %d transakcí", len(transakce))

        return ParsedStatement(
            pocatecni_stav=ps,
            konecny_stav=ks,
            cislo_vypisu=cislo,
            datum_od=datum_od,
            datum_do=datum_do,
            transakce=transakce,
            chyby=chyby,
        )

    @staticmethod
    def _extract_all(pdf_path: Path) -> tuple[str, list[list[list[str | None]]]]:
        """Extrahuje text i tabulky ze všech stránek."""
        import pdfplumber

        pages_text: list[str] = []
        all_tables: list[list[list[str | None]]] = []

        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
                tables = page.extract_tables()
                for table in tables:
                    all_tables.append(table)

        return "\n".join(pages_text), all_tables

    @staticmethod
    def _extract_stav(text: str, pattern: re.Pattern) -> Money | None:
        m = pattern.search(text)
        if not m:
            return None
        try:
            return _parse_cs_money(m.group(1))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _extract_cislo(text: str) -> str | None:
        m = _CISLO_RE.search(text)
        return m.group(1) if m else None

    @staticmethod
    def _extract_obdobi(text: str) -> tuple[date | None, date | None]:
        m = _OBDOBI_RE.search(text)
        if not m:
            return None, None
        try:
            datum_od = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            datum_do = date(int(m.group(6)), int(m.group(5)), int(m.group(4)))
            return datum_od, datum_do
        except ValueError:
            return None, None

    @staticmethod
    def _extract_pocet(text: str) -> int | None:
        """Počet položek na výpise = odepsáno + připsáno."""
        m = _POCET_RE.search(text)
        if not m:
            return None
        try:
            return int(m.group(1)) + int(m.group(2))
        except ValueError:
            return None

    def _extract_transakce(
        self, tables: list[list[list[str | None]]],
    ) -> list[ParsedPdfTransaction]:
        results: list[ParsedPdfTransaction] = []

        for table in tables:
            for row in table:
                # Každý row je list[str|None], ČS má typicky 1 buňku
                for cell in row:
                    if not cell:
                        continue
                    txs = self._parse_cell(cell)
                    results.extend(txs)

        return results

    def _parse_cell(self, cell: str) -> list[ParsedPdfTransaction]:
        """Parsuje jednu buňku tabulky — může obsahovat 1 tx nebo "Ceny za služby"."""
        lines = cell.strip().split("\n")
        if not lines:
            return []

        first_line = lines[0].strip()

        # Přeskoč header řádky
        if first_line.startswith("Zaúčtováno") or first_line.startswith("Typ "):
            return []

        # "Ceny za služby" — první řádek nemá částku, jen datum + text
        ceny_m = re.match(r"^(\d{2}\.\d{2}\.\d{4})\s+Ceny za služby", first_line)
        if ceny_m:
            datum = _parse_date_cz(ceny_m.group(1))
            return self._parse_ceny_za_sluzby(datum, lines[1:])

        # Zkus matchnout hlavní transakční řádek
        m = _TX_FIRST_LINE_RE.match(first_line)
        if not m:
            # Zkus "Obraty za období" summary řádek — přeskoč
            return []

        datum_str = m.group(1)
        middle = m.group(2).strip()
        castka_str = m.group(3)

        try:
            datum = _parse_date_cz(datum_str)
            castka_dec = _parse_cs_amount(castka_str)
        except (ValueError, InvalidOperation):
            return []

        # Přeskoč nulové částky ("Založení účtu 0.00")
        if castka_dec == 0:
            return []

        # Check for "Ceny za služby" — sub-items
        if "Ceny za služby" in middle:
            return self._parse_ceny_za_sluzby(datum, lines[1:])

        # Normální transakce — extrahuj VS, protiúčet, popis z middle
        vs, protiucet, popis = self._parse_middle(middle)

        return [ParsedPdfTransaction(
            datum_transakce=datum,
            datum_zauctovani=None,
            castka=Money.from_koruny(str(castka_dec)),
            variabilni_symbol=vs,
            popis=popis,
        )]

    def _parse_ceny_za_sluzby(
        self, datum: date, remaining_lines: list[str],
    ) -> list[ParsedPdfTransaction]:
        """Parsuje sub-položky 'Cena za ...' z buňky Ceny za služby."""
        results: list[ParsedPdfTransaction] = []

        for line in remaining_lines:
            line = line.strip()
            m = _SUBITEM_RE.match(line)
            if not m:
                continue
            popis = m.group(1).strip()
            try:
                castka_dec = _parse_cs_amount(m.group(2))
            except (InvalidOperation, ValueError):
                continue

            if castka_dec == 0:
                continue

            results.append(ParsedPdfTransaction(
                datum_transakce=datum,
                datum_zauctovani=None,
                castka=Money.from_koruny(str(castka_dec)),
                variabilni_symbol=None,
                popis=popis,
            ))

        return results

    @staticmethod
    def _parse_middle(middle: str) -> tuple[str | None, str | None, str]:
        """Extrahuje VS, protiúčet a popis z prostřední části řádku."""
        parts = middle.split()

        # VS: poslední token, pouze číslice, ≥4 znaků
        vs: str | None = None
        if parts and parts[-1].isdigit() and len(parts[-1]) >= 4:
            vs = parts[-1]
            parts = parts[:-1]

        # Protiúčet: token obsahující "/" s číslicemi
        protiucet: str | None = None
        for j, part in enumerate(parts):
            if "/" in part and any(c.isdigit() for c in part):
                protiucet = part
                parts = parts[:j] + parts[j + 1:]
                break

        popis = " ".join(parts).strip()
        return vs, protiucet, popis
