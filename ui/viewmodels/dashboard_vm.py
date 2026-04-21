"""DashboardViewModel — prezentační stav pro Dashboard stránku.

Pure Python, žádný Qt import. Drží:
    * data: poslední úspěšný snapshot DashboardData (None před prvním load)
    * error: text chyby z posledního pokusu (None pokud OK)

`load()` zavolá injectované query a aktualizuje stav. Při výjimce uloží
její string do `error` a `data` zůstane None — UI tak může vykreslit
chybový stav místo crashe.
"""

from __future__ import annotations

from typing import Protocol

from services.queries.dashboard import DashboardData


class _DashboardQuery(Protocol):
    """Strukturální typ — cokoli s `execute() -> DashboardData`."""

    def execute(self, *, zisk_rok: int | None = None) -> DashboardData: ...


class DashboardViewModel:
    """ViewModel pro Dashboard. Bez Qt, jen Python state."""

    def __init__(self, query: _DashboardQuery) -> None:
        self._query = query
        self._data: DashboardData | None = None
        self._error: str | None = None
        self._zisk_rok: int | None = None  # None = aktuální rok

    @property
    def data(self) -> DashboardData | None:
        return self._data

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def has_data(self) -> bool:
        return self._data is not None

    @property
    def zisk_rok(self) -> int | None:
        return self._zisk_rok

    def set_zisk_rok(self, rok: int) -> None:
        """Nastav rok pro výpočet zisku a reloadni."""
        self._zisk_rok = rok

    def load(self) -> None:
        """Načti data ze query. Při chybě nastav error, data zůstanou None."""
        try:
            self._data = self._query.execute(zisk_rok=self._zisk_rok)
            self._error = None
        except Exception as exc:  # noqa: BLE001 — UI musí přežít cokoliv
            self._data = None
            self._error = str(exc) or exc.__class__.__name__
