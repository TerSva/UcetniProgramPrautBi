"""Firma — singleton entita s údaji o účetní jednotce.

Jeden záznam v celém systému. Pro PRAUT s.r.o. pre-fillnuto seed daty.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from domain.shared.errors import ValidationError
from domain.shared.money import Money


@dataclass
class Firma:
    """Údaje o firmě — singleton."""

    nazev: str
    ico: str | None = None
    dic: str | None = None
    sidlo: str | None = None
    pravni_forma: str = "s.r.o."
    datum_zalozeni: date | None = None
    rok_zacatku_uctovani: int = 2025
    zakladni_kapital: Money | None = None
    kategorie_uj: str = "mikro"
    je_identifikovana_osoba_dph: bool = True
    je_platce_dph: bool = False
    bankovni_ucet_1: str | None = None
    bankovni_ucet_2: str | None = None
    # Pole pro účetní závěrku (minimální příloha + cover 25 5404)
    predmet_cinnosti: str | None = None
    prumerny_pocet_zamestnancu: int = 0
    zpusob_oceneni: str = "pořizovacími cenami"
    odpisovy_plan: str = "lineární"
    statutarni_organ: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.nazev or not self.nazev.strip():
            raise ValidationError("Název firmy je povinný.")
        if self.ico is not None and len(self.ico) != 8:
            raise ValidationError("IČO musí mít 8 číslic.")
        if self.prumerny_pocet_zamestnancu < 0:
            raise ValidationError("Průměrný počet zaměstnanců nemůže být záporný.")
