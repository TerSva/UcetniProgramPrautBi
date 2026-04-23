"""ChartOfAccountsViewModel — prezentační stav pro stránku Účtová osnova.

Pure Python, žádný Qt import.
"""

from __future__ import annotations

from typing import Protocol

from services.queries.chart_of_accounts import (
    ChartOfAccountsItem,
    TridaGroup,
)


class _ChartQuery(Protocol):
    def execute(self, show_inactive: bool = True) -> list[TridaGroup]: ...


class _ManageCommand(Protocol):
    def activate_ucet(self, cislo: str) -> None: ...
    def deactivate_ucet(self, cislo: str) -> None: ...
    def add_analytika(
        self, syntetic_kod: str, analytika_suffix: str,
        nazev: str, popis: str | None = None,
    ) -> object: ...
    def update_analytika(
        self, cislo: str, nazev: str, popis: str | None = None,
    ) -> None: ...
    def update_ucet(
        self, cislo: str, nazev: str, popis: str | None = None,
    ) -> None: ...


class ChartOfAccountsViewModel:
    """ViewModel pro stránku Účtová osnova."""

    def __init__(
        self,
        query: _ChartQuery,
        command: _ManageCommand,
    ) -> None:
        self._query = query
        self._command = command
        self._tridy: list[TridaGroup] = []
        self._show_inactive: bool = True
        self._error: str | None = None

    # ─── Read-only state ──────────────────────────────

    @property
    def tridy(self) -> list[TridaGroup]:
        return self._tridy

    @property
    def show_inactive(self) -> bool:
        return self._show_inactive

    @property
    def error(self) -> str | None:
        return self._error

    # ─── Commands ─────────────────────────────────────

    def load(self) -> None:
        """Načti osnovu."""
        try:
            self._tridy = self._query.execute(
                show_inactive=self._show_inactive,
            )
            self._error = None
        except Exception as exc:
            self._tridy = []
            self._error = str(exc) or exc.__class__.__name__

    def toggle_show_inactive(self) -> None:
        """Přepni filtr zobrazení neaktivních účtů."""
        self._show_inactive = not self._show_inactive
        self.load()

    def activate_ucet(self, cislo: str) -> None:
        """Aktivuj účet a reloadni."""
        try:
            self._command.activate_ucet(cislo)
            self._error = None
        except Exception as exc:
            self._error = str(exc)
        self.load()

    def deactivate_ucet(self, cislo: str) -> None:
        """Deaktivuj účet a reloadni."""
        try:
            self._command.deactivate_ucet(cislo)
            self._error = None
        except Exception as exc:
            self._error = str(exc)
        self.load()

    def add_analytika(
        self, syntetic_kod: str, suffix: str,
        nazev: str, popis: str | None = None,
    ) -> None:
        """Přidej analytiku a reloadni."""
        try:
            self._command.add_analytika(syntetic_kod, suffix, nazev, popis)
            self._error = None
        except Exception as exc:
            self._error = str(exc)
        self.load()

    def update_analytika(
        self, cislo: str, nazev: str, popis: str | None = None,
    ) -> None:
        """Uprav analytiku a reloadni."""
        try:
            self._command.update_analytika(cislo, nazev, popis)
            self._error = None
        except Exception as exc:
            self._error = str(exc)
        self.load()

    def update_ucet(
        self, cislo: str, nazev: str, popis: str | None = None,
    ) -> None:
        """Uprav účet (syntetický i analytický) a reloadni."""
        try:
            self._command.update_ucet(cislo, nazev, popis)
            self._error = None
        except Exception as exc:
            self._error = str(exc)
        self.load()
