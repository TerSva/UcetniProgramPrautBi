"""BankovniVypisyViewModel — ViewModel pro stránku bankovních výpisů."""

from __future__ import annotations

from datetime import date
from typing import Callable

from domain.banka.bankovni_transakce import StavTransakce
from domain.banka.bankovni_ucet import BankovniUcet
from domain.shared.money import Money
from infrastructure.database.repositories.banka_repository import (
    SqliteBankovniTransakceRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.banka.auto_uctovani import AutoUctovaniBankyCommand, AutoUctovaniResult
from services.banka.smazat_vypis import SmazatVypisCommand, SmazatVypisResult
from services.commands.rozparovat_platbu import RozparovatPlatbuCommand
from services.commands.sparovat_platbu_dokladem import (
    SparovatPlatbuDoklademCommand,
    SparovaniResult,
)
from services.queries.banka import (
    BankovniTransakceQuery,
    BankovniUctyQuery,
    BankovniVypisyQuery,
    TransakceListItem,
    VypisListItem,
)
from services.queries.neuhrazene_doklady import NeuhrazeneDokladyQuery


class BankovniVypisyViewModel:
    """ViewModel pro stránku Bankovní výpisy."""

    def __init__(
        self,
        ucty_query: BankovniUctyQuery,
        vypisy_query: BankovniVypisyQuery,
        transakce_query: BankovniTransakceQuery,
        auto_uctovani_cmd: AutoUctovaniBankyCommand,
        smazat_cmd: SmazatVypisCommand | None = None,
        sparovat_cmd: SparovatPlatbuDoklademCommand | None = None,
        rozparovat_cmd: RozparovatPlatbuCommand | None = None,
        neuhrazene_query: NeuhrazeneDokladyQuery | None = None,
        uow_factory: Callable[[], SqliteUnitOfWork] | None = None,
    ) -> None:
        self._ucty_query = ucty_query
        self._vypisy_query = vypisy_query
        self._transakce_query = transakce_query
        self._auto_uctovani_cmd = auto_uctovani_cmd
        self._smazat_cmd = smazat_cmd
        self._sparovat_cmd = sparovat_cmd
        self._rozparovat_cmd = rozparovat_cmd
        self._neuhrazene_query = neuhrazene_query
        self._uow_factory = uow_factory

        self._ucty: list[BankovniUcet] = []
        self._vypisy: list[VypisListItem] = []
        self._transakce: list[TransakceListItem] = []
        self._selected_ucet_id: int | None = None
        self._selected_vypis_id: int | None = None
        self._stav_filter: StavTransakce | None = None
        self._vs_filter: str = ""
        self._protiucet_filter: str = ""
        self._castka_od: Money | None = None
        self._castka_do: Money | None = None
        self._den_filter: int | None = None
        self._datum_od: date | None = None
        self._datum_do: date | None = None
        self._search_text: str = ""
        self._error: str | None = None

    # ── Properties ──

    @property
    def ucty(self) -> list[BankovniUcet]:
        return self._ucty

    @property
    def vypisy(self) -> list[VypisListItem]:
        return self._vypisy

    @property
    def transakce(self) -> list[TransakceListItem]:
        return self._filtered_transakce()

    @property
    def selected_ucet_id(self) -> int | None:
        return self._selected_ucet_id

    @property
    def selected_vypis_id(self) -> int | None:
        return self._selected_vypis_id

    @property
    def error(self) -> str | None:
        return self._error

    # ── Filtering ──

    def _filtered_transakce(self) -> list[TransakceListItem]:
        """Aplikuje klientské filtry.

        Primární: datum_od/datum_do range, fulltext search (popis, VS,
        protiúčet, partner). Sekundární: VS, protiúčet, částka, den.
        """
        result = self._transakce

        # Datum range — primární filtr
        if self._datum_od is not None:
            result = [
                tx for tx in result
                if tx.datum_zauctovani >= self._datum_od
            ]
        if self._datum_do is not None:
            result = [
                tx for tx in result
                if tx.datum_zauctovani <= self._datum_do
            ]

        # Fulltext search — popis, VS, protiúčet, partner
        search = self._search_text.strip().lower()
        if search:
            def matches(tx: TransakceListItem) -> bool:
                fields = [
                    (tx.popis or "").lower(),
                    (tx.variabilni_symbol or "").lower(),
                    (tx.protiucet or "").lower(),
                    (getattr(tx, "partner_nazev", None) or "").lower(),
                ]
                return any(search in f for f in fields)
            result = [tx for tx in result if matches(tx)]

        # Sekundární: VS, protiúčet (samostatné inputy — pro přesnější filtr)
        if self._vs_filter:
            needle = self._vs_filter.lower()
            result = [
                tx for tx in result
                if tx.variabilni_symbol and needle in tx.variabilni_symbol.lower()
            ]
        if self._protiucet_filter:
            needle = self._protiucet_filter.lower()
            result = [
                tx for tx in result
                if tx.protiucet and needle in tx.protiucet.lower()
            ]
        if self._castka_od is not None:
            limit = self._castka_od.to_halire()
            result = [tx for tx in result if abs(tx.castka.to_halire()) >= abs(limit)]
        if self._castka_do is not None:
            limit = self._castka_do.to_halire()
            result = [tx for tx in result if abs(tx.castka.to_halire()) <= abs(limit)]
        if self._den_filter is not None:
            result = [
                tx for tx in result if tx.datum_zauctovani.day == self._den_filter
            ]
        return result

    # ── Actions ──

    def load(self) -> None:
        """Načte účty a výpisy."""
        try:
            self._ucty = self._ucty_query.list_aktivni()
            self._vypisy = self._vypisy_query.list_all()
            self._error = None
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)

    def select_ucet(self, ucet_id: int | None) -> None:
        """Filtruj výpisy podle účtu."""
        self._selected_ucet_id = ucet_id
        try:
            if ucet_id is not None:
                self._vypisy = self._vypisy_query.list_by_ucet(ucet_id)
            else:
                self._vypisy = self._vypisy_query.list_all()
            self._error = None
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)

    def select_vypis(self, vypis_id: int | None) -> None:
        """Načte transakce pro vybraný výpis."""
        self._selected_vypis_id = vypis_id
        if vypis_id is None:
            self._transakce = []
            return
        try:
            self._transakce = self._transakce_query.list_by_vypis(
                vypis_id, stav=self._stav_filter,
            )
            self._error = None
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)

    def set_stav_filter(self, stav: StavTransakce | None) -> None:
        """Nastav filtr stavu transakcí a obnov seznam."""
        self._stav_filter = stav
        if self._selected_vypis_id is not None:
            self.select_vypis(self._selected_vypis_id)

    def set_vs_filter(self, vs: str) -> None:
        self._vs_filter = vs.strip()

    def set_protiucet_filter(self, protiucet: str) -> None:
        self._protiucet_filter = protiucet.strip()

    def set_castka_od(self, castka: Money | None) -> None:
        self._castka_od = castka

    def set_castka_do(self, castka: Money | None) -> None:
        self._castka_do = castka

    def set_den_filter(self, den: int | None) -> None:
        self._den_filter = den

    def set_datum_range(
        self, od: date | None, do: date | None,
    ) -> None:
        """Primární datum filter pro transakce."""
        self._datum_od = od
        self._datum_do = do

    def set_search_text(self, text: str) -> None:
        """Fulltext search nad popis / VS / protiúčet / partner."""
        self._search_text = text or ""

    def auto_zauctuj(self, vypis_id: int) -> AutoUctovaniResult | None:
        """Spusť automatické zaúčtování pro výpis."""
        try:
            result = self._auto_uctovani_cmd.execute(vypis_id)
            self.select_vypis(vypis_id)
            self._error = None
            return result
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return None

    def smazat_vypis(self, vypis_id: int) -> SmazatVypisResult | None:
        """Kaskádní smazání výpisu."""
        if self._smazat_cmd is None:
            self._error = "Příkaz pro mazání není nakonfigurován"
            return None
        try:
            result = self._smazat_cmd.execute(vypis_id)
            if result.success:
                self._selected_vypis_id = None
                self._transakce = []
                self.load()
            self._error = None
            return result
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return None

    @property
    def neuhrazene_query(self) -> NeuhrazeneDokladyQuery | None:
        return self._neuhrazene_query

    def sparovat_platbu(
        self, transakce_id: int, doklad_id: int,
    ) -> SparovaniResult | None:
        """Spáruje transakci s dokladem."""
        if self._sparovat_cmd is None:
            self._error = "Příkaz pro párování není nakonfigurován"
            return None
        try:
            result = self._sparovat_cmd.execute(transakce_id, doklad_id)
            if self._selected_vypis_id is not None:
                self.select_vypis(self._selected_vypis_id)
            self._error = None
            return result
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return None

    def ignoruj_transakci(self, tx_id: int) -> bool:
        """Označ transakci jako ignorovanou."""
        if self._uow_factory is None:
            self._error = "uow_factory není k dispozici"
            return False
        try:
            uow = self._uow_factory()
            with uow:
                repo = SqliteBankovniTransakceRepository(uow)
                tx = repo.get(tx_id)
                if tx is None:
                    self._error = f"Transakce {tx_id} nenalezena"
                    return False
                tx.ignoruj()
                repo.update(tx)
                uow.commit()
            if self._selected_vypis_id is not None:
                self.select_vypis(self._selected_vypis_id)
            self._error = None
            return True
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return False

    def obnov_transakci(self, tx_id: int) -> bool:
        """Vrátí ignorovanou transakci zpět na NESPAROVANO.

        Po obnovení se v UI znovu objeví tlačítka Spárovat/Zaúčtovat/Ignorovat.
        """
        if self._uow_factory is None:
            self._error = "uow_factory není k dispozici"
            return False
        try:
            uow = self._uow_factory()
            with uow:
                repo = SqliteBankovniTransakceRepository(uow)
                tx = repo.get(tx_id)
                if tx is None:
                    self._error = f"Transakce {tx_id} nenalezena"
                    return False
                tx.obnov()
                repo.update(tx)
                uow.commit()
            if self._selected_vypis_id is not None:
                self.select_vypis(self._selected_vypis_id)
            self._error = None
            return True
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return False

    def rozparuj_transakci(self, tx_id: int) -> bool:
        """Rozpáruje spárovanou transakci s dokladem.

        Vytvoří storno protizápisy v deníku (audit trail), resetuje
        stav transakce na NESPAROVANO a vrátí stav dokladu zpět dle
        zbývajících úhrad.
        """
        if self._rozparovat_cmd is None:
            self._error = "Rozpárovat command není k dispozici"
            return False
        try:
            self._rozparovat_cmd.execute(transakce_id=tx_id)
            if self._selected_vypis_id is not None:
                self.select_vypis(self._selected_vypis_id)
            self._error = None
            return True
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return False

    def zauctovat_transakci(
        self,
        tx_id: int,
        md_ucet: str,
        dal_ucet: str,
        popis: str | None = None,
    ) -> bool:
        """Přímé zaúčtování transakce (bez dokladu)."""
        if self._uow_factory is None:
            self._error = "uow_factory není k dispozici"
            return False
        try:
            from domain.shared.money import Money
            from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
            from infrastructure.database.repositories.ucetni_denik_repository import (
                SqliteUcetniDenikRepository,
            )

            uow = self._uow_factory()
            with uow:
                tx_repo = SqliteBankovniTransakceRepository(uow)
                denik_repo = SqliteUcetniDenikRepository(uow)

                tx = tx_repo.get(tx_id)
                if tx is None:
                    self._error = f"Transakce {tx_id} nenalezena"
                    return False

                # BV doklad_id z výpisu
                row = uow.connection.execute(
                    "SELECT bv_doklad_id FROM bankovni_vypisy WHERE id = ?",
                    (tx.bankovni_vypis_id,),
                ).fetchone()
                bv_doklad_id = row["bv_doklad_id"] if row else None
                if bv_doklad_id is None:
                    self._error = "BV doklad nenalezen"
                    return False

                castka = (
                    tx.castka
                    if tx.castka.is_positive
                    else Money(-tx.castka.to_halire())
                )

                zaznam = UcetniZaznam(
                    doklad_id=bv_doklad_id,
                    datum=tx.datum_zauctovani,
                    md_ucet=md_ucet,
                    dal_ucet=dal_ucet,
                    castka=castka,
                    popis=popis,
                )
                zapis_id = denik_repo.add(zaznam)
                tx.auto_zauctuj(zapis_id)
                tx_repo.update(tx)
                uow.commit()

            if self._selected_vypis_id is not None:
                self.select_vypis(self._selected_vypis_id)
            self._error = None
            return True
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            return False

    def get_ucet_kod_for_vypis(self) -> str | None:
        """Vrátí ucet_kod (221.xxx) vybraného výpisu."""
        if self._selected_vypis_id is None:
            return None
        for v in self._vypisy:
            if v.id == self._selected_vypis_id:
                return v.ucet_kod
        return None
