"""OcrInboxQuery — seznam uploadů v OCR inboxu."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable

from domain.ocr.ocr_upload import StavUploadu
from domain.shared.money import Money
from infrastructure.database.repositories.ocr_upload_repository import (
    SqliteOcrUploadRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from infrastructure.ocr.invoice_parser import ParsedInvoice


@dataclass(frozen=True)
class OcrInboxItem:
    """Položka v OCR inboxu."""

    id: int
    file_name: str
    mime_type: str
    stav: str
    created_at: datetime | None
    parsed_typ: str | None
    parsed_dodavatel: str | None
    parsed_castka: Money | None
    parsed_datum: date | None
    parsed_cislo: str | None
    is_pytlovani: bool
    pytlovani_jmeno: str | None
    parsed_vs: str | None
    ocr_method: str | None
    ocr_confidence: int | None
    file_path: str | None = None


class OcrInboxQuery:
    """Query pro seznam položek v OCR inboxu."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(
        self, stav: StavUploadu | None = None,
    ) -> list[OcrInboxItem]:
        uow = self._uow_factory()
        with uow:
            repo = SqliteOcrUploadRepository(uow)
            uploads = repo.list_by_stav(stav)

        items: list[OcrInboxItem] = []
        for u in uploads:
            parsed_typ = None
            parsed_dodavatel = None
            parsed_castka = None
            parsed_datum = None
            parsed_cislo = None
            parsed_vs = None
            is_pytlovani = False
            pytlovani_jmeno = None

            if u.parsed_data:
                parsed = ParsedInvoice.from_dict(u.parsed_data)
                if parsed.typ_dokladu:
                    parsed_typ = parsed.typ_dokladu.value
                parsed_dodavatel = parsed.dodavatel_nazev
                parsed_castka = parsed.castka_celkem
                parsed_datum = parsed.datum_vystaveni
                parsed_cislo = parsed.cislo_dokladu
                parsed_vs = parsed.variabilni_symbol
                is_pytlovani = parsed.is_pytlovani
                pytlovani_jmeno = parsed.pytlovani_jmeno

            items.append(OcrInboxItem(
                id=u.id,
                file_name=u.file_name,
                mime_type=u.mime_type,
                stav=u.stav.value,
                created_at=u.created_at,
                parsed_typ=parsed_typ,
                parsed_dodavatel=parsed_dodavatel,
                parsed_castka=parsed_castka,
                parsed_datum=parsed_datum,
                parsed_cislo=parsed_cislo,
                is_pytlovani=is_pytlovani,
                pytlovani_jmeno=pytlovani_jmeno,
                parsed_vs=parsed_vs,
                ocr_method=u.ocr_method,
                ocr_confidence=u.ocr_confidence,
                file_path=u.file_path,
            ))

        return items

    def count_nezpracovane(self) -> int:
        """Počet uploadů ve stavu ZPRACOVANY (čekají na review)."""
        uow = self._uow_factory()
        with uow:
            repo = SqliteOcrUploadRepository(uow)
            return repo.count_by_stav(StavUploadu.ZPRACOVANY)
