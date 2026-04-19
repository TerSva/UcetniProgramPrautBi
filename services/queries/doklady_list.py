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
from decimal import Decimal
from enum import Enum
from typing import Callable

from domain.doklady.doklad import Doklad
from domain.doklady.repository import DokladyRepository
from domain.doklady.typy import DphRezim, Mena, StavDokladu, TypDokladu
from domain.partneri.repository import PartneriRepository
from domain.shared.money import Money
from domain.ucetnictvi.repository import UcetniDenikRepository
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
    k_doreseni: KDoreseniFilter = KDoreseniFilter.VSE

    @property
    def je_vychozi(self) -> bool:
        """True pokud jsou všechny filtry na výchozích hodnotách.

        Slouží k odlišení "prázdná DB" vs. "žádné výsledky kvůli filtru".
        """
        return (
            self.rok is None
            and self.typ is None
            and self.stav is None
            and self.k_doreseni == KDoreseniFilter.VSE
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
    partner_id: int | None
    partner_nazev: str | None
    castka_celkem: Money
    stav: StavDokladu
    k_doreseni: bool
    poznamka_doreseni: str | None
    popis: str | None
    mena: Mena = Mena.CZK
    castka_mena: Money | None = None
    kurz: Decimal | None = None
    variabilni_symbol: str | None = None
    dph_rezim: DphRezim = DphRezim.TUZEMSKO
    datum_storna: date | None = None

    @classmethod
    def from_domain(
        cls,
        doklad: Doklad,
        datum_storna: date | None = None,
        partner_nazev: str | None = None,
    ) -> "DokladyListItem":
        """Vytvoří DTO z doménové entity. `id` musí být nastaveno.

        Args:
            doklad: doménová entita.
            datum_storna: pro STORNOVANY dokladu datum opravného zápisu.
            partner_nazev: název partnera (z JOIN).
        """
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
            partner_id=doklad.partner_id,
            partner_nazev=partner_nazev,
            castka_celkem=doklad.castka_celkem,
            stav=doklad.stav,
            k_doreseni=doklad.k_doreseni,
            poznamka_doreseni=doklad.poznamka_doreseni,
            popis=doklad.popis,
            mena=doklad.mena,
            castka_mena=doklad.castka_mena,
            kurz=doklad.kurz,
            variabilni_symbol=doklad.variabilni_symbol,
            dph_rezim=doklad.dph_rezim,
            datum_storna=datum_storna,
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

    Fáze 6.5: Pro STORNOVANY doklady obohacuje DTO o ``datum_storna``
    (datum prvního protizápisu v deníku). Lookup je per-doklad — běžící
    N+1, ale v praxi se stornovaných dokladů v listu objeví pár kusů za rok.
    TODO: pokud se časem ukáže jako hot path, přenést do jedné SQL query
    nebo zkešovat v DokladyRepository.
    """

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
        denik_repo_factory: Callable[
            [SqliteUnitOfWork], UcetniDenikRepository
        ] | None = None,
        partneri_repo_factory: Callable[
            [SqliteUnitOfWork], PartneriRepository
        ] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._doklady_repo_factory = doklady_repo_factory
        self._denik_repo_factory = denik_repo_factory
        self._partneri_repo_factory = partneri_repo_factory

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
            # BV are managed in Banka section, never shown in Doklady
            _EXCLUDED_TYPY = {TypDokladu.BANKOVNI_VYPIS}
            filtered: list[Doklad] = []
            for d in doklady:
                if d.typ in _EXCLUDED_TYPY:
                    continue
                if f.typ is not None and d.typ != f.typ:
                    continue
                if f.stav is not None and d.stav != f.stav:
                    continue
                if f.k_doreseni == KDoreseniFilter.SKRYT and d.k_doreseni:
                    continue
                if f.k_doreseni == KDoreseniFilter.POUZE and not d.k_doreseni:
                    continue
                filtered.append(d)

            # Enrichment: partner_nazev (batch lookup)
            partner_names: dict[int, str] = {}
            if self._partneri_repo_factory is not None:
                partner_ids = {
                    d.partner_id for d in filtered
                    if d.partner_id is not None
                }
                if partner_ids:
                    p_repo = self._partneri_repo_factory(uow)
                    for pid in partner_ids:
                        try:
                            p = p_repo.get_by_id(pid)
                            partner_names[pid] = p.nazev
                        except Exception:
                            pass

            # Enrichment: datum_storna pro STORNOVANY
            denik_repo = (
                self._denik_repo_factory(uow)
                if self._denik_repo_factory is not None
                else None
            )
            items: list[DokladyListItem] = []
            for d in filtered:
                datum_storna: date | None = None
                if (
                    denik_repo is not None
                    and d.stav == StavDokladu.STORNOVANY
                    and d.id is not None
                ):
                    zaznamy = denik_repo.list_by_doklad(d.id)
                    storno = next(
                        (z for z in zaznamy if z.je_storno), None,
                    )
                    datum_storna = storno.datum if storno is not None else None

                p_name = (
                    partner_names.get(d.partner_id)
                    if d.partner_id is not None
                    else None
                )
                items.append(
                    DokladyListItem.from_domain(
                        d,
                        datum_storna=datum_storna,
                        partner_nazev=p_name,
                    )
                )
            return items
