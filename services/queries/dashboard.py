"""DashboardDataQuery — agregace KPI dat pro úvodní obrazovku.

Read-only query, žádná mutace stavu. Snapshot je frozen DTO bez závislostí
na DB — UI vrstva ho dostává hotový a pouze ho formátuje.

Algoritmus:
  * doklady_celkem / k_zauctovani — celé období (all-time do today)
  * doklady_k_doreseni — count přes len(list_k_doreseni()) — žádné backend změny
  * pohledavky / zavazky — all-time saldo na účtech 311 / 321
  * vynosy / naklady / hruby_zisk — za vybraný rok (zisk_rok parametr)
  * odhad_dane = max(hrubý zisk × 19 %, 0)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable, Final

from domain.doklady.repository import DokladyRepository
from domain.doklady.typy import StavDokladu
from domain.shared.money import Money
from domain.ucetnictvi.repository import (
    UcetniDenikRepository,
    UctovaOsnovaRepository,
)
from domain.ucetnictvi.typy import TypUctu
from infrastructure.database.unit_of_work import SqliteUnitOfWork

#: Sazba daně z příjmu právnických osob v ČR (2026 = 19 %).
DPPO_SAZBA: Final[Decimal] = Decimal("0.19")

# TODO: Zjednodušení Fáze 6 — pohledávky/závazky bereme z 311 / 321
# ignorujeme zálohové účty 314/324 a další analytiky. Pro plnou
# přesnost saldokonta v dalších fázích projekt rozšíří agregaci na
# celé skupiny (31x, 32x) a partner-level rozpad.
UCET_POHLEDAVKY: Final[str] = "311"
UCET_ZAVAZKY: Final[str] = "321"


@dataclass(frozen=True)
class DashboardData:
    """Snapshot dat pro Dashboard. Read-only DTO."""

    # Doklady (YTD)
    doklady_celkem: int
    doklady_k_zauctovani: int
    doklady_k_doreseni: int

    # Saldokonto (all-time)
    pohledavky: Money
    zavazky: Money

    # Hospodářský výsledek (YTD)
    rok: int
    vynosy: Money
    naklady: Money
    hruby_zisk: Money
    odhad_dane: Money

    @property
    def je_ve_ztrate(self) -> bool:
        """True pokud hrubý zisk je záporný."""
        return self.hruby_zisk.is_negative

    @property
    def ma_doklady_k_doreseni(self) -> bool:
        """True pokud je aspoň jeden doklad označený k dořešení."""
        return self.doklady_k_doreseni > 0


class DashboardDataQuery:
    """Spočítá Dashboard snapshot v jedné transakci.

    Konstruktor přijímá abstraktní repository typy (factory pattern),
    aby query bylo testovatelné s jakoukoli implementací repository.
    """

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
        denik_repo_factory: Callable[[SqliteUnitOfWork], UcetniDenikRepository],
        osnova_repo_factory: Callable[[SqliteUnitOfWork], UctovaOsnovaRepository],
    ) -> None:
        self._uow_factory = uow_factory
        self._doklady_repo_factory = doklady_repo_factory
        self._denik_repo_factory = denik_repo_factory
        self._osnova_repo_factory = osnova_repo_factory

    def execute(
        self,
        today: date | None = None,
        zisk_rok: int | None = None,
    ) -> DashboardData:
        """Spočítá snapshot.

        `today` je parametrizovatelný pro testy.
        `zisk_rok` určuje rok pro výpočet výnosů/nákladů/zisku.
        Pokud None, použije se today.year.
        """
        if today is None:
            today = date.today()
        if zisk_rok is None:
            zisk_rok = today.year
        zacatek_zisk_roku = date(zisk_rok, 1, 1)
        konec_zisk_roku = min(date(zisk_rok, 12, 31), today)
        davno = date(1900, 1, 1)

        uow = self._uow_factory()
        with uow:
            doklady_repo = self._doklady_repo_factory(uow)
            denik_repo = self._denik_repo_factory(uow)
            osnova_repo = self._osnova_repo_factory(uow)

            # ── Doklady (celé období) ──────────────────────────────────
            doklady_all = doklady_repo.list_by_obdobi(
                davno, today, limit=100_000
            )
            doklady_celkem = len(doklady_all)
            doklady_k_zauctovani = sum(
                1 for d in doklady_all if d.stav == StavDokladu.NOVY
            )
            doklady_k_doreseni = len(
                doklady_repo.list_k_doreseni(limit=100_000)
            )

            # ── Saldokonto (all-time) ─────────────────────────────────
            zaznamy_all = denik_repo.list_by_obdobi(
                davno, today, limit=1_000_000
            )

            # Pohledávky = MD(311) - Dal(311), Závazky = Dal(321) - MD(321)
            md_311 = Money.zero()
            dal_311 = Money.zero()
            md_321 = Money.zero()
            dal_321 = Money.zero()
            for z in zaznamy_all:
                if z.md_ucet == UCET_POHLEDAVKY:
                    md_311 = md_311 + z.castka
                if z.dal_ucet == UCET_POHLEDAVKY:
                    dal_311 = dal_311 + z.castka
                if z.md_ucet == UCET_ZAVAZKY:
                    md_321 = md_321 + z.castka
                if z.dal_ucet == UCET_ZAVAZKY:
                    dal_321 = dal_321 + z.castka
            pohledavky = md_311 - dal_311
            zavazky = dal_321 - md_321

            # ── Hospodářský výsledek (vybraný rok) ─────────────────────
            zaznamy_ytd = denik_repo.list_by_obdobi(
                zacatek_zisk_roku, konec_zisk_roku, limit=1_000_000
            )

            # Načti osnovu jednou (vč. neaktivních pro úplnost agregace)
            ucty = osnova_repo.list_all(jen_aktivni=False)
            typ_uctu: dict[str, TypUctu] = {u.cislo: u.typ for u in ucty}

            # Výnosy: Dal(VYNOSY) - MD(VYNOSY)  → kreditní zůstatek
            # Náklady: MD(NAKLADY) - Dal(NAKLADY) → debetní zůstatek
            vynosy = Money.zero()
            naklady = Money.zero()
            for z in zaznamy_ytd:
                md_typ = typ_uctu.get(z.md_ucet)
                dal_typ = typ_uctu.get(z.dal_ucet)
                if md_typ == TypUctu.NAKLADY:
                    naklady = naklady + z.castka
                if dal_typ == TypUctu.NAKLADY:
                    naklady = naklady - z.castka
                if dal_typ == TypUctu.VYNOSY:
                    vynosy = vynosy + z.castka
                if md_typ == TypUctu.VYNOSY:
                    vynosy = vynosy - z.castka

            hruby_zisk = vynosy - naklady
            if hruby_zisk.is_positive:
                odhad_dane = hruby_zisk * DPPO_SAZBA
            else:
                odhad_dane = Money.zero()

        return DashboardData(
            doklady_celkem=doklady_celkem,
            doklady_k_zauctovani=doklady_k_zauctovani,
            doklady_k_doreseni=doklady_k_doreseni,
            pohledavky=pohledavky,
            zavazky=zavazky,
            rok=zisk_rok,
            vynosy=vynosy,
            naklady=naklady,
            hruby_zisk=hruby_zisk,
            odhad_dane=odhad_dane,
        )
