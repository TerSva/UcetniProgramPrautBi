"""CreateDokladCommand — vytvoření nového dokladu ve stavu NOVY.

Vstup je immutable DTO ``CreateDokladInput``. Command:

1. Ověří, že ``cislo`` ještě neexistuje (ConflictError pokud ano).
2. Sestaví entitu ``Doklad`` (doménové validace se provedou v konstruktoru).
3. Uloží přes ``doklady_repo.add()``.
4. Vrátí ``DokladyListItem`` DTO s vygenerovaným ``id``.

Žádné zaúčtování — to je samostatná akce přes ``ZauctovatDokladCommand``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from decimal import Decimal

from domain.doklady.doklad import Doklad
from domain.doklady.repository import DokladyRepository
from domain.doklady.typy import DphRezim, Mena, TypDokladu
from domain.doklady.errors import CisloDokladuJizExistujeError
from domain.shared.money import Money
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.doklady_list import DokladyListItem


@dataclass(frozen=True)
class CreateDokladInput:
    """Input DTO pro vytvoření nového dokladu.

    Hodnoty odpovídají 1:1 formulářovým polím dialogu. Doménové validace
    běží až v ``Doklad.__init__``.
    """

    cislo: str
    typ: TypDokladu
    datum_vystaveni: date
    castka_celkem: Money
    datum_splatnosti: date | None = None
    popis: str | None = None
    partner_id: int | None = None
    mena: Mena = Mena.CZK
    castka_mena: Money | None = None
    kurz: Decimal | None = None
    variabilni_symbol: str | None = None
    dph_rezim: DphRezim = DphRezim.TUZEMSKO


class CreateDokladCommand:
    """Vytvoří doklad ve stavu NOVY. Jedna transakce."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
    ) -> None:
        self._uow_factory = uow_factory
        self._doklady_repo_factory = doklady_repo_factory

    def execute(self, data: CreateDokladInput) -> DokladyListItem:
        """Vytvoří nový doklad. Vrátí DTO s vygenerovaným id.

        Raises:
            ConflictError: číslo dokladu už existuje.
            ValidationError: jakákoli doménová invariant (propaguje se
                z ``Doklad.__init__``).
        """
        doklad = Doklad(
            cislo=data.cislo,
            typ=data.typ,
            datum_vystaveni=data.datum_vystaveni,
            castka_celkem=data.castka_celkem,
            partner_id=data.partner_id,
            datum_splatnosti=data.datum_splatnosti,
            popis=data.popis,
            mena=data.mena,
            castka_mena=data.castka_mena,
            kurz=data.kurz,
            variabilni_symbol=data.variabilni_symbol,
            dph_rezim=data.dph_rezim,
        )

        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            if repo.existuje_cislo(data.cislo):
                raise CisloDokladuJizExistujeError(
                    f"Doklad s číslem '{data.cislo}' už existuje. "
                    "Zvol jiné číslo."
                )
            saved = repo.add(doklad)
            uow.commit()

        return DokladyListItem.from_domain(saved)
