"""Testy pro PdfStatementParser."""

from __future__ import annotations

from pathlib import Path

from domain.banka.bankovni_ucet import FormatCsv
from domain.shared.money import Money
from infrastructure.banka.pdf_statement_parser import (
    PdfStatementParser,
    _PS_PATTERNS,
    _KS_PATTERNS,
)


class TestPdfStatementParser:

    def setup_method(self):
        self.parser = PdfStatementParser()

    def test_nonexistent_file_returns_error(self, tmp_path):
        result = self.parser.parse(
            tmp_path / "neexistuje.pdf", FormatCsv.MONEY_BANKA,
        )
        assert result.chyby
        assert "neexistuje" in result.chyby[0].lower()

    def test_extract_stav_parses_cs_amount(self):
        text = "Počáteční stav: 125 432,50"
        result = PdfStatementParser._extract_stav(text, _PS_PATTERNS)
        assert result is not None
        assert result.to_halire() == 12543250

    def test_extract_stav_parses_negative(self):
        text = "Konečný stav: -5 000,00"
        result = PdfStatementParser._extract_stav(text, _KS_PATTERNS)
        assert result is not None
        assert result.to_halire() == -500000

    def test_extract_stav_returns_none_if_not_found(self):
        text = "Žádný stav tu není"
        result = PdfStatementParser._extract_stav(text, _PS_PATTERNS)
        assert result is None

    def test_extract_stav_ps_abbreviation(self):
        text = "PS: 150 000,00 Kč"
        result = PdfStatementParser._extract_stav(text, _PS_PATTERNS)
        assert result is not None
        assert result.to_halire() == 15000000

    def test_extract_stav_zustatek_format(self):
        text = "Předchozí zůstatek: 250 000,00"
        result = PdfStatementParser._extract_stav(text, _PS_PATTERNS)
        assert result is not None
        assert result.to_halire() == 25000000


class TestPdfTransakceExtraction:
    """Testy pro extrakci transakcí z PDF textu — ověření, že se
    datumy nepletou s částkami."""

    def setup_method(self):
        self.parser = PdfStatementParser()

    def test_datum_not_confused_with_castka(self):
        """14.02.2025 nesmí generovat transakci s částkou 14,02 Kč."""
        text = "14.02.2025 Poplatek za vedení účtu"
        txs = self.parser._extract_transakce(text)
        # Řádek bez reálné částky → žádná transakce
        assert len(txs) == 0

    def test_datum_with_real_castka(self):
        """Řádek s datem a reálnou částkou → validní transakce."""
        text = "14.02.2025 Poplatek za vedení účtu -150,00"
        txs = self.parser._extract_transakce(text)
        assert len(txs) == 1
        assert txs[0].castka == Money(-15000)
        assert txs[0].datum_transakce.day == 14
        assert txs[0].datum_transakce.month == 2

    def test_large_amount_extracted(self):
        """Větší částka se správně extrahuje."""
        text = "13.02.2025 Přijatá platba 150 000,00"
        txs = self.parser._extract_transakce(text)
        assert len(txs) == 1
        assert txs[0].castka == Money(15000000)

    def test_multiple_dates_same_line(self):
        """Dva datumy na řádku — druhé datum se neinterpretuje jako částka."""
        text = "13.02.2025 14.02.2025 Převod -5 000,00"
        txs = self.parser._extract_transakce(text)
        assert len(txs) == 1
        assert txs[0].castka == Money(-500000)

    def test_tiny_amount_rejected(self):
        """Částka pod 1 Kč se odmítne jako artefakt."""
        text = "15.03.2025 Nějaký text 0,50"
        txs = self.parser._extract_transakce(text)
        assert len(txs) == 0

    def test_vs_extracted(self):
        """VS se extrahuje z řádku."""
        text = "13.02.2025 Platba VS: 2025001234 -8 447,00"
        txs = self.parser._extract_transakce(text)
        assert len(txs) == 1
        assert txs[0].variabilni_symbol == "2025001234"

    def test_no_duplicates_from_multipage(self):
        """Stejný řádek dvakrát → dvě transakce (parser neodstraňuje dupl.,
        to je odpovědnost validátoru)."""
        text = (
            "13.02.2025 Platba -8 447,00\n"
            "14.02.2025 Poplatek -150,00\n"
        )
        txs = self.parser._extract_transakce(text)
        assert len(txs) == 2

    def test_eur_amount_not_extracted(self):
        """Cizoměnová částka (27.00 EUR) se nesmí extrahovat."""
        text = "05.03.2025 27.00 EUR 07.03.2025"
        txs = self.parser._extract_transakce(text)
        assert len(txs) == 0

    def test_exchange_rate_not_extracted(self):
        """Kurz (25.9337) se nesmí extrahovat jako transakce."""
        text = "KI: KURZ 1 EUR:25.9337 (05.03.2025)"
        txs = self.parser._extract_transakce(text)
        assert len(txs) == 0

    def test_usd_amount_not_extracted(self):
        """USD částka se nesmí extrahovat."""
        text = "20.03.2025 30.25 USD 21.03.2025"
        txs = self.parser._extract_transakce(text)
        assert len(txs) == 0

    def test_smenný_kurz_line_ignored(self):
        """Řádek se směnným kurzem se přeskočí."""
        text = "14.03.2025 AV: Směnný kurz: 25,9930; 5068,64 CZK/195,00 EUR; Promo"
        txs = self.parser._extract_transakce(text)
        assert len(txs) == 0


