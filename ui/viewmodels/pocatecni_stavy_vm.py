"""PocatecniStavyViewModel — stránka počátečních stavů."""

from __future__ import annotations

from typing import Callable

from domain.firma.firma import Firma
from domain.firma.pocatecni_stav import PocatecniStav
from domain.shared.money import Money
from services.commands.pocatecni_stavy import PocatecniStavyCommand
from services.commands.prenos_zustatku import (
    PrenosZustatkuCommand,
    PrenosZustatkuVysledek,
)
from services.commands.vklad_zk import VkladZKCommand


class PocatecniStavyViewModel:
    """ViewModel pro stránku Počáteční stavy."""

    def __init__(
        self,
        pocatecni_cmd: PocatecniStavyCommand,
        vklad_zk_cmd: VkladZKCommand,
        firma_loader: Callable[[], Firma | None],
        prenos_cmd: PrenosZustatkuCommand | None = None,
    ) -> None:
        self._ps_cmd = pocatecni_cmd
        self._vklad_cmd = vklad_zk_cmd
        self._prenos_cmd = prenos_cmd
        self._firma_loader = firma_loader

        self._rok: int = 2025
        self._stavy: list[PocatecniStav] = []
        self._firma: Firma | None = None
        self._error: str | None = None
        self._posledni_prenos: PrenosZustatkuVysledek | None = None

    @property
    def rok(self) -> int:
        return self._rok

    @property
    def stavy(self) -> list[PocatecniStav]:
        return self._stavy

    @property
    def firma(self) -> Firma | None:
        return self._firma

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def soucet_md(self) -> Money:
        total = Money.zero()
        for s in self._stavy:
            if s.strana == "MD":
                total = total + s.castka
        return total

    @property
    def soucet_dal(self) -> Money:
        total = Money.zero()
        for s in self._stavy:
            if s.strana == "DAL":
                total = total + s.castka
        return total

    @property
    def bilance_souhlasi(self) -> bool:
        return self.soucet_md == self.soucet_dal

    def set_rok(self, rok: int) -> None:
        self._rok = rok

    def load(self) -> None:
        try:
            self._firma = self._firma_loader()
            self._stavy = self._ps_cmd.list_by_rok(self._rok)
            self._error = None
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__

    def pridat_stav(
        self,
        ucet_kod: str,
        castka: Money,
        strana: str,
        poznamka: str | None = None,
    ) -> None:
        try:
            self._ps_cmd.pridat(
                rok=self._rok,
                ucet_kod=ucet_kod,
                castka=castka,
                strana=strana,
                poznamka=poznamka,
            )
            self._error = None
            self.load()
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__

    def smazat_stav(self, stav_id: int) -> None:
        try:
            self._ps_cmd.smazat(stav_id)
            self._error = None
            self.load()
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__

    def generovat_doklad(self) -> int | None:
        try:
            result = self._ps_cmd.generovat_id_doklad(self._rok)
            self._error = None
            return result
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
            return None

    @property
    def posledni_prenos(self) -> PrenosZustatkuVysledek | None:
        return self._posledni_prenos

    def prenest_zustatky_z(self, rok_zdroj: int) -> PrenosZustatkuVysledek | None:
        """Přenese KZ z rok_zdroj jako PS aktuálního self._rok.

        Vyžaduje rok_zdroj == self._rok - 1.
        """
        if self._prenos_cmd is None:
            self._error = "Přenos zůstatků není k dispozici."
            return None
        try:
            vysledek = self._prenos_cmd.prenest(
                z_roku=rok_zdroj, do_roku=self._rok,
            )
            self._posledni_prenos = vysledek
            self._error = None
            self.load()
            return vysledek
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
            return None
