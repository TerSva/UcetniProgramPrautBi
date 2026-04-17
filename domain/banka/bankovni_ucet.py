"""BankovniUcet — entita bankovního účtu."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.doklady.typy import Mena
from domain.shared.errors import ValidationError


class FormatCsv(str, Enum):
    """Formát CSV exportu banky."""

    MONEY_BANKA = "money_banka"
    CESKA_SPORITELNA = "ceska_sporitelna"
    OBECNY = "obecny"


@dataclass
class BankovniUcet:
    """Bankovní účet firmy."""

    nazev: str
    cislo_uctu: str
    ucet_kod: str  # "221.001"
    format_csv: FormatCsv = FormatCsv.OBECNY
    mena: Mena = Mena.CZK
    je_aktivni: bool = True
    poznamka: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.nazev or not self.nazev.strip():
            raise ValidationError("Název účtu je povinný.")
        if not self.cislo_uctu or not self.cislo_uctu.strip():
            raise ValidationError("Číslo účtu je povinné.")
        if not self.ucet_kod or not self.ucet_kod.strip():
            raise ValidationError("Kód účtu je povinný.")
