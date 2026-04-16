"""DokladFormViewModel — prezentační stav pro dialog „Nový doklad".

Pure Python, žádný Qt import. Drží:
    * navrhované číslo (z NextDokladNumberQuery — pre-fill pole „Číslo")
    * poslední úspěšně vytvořený DTO (``created_item``)
    * chybu z posledního pokusu (``error``)

Dialog si drží vlastní widgetový stav formuláře. VM obsluhuje pouze:
    * ``suggest_cislo(typ, rok)`` — vrátí navrhované číslo, neukládá state
    * ``submit(data, k_doreseni, poznamka)`` — zavolá CreateDokladCommand,
      při požadavku na flag následně DokladActionsCommand.oznac_k_doreseni.
      Vrátí DTO | None.

Fáze 6.7 — atomicita: create + flag běží ve DVOU UoW transakcích (jedna
pro create v ``CreateDokladCommand``, druhá pro ``oznac_k_doreseni`` v
``DokladActionsCommand``). Když selže druhá transakce, doklad existuje,
ale flag není nastavený; VM vrátí vytvořený DTO a nastaví ``error``.
TODO (post-MVP): dedikovaný ``CreateAndFlagDokladCommand`` pro jednu
transakci — viz ROADMAP.
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


class _ActionsCommand(Protocol):
    def oznac_k_doreseni(
        self, doklad_id: int, poznamka: str | None = None,
    ) -> DokladyListItem: ...


class DokladFormViewModel:
    """ViewModel pro dialog nového dokladu."""

    def __init__(
        self,
        next_number_query: _NextNumberQuery,
        create_command: _CreateCommand,
        actions_command: _ActionsCommand | None = None,
    ) -> None:
        self._next_number_query = next_number_query
        self._create_command = create_command
        self._actions_command = actions_command
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

    def submit(
        self,
        data: CreateDokladInput,
        k_doreseni: bool = False,
        poznamka_doreseni: str | None = None,
    ) -> DokladyListItem | None:
        """Zavolá CreateDokladCommand. Vrátí DTO nebo None při chybě.

        Při chybě v create nastaví ``error`` (text pro UI). DTO je také
        dostupné přes ``created_item``.

        Pokud ``k_doreseni=True``, po úspěšném create navíc zavolá
        ``DokladActionsCommand.oznac_k_doreseni(doklad_id, poznamka)``.
        Když flag krok selže, doklad zůstane vytvořený (DTO se vrátí)
        a ``error`` obsahuje popis chyby — UI může zobrazit toast.
        """
        try:
            item = self._create_command.execute(data)
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
            self._created_item = None
            return None

        if k_doreseni and self._actions_command is not None:
            try:
                item = self._actions_command.oznac_k_doreseni(
                    item.id, poznamka_doreseni,
                )
            except Exception as exc:  # noqa: BLE001
                # Doklad vznikl, ale flag se nepodařilo nastavit.
                # Vracíme původní item, ale error informuje UI.
                self._created_item = item
                self._error = (
                    f"Doklad vytvořen, ale nepodařilo se označit k dořešení: "
                    f"{exc or exc.__class__.__name__}"
                )
                return item

        self._created_item = item
        self._error = None
        return item
