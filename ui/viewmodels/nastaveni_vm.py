"""NastaveniViewModel — firemní údaje v Nastavení."""

from __future__ import annotations

from datetime import date
from typing import Callable

from domain.firma.firma import Firma
from domain.shared.money import Money
from infrastructure.database.repositories.firma_repository import (
    SqliteFirmaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class NastaveniViewModel:
    """ViewModel pro stránku Nastavení — firma."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory
        self._firma: Firma | None = None
        self._error: str | None = None

    @property
    def firma(self) -> Firma | None:
        return self._firma

    @property
    def error(self) -> str | None:
        return self._error

    def load(self) -> None:
        try:
            uow = self._uow_factory()
            with uow:
                repo = SqliteFirmaRepository(uow)
                self._firma = repo.get()
            self._error = None
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__

    def save(self, firma: Firma) -> None:
        try:
            uow = self._uow_factory()
            with uow:
                repo = SqliteFirmaRepository(uow)
                repo.upsert(firma)
                uow.commit()
            self._firma = firma
            self._error = None
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
