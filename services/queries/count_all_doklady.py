"""CountAllDokladyQuery — triviální read-only query pro status bar.

Vrátí celkový počet všech dokladů v DB bez ohledu na typ/stav/flag.
Používá se pro status bar pod tabulkou Doklady:
„Zobrazeno X z Y dokladů · N filtrů aktivní".
"""

from __future__ import annotations

from typing import Callable

from domain.doklady.repository import DokladyRepository
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class CountAllDokladyQuery:
    """Read-only query: vrátí celkový počet všech dokladů v DB.

    Použití: status bar „Zobrazeno X z Y dokladů" pod tabulkou Doklady,
    aby uživatel viděl, kolik dokladů je celkem v evidenci a kolik
    z toho je aktuálně zobrazeno po aplikaci filtrů.
    """

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
    ) -> None:
        self._uow_factory = uow_factory
        self._doklady_repo_factory = doklady_repo_factory

    def execute(self) -> int:
        """Vrátí celkový počet dokladů v DB."""
        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            return repo.count_all()
