"""DphPodaniCommand — označení DPH přiznání jako podaného."""

from __future__ import annotations

from datetime import date
from typing import Callable

from infrastructure.database.unit_of_work import SqliteUnitOfWork


class DphPodaniCommand:
    """Nastaví/odnastaví flag podáno pro DPH přiznání za měsíc."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(
        self,
        rok: int,
        mesic: int,
        podano: bool,
        poznamka: str | None = None,
    ) -> None:
        uow = self._uow_factory()
        with uow:
            conn = uow.connection
            datum_podani = date.today().isoformat() if podano else None
            conn.execute(
                """
                INSERT INTO dph_podani (rok, mesic, podano, datum_podani, poznamka)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (rok, mesic) DO UPDATE SET
                    podano = excluded.podano,
                    datum_podani = excluded.datum_podani,
                    poznamka = excluded.poznamka
                """,
                (rok, mesic, 1 if podano else 0, datum_podani, poznamka),
            )
            uow.commit()
