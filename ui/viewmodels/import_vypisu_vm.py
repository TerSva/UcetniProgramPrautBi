"""ImportVypisuViewModel — ViewModel pro stránku importu bankovních výpisů."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from domain.banka.bankovni_ucet import BankovniUcet
from domain.shared.money import Money
from domain.ucetnictvi.ucet import Ucet
from infrastructure.banka.csv_parser import ParsedTransaction
from infrastructure.database.repositories.banka_repository import (
    SqliteBankovniUcetRepository,
)
from infrastructure.database.repositories.uctova_osnova_repository import (
    SqliteUctovaOsnovaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.banka.import_vypisu import ImportResult, ImportVypisuCommand
from services.banka.validator import ValidationResult
from services.queries.banka import BankovniUctyQuery


class ImportVypisuViewModel:
    """ViewModel pro 3-krokový import bankovního výpisu."""

    def __init__(
        self,
        ucty_query: BankovniUctyQuery,
        import_cmd: ImportVypisuCommand,
        uow_factory: Callable[[], SqliteUnitOfWork] | None = None,
    ) -> None:
        self._ucty_query = ucty_query
        self._import_cmd = import_cmd
        self._uow_factory = uow_factory

        self._ucty: list[BankovniUcet] = []
        self._selected_ucet_id: int | None = None
        self._csv_path: Path | None = None
        self._pdf_path: Path | None = None
        self._validation_result: ValidationResult | None = None
        self._import_result: ImportResult | None = None
        self._error: str | None = None

    # ── Properties ──

    @property
    def ucty(self) -> list[BankovniUcet]:
        return self._ucty

    @property
    def selected_ucet_id(self) -> int | None:
        return self._selected_ucet_id

    @selected_ucet_id.setter
    def selected_ucet_id(self, value: int | None) -> None:
        self._selected_ucet_id = value

    @property
    def csv_path(self) -> Path | None:
        return self._csv_path

    @csv_path.setter
    def csv_path(self, value: Path | None) -> None:
        self._csv_path = value

    @property
    def pdf_path(self) -> Path | None:
        return self._pdf_path

    @pdf_path.setter
    def pdf_path(self, value: Path | None) -> None:
        self._pdf_path = value

    @property
    def validation_result(self) -> ValidationResult | None:
        return self._validation_result

    @property
    def import_result(self) -> ImportResult | None:
        return self._import_result

    @property
    def error(self) -> str | None:
        return self._error

    # ── Actions ──

    def load_ucty(self) -> None:
        """Načte seznam aktivních bankovních účtů."""
        try:
            self._ucty = self._ucty_query.list_aktivni()
            self._error = None
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)

    def validate(self) -> ValidationResult | None:
        """Validuje CSV vs PDF. Vrátí výsledek."""
        if not self._csv_path or not self._pdf_path or not self._selected_ucet_id:
            self._error = "Vyplňte všechna pole (účet, CSV, PDF)"
            return None

        try:
            self._validation_result = self._import_cmd.validate(
                csv_path=self._csv_path,
                pdf_path=self._pdf_path,
                ucet_id=self._selected_ucet_id,
            )
            self._error = None
            return self._validation_result
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return None

    def execute_import(self) -> ImportResult | None:
        """Provede import. Vyžaduje úspěšnou validaci."""
        if self._validation_result is None:
            self._error = "Nejdříve proveďte validaci"
            return None

        if not self._csv_path or not self._pdf_path or not self._selected_ucet_id:
            self._error = "Chybí vstupní data"
            return None

        # Matched transakce z CSV+PDF páru, nebo všechny CSV pokud PDF
        # nemá transakce (např. ČS výpis — jiný layout)
        matched_txs = [m.csv for m in self._validation_result.transakce_shoduji]
        if not matched_txs:
            matched_txs = list(self._validation_result.pouze_v_csv)
        ps = self._validation_result.ps_pdf or Money(0)
        ks = self._validation_result.ks_pdf or Money(0)

        try:
            self._import_result = self._import_cmd.execute(
                csv_path=self._csv_path,
                pdf_path=self._pdf_path,
                ucet_id=self._selected_ucet_id,
                matched_transactions=matched_txs,
                ps=ps,
                ks=ks,
                cislo_vypisu=self._validation_result.cislo_vypisu,
                datum_od=self._validation_result.datum_od,
                datum_do=self._validation_result.datum_do,
            )
            self._error = None
            return self._import_result
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return None

    def reset(self) -> None:
        """Reset stavu pro nový import."""
        self._csv_path = None
        self._pdf_path = None
        self._validation_result = None
        self._import_result = None
        self._error = None

    def get_analytiky_221(self) -> list[Ucet]:
        """Vrátí analytické účty pod 221 (pro dialog založení účtu)."""
        if self._uow_factory is None:
            return []
        try:
            uow = self._uow_factory()
            with uow:
                repo = SqliteUctovaOsnovaRepository(uow)
                return repo.get_analytiky("221")
        except Exception:  # noqa: BLE001
            return []

    def zaloz_ucet(self, ucet: BankovniUcet) -> bool:
        """Založí nový bankovní účet. Vrátí True při úspěchu."""
        if self._uow_factory is None:
            self._error = "UoW factory není nakonfigurována"
            return False
        try:
            uow = self._uow_factory()
            with uow:
                repo = SqliteBankovniUcetRepository(uow)
                repo.add(ucet)
                uow.commit()
            self._error = None
            return True
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return False
