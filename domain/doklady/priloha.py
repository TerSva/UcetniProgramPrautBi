"""PrilohaDokladu — doménová entita pro přílohu (PDF) k dokladu.

Frozen dataclass — příloha je po vytvoření immutable (value object s identitou).
Jeden doklad může mít více příloh (1:N).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.shared.errors import ValidationError


@dataclass(frozen=True)
class PrilohaDokladu:
    """Příloha (typicky PDF) přiřazená k dokladu."""

    id: int | None
    doklad_id: int
    nazev_souboru: str
    relativni_cesta: str
    velikost_bytes: int
    mime_type: str
    vytvoreno: datetime

    def __post_init__(self) -> None:
        if not self.nazev_souboru:
            raise ValidationError("Název souboru nesmí být prázdný.")
        if self.velikost_bytes < 0:
            raise ValidationError("Velikost nemůže být záporná.")