class TestMonetaRealPdf:
    """Testy proti reálnému Moneta PDF (březen 2025)."""

    FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "banka" / "moneta_brezen_2025.pdf"

    def setup_method(self):
        self.parser = PdfStatementParser()

    def test_fixture_exists(self):
        assert self.FIXTURE.exists(), f"Fixture {self.FIXTURE} neexistuje"

    def test_exact_transaction_count(self):
        result = self.parser.parse(self.FIXTURE, FormatCsv.MONEY_BANKA)
        assert len(result.transakce) == 36

    def test_no_hallucinated_eur_amounts(self):
        result = self.parser.parse(self.FIXTURE, FormatCsv.MONEY_BANKA)
        amounts_halire = [tx.castka.to_halire() for tx in result.transakce]
        assert 2700 not in amounts_halire, "27,00 Kč = hallucinated 27.00 EUR"
        assert 2593 not in amounts_halire, "25,93 Kč = hallucinated kurz 25.9337"
        assert 2178 not in amounts_halire, "21,78 Kč = hallucinated 21.78 EUR"
        assert 2662 not in amounts_halire, "26,62 Kč = hallucinated 26.62 USD"

    def test_canva_amount(self):
        result = self.parser.parse(self.FIXTURE, FormatCsv.MONEY_BANKA)
        amounts = [tx.castka.to_halire() for tx in result.transakce]
        assert -70021 in amounts, "Canva -700,21 Kč chybí"

    def test_claude_ai_amount(self):
        result = self.parser.parse(self.FIXTURE, FormatCsv.MONEY_BANKA)
        amounts = [tx.castka.to_halire() for tx in result.transakce]
        assert -56483 in amounts, "Claude.ai -564,83 Kč chybí"

    def test_ps(self):
        result = self.parser.parse(self.FIXTURE, FormatCsv.MONEY_BANKA)
        assert result.pocatecni_stav is not None
        assert result.pocatecni_stav.to_halire() == 12731591

    def test_ks(self):
        result = self.parser.parse(self.FIXTURE, FormatCsv.MONEY_BANKA)
        assert result.konecny_stav is not None
        assert result.konecny_stav.to_halire() == 4344744

    def test_total_debet_matches_pdf(self):
        """Součet debetních obratů = 83 868,47 Kč (dle PDF)."""
        result = self.parser.parse(self.FIXTURE, FormatCsv.MONEY_BANKA)
        total = sum(abs(tx.castka.to_halire()) for tx in result.transakce if tx.castka.to_halire() < 0)
        assert total == 8386847

    def test_no_validation_errors(self):
        result = self.parser.parse(self.FIXTURE, FormatCsv.MONEY_BANKA)
        assert result.chyby == []
