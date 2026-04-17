"""Testy pro CsvBankParser + GenericCsvParser."""

from __future__ import annotations

from pathlib import Path

from domain.banka.bankovni_ucet import FormatCsv
from domain.shared.money import Money
from infrastructure.banka.csv_parser import CsvBankParser, GenericCsvParser

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "banka"


class TestCsvBankParser:

    def setup_method(self):
        self.parser = CsvBankParser()

    def test_parse_money_banka_format(self):
        # Money Banka: skip_rows=1, windows-1250, ; delimiter
        csv_text = (
            "Hlavicka skip\n"
            "Datum provedení;Datum zaúčtování;Částka;VS;KS;SS;Protiúčet;Zpráva pro příjemce\n"
            "15.03.2025;15.03.2025;-1 500,00;1234567890;;0558;123456/0100;Poplatek za vedení\n"
            "16.03.2025;16.03.2025;25 000,50;9876543210;;0008;987654/0300;Přijatá platba\n"
        )
        txs = self.parser.parse_text(csv_text, FormatCsv.MONEY_BANKA)
        assert len(txs) == 2

        # First transaction: výdaj
        assert txs[0].castka == Money(-150000)
        assert txs[0].smer == "V"
        assert txs[0].variabilni_symbol == "1234567890"
        assert txs[0].popis == "Poplatek za vedení"

        # Second transaction: příjem
        assert txs[1].castka == Money(2500050)
        assert txs[1].smer == "P"
        assert txs[1].variabilni_symbol == "9876543210"

    def test_parse_ceska_sporitelna_format(self):
        csv_text = (
            "Datum splatnosti;Datum zaúčtování;Částka;VS;KS;SS;Protiúčet;Poznámka\n"
            "01.04.2025;01.04.2025;-250,00;12345;;;111222/0800;Poplatek\n"
        )
        txs = self.parser.parse_text(csv_text, FormatCsv.CESKA_SPORITELNA)
        assert len(txs) == 1
        assert txs[0].castka == Money(-25000)
        assert txs[0].smer == "V"

    def test_row_hash_unique(self):
        csv_text = (
            "Hlavicka skip\n"
            "Datum provedení;Datum zaúčtování;Částka;VS;KS;SS;Protiúčet;Zpráva pro příjemce\n"
            "15.03.2025;15.03.2025;-100,00;111;;0558;123456/0100;Tx1\n"
            "15.03.2025;15.03.2025;-100,00;222;;0558;123456/0100;Tx2\n"
        )
        txs = self.parser.parse_text(csv_text, FormatCsv.MONEY_BANKA)
        assert len(txs) == 2
        assert txs[0].row_hash != txs[1].row_hash

    def test_empty_csv(self):
        txs = self.parser.parse_text("", FormatCsv.MONEY_BANKA)
        assert txs == []

    def test_invalid_date_skipped(self):
        csv_text = (
            "Hlavicka skip\n"
            "Datum provedení;Datum zaúčtování;Částka;VS;KS;SS;Protiúčet;Zpráva pro příjemce\n"
            "invalid;15.03.2025;-100,00;111;;0558;123456/0100;Tx\n"
        )
        txs = self.parser.parse_text(csv_text, FormatCsv.MONEY_BANKA)
        assert len(txs) == 0

    def test_missing_amount_skipped(self):
        csv_text = (
            "Hlavicka skip\n"
            "Datum provedení;Datum zaúčtování;Částka;VS;KS;SS;Protiúčet;Zpráva pro příjemce\n"
            "15.03.2025;15.03.2025;;111;;0558;123456/0100;Tx\n"
        )
        txs = self.parser.parse_text(csv_text, FormatCsv.MONEY_BANKA)
        assert len(txs) == 0


