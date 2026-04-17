"""BankovniVypis — entita bankovního výpisu."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from domain.shared.errors import ValidationError
from domain.shared.money import Money


@dataclass
class BankovniVypis:
    """Bankovní výpis — 1 CSV import = 1 výpis = 1 BV doklad.

    Identifikace výpisu:
    - cislo_vypisu (z PDF, např. "2025/2") — primární unikátní klíč
    - datum_od / datum_do — období transakcí
    - rok / mesic — zachováno pro kompatibilitu, ale už není unikátní
    """

    bankovni_ucet_id: int
    rok: int
    mesic: int
    pocatecni_stav: Money
    konecny_stav: Money
    pdf_path: str
    bv_doklad_id: int
    cislo_vypisu: str | None = None
    datum_od: date | None = None
    datum_do: date | None = None
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

    @property
    def label(self) -> str:
        """Lidsky čitelné označení výpisu."""
        if self.cislo_vypisu:
            return self.cislo_vypisu
        return f"{self.mesic:02d}/{self.rok}"

    @property
    def obdobi_text(self) -> str:
        """Formátované období."""
        if self.datum_od and self.datum_do:
            return (
                f"{self.datum_od.strftime('%d.%m.')}"
                f"–{self.datum_do.strftime('%d.%m.%Y')}"
            )
        return f"{self.mesic:02d}/{self.rok}"
