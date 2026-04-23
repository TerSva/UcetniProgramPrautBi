"""Queries pro bankovní modul — výpisy, transakce, účty."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from domain.banka.bankovni_transakce import StavTransakce
from domain.banka.bankovni_ucet import BankovniUcet
from domain.banka.bankovni_vypis import BankovniVypis
from domain.shared.money import Money
from infrastructure.database.repositories.banka_repository import (
    SqliteBankovniTransakceRepository,
    SqliteBankovniUcetRepository,
    SqliteBankovniVypisRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork


@dataclass(frozen=True)
class VypisListItem:
    """DTO pro seznam výpisů."""

    id: int
    ucet_nazev: str
    ucet_kod: str
    rok: int
    mesic: int
    pocatecni_stav: Money
    konecny_stav: Money
    pocet_transakci: int
    pocet_nesparovanych: int
    pdf_path: str
    cislo_vypisu: str | None = None
    datum_od: date | None = None
    datum_do: date | None = None


@dataclass(frozen=True)
class TransakceListItem:
    """DTO pro seznam transakcí."""

    id: int
    datum_transakce: date
    datum_zauctovani: date
    castka: Money
    smer: str
    variabilni_symbol: str | None
    protiucet: str | None
    popis: str | None
    stav: StavTransakce


class BankovniUctyQuery:
    """Načte seznam bankovních účtů."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def list_aktivni(self) -> list[BankovniUcet]:
        uow = self._uow_factory()
        with uow:
            repo = SqliteBankovniUcetRepository(uow)
            return repo.list_aktivni()

    def list_all(self) -> list[BankovniUcet]:
        uow = self._uow_factory()
        with uow:
            repo = SqliteBankovniUcetRepository(uow)
            return repo.list_all()


class BankovniVypisyQuery:
    """Načte výpisy s agregovanými daty."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def list_by_ucet(self, ucet_id: int) -> list[VypisListItem]:
        uow = self._uow_factory()
        with uow:
            ucet_repo = SqliteBankovniUcetRepository(uow)
            vypis_repo = SqliteBankovniVypisRepository(uow)
            tx_repo = SqliteBankovniTransakceRepository(uow)

            ucet = ucet_repo.get(ucet_id)
            if ucet is None:
                return []

            vypisy = vypis_repo.list_by_ucet(ucet_id)
            items: list[VypisListItem] = []

            for v in vypisy:
                all_tx = tx_repo.list_by_vypis(v.id)
                nesparovane = tx_repo.count_by_stav(
                    v.id, StavTransakce.NESPAROVANO,
                )
                items.append(VypisListItem(
                    id=v.id,
                    ucet_nazev=ucet.nazev,
                    ucet_kod=ucet.ucet_kod,
                    rok=v.rok,
                    mesic=v.mesic,
                    pocatecni_stav=v.pocatecni_stav,
                    konecny_stav=v.konecny_stav,
                    pocet_transakci=len(all_tx),
                    pocet_nesparovanych=nesparovane,
                    pdf_path=v.pdf_path,
                    cislo_vypisu=v.cislo_vypisu,
                    datum_od=v.datum_od,
                    datum_do=v.datum_do,
                ))

            return items

    def list_all(self) -> list[VypisListItem]:
        uow = self._uow_factory()
        with uow:
            ucet_repo = SqliteBankovniUcetRepository(uow)
            ucty = ucet_repo.list_all()
            all_items: list[VypisListItem] = []
            for ucet in ucty:
                vypis_repo = SqliteBankovniVypisRepository(uow)
                tx_repo = SqliteBankovniTransakceRepository(uow)
                vypisy = vypis_repo.list_by_ucet(ucet.id)
                for v in vypisy:
                    all_tx = tx_repo.list_by_vypis(v.id)
                    nesparovane = tx_repo.count_by_stav(
                        v.id, StavTransakce.NESPAROVANO,
                    )
                    all_items.append(VypisListItem(
                        id=v.id,
                        ucet_nazev=ucet.nazev,
                        ucet_kod=ucet.ucet_kod,
                        rok=v.rok,
                        mesic=v.mesic,
                        pocatecni_stav=v.pocatecni_stav,
                        konecny_stav=v.konecny_stav,
                        pocet_transakci=len(all_tx),
                        pocet_nesparovanych=nesparovane,
                        pdf_path=v.pdf_path,
                        cislo_vypisu=v.cislo_vypisu,
                        datum_od=v.datum_od,
                        datum_do=v.datum_do,
                    ))
            return all_items


class BankovniTransakceQuery:
    """Načte transakce pro daný výpis."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def list_by_vypis(
        self, vypis_id: int, stav: StavTransakce | None = None,
    ) -> list[TransakceListItem]:
        uow = self._uow_factory()
        with uow:
            repo = SqliteBankovniTransakceRepository(uow)
            txs = repo.list_by_vypis(vypis_id, stav=stav)
            return [
                TransakceListItem(
                    id=tx.id,
                    datum_transakce=tx.datum_transakce,
                    datum_zauctovani=tx.datum_zauctovani,
                    castka=tx.castka,
                    smer=tx.smer,
                    variabilni_symbol=tx.variabilni_symbol,
                    protiucet=tx.protiucet,
                    popis=tx.popis,
                    stav=tx.stav,
                )
                for tx in txs
            ]

    def list_nesparovane(
        self,
        castka_od: Money | None = None,
        castka_do: Money | None = None,
    ) -> list[TransakceListItem]:
        """Vrátí nespárované transakce ze všech výpisů (pro párování z dokladu)."""
        uow = self._uow_factory()
        with uow:
            sql = """
                SELECT * FROM bankovni_transakce
                WHERE stav = ?
            """
            params: list = [StavTransakce.NESPAROVANO.value]

            if castka_od is not None:
                sql += " AND ABS(castka) >= ?"
                params.append(abs(castka_od.to_halire()))
            if castka_do is not None:
                sql += " AND ABS(castka) <= ?"
                params.append(abs(castka_do.to_halire()))

            sql += " ORDER BY datum_zauctovani DESC, id DESC"

            rows = uow.connection.execute(sql, params).fetchall()
            return [
                TransakceListItem(
                    id=r["id"],
                    datum_transakce=date.fromisoformat(r["datum_transakce"]),
                    datum_zauctovani=date.fromisoformat(r["datum_zauctovani"]),
                    castka=Money(r["castka"]),
                    smer=r["smer"],
                    variabilni_symbol=r["variabilni_symbol"],
                    protiucet=r["protiucet"],
                    popis=r["popis"],
                    stav=StavTransakce(r["stav"]),
                )
                for r in rows
            ]
