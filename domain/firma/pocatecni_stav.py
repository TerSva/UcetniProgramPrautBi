"""PocatecniStav — počáteční zůstatek účtu na začátku účetního roku."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from domain.shared.errors import ValidationError
from domain.shared.money import Money


@dataclass(frozen=True)
class PocatecniStav:
    """Jeden počáteční zůstatek — účet + částka + strana (MD/DAL)."""

    ucet_kod: str
    castka: Money
    strana: Literal["MD", "DAL"]
    rok: int
    poznamka: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.ucet_kod or not self.ucet_kod.strip():
            raise ValidationError("Účet je povinný.")
        if not self.castka.is_positive:
            raise ValidationError("Částka musí být kladná.")
        if self.strana not in ("MD", "DAL"):
            raise ValidationError("Strana musí být 'MD' nebo 'DAL'.")
        if self.rok < 2000 or self.rok > 2100:
            raise ValidationError("Rok mimo platný rozsah.")
