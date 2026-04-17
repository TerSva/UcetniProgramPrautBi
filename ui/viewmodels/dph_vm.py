"""DphViewModel — prezentační stav pro DPH stránku.

Spravuje rok, měsíční přehled a detail zvoleného měsíce.
"""

from __future__ import annotations

from typing import Protocol

from services.commands.dph_podani import DphPodaniCommand
from services.queries.dph_prehled import (
    DphMesicDetailQuery,
    DphMesicItem,
    DphPrehledQuery,
    DphTransakceItem,
)


class DphViewModel:
    """ViewModel pro DPH stránku a detail."""

    def __init__(
        self,
        prehled_query: DphPrehledQuery,
        detail_query: DphMesicDetailQuery,
        podani_command: DphPodaniCommand,
    ) -> None:
        self._prehled_query = prehled_query
        self._detail_query = detail_query
        self._podani_command = podani_command

        self._rok: int = 2025
        self._mesice: list[DphMesicItem] = []
        self._detail: list[DphTransakceItem] = []
        self._error: str | None = None

    @property
    def rok(self) -> int:
        return self._rok

    @property
    def mesice(self) -> list[DphMesicItem]:
        return self._mesice

    @property
    def detail(self) -> list[DphTransakceItem]:
        return self._detail

    @property
    def error(self) -> str | None:
        return self._error

    def set_rok(self, rok: int) -> None:
        self._rok = rok

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
            self._error = None
        except Exception as exc:  # noqa: BLE001
            self._detail = []
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
