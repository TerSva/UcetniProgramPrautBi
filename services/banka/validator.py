"""CsvPdfValidator — porovnání CSV transakcí s PDF výpisem."""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.shared.money import Money
from infrastructure.banka.csv_parser import ParsedTransaction
from infrastructure.banka.pdf_statement_parser import (
    ParsedPdfTransaction,
    ParsedStatement,
)


@dataclass(frozen=True)
class MatchedTransaction:
    """Transakce nalezená v CSV i PDF."""

    csv: ParsedTransaction
    pdf: ParsedPdfTransaction


@dataclass(frozen=True)
class ValidationResult:
    """Výsledek porovnání CSV vs PDF."""

    is_valid: bool
    transakce_shoduji: list[MatchedTransaction] = field(default_factory=list)
    pouze_v_csv: list[ParsedTransaction] = field(default_factory=list)
    pouze_v_pdf: list[ParsedPdfTransaction] = field(default_factory=list)
    ps_pdf: Money | None = None
    ks_pdf: Money | None = None
    varovani: list[str] = field(default_factory=list)


class CsvPdfValidator:
    """Porovnává CSV transakce s PDF výpisem."""

    def validate(
        self,
        csv_transakce: list[ParsedTransaction],
        pdf_statement: ParsedStatement,
    ) -> ValidationResult:
        varovani_base: list[str] = []

        if not csv_transakce:
            varovani_base.append(
                "CSV neobsahuje žádné transakce — zkontrolujte formát CSV "
                "(hlavičky sloupců musí odpovídat zvolenému formátu banky)"
            )

        if pdf_statement.chyby:
            return ValidationResult(
                is_valid=False,
                varovani=pdf_statement.chyby + varovani_base,
                ps_pdf=pdf_statement.pocatecni_stav,
                ks_pdf=pdf_statement.konecny_stav,
            )

        matched: list[MatchedTransaction] = []
        pouze_csv: list[ParsedTransaction] = []
        pdf_used: set[int] = set()

        pdf_txs = pdf_statement.transakce

        for csv_tx in csv_transakce:
            found = False
            for i, pdf_tx in enumerate(pdf_txs):
                if i in pdf_used:
                    continue
                if self._match(csv_tx, pdf_tx):
                    matched.append(MatchedTransaction(csv=csv_tx, pdf=pdf_tx))
                    pdf_used.add(i)
                    found = True
                    break
            if not found:
                pouze_csv.append(csv_tx)

        pouze_pdf = [
            pdf_txs[i] for i in range(len(pdf_txs)) if i not in pdf_used
        ]

        varovani: list[str] = list(varovani_base)
        if pouze_csv:
            varovani.append(
                f"{len(pouze_csv)} transakce v CSV, ale nejsou na PDF"
            )
        if pouze_pdf:
            varovani.append(
                f"{len(pouze_pdf)} transakce na PDF, ale chybí v CSV"
            )

        # Valid if no transactions only in PDF (those are critical)
        is_valid = len(pouze_pdf) == 0

        return ValidationResult(
            is_valid=is_valid,
            transakce_shoduji=matched,
            pouze_v_csv=pouze_csv,
            pouze_v_pdf=pouze_pdf,
            ps_pdf=pdf_statement.pocatecni_stav,
            ks_pdf=pdf_statement.konecny_stav,
            varovani=varovani,
        )

    @staticmethod
    def _match(
        csv_tx: ParsedTransaction,
        pdf_tx: ParsedPdfTransaction,
    ) -> bool:
        """Match CSV and PDF transaction by date + amount."""
        # Date match (datum_zauctovani or datum_transakce)
        date_ok = (
            csv_tx.datum_zauctovani == pdf_tx.datum_transakce
            or csv_tx.datum_transakce == pdf_tx.datum_transakce
        )
        if not date_ok:
            return False

        # Amount match
        if csv_tx.castka.to_halire() != pdf_tx.castka.to_halire():
            return False

        # VS match (if both have it)
        if csv_tx.variabilni_symbol and pdf_tx.variabilni_symbol:
            if csv_tx.variabilni_symbol != pdf_tx.variabilni_symbol:
                return False

        return True
