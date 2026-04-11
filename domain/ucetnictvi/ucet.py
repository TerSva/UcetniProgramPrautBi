"""Ucet — entita účtu z účtové osnovy."""

from __future__ import annotations

import re

from domain.shared.errors import ValidationError
from domain.ucetnictvi.typy import TypUctu

_CISLO_RE = re.compile(r"^\d{3,6}$")


class Ucet:
    """Účet z účtové osnovy. Identita podle cislo (PK)."""

    def __init__(
        self,
        cislo: str,
        nazev: str,
        typ: TypUctu,
        je_aktivni: bool = True,
    ) -> None:
        # Validace cislo
        if not isinstance(cislo, str) or not cislo.strip():
            raise ValidationError("Číslo účtu nesmí být prázdné.")
        if not _CISLO_RE.match(cislo):
            raise ValidationError(
                f"Číslo účtu musí být 3-6 číslic, got: {cislo!r}"
            )
        # Validace nazev
        if not isinstance(nazev, str) or not nazev.strip():
            raise ValidationError("Název účtu nesmí být prázdný.")
        if len(nazev) > 200:
            raise ValidationError("Název účtu max 200 znaků.")
        # Validace typ
        if not isinstance(typ, TypUctu):
            raise TypeError("typ musí být TypUctu")

        self._cislo = cislo
        self._nazev = nazev
        self._typ = typ
        self._je_aktivni = je_aktivni

    @property
    def cislo(self) -> str:
        return self._cislo

    @property
    def nazev(self) -> str:
        return self._nazev

    @property
    def typ(self) -> TypUctu:
        return self._typ

    @property
    def je_aktivni(self) -> bool:
        return self._je_aktivni

    def deaktivuj(self) -> None:
        """Deaktivuje účet — nelze ho dál používat v nových zápisech."""
        self._je_aktivni = False

    def aktivuj(self) -> None:
        """Aktivuje účet zpět."""
        self._je_aktivni = True

    def uprav_nazev(self, novy_nazev: str) -> None:
        """Změní název účtu."""
        if not isinstance(novy_nazev, str) or not novy_nazev.strip():
            raise ValidationError("Název účtu nesmí být prázdný.")
        if len(novy_nazev) > 200:
            raise ValidationError("Název účtu max 200 znaků.")
        self._nazev = novy_nazev

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Ucet):
            return NotImplemented
        return self._cislo == other._cislo

    def __hash__(self) -> int:
        return hash(self._cislo)

    def __repr__(self) -> str:
        return f"Ucet(cislo={self._cislo!r}, nazev={self._nazev!r}, typ={self._typ.value})"
