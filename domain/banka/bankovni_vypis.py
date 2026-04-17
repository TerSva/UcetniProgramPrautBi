"""BankovniVypis — entita bankovního výpisu (1 měsíc = 1 výpis)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.shared.errors import ValidationError
from domain.shared.money import Money


@dataclass
class BankovniVypis:
    """Bankovní výpis — 1 CSV import = 1 výpis = 1 BV doklad."""

    bankovni_ucet_id: int
    rok: int
    mesic: int
    pocatecni_stav: Money
    konecny_stav: Money
    pdf_path: str
    bv_doklad_id: int
    csv_path: str | None = None
    created_at: datetime | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.mesic <= 12:
            raise ValidationError(
                f"Měsíc musí být 1–12, dostal: {self.mesic}"
            )
        if self.rok < 2000 or self.rok > 2099:
            raise ValidationError(
                f"Neplatný rok: {self.rok}"
            )
        if not self.pdf_path:
            raise ValidationError("PDF výpisu je povinný.")
