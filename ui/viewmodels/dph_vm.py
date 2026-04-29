"""DphViewModel — prezentační stav pro DPH stránku.

Spravuje rok, měsíční přehled, detail měsíce, řádky přiznání EPO
a souhrnné hlášení (VIES). Měsíční filter na hlavní tabulce.
"""

from __future__ import annotations

from services.commands.dph_podani import DphPodaniCommand
from services.queries.dph_prehled import (
    DphMesicDetailQuery,
    DphMesicItem,
    DphPrehledQuery,
    DphPriznaniQuery,
    DphPriznaniRadky,
    DphTransakceItem,
    ViesItem,
    ViesQuery,
)


class DphViewModel:
    """ViewModel pro DPH stránku, detail dialog, VIES a KH záložky."""

    def __init__(
        self,
        prehled_query: DphPrehledQuery,
        detail_query: DphMesicDetailQuery,
        podani_command: DphPodaniCommand,
        priznani_query: DphPriznaniQuery | None = None,
        vies_query: ViesQuery | None = None,
    ) -> None:
        self._prehled_query = prehled_query
        self._detail_query = detail_query
        self._podani_command = podani_command
        self._priznani_query = priznani_query or DphPriznaniQuery(detail_query)
        self._vies_query = vies_query

        self._rok: int = 2025
        self._mesic_filter: int | None = None  # None = všechny
        self._mesice: list[DphMesicItem] = []
        self._detail: list[DphTransakceItem] = []
        self._priznani: DphPriznaniRadky | None = None
        self._vies: list[ViesItem] = []
        self._error: str | None = None

    @property
    def rok(self) -> int:
        return self._rok

    @property
    def mesic_filter(self) -> int | None:
        return self._mesic_filter

    @property
    def mesice(self) -> list[DphMesicItem]:
        """12 měsíců s daty (filter aplikován až ve view)."""
        return self._mesice

    @property
    def mesice_filtered(self) -> list[DphMesicItem]:
        """Měsíční přehled s aplikovaným filterem (None = vše, jinak 1 měsíc)."""
        if self._mesic_filter is None:
            return self._mesice
        return [m for m in self._mesice if m.mesic == self._mesic_filter]

    @property
    def detail(self) -> list[DphTransakceItem]:
        return self._detail

    @property
    def priznani(self) -> DphPriznaniRadky | None:
        return self._priznani

    @property
    def vies(self) -> list[ViesItem]:
        return self._vies

    @property
    def error(self) -> str | None:
        return self._error

    def set_rok(self, rok: int) -> None:
        self._rok = rok

    def set_mesic_filter(self, mesic: int | None) -> None:
        """None = všechny měsíce, 1–12 = jeden měsíc."""
        self._mesic_filter = mesic

    def load_prehled(self) -> None:
        try:
            self._mesice = self._prehled_query.execute(self._rok)
            self._error = None
        except Exception as exc:  # noqa: BLE001
            self._mesice = []
            self._error = str(exc) or exc.__class__.__name__

    def load_detail(self, mesic: int) -> None:
        try:
            self._detail = self._detail_query.execute(self._rok, mesic)
            self._priznani = self._priznani_query.execute(self._rok, mesic)
            self._error = None
        except Exception as exc:  # noqa: BLE001
            self._detail = []
            self._priznani = None
            self._error = str(exc) or exc.__class__.__name__

    def load_vies(self) -> None:
        if self._vies_query is None:
            self._vies = []
            return
        try:
            self._vies = self._vies_query.execute(self._rok)
            self._error = None
        except Exception as exc:  # noqa: BLE001
            self._vies = []
            self._error = str(exc) or exc.__class__.__name__

    def oznac_podane(self, mesic: int, podano: bool) -> None:
        try:
            self._podani_command.execute(
                rok=self._rok, mesic=mesic, podano=podano,
            )
            self._error = None
            self.load_prehled()
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
