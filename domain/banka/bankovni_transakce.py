"""BankovniTransakce — entita jedné transakce z bankovního výpisu."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Literal

from domain.shared.errors import ValidationError
from domain.shared.money import Money


class StavTransakce(str, Enum):
    """Stav zpracování bankovní transakce."""

    NESPAROVANO = "nesparovano"
    SPAROVANO = "sparovano"
    AUTO_ZAUCTOVANO = "auto_zauctovano"
    IGNOROVANO = "ignorovano"


@dataclass
class BankovniTransakce:
    """Jedna transakce z bankovního výpisu."""

    bankovni_vypis_id: int
    datum_transakce: date
    datum_zauctovani: date
    castka: Money
    smer: Literal["P", "V"]
    row_hash: str
    variabilni_symbol: str | None = None
    konstantni_symbol: str | None = None
    specificky_symbol: str | None = None
    protiucet: str | None = None
    popis: str | None = None
    stav: StavTransakce = StavTransakce.NESPAROVANO
    sparovany_doklad_id: int | None = None
    ucetni_zapis_id: int | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if self.smer not in ("P", "V"):
            raise ValidationError(f"Neplatný směr: {self.smer}")

    def sparuj(self, doklad_id: int) -> None:
        """Spáruj transakci s dokladem."""
        self.sparovany_doklad_id = doklad_id
        self.stav = StavTransakce.SPAROVANO

    def auto_zauctuj(self, ucetni_zapis_id: int) -> None:
        """Označ jako automaticky zaúčtovanou."""
        self.ucetni_zapis_id = ucetni_zapis_id
        self.stav = StavTransakce.AUTO_ZAUCTOVANO

    def ignoruj(self) -> None:
        """Označ jako ignorovanou."""
        self.stav = StavTransakce.IGNOROVANO

    def obnov(self) -> None:
        """Vrátí ignorovanou transakci zpět na NESPAROVANO.

        Funguje jen pro IGNOROVANO — pro SPAROVANO/AUTO_ZAUCTOVANO existují
        navázané záznamy (úhrady, účetní zápisy), jejichž rušení vyžaduje
        odstornovat celý výpis.
        """
        if self.stav != StavTransakce.IGNOROVANO:
            raise ValidationError(
                f"Lze obnovit pouze ignorovanou transakci, "
                f"aktuální stav: {self.stav.value}"
            )
        self.stav = StavTransakce.NESPAROVANO
