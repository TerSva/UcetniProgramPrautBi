"""DokladyListQuery — seznam dokladů pro Doklady stránku s filtry.

Read-only query: načte doklady z DB, provede filtraci v Pythonu, vrátí
immutable DTO list. Žádná SQL logika mimo `list_by_obdobi()` z repository.

Variant A: pull + Python filter — repository neposkytuje kombinované filtry,
takže načítáme všechny doklady ve zvoleném roce (nebo vše) a filtrujeme
v paměti. Pro typické roční objemy (stovky až tisíce dokladů) je to
naprosto v pořádku a šetří komplexitu v repository/SQL vrstvě.

Řazení: datum_vystaveni DESC, id DESC (stejně jako `list_by_obdobi`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Callable

from domain.doklady.doklad import Doklad
from domain.doklady.repository import DokladyRepository
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from infrastructure.database.unit_of_work import SqliteUnitOfWork


# ══════════════════════════════════════════════
# Filter types
# ══════════════════════════════════════════════


class KDoreseniFilter(Enum):
    """Režim filtrování dokladů podle flagu k_doreseni."""

    SKRYT = "skryt"   # default — nezobrazuj flagnuté doklady
    VSE = "vse"       # všechny doklady bez ohledu na flag
    POUZE = "pouze"   # jen flagnuté (drill z Dashboardu)


@dataclass(frozen=True)
class DokladyFilter:
    """Immutable snapshot stavu filtrů.

    None hodnoty = filtr není aplikován (ukazuj vše v daném rozměru).
    """

    rok: int | None = None
    typ: TypDokladu | None = None
    stav: StavDokladu | None = None
    k_doreseni: KDoreseniFilter = KDoreseniFilter.SKRYT

    @property
    def je_vychozi(self) -> bool:
        """True pokud jsou všechny filtry na výchozích hodnotách.

        Slouží k odlišení "prázdná DB" vs. "žádné výsledky kvůli filtru".
        """
        return (
            self.rok is None
            and self.typ is None
            and self.stav is None
            and self.k_doreseni == KDoreseniFilter.SKRYT
        )


# ══════════════════════════════════════════════
# Read-only DTO (snapshot pro UI)
# ══════════════════════════════════════════════


@dataclass(frozen=True)
class DokladyListItem:
    """Jeden řádek v tabulce Dokladů. Čistý snímek pro UI."""

    id: int
    cislo: str
    typ: TypDokladu
    datum_vystaveni: date
    datum_splatnosti: date | None
    partner_nazev: str | None   # zatím vždy None (Partneři entita neexistuje)
    castka_celkem: Money
    stav: StavDokladu
    k_doreseni: bool
    poznamka_doreseni: str | None
    popis: str | None

    @classmethod
    def from_domain(cls, doklad: Doklad) -> "DokladyListItem":
        """Vytvoří DTO z doménové entity. `id` musí být nastaveno."""
        if doklad.id is None:
            raise ValueError(
                "DokladyListItem.from_domain: doklad nemá id (není persistovaný)."
            )
        return cls(
            id=doklad.id,
            cislo=doklad.cislo,
            typ=doklad.typ,
            datum_vystaveni=doklad.datum_vystaveni,
            datum_splatnosti=doklad.datum_splatnosti,
            partner_nazev=None,
            castka_celkem=doklad.castka_celkem,
            stav=doklad.stav,
            k_doreseni=doklad.k_doreseni,
            poznamka_doreseni=doklad.poznamka_doreseni,
            popis=doklad.popis,
        )


# ══════════════════════════════════════════════
# Query
# ══════════════════════════════════════════════


#: Minimum datum rozsahu pro „bez filtru".
_DATE_MIN = date(1970, 1, 1)
#: Maximum datum rozsahu pro „bez filtru".
_DATE_MAX = date(9999, 12, 31)

#: Horní strop načtených dokladů (safety). Pro reálné objemy dostatečné.
_LIMIT = 100_000


class DokladyListQuery:
    """Spočítá filtrovaný seznam dokladů v jedné transakci.

    Konstruktor přijímá abstraktní factory typy — testovatelné proti libovolné
    implementaci repository.
    """

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
    ) -> None:
        self._uow_factory = uow_factory
        self._doklady_repo_factory = doklady_repo_factory

    def execute(self, f: DokladyFilter) -> list[DokladyListItem]:
        """Vrátí filtrovaný seznam DTO, řazeno datum_vystaveni DESC, id DESC."""
        if f.rok is not None:
            start = date(f.rok, 1, 1)
            end = date(f.rok, 12, 31)
        else:
            start = _DATE_MIN
            end = _DATE_MAX

        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            doklady = repo.list_by_obdobi(start, end, limit=_LIMIT)

        # Python-side filter
        filtered: list[Doklad] = []
        for d in doklady:
            if f.typ is not None and d.typ != f.typ:
                continue
            if f.stav is not None and d.stav != f.stav:
                continue
            if f.k_doreseni == KDoreseniFilter.SKRYT and d.k_doreseni:
                continue
            if f.k_doreseni == KDoreseniFilter.POUZE and not d.k_doreseni:
                continue
            filtered.append(d)

        return [DokladyListItem.from_domain(d) for d in filtered]
