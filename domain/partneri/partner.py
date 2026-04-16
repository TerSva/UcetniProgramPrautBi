"""Partner — doménová entita pro evidenci odběratelů, dodavatelů a společníků.

Pure Python + stdlib. Žádný import z infrastructure/, services/, ui/.
"""

from __future__ import annotations

import re
from decimal import Decimal
from enum import Enum

from domain.shared.errors import ValidationError

_ICO_PATTERN = re.compile(r"^\d{8}$")


class KategoriePartnera(Enum):
    """Kategorie partnera."""

    ODBERATEL = "odberatel"
    DODAVATEL = "dodavatel"
    SPOLECNIK = "spolecnik"
    KOMBINOVANY = "kombinovany"


class Partner:
    """Doménová entita Partner.

    Má identitu (id), soft-delete (je_aktivni), a společnické rozšíření.
    """

    def __init__(
        self,
        nazev: str,
        kategorie: KategoriePartnera,
        ico: str | None = None,
        dic: str | None = None,
        adresa: str | None = None,
        bankovni_ucet: str | None = None,
        email: str | None = None,
        telefon: str | None = None,
        poznamka: str | None = None,
        je_aktivni: bool = True,
        podil_procent: Decimal | None = None,
        ucet_pohledavka: str | None = None,
        ucet_zavazek: str | None = None,
        id: int | None = None,
    ) -> None:
        # Validace nazev
        if not nazev or not nazev.strip():
            raise ValidationError("Název partnera je povinný.")

        # Validace ICO
        if ico is not None and not _ICO_PATTERN.match(ico):
            raise ValidationError(
                f"IČO musí mít 8 číslic: {ico!r}."
            )

        # Validace společníka
        if kategorie == KategoriePartnera.SPOLECNIK:
            if podil_procent is None:
                raise ValidationError(
                    "Společník musí mít vyplněný podíl."
                )
            if podil_procent <= 0 or podil_procent > 100:
                raise ValidationError(
                    f"Podíl musí být v rozsahu (0, 100]: {podil_procent}."
                )

        self._id = id
        self._nazev = nazev.strip()
        self._kategorie = kategorie
        self._ico = ico
        self._dic = dic
        self._adresa = adresa
        self._bankovni_ucet = bankovni_ucet
        self._email = email
        self._telefon = telefon
        self._poznamka = poznamka
        self._je_aktivni = je_aktivni
        self._podil_procent = podil_procent
        self._ucet_pohledavka = ucet_pohledavka
        self._ucet_zavazek = ucet_zavazek

    # --- Properties ---

    @property
    def id(self) -> int | None:
        return self._id

    @property
    def nazev(self) -> str:
        return self._nazev

    @property
    def kategorie(self) -> KategoriePartnera:
        return self._kategorie

    @property
    def ico(self) -> str | None:
        return self._ico

    @property
    def dic(self) -> str | None:
        return self._dic

    @property
    def adresa(self) -> str | None:
        return self._adresa

    @property
    def bankovni_ucet(self) -> str | None:
        return self._bankovni_ucet

    @property
    def email(self) -> str | None:
        return self._email

    @property
    def telefon(self) -> str | None:
        return self._telefon

    @property
    def poznamka(self) -> str | None:
        return self._poznamka

    @property
    def je_aktivni(self) -> bool:
        return self._je_aktivni

    @property
    def podil_procent(self) -> Decimal | None:
        return self._podil_procent

    @property
    def ucet_pohledavka(self) -> str | None:
        return self._ucet_pohledavka

    @property
    def ucet_zavazek(self) -> str | None:
        return self._ucet_zavazek

    # --- Mutace ---

    def uprav(
        self,
        nazev: str | None = None,
        kategorie: KategoriePartnera | None = None,
        ico: str | None = ...,  # type: ignore[assignment]
        dic: str | None = ...,  # type: ignore[assignment]
        adresa: str | None = ...,  # type: ignore[assignment]
        bankovni_ucet: str | None = ...,  # type: ignore[assignment]
        email: str | None = ...,  # type: ignore[assignment]
        telefon: str | None = ...,  # type: ignore[assignment]
        poznamka: str | None = ...,  # type: ignore[assignment]
        podil_procent: Decimal | None = ...,  # type: ignore[assignment]
        ucet_pohledavka: str | None = ...,  # type: ignore[assignment]
        ucet_zavazek: str | None = ...,  # type: ignore[assignment]
    ) -> None:
        """Uprav editovatelná pole. Sentinel ... = beze změny."""
        if nazev is not None:
            if not nazev.strip():
                raise ValidationError("Název partnera je povinný.")
            self._nazev = nazev.strip()

        if kategorie is not None:
            self._kategorie = kategorie

        if ico is not ...:
            if ico is not None and not _ICO_PATTERN.match(ico):
                raise ValidationError(f"IČO musí mít 8 číslic: {ico!r}.")
            self._ico = ico

        if dic is not ...:
            self._dic = dic
        if adresa is not ...:
            self._adresa = adresa
        if bankovni_ucet is not ...:
            self._bankovni_ucet = bankovni_ucet
        if email is not ...:
            self._email = email
        if telefon is not ...:
            self._telefon = telefon
        if poznamka is not ...:
            self._poznamka = poznamka
        if podil_procent is not ...:
            self._podil_procent = podil_procent
        if ucet_pohledavka is not ...:
            self._ucet_pohledavka = ucet_pohledavka
        if ucet_zavazek is not ...:
            self._ucet_zavazek = ucet_zavazek

        # Re-validate společník
        if self._kategorie == KategoriePartnera.SPOLECNIK:
            if self._podil_procent is None:
                raise ValidationError(
                    "Společník musí mít vyplněný podíl."
                )

    def deaktivuj(self) -> None:
        """Soft delete."""
        self._je_aktivni = False

    def reaktivuj(self) -> None:
        """Undo soft delete."""
        self._je_aktivni = True

    # --- Equality ---

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Partner):
            return NotImplemented
        if self._id is not None and other._id is not None:
            return self._id == other._id
        return self is other

    def __hash__(self) -> int:
        if self._id is not None:
            return hash(self._id)
        return hash(id(self))

    def __repr__(self) -> str:
        return (
            f"Partner(id={self._id}, nazev={self._nazev!r}, "
            f"kategorie={self._kategorie.value})"
        )
