"""DokladyListViewModel — prezentační stav pro Doklady stránku.

Pure Python, žádný Qt import. Drží aktuální filtr + poslední načtený
seznam + případný error. Page volá commands (apply_filters, clear_filters,
set_k_doreseni_only) a po každém commandu čte properties.
"""

from __future__ import annotations

from typing import Protocol

from services.queries.doklady_list import (
    DokladyFilter,
    DokladyListItem,
    KDoreseniFilter,
)


class _DokladyListQuery(Protocol):
    """Strukturální typ — cokoli s `execute(f) -> list[DokladyListItem]`."""

    def execute(self, f: DokladyFilter) -> list[DokladyListItem]: ...


class DokladyListViewModel:
    """ViewModel pro stránku Doklady. Bez Qt, jen Python state."""

    def __init__(self, query: _DokladyListQuery) -> None:
        self._query = query
        self._items: list[DokladyListItem] = []
        self._filter: DokladyFilter = DokladyFilter()
        self._error: str | None = None
        self._loaded: bool = False

    # ────────────────────────────────────────────────
    # Read-only state
    # ────────────────────────────────────────────────

    @property
    def items(self) -> list[DokladyListItem]:
        """Snapshot posledně načtených dokladů. Prázdný list před load()."""
        return self._items

    @property
    def filter(self) -> DokladyFilter:
        """Aktuálně platný filtr."""
        return self._filter

    @property
    def error(self) -> str | None:
        """Text chyby z posledního pokusu (None pokud OK nebo před load)."""
        return self._error

    @property
    def has_data(self) -> bool:
        """True pokud byl proveden alespoň jeden úspěšný load."""
        return self._loaded and self._error is None

    @property
    def is_empty_because_of_filter(self) -> bool:
        """True, když items=[] ale filtr není výchozí.

        Odlišuje "prázdná DB" (zobraz CTA „Vytvoř první doklad")
        od "žádné výsledky kvůli filtru" (zobraz „Vymazat filtry").
        """
        return (
            self._loaded
            and not self._items
            and not self._filter.je_vychozi
        )

    # ────────────────────────────────────────────────
    # Commands
    # ────────────────────────────────────────────────

    def load(self) -> None:
        """Načti data se současným filtrem. Při výjimce nastav error."""
        try:
            self._items = self._query.execute(self._filter)
            self._error = None
        except Exception as exc:  # noqa: BLE001 — UI musí přežít cokoli
            self._items = []
            self._error = str(exc) or exc.__class__.__name__
        self._loaded = True

    def apply_filters(self, new_filter: DokladyFilter) -> None:
        """Nahraď filtr novým snapshotem a reloadni data."""
        self._filter = new_filter
        self.load()

    def clear_filters(self) -> None:
        """Vrať se na výchozí filtr a reloadni."""
        self._filter = DokladyFilter()
        self.load()

    def set_k_doreseni_only(self) -> None:
        """Dashboard drill — KDoreseniFilter.POUZE, ostatní filtry resetuj.

        Vrací uživatele na view „jen doklady k dořešení" bez ohledu
        na předchozí stav filtrů.
        """
        self._filter = DokladyFilter(k_doreseni=KDoreseniFilter.POUZE)
        self.load()
