"""OcrUpload — entita nahraného souboru v OCR inboxu."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from domain.shared.errors import ValidationError


class StavUploadu(str, Enum):
    """Stav uploadu v OCR inboxu."""

    NAHRANY = "nahrany"
    ZPRACOVANY = "zpracovany"
    SCHVALENY = "schvaleny"
    ZAMITNUTY = "zamitnuty"


@dataclass
class OcrUpload:
    """Nahraný soubor v OCR inboxu."""

    file_path: str
    file_name: str
    file_hash: str
    mime_type: str
    stav: StavUploadu = StavUploadu.NAHRANY
    ocr_text: str | None = None
    ocr_method: str | None = None
    ocr_confidence: int | None = None
    parsed_data: dict[str, Any] | None = None
    vytvoreny_doklad_id: int | None = None
    error: str | None = None
    created_at: datetime | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.file_name or not self.file_name.strip():
            raise ValidationError("Název souboru je povinný.")
        if not self.file_hash:
            raise ValidationError("Hash souboru je povinný.")
        if self.mime_type not in (
            "application/pdf", "image/jpeg", "image/png",
        ):
            raise ValidationError(
                f"Nepodporovaný typ souboru: {self.mime_type}"
            )

    def zpracuj(
        self,
        ocr_text: str,
        ocr_method: str,
        ocr_confidence: int,
        parsed_data: dict[str, Any] | None,
    ) -> None:
        """Přechod NAHRANY → ZPRACOVANY po dokončení OCR."""
        if self.stav != StavUploadu.NAHRANY:
            raise ValidationError(
                f"Nelze zpracovat upload ve stavu {self.stav.value}."
            )
        self.ocr_text = ocr_text
        self.ocr_method = ocr_method
        self.ocr_confidence = ocr_confidence
        self.parsed_data = parsed_data
        self.stav = StavUploadu.ZPRACOVANY

    def schval(self, doklad_id: int) -> None:
        """Přechod ZPRACOVANY → SCHVALENY po vytvoření dokladu."""
        if self.stav != StavUploadu.ZPRACOVANY:
            raise ValidationError(
                f"Nelze schválit upload ve stavu {self.stav.value}."
            )
        self.vytvoreny_doklad_id = doklad_id
        self.stav = StavUploadu.SCHVALENY

    def zamitni(self) -> None:
        """Přechod ZPRACOVANY → ZAMITNUTY."""
        if self.stav not in (StavUploadu.NAHRANY, StavUploadu.ZPRACOVANY):
            raise ValidationError(
                f"Nelze zamítnout upload ve stavu {self.stav.value}."
            )
        self.stav = StavUploadu.ZAMITNUTY

    def oznac_chybu(self, msg: str) -> None:
        """Zaznamená chybu OCR."""
        self.error = msg
        self.stav = StavUploadu.ZPRACOVANY
        self.ocr_method = "failed"
        self.ocr_confidence = 0
