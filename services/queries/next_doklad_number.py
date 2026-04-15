"""NextDokladNumberQuery — návrh čísla pro nový doklad.

Format: ``{TYP}-{ROK}-{NEXT:03d}``, např. ``"FV-2026-004"``.

Algoritmus:
1. Načte všechny doklady v daném roce přes ``list_by_obdobi``.
2. Filtruje podle typu.
3. Vyparsuje číslicovou část z konce čísla (matching regex).
4. Vrátí ``max + 1`` (nebo ``001`` pokud žádný neexistuje).

TODO Fáze 9: konfigurovatelné číselné řady (uživatelské masky, různé řady
pro různé typy, reset počítadla na začátku roku).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Callable

from domain.doklady.repository import DokladyRepository
from domain.doklady.typy import TypDokladu
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class NextDokladNumberQuery:
    """Read-only query: navrhne další číslo pro nový doklad."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
    ) -> None:
        self._uow_factory = uow_factory
        self._doklady_repo_factory = doklady_repo_factory

    def execute(self, typ: TypDokladu, rok: int) -> str:
        """Vrátí navrhované číslo typu ``"FV-2026-005"``.

        Pokud existují doklady s nestandardními čísly (např. ``"FAK-001"``),
        jsou ignorovány — regex match pouze na očekávaný formát.
        """
        prefix = f"{typ.value}-{rok}-"
        pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")

        start = date(rok, 1, 1)
        end = date(rok, 12, 31)

        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            doklady = repo.list_by_obdobi(start, end, limit=10_000)

        max_num = 0
        for d in doklady:
            if d.typ != typ:
                continue
            match = pattern.match(d.cislo)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num

        return f"{prefix}{max_num + 1:03d}"
