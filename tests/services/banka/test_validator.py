"""Testy pro CsvPdfValidator."""

from __future__ import annotations

from datetime import date

from domain.shared.money import Money
from infrastructure.banka.csv_parser import ParsedTransaction
from infrastructure.banka.pdf_statement_parser import ParsedPdfTransaction, ParsedStatement
from services.banka.validator import CsvPdfValidator


def _csv_tx(datum, castka_hal, vs=None) -> ParsedTransaction:
    return ParsedTransaction(
        datum_transakce=datum,
        datum_zauctovani=datum,
        castka=Money(castka_hal),
        smer="P" if castka_hal > 0 else "V",
        variabilni_symbol=vs,
        konstantni_symbol=None,
        specificky_symbol=None,
        protiucet=None,
        popis=None,
        row_hash=f"hash_{datum}_{castka_hal}_{vs}",
    )


def _pdf_tx(datum, castka_hal, vs=None) -> ParsedPdfTransaction:
    return ParsedPdfTransaction(
        datum_transakce=datum,
        datum_zauctovani=None,
        castka=Money(castka_hal),
        variabilni_symbol=vs,
        popis=None,
    )


class TestCsvPdfValidator:

    def setup_method(self):
        self.validator = CsvPdfValidator()

    def test_all_match(self):
        d = date(2025, 3, 15)
        csv_txs = [_csv_tx(d, 10000), _csv_tx(d, -5000)]
        pdf_stmt = ParsedStatement(
            pocatecni_stav=Money(100000),
            konecny_stav=Money(105000),
            transakce=[_pdf_tx(d, 10000), _pdf_tx(d, -5000)],
        )
        result = self.validator.validate(csv_txs, pdf_stmt)
        assert result.is_valid
        assert len(result.transakce_shoduji) == 2
        assert len(result.pouze_v_csv) == 0
        assert len(result.pouze_v_pdf) == 0

    def test_csv_only_warning(self):
        d = date(2025, 3, 15)
        csv_txs = [_csv_tx(d, 10000), _csv_tx(d, -5000)]
        pdf_stmt = ParsedStatement(
            pocatecni_stav=Money(100000),
            konecny_stav=Money(105000),
            transakce=[_pdf_tx(d, 10000)],
        )
        result = self.validator.validate(csv_txs, pdf_stmt)
        assert result.is_valid  # CSV-only is warning, not blocking
        assert len(result.pouze_v_csv) == 1

    def test_pdf_only_invalid(self):
        d = date(2025, 3, 15)
        csv_txs = [_csv_tx(d, 10000)]
        pdf_stmt = ParsedStatement(
            pocatecni_stav=Money(100000),
            konecny_stav=Money(105000),
            transakce=[_pdf_tx(d, 10000), _pdf_tx(d, -5000)],
        )
        result = self.validator.validate(csv_txs, pdf_stmt)
        assert not result.is_valid
        assert len(result.pouze_v_pdf) == 1

    def test_pdf_errors_propagated(self):
        csv_txs = [_csv_tx(date(2025, 3, 15), 10000)]
        pdf_stmt = ParsedStatement(
            pocatecni_stav=None,
            konecny_stav=None,
            chyby=["Chyba čtení PDF"],
        )
        result = self.validator.validate(csv_txs, pdf_stmt)
        assert not result.is_valid
        assert "Chyba čtení PDF" in result.varovani

    def test_vs_mismatch_not_matched(self):
        d = date(2025, 3, 15)
        csv_txs = [_csv_tx(d, 10000, vs="111")]
        pdf_stmt = ParsedStatement(
            pocatecni_stav=Money(100000),
            konecny_stav=Money(110000),
            transakce=[_pdf_tx(d, 10000, vs="222")],
        )
        result = self.validator.validate(csv_txs, pdf_stmt)
        assert not result.is_valid
        assert len(result.pouze_v_csv) == 1
        assert len(result.pouze_v_pdf) == 1

    def test_ps_ks_from_pdf(self):
        csv_txs = [_csv_tx(date(2025, 3, 15), 10000)]
        pdf_stmt = ParsedStatement(
            pocatecni_stav=Money(100000),
            konecny_stav=Money(110000),
            transakce=[_pdf_tx(date(2025, 3, 15), 10000)],
        )
        result = self.validator.validate(csv_txs, pdf_stmt)
        assert result.ps_pdf == Money(100000)
        assert result.ks_pdf == Money(110000)
