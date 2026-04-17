"""SmazatVypisCommand — kaskádní smazání bankovního výpisu."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from infrastructure.database.repositories.banka_repository import (
    SqliteBankovniTransakceRepository,
    SqliteBankovniVypisRepository,
)
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork


@dataclass(frozen=True)
class SmazatVypisResult:
    """Výsledek smazání výpisu."""

    success: bool
    smazano_transakci: int = 0
    smazano_ucetnich_zapisu: int = 0
    smazan_doklad: bool = False
    smazany_soubory: list[str] | None = None
    error: str | None = None


class SmazatVypisCommand:
    """Kaskádní smazání bankovního výpisu.

    Pořadí:
    1. Smaž účetní záznamy (ucetni_zaznamy) navázané na BV doklad
    2. Smaž transakce (bankovni_transakce) navázané na výpis
    3. Smaž výpis (bankovni_vypisy)
    4. Smaž BV doklad (doklady)
    5. Smaž PDF + CSV soubory z disku
    """

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(self, vypis_id: int) -> SmazatVypisResult:
        """Smaže výpis a vše navázané."""
        uow = self._uow_factory()
        with uow:
            vypis_repo = SqliteBankovniVypisRepository(uow)
            tx_repo = SqliteBankovniTransakceRepository(uow)
            doklady_repo = SqliteDokladyRepository(uow)
            denik_repo = SqliteUcetniDenikRepository(uow)

            # Načti výpis
            vypis = vypis_repo.get(vypis_id)
            if vypis is None:
                return SmazatVypisResult(
                    success=False,
                    error=f"Výpis s ID {vypis_id} nenalezen",
                )

            # 1. Smaž účetní záznamy navázané na BV doklad
            smazano_zapisu = 0
            if vypis.bv_doklad_id:
                smazano_zapisu = denik_repo.delete_by_doklad(vypis.bv_doklad_id)

            # 2. Smaž transakce
            smazano_tx = tx_repo.delete_by_vypis(vypis_id)

            # 3. Smaž výpis
            vypis_repo.delete(vypis_id)

            # 4. Smaž BV doklad (force delete — obejdeme stav check)
            smazan_doklad = False
            if vypis.bv_doklad_id:
                uow.connection.execute(
                    "DELETE FROM doklady WHERE id = ?",
                    (vypis.bv_doklad_id,),
                )
                smazan_doklad = True

            uow.commit()

        # 5. Smaž soubory z disku (mimo UoW)
        smazane_soubory: list[str] = []
        for path_str in [vypis.pdf_path, vypis.csv_path]:
            if path_str and os.path.exists(path_str):
                try:
                    os.remove(path_str)
                    smazane_soubory.append(path_str)
                except OSError:
                    pass

        return SmazatVypisResult(
            success=True,
            smazano_transakci=smazano_tx,
            smazano_ucetnich_zapisu=smazano_zapisu,
            smazan_doklad=smazan_doklad,
            smazany_soubory=smazane_soubory,
        )
