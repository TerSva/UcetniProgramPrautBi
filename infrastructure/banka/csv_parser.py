"""CSV parser pro bankovní výpisy — Money Banka, Česká spořitelna, obecný.

Obecný parser automaticky detekuje:
    - Delimiter (čárka, středník, tabulátor)
    - Encoding (UTF-8, Windows-1250, latin-1)
    - Formát data (%Y-%m-%d, %d.%m.%Y, %d/%m/%Y, %Y/%m/%d)
    - Mapování sloupců (fuzzy, case-insensitive, bez diakritiky)
    - Desetinný oddělovač (tečka vs. čárka)
"""

from __future__ import annotations

import csv
import hashlib
import io
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from domain.banka.bankovni_ucet import FormatCsv
from domain.shared.money import Money


@dataclass(frozen=True)
class CsvColumnMapping:
    """Mapování sloupců CSV na interní strukturu."""

    datum_transakce: str
    datum_zauctovani: str
    datum_format: str
    castka: str
    variabilni_symbol: str | None
    konstantni_symbol: str | None
    specificky_symbol: str | None
    protiucet: str | None
    popis: str | None
    delimiter: str = ";"
    encoding: str = "utf-8"
    skip_rows: int = 0


MONEY_BANKA_MAPPING = CsvColumnMapping(
    datum_transakce="Datum provedení",
    datum_zauctovani="Datum zaúčtování",
    datum_format="%d.%m.%Y",
    castka="Částka",
    variabilni_symbol="VS",
    konstantni_symbol="KS",
    specificky_symbol="SS",
    protiucet="Protiúčet",
    popis="Zpráva pro příjemce",
    delimiter=";",
    encoding="windows-1250",
    skip_rows=1,
)

CESKA_SPORITELNA_MAPPING = CsvColumnMapping(
    datum_transakce="Datum splatnosti",
    datum_zauctovani="Datum zaúčtování",
    datum_format="%d.%m.%Y",
    castka="Částka",
    variabilni_symbol="VS",
    konstantni_symbol="KS",
    specificky_symbol="SS",
    protiucet="Protiúčet",
    popis="Poznámka",
    delimiter=";",
    encoding="utf-8",
)


def _get_mapping(format_csv: FormatCsv) -> CsvColumnMapping:
    if format_csv == FormatCsv.MONEY_BANKA:
        return MONEY_BANKA_MAPPING
    if format_csv == FormatCsv.CESKA_SPORITELNA:
        return CESKA_SPORITELNA_MAPPING
    # OBECNY — vrací None, parse se řeší přes GenericCsvParser
    return None  # type: ignore[return-value]


# ═══════════════════════════════════════════════════════════════════
# Fuzzy column mapping pro obecný parser
# ═══════════════════════════════════════════════════════════════════

