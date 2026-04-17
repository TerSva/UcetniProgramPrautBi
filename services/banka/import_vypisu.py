"""ImportVypisuCommand — import bankovního výpisu (CSV + PDF)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from domain.banka.bankovni_transakce import BankovniTransakce
from domain.banka.bankovni_ucet import BankovniUcet
from domain.banka.bankovni_vypis import BankovniVypis
from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.money import Money
from infrastructure.banka.csv_parser import CsvBankParser, ParsedTransaction
from infrastructure.banka.pdf_statement_parser import (
    ParsedStatement,
    PdfStatementParser,
)
from infrastructure.database.repositories.banka_repository import (
    SqliteBankovniTransakceRepository,
    SqliteBankovniUcetRepository,
    SqliteBankovniVypisRepository,
)
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.banka.validator import CsvPdfValidator, ValidationResult


@dataclass(frozen=True)
class ImportResult:
    """Výsledek importu výpisu."""

    success: bool
    vypis_id: int | None = None
    doklad_cislo: str | None = None
    pocet_transakci: int = 0
    error: str | None = None


class ImportVypisuCommand:
    """Import CSV + PDF bankovního výpisu."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        upload_dir: Path,
    ) -> None:
        self._uow_factory = uow_factory
        self._upload_dir = upload_dir
        self._csv_parser = CsvBankParser()
        self._pdf_parser = PdfStatementParser()
        self._validator = CsvPdfValidator()

    def validate(
        self,
        csv_path: Path,
        pdf_path: Path,
        ucet_id: int,
    ) -> ValidationResult:
        """Validace CSV vs PDF — vrátí report."""
        uow = self._uow_factory()
        with uow:
            ucet_repo = SqliteBankovniUcetRepository(uow)
            ucet = ucet_repo.get(ucet_id)

        if ucet is None:
            from services.banka.validator import ValidationResult
            return ValidationResult(
                is_valid=False,
                varovani=[f"Účet s ID {ucet_id} nenalezen"],
            )

        csv_txs = self._csv_parser.parse(csv_path, ucet.format_csv)
        pdf_stmt = self._pdf_parser.parse(pdf_path, ucet.format_csv)

        return self._validator.validate(csv_txs, pdf_stmt)

    def execute(
        self,
        csv_path: Path,
        pdf_path: Path,
        ucet_id: int,
        matched_transactions: list[ParsedTransaction],
        ps: Money,
        ks: Money,
        cislo_vypisu: str | None = None,
        datum_od: date | None = None,
        datum_do: date | None = None,
    ) -> ImportResult:
        """Naimportuje validované transakce do DB."""
        if not matched_transactions:
            return ImportResult(success=False, error="Žádné transakce k importu")

        # Determine rok/mesic — prefer datum_do (konec období), fallback na transakce
        if datum_do:
            rok = datum_do.year
            mesic = datum_do.month
        else:
            first_date = matched_transactions[0].datum_zauctovani
            rok = first_date.year
            mesic = first_date.month

        uow = self._uow_factory()
        with uow:
            ucet_repo = SqliteBankovniUcetRepository(uow)
            ucet = ucet_repo.get(ucet_id)
            if ucet is None:
                return ImportResult(
                    success=False, error="Účet nenalezen",
                )

            # Check for duplicate — use cislo_vypisu if available
            vypis_repo = SqliteBankovniVypisRepository(uow)
            if cislo_vypisu:
                existing = vypis_repo.get_by_cislo(ucet_id, cislo_vypisu)
                if existing is not None:
                    return ImportResult(
                        success=False,
                        error=f"Výpis {cislo_vypisu} pro tento účet již existuje",
                    )
            else:
                existing = vypis_repo.get_by_ucet_mesic(ucet_id, rok, mesic)
                if existing is not None:
                    return ImportResult(
                        success=False,
                        error=f"Výpis {rok}/{mesic:02d} pro tento účet již existuje",
                    )

            # Store PDF
            self._upload_dir.mkdir(parents=True, exist_ok=True)
            suffix = cislo_vypisu.replace("/", "_") if cislo_vypisu else f"{mesic:02d}"
            pdf_dest = (
                self._upload_dir
                / f"{ucet.ucet_kod}_{rok}_{suffix}.pdf"
            )
            shutil.copy2(pdf_path, pdf_dest)

            # Store CSV
            csv_dest = (
                self._upload_dir
                / f"{ucet.ucet_kod}_{rok}_{suffix}.csv"
            )
            shutil.copy2(csv_path, csv_dest)

            # Create BV doklad
            doklady_repo = SqliteDokladyRepository(uow)
            if cislo_vypisu:
                # e.g. "2025/2" → cislo_label = "2", popis_label = "2025/2"
                parts = cislo_vypisu.split("/")
                cislo_label = parts[-1] if len(parts) > 1 else cislo_vypisu
                popis_label = cislo_vypisu
            else:
                cislo_label = f"{mesic:02d}"
                popis_label = f"{mesic:02d}"
            cislo = f"BV-{rok}-{cislo_label}"

            # Sum up amounts
            celkem = Money(0)
            for tx in matched_transactions:
                h = tx.castka.to_halire()
                if h < 0:
                    h = -h
                celkem = Money(celkem.to_halire() + h)

            doklad = Doklad(
                cislo=cislo,
                typ=TypDokladu.BANKOVNI_VYPIS,
                datum_vystaveni=datum_do or date(rok, mesic, 1),
                castka_celkem=celkem,
                popis=f"Bankovní výpis {ucet.nazev} {popis_label}/{rok}",
            )
            doklad = doklady_repo.add(doklad)

            # Create vypis
            vypis = BankovniVypis(
                bankovni_ucet_id=ucet_id,
                rok=rok,
                mesic=mesic,
                pocatecni_stav=ps,
                konecny_stav=ks,
                pdf_path=str(pdf_dest),
                csv_path=str(csv_dest),
                bv_doklad_id=doklad.id,
                cislo_vypisu=cislo_vypisu,
                datum_od=datum_od,
                datum_do=datum_do,
            )
            vypis_repo.add(vypis)

            # Create transakce
            tx_repo = SqliteBankovniTransakceRepository(uow)
            for ptx in matched_transactions:
                tx = BankovniTransakce(
                    bankovni_vypis_id=vypis.id,
                    datum_transakce=ptx.datum_transakce,
                    datum_zauctovani=ptx.datum_zauctovani,
                    castka=ptx.castka,
                    smer=ptx.smer,
                    variabilni_symbol=ptx.variabilni_symbol,
                    konstantni_symbol=ptx.konstantni_symbol,
                    specificky_symbol=ptx.specificky_symbol,
                    protiucet=ptx.protiucet,
                    popis=ptx.popis,
                    row_hash=ptx.row_hash,
                )
                tx_repo.add(tx)

            uow.commit()

        return ImportResult(
            success=True,
            vypis_id=vypis.id,
            doklad_cislo=cislo,
            pocet_transakci=len(matched_transactions),
        )
