"""Ucet — entita účtu z účtové osnovy.

Podporuje syntetické účty (3 číslice, např. '501') i analytické účty
(formát xxx.yyy, např. '501.100'). Analytika odkazuje na parent syntetický
účet přes parent_kod.
"""

from __future__ import annotations

import re

from domain.shared.errors import ValidationError
from domain.ucetnictvi.typy import TypUctu

_SYNTETIC_RE = re.compile(r"^\d{3}$")
_ANALYTIC_RE = re.compile(r"^\d{3}\.\w{1,3}$")


class Ucet:
    """Účet z účtové osnovy. Identita podle cislo (PK)."""

    def __init__(
        self,
        cislo: str,
        nazev: str,
        typ: TypUctu,
        je_aktivni: bool = True,
        parent_kod: str | None = None,
        popis: str | None = None,
        je_danovy: bool | None = None,
    ) -> None:
        # Validace cislo
        if not isinstance(cislo, str) or not cislo.strip():
            raise ValidationError("Číslo účtu nesmí být prázdné.")

        is_analytic = "." in cislo

        if is_analytic:
            if not _ANALYTIC_RE.match(cislo):
                raise ValidationError(
                    f"Neplatný kód analytiky: {cislo!r}. "
                    f"Očekáván formát xxx.yyy (např. 501.100)."
                )
            # Analytika musí mít parent_kod
            if parent_kod is None:
                raise ValidationError(
                    f"Analytika {cislo} nemá parent_kod."
                )
            expected_parent = cislo.split(".")[0]
            if parent_kod != expected_parent:
                raise ValidationError(
                    f"Parent_kod {parent_kod!r} neodpovídá "
                    f"syntetiku {expected_parent!r} v kódu {cislo!r}."
                )
        else:
            if not _SYNTETIC_RE.match(cislo):
                raise ValidationError(
                    f"Číslo účtu musí být 3 číslice (syntetický) "
                    f"nebo xxx.yyy (analytický), got: {cislo!r}"
                )
            if parent_kod is not None:
                raise ValidationError(
                    f"Syntetický účet {cislo} nesmí mít parent_kod."
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
        self._parent_kod = parent_kod
        self._popis = popis
        self._je_danovy = je_danovy

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

    @property
    def parent_kod(self) -> str | None:
        return self._parent_kod

    @property
    def popis(self) -> str | None:
        return self._popis

    @property
    def je_danovy(self) -> bool | None:
        """Daňová uznatelnost: True/False/None (None = irrelevantní pro A/P/Z)."""
        return self._je_danovy

    def nastav_danovost(self, je_danovy: bool | None) -> None:
        """Změní příznak daňovosti (pouze pro N/V účty)."""
        if je_danovy is not None and self._typ.value not in ("N", "V"):
            raise ValidationError(
                f"Daňovost lze nastavit jen pro N (náklady) / V (výnosy), "
                f"ne pro {self._typ.value} ({self._cislo})."
            )
        self._je_danovy = je_danovy

    @property
    def is_analytic(self) -> bool:
        """True pokud je to analytický účet (obsahuje tečku)."""
        return "." in self._cislo

    @property
    def syntetic_kod(self) -> str:
        """Vrátí syntetický kód. Pro analytiku '501.100' vrátí '501'."""
        if self.is_analytic:
            return self._cislo.split(".")[0]
        return self._cislo

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

    def uprav_popis(self, novy_popis: str | None) -> None:
        """Změní popis účtu."""
        self._popis = novy_popis

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Ucet):
            return NotImplemented
        return self._cislo == other._cislo

    def __hash__(self) -> int:
        return hash(self._cislo)

    def __repr__(self) -> str:
        return f"Ucet(cislo={self._cislo!r}, nazev={self._nazev!r}, typ={self._typ.value})"