def _strip_diacritics(s: str) -> str:
    """Odstraní diakritiku z textu."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalize_col(name: str) -> str:
    """Normalizuje název sloupce pro fuzzy matching."""
    s = name.strip().lower()
    s = _strip_diacritics(s)
    s = s.replace(" ", "_").replace("-", "_")
    return s


# Aliasy pro jednotlivá pole — klíč je normalizovaný název sloupce
_DATUM_ALIASES = {
    "datum", "date", "datum_provedeni", "datum_transakce",
    "datum_zauctovani", "datum_splatnosti", "datum_pohybu",
    "transaction_date", "value_date",
}
_DATUM_ZAUCTOVANI_ALIASES = {
    "datum_zauctovani", "datum_ucetni", "posting_date",
    "accounting_date",
}
_CASTKA_ALIASES = {
    "castka", "amount", "suma", "objem", "value",
    "castka_v_mene_uctu",
}
_VS_ALIASES = {
    "vs", "variabilni_symbol", "variable_symbol",
}
_KS_ALIASES = {
    "ks", "konstantni_symbol", "constant_symbol",
}
_SS_ALIASES = {
    "ss", "specificky_symbol", "specific_symbol",
}
_PROTIUCET_ALIASES = {
    "protiucet", "counterparty", "protistrana",
    "cislo_protiuctu", "counterparty_account",
}
_POPIS_ALIASES = {
    "popis", "zprava", "description", "text",
    "zprava_pro_prijemce", "poznamka", "message",
    "note", "ucel_platby", "detail",
}
_NAZEV_PROTISTRANY_ALIASES = {
    "nazev_protistrany", "counterparty_name", "name",
    "jmeno_protistrany", "nazev_prijemce",
}

_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%d-%m-%Y",
]

_DELIMITERS = [",", ";", "\t"]
_ENCODINGS = ["utf-8", "windows-1250", "latin-1"]


class _FuzzyMapping:
    """Výsledek fuzzy detekce sloupců."""

    def __init__(self, headers: list[str]) -> None:
        norm_map: dict[str, str] = {}
        for h in headers:
            norm_map[_normalize_col(h)] = h

        # Nejdřív najdi datum_zauctovani (specifičtější)
        self.datum_zauctovani = self._find(norm_map, _DATUM_ZAUCTOVANI_ALIASES)
        # Pak najdi obecný datum — ale ne ten, co už je datum_zauctovani
        self.datum = self._find(
            norm_map, _DATUM_ALIASES, exclude=self.datum_zauctovani,
        )
        # Pokud se nenašel jiný datum sloupec, použij datum_zauctovani
        if self.datum is None and self.datum_zauctovani is not None:
            self.datum = self.datum_zauctovani

        self.castka = self._find(norm_map, _CASTKA_ALIASES)
        self.vs = self._find(norm_map, _VS_ALIASES)
        self.ks = self._find(norm_map, _KS_ALIASES)
        self.ss = self._find(norm_map, _SS_ALIASES)
        self.protiucet = self._find(norm_map, _PROTIUCET_ALIASES)
        self.popis = self._find(norm_map, _POPIS_ALIASES)
        self.nazev_protistrany = self._find(norm_map, _NAZEV_PROTISTRANY_ALIASES)

    @staticmethod
    def _find(
        norm_map: dict[str, str],
        aliases: set[str],
        exclude: str | None = None,
    ) -> str | None:
        for alias in aliases:
            if alias in norm_map:
                val = norm_map[alias]
                if exclude is not None and val == exclude:
                    continue
                return val
        return None

    @property
    def is_valid(self) -> bool:
        return self.datum is not None and self.castka is not None


class GenericCsvParser:
    """Univerzální CSV parser s auto-detekcí."""

    def parse(self, csv_path: Path) -> list[ParsedTransaction]:
        """Parsuje CSV soubor s auto-detekcí formátu."""
        raw = csv_path.read_bytes()
        text = self._detect_encoding(raw)
        return self._parse_text(text)

    def parse_text(self, text: str) -> list[ParsedTransaction]:
        """Parsuje CSV z textu (pro testování)."""
        return self._parse_text(text)

    def _parse_text(self, text: str) -> list[ParsedTransaction]:
        lines = [l for l in text.splitlines() if l.strip()]
        if len(lines) < 2:
            return []

        delimiter = self._detect_delimiter(lines)
        header_line = lines[0]
        reader = csv.DictReader(lines, delimiter=delimiter)

        headers = next(csv.reader([header_line], delimiter=delimiter))
        mapping = _FuzzyMapping(headers)
        if not mapping.is_valid:
            return []

        date_format = None
        results: list[ParsedTransaction] = []

        for row in reader:
            if date_format is None:
                date_format = self._detect_date_format(
                    row.get(mapping.datum, ""),
                )
                if date_format is None:
                    continue

            tx = self._parse_row(row, mapping, date_format)
            if tx is not None:
                results.append(tx)

        return results

    @staticmethod
    def _detect_encoding(raw: bytes) -> str:
        for enc in _ENCODINGS:
            try:
                text = raw.decode(enc)
                # Pokud se podaří dekódovat a má rozumný header, OK
                if any(c in text[:200].lower() for c in ("datum", "date", "castka", "amount")):
                    return text
                # I bez rozpoznaného headeru — pokud UTF-8 projde, použij ho
                if enc == "utf-8":
                    return text
            except (UnicodeDecodeError, ValueError):
                continue
        return raw.decode("latin-1", errors="replace")

    @staticmethod
    def _detect_delimiter(lines: list[str]) -> str:
        """Detekuje delimiter podle konzistence počtu sloupců."""
        best = ","
        best_score = 0

        for delim in _DELIMITERS:
            counts = [len(line.split(delim)) for line in lines[:5]]
            if len(counts) < 2:
                continue
            # Konzistentní počet sloupců a víc než 1
            if counts[0] > 1 and all(c == counts[0] for c in counts):
                if counts[0] > best_score:
                    best_score = counts[0]
                    best = delim

        return best

    @staticmethod
    def _detect_date_format(sample: str) -> str | None:
        sample = sample.strip()
        if not sample:
            return None
        for fmt in _DATE_FORMATS:
            try:
                datetime.strptime(sample, fmt)
                return fmt
            except ValueError:
                continue
        return None

    def _parse_row(
        self,
        row: dict[str, str],
        mapping: _FuzzyMapping,
        date_format: str,
    ) -> ParsedTransaction | None:
        # Datum
        dt_str = row.get(mapping.datum, "").strip()
        if not dt_str:
            return None
        try:
            datum_tx = datetime.strptime(dt_str, date_format).date()
        except ValueError:
            return None

        # Datum zaúčtování
        datum_zau = datum_tx
        if mapping.datum_zauctovani and mapping.datum_zauctovani != mapping.datum:
            dz_str = row.get(mapping.datum_zauctovani, "").strip()
            if dz_str:
                try:
                    datum_zau = datetime.strptime(dz_str, date_format).date()
                except ValueError:
                    pass

        # Částka
        castka_str = row.get(mapping.castka, "").strip()
        if not castka_str:
            return None
        castka = _parse_amount(castka_str)
        if castka is None:
            return None

        # Směr
        smer: Literal["P", "V"] = "P" if castka.is_positive else "V"

        # Symboly a popis
        vs = _get_field(row, mapping.vs)
        ks = _get_field(row, mapping.ks)
        ss = _get_field(row, mapping.ss)
        protiucet = _get_field(row, mapping.protiucet)

        # Popis — kombinace popis + nazev_protistrany
        popis = _get_field(row, mapping.popis)
        nazev = _get_field(row, mapping.nazev_protistrany)
        if popis and nazev:
            popis = f"{popis} — {nazev}"
        elif nazev and not popis:
            popis = nazev

        # Hash
        hash_src = (
            f"{datum_zau.isoformat()}|{castka.to_halire()}"
            f"|{vs or ''}|{popis or ''}"
        )
        row_hash = hashlib.sha256(hash_src.encode()).hexdigest()[:32]

        return ParsedTransaction(
            datum_transakce=datum_tx,
            datum_zauctovani=datum_zau,
            castka=castka,
            smer=smer,
            variabilni_symbol=vs,
            konstantni_symbol=ks,
            specificky_symbol=ss,
            protiucet=protiucet,
            popis=popis,
            row_hash=row_hash,
        )


# ═══════════════════════════════════════════════════════════════════
# Společné utility
# ═══════════════════════════════════════════════════════════════════

def _parse_amount(raw: str) -> Money | None:
    normalized = raw.replace(" ", "").replace("\u00A0", "")
    # Detekce: "1.234,56" → čárka je desetinný, "1,234.56" → tečka je desetinný
    has_comma = "," in normalized
    has_dot = "." in normalized
    if has_comma and has_dot:
        # Pokud čárka je za tečkou → čárka je desetinný oddělovač
        if normalized.rindex(",") > normalized.rindex("."):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
    elif has_comma and not has_dot:
        # "1234,56" → čárka je desetinný
        # Ale "1,234" bez dalšího kontextu — čárka za 3 ciframi = tisíce
        parts = normalized.split(",")
        if len(parts) == 2 and len(parts[1]) == 2:
            normalized = normalized.replace(",", ".")
        elif len(parts) == 2 and len(parts[1]) == 3:
            # Pravděpodobně tisícový separátor
            normalized = normalized.replace(",", "")
        else:
            normalized = normalized.replace(",", ".")
    try:
        dec = Decimal(normalized)
        return Money.from_koruny(str(dec))
    except (InvalidOperation, ValueError):
        return None


def _get_field(row: dict[str, str], key: str | None) -> str | None:
    if key is None:
        return None
    val = row.get(key, "").strip()
    return val if val else None


@dataclass(frozen=True)
class ParsedTransaction:
    """Jedna parsovaná transakce z CSV."""

    datum_transakce: date
    datum_zauctovani: date
    castka: Money
    smer: Literal["P", "V"]
    variabilni_symbol: str | None
    konstantni_symbol: str | None
    specificky_symbol: str | None
    protiucet: str | None
    popis: str | None
    row_hash: str


class CsvBankParser:
    """Parsuje CSV bankovní výpis podle formátu banky."""

    def __init__(self) -> None:
        self._generic = GenericCsvParser()

    def parse(
        self, csv_path: Path, format_csv: FormatCsv,
    ) -> list[ParsedTransaction]:
        if format_csv == FormatCsv.OBECNY:
            return self._generic.parse(csv_path)

        mapping = _get_mapping(format_csv)
        content = csv_path.read_bytes()
        text = content.decode(mapping.encoding, errors="replace")
        lines = text.splitlines()

        if mapping.skip_rows > 0:
            lines = lines[mapping.skip_rows:]

        if not lines:
            return []

        reader = csv.DictReader(
            lines, delimiter=mapping.delimiter,
        )

        results: list[ParsedTransaction] = []
        for row in reader:
            tx = self._parse_row(row, mapping)
            if tx is not None:
                results.append(tx)

        # Fallback: pokud specifický parser nenašel nic, zkus obecný
        if not results:
            results = self._generic.parse(csv_path)

        return results

    def parse_text(
        self, text: str, format_csv: FormatCsv,
    ) -> list[ParsedTransaction]:
        """Parse CSV from string (for testing)."""
        if format_csv == FormatCsv.OBECNY:
            return self._generic.parse_text(text)

        mapping = _get_mapping(format_csv)
        lines = text.splitlines()

        if mapping.skip_rows > 0:
            lines = lines[mapping.skip_rows:]

        if not lines:
            return []

        reader = csv.DictReader(
            lines, delimiter=mapping.delimiter,
        )

        results: list[ParsedTransaction] = []
        for row in reader:
            tx = self._parse_row(row, mapping)
            if tx is not None:
                results.append(tx)

        return results

    def _parse_row(
        self, row: dict[str, str], mapping: CsvColumnMapping,
    ) -> ParsedTransaction | None:
        # Datum transakce
        dt_str = row.get(mapping.datum_transakce, "").strip()
        if not dt_str:
            return None
        try:
            datum_tx = datetime.strptime(dt_str, mapping.datum_format).date()
        except ValueError:
            return None

        # Datum zaúčtování
        dz_str = row.get(mapping.datum_zauctovani, "").strip()
        if dz_str:
            try:
                datum_zau = datetime.strptime(dz_str, mapping.datum_format).date()
            except ValueError:
                datum_zau = datum_tx
        else:
            datum_zau = datum_tx

        # Částka
        castka_str = row.get(mapping.castka, "").strip()
        if not castka_str:
            return None
        castka = _parse_amount(castka_str)
        if castka is None:
            return None

        # Směr
        smer: Literal["P", "V"] = "P" if castka.is_positive else "V"

        # Symboly
        vs = _get_field(row, mapping.variabilni_symbol)
        ks = _get_field(row, mapping.konstantni_symbol)
        ss = _get_field(row, mapping.specificky_symbol)
        protiucet = _get_field(row, mapping.protiucet)
        popis = _get_field(row, mapping.popis)

        # Hash
        hash_src = (
            f"{datum_zau.isoformat()}|{castka.to_halire()}"
            f"|{vs or ''}|{popis or ''}"
        )
        row_hash = hashlib.sha256(hash_src.encode()).hexdigest()[:32]

        return ParsedTransaction(
            datum_transakce=datum_tx,
            datum_zauctovani=datum_zau,
            castka=castka,
            smer=smer,
            variabilni_symbol=vs,
            konstantni_symbol=ks,
            specificky_symbol=ss,
            protiucet=protiucet,
            popis=popis,
            row_hash=row_hash,
        )
