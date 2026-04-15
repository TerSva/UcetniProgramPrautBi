"""DokladFormViewModel — prezentační stav pro dialog „Nový doklad".

Pure Python, žádný Qt import. Drží:
    * navrhované číslo (z NextDokladNumberQuery — pre-fill pole „Číslo")
    * poslední úspěšně vytvořený DTO (``created_item``)
    * chybu z posledního pokusu (``error``)

Dialog si drží vlastní widgetový stav formuláře. VM obsluhuje pouze:
    * ``suggest_cislo(typ, rok)`` — vrátí navrhované číslo, neukládá state
    * ``submit(data)`` — zavolá CreateDokladCommand, vrátí DTO | None
"""

from __future__ import annotations

from typing import Protocol

from domain.doklady.typy import TypDokladu
from services.commands.create_doklad import CreateDokladInput
from services.queries.doklady_list import DokladyListItem


class _NextNumberQuery(Protocol):
    def execute(self, typ: TypDokladu, rok: int) -> str: ...


class _CreateCommand(Protocol):
    def execute(self, data: CreateDokladInput) -> DokladyListItem: ...


class DokladFormViewModel:
    """ViewModel pro dialog nového dokladu."""

    def __init__(
        self,
        next_number_query: _NextNumberQuery,
        create_command: _CreateCommand,
    ) -> None:
        self._next_number_query = next_number_query
        self._create_command = create_command
        self._created_item: DokladyListItem | None = None
        self._error: str | None = None

    # ─── Read-only state ──────────────────────────────────────────────

    @property
    def created_item(self) -> DokladyListItem | None:
        """DTO posledně úspěšně vytvořeného dokladu (None před submit)."""
        return self._created_item

    @property
    def error(self) -> str | None:
        """Text chyby z posledního submit (None pokud OK)."""
        return self._error

    # ─── Commands ─────────────────────────────────────────────────────

    def suggest_cislo(self, typ: TypDokladu, rok: int) -> str:
        """Navrhne číslo pro zadaný typ + rok (``"FV-2026-004"``).

        Pokud query selže, vrací prázdný řetězec a nastaví ``error``.
        UI si číslo dosadí do pole, uživatelka ho může přepsat.
        """
        try:
            cislo = self._next_number_query.execute(typ, rok)
            self._error = None
            return cislo
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
            return ""

    def submit(self, data: CreateDokladInput) -> DokladyListItem | None:
        """Zavolá CreateDokladCommand. Vrátí DTO nebo None při chybě.

        Při chybě nastaví ``error`` (text pro UI). DTO je také dostupné
        přes ``created_item``.
        """
        try:
            item = self._create_command.execute(data)
            self._created_item = item
            self._error = None
            return item
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
            self._created_item = None
            return None