class TestGenericCsvParser:
    """Testy pro univerzální auto-detekční parser."""

    def setup_method(self):
        self.parser = GenericCsvParser()

    def test_moneta_claude_ai_format(self):
        """Reálný formát: čárka delimiter, ISO data, snake_case sloupce."""
        csv_text = (
            "datum,castka,mena,protiucet,variabilni_symbol,"
            "konstantni_symbol,specificky_symbol,popis,nazev_protistrany\n"
            "2025-02-13,150000.00,CZK,123-9769760237/0100,,,,DI: HŮF TOMÁŠ,HŮF TOMÁŠ\n"
            "2025-02-14,-8447.00,CZK,2112694069/2700,02132025,,,PŘÍKAZ K ÚHRADĚ,\n"
            "2025-02-16,-7413.00,CZK,154970528/0300,,,,OKAMŽITÁ ÚHRADA,\n"
            "2025-02-17,-803.00,CZK,942942341/5500,2025183004,,,OKAMŽITÁ ÚHRADA,\n"
        )
        txs = self.parser.parse_text(csv_text)
        assert len(txs) == 4

        # Příjem 150 000 Kč
        assert txs[0].castka == Money(15000000)
        assert txs[0].smer == "P"
        assert txs[0].protiucet == "123-9769760237/0100"
        assert "HŮF TOMÁŠ" in txs[0].popis

        # Výdaj 8 447 Kč
        assert txs[1].castka == Money(-844700)
        assert txs[1].smer == "V"
        assert txs[1].variabilni_symbol == "02132025"

        # Výdaj 7 413 Kč
        assert txs[2].castka == Money(-741300)
        assert txs[2].protiucet == "154970528/0300"

        # Výdaj 803 Kč
        assert txs[3].castka == Money(-80300)
        assert txs[3].variabilni_symbol == "2025183004"

    def test_moneta_fixture_file(self):
        """Parsování fixture souboru z disku."""
        fixture = FIXTURE_DIR / "moneta_claude_ai_2025_02.csv"
        txs = self.parser.parse(fixture)
        assert len(txs) == 4
        assert txs[0].datum_transakce.year == 2025
        assert txs[0].datum_transakce.month == 2
        assert txs[0].datum_transakce.day == 13

    def test_obecny_via_csv_bank_parser(self):
        """CsvBankParser s FormatCsv.OBECNY deleguje na GenericCsvParser."""
        parser = CsvBankParser()
        csv_text = (
            "datum,castka,protiucet,popis\n"
            "2025-03-01,-150.00,123/0100,Poplatek\n"
        )
        txs = parser.parse_text(csv_text, FormatCsv.OBECNY)
        assert len(txs) == 1
        assert txs[0].castka == Money(-15000)

    def test_auto_detect_delimiter_semicolon(self):
        """Středníkový formát s českými hlavičkami."""
        csv_text = (
            "Datum;Částka;VS;Popis\n"
            "15.03.2025;-1500,00;12345;Poplatek\n"
        )
        txs = self.parser.parse_text(csv_text)
        assert len(txs) == 1
        assert txs[0].castka == Money(-150000)
        assert txs[0].variabilni_symbol == "12345"

    def test_auto_detect_delimiter_tab(self):
        """Tabulátorový delimiter."""
        csv_text = (
            "datum\tcastka\tpopis\n"
            "2025-01-10\t-500.00\tPoplatek\n"
        )
        txs = self.parser.parse_text(csv_text)
        assert len(txs) == 1
        assert txs[0].castka == Money(-50000)

    def test_auto_detect_date_format_czech(self):
        """České datum dd.mm.yyyy."""
        csv_text = (
            "datum,castka,popis\n"
            "15.03.2025,-100.00,Test\n"
        )
        txs = self.parser.parse_text(csv_text)
        assert len(txs) == 1
        assert txs[0].datum_transakce.day == 15
        assert txs[0].datum_transakce.month == 3

    def test_auto_detect_date_format_iso(self):
        """ISO datum yyyy-mm-dd."""
        csv_text = (
            "datum,castka,popis\n"
            "2025-03-15,-100.00,Test\n"
        )
        txs = self.parser.parse_text(csv_text)
        assert len(txs) == 1
        assert txs[0].datum_transakce.day == 15
        assert txs[0].datum_transakce.month == 3

    def test_fuzzy_mapping_case_insensitive(self):
        """Hlavičky UPPERCASE fungují."""
        csv_text = (
            "DATUM,CASTKA,VS,POPIS\n"
            "2025-01-01,-100.00,999,Test\n"
        )
        txs = self.parser.parse_text(csv_text)
        assert len(txs) == 1
        assert txs[0].variabilni_symbol == "999"

    def test_fuzzy_mapping_diacritics(self):
        """Hlavičky s diakritikou."""
        csv_text = (
            "Datum;Částka;Variabilní symbol;Protiúčet;Popis\n"
            "15.03.2025;-1500,00;12345;123/0100;Poplatek\n"
        )
        txs = self.parser.parse_text(csv_text)
        assert len(txs) == 1
        assert txs[0].variabilni_symbol == "12345"
        assert txs[0].protiucet == "123/0100"

    def test_single_datum_used_for_both(self):
        """Jeden sloupec datum → datum_transakce i datum_zauctovani."""
        csv_text = (
            "datum,castka,popis\n"
            "2025-03-15,-100.00,Test\n"
        )
        txs = self.parser.parse_text(csv_text)
        assert len(txs) == 1
        assert txs[0].datum_transakce == txs[0].datum_zauctovani

    def test_two_date_columns(self):
        """Dva sloupce datum — datum_transakce a datum_zauctovani."""
        csv_text = (
            "datum_transakce;datum_zauctovani;castka;popis\n"
            "15.03.2025;16.03.2025;-100,00;Test\n"
        )
        txs = self.parser.parse_text(csv_text)
        assert len(txs) == 1
        assert txs[0].datum_transakce.day == 15
        assert txs[0].datum_zauctovani.day == 16

    def test_empty_lines_ignored(self):
        """Prázdné řádky se ignorují."""
        csv_text = (
            "datum,castka,popis\n"
            "\n"
            "2025-03-15,-100.00,Test\n"
            "\n"
        )
        txs = self.parser.parse_text(csv_text)
        assert len(txs) == 1

    def test_optional_columns_missing(self):
        """Chybějící volitelné sloupce se nevyplní."""
        csv_text = (
            "datum,castka\n"
            "2025-03-15,-100.00\n"
        )
        txs = self.parser.parse_text(csv_text)
        assert len(txs) == 1
        assert txs[0].variabilni_symbol is None
        assert txs[0].protiucet is None
        assert txs[0].popis is None

    def test_decimal_comma_separator(self):
        """Desetinná čárka v částce."""
        csv_text = (
            "datum;castka;popis\n"
            "15.03.2025;-1500,50;Test\n"
        )
        txs = self.parser.parse_text(csv_text)
        assert len(txs) == 1
        assert txs[0].castka == Money(-150050)

    def test_nazev_protistrany_combined_with_popis(self):
        """nazev_protistrany se spojí s popis."""
        csv_text = (
            "datum,castka,popis,nazev_protistrany\n"
            "2025-01-01,1000.00,Platba,Jan Novák\n"
        )
        txs = self.parser.parse_text(csv_text)
        assert len(txs) == 1
        assert "Platba" in txs[0].popis
        assert "Jan Novák" in txs[0].popis

    def test_nazev_protistrany_without_popis(self):
        """nazev_protistrany bez popis sloupce."""
        csv_text = (
            "datum,castka,nazev_protistrany\n"
            "2025-01-01,1000.00,Jan Novák\n"
        )
        txs = self.parser.parse_text(csv_text)
        assert len(txs) == 1
        assert txs[0].popis == "Jan Novák"
