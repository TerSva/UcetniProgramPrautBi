"""PrilohaCommands — připojení PDF příloh k dokladům."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from domain.doklady.priloha import PrilohaDokladu
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.priloha_repository import (
    SqlitePrilohaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from infrastructure.storage.priloha_storage import PrilohaStorage


class PrilohaCommands:
    """Správa příloh dokladů — připojení PDF, smazání."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        storage: PrilohaStorage | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._storage = storage or PrilohaStorage()

    def priloz_pdf_k_dokladu(
        self,
        doklad_id: int,
        source_path: Path,
        original_name: str,
    ) -> PrilohaDokladu:
        """Zkopíruje PDF a vytvoří záznam v DB.

        Args:
            doklad_id: ID dokladu, ke kterému se příloha připojí.
            source_path: Cesta ke zdrojovému souboru na disku.
            original_name: Původní název souboru (ukládá se do DB nezměněný).

        Returns:
            Uložená PrilohaDokladu s naplněným id.

        Raises:
            ValueError: Doklad neexistuje.
        """
        uow = self._uow_factory()
        with uow:
            drepo = SqliteDokladyRepository(uow)
            prepo = SqlitePrilohaRepository(uow)

            doklad = drepo.get_by_id(doklad_id)

            rel_path, size = self._storage.save(
                source_path,
                doklad_typ=doklad.typ.value,
                doklad_cislo=doklad.cislo,
                original_name=original_name,
                rok=doklad.datum_vystaveni.year,
            )

            priloha = PrilohaDokladu(
                id=None,
                doklad_id=doklad_id,
                nazev_souboru=original_name,
                relativni_cesta=rel_path,
                velikost_bytes=size,
                mime_type="application/pdf",
                vytvoreno=datetime.now(),
            )
            saved = prepo.add(priloha)
            uow.commit()
            return saved
