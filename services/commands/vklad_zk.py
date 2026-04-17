"""VkladZKCommand — vytvoří 2 ID doklady pro upsání a splacení ZK."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork


@dataclass(frozen=True)
class SpolecnikPodil:
    """Podíl společníka na ZK."""

    partner_id: int
    nazev: str
    podil_procent: Decimal
    castka: Money


class VkladZKCommand:
    """Vytvoří 2 ID doklady: upsání + splacení ZK."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(
        self,
        castka_zk: Money,
        datum: date,
        bankovni_ucet: str,
        rok: int,
    ) -> list[int]:
        """Vrátí seznam ID vytvořených dokladů."""
        uow = self._uow_factory()
        with uow:
            drepo = SqliteDokladyRepository(uow)
            denik = SqliteUcetniDenikRepository(uow)

            created_ids: list[int] = []

            # 1. ID doklad: Upsání ZK (MD 353 / Dal 411)
            cislo_1 = f"ID-{rok}-001"
            if not drepo.existuje_cislo(cislo_1):
                d1 = Doklad(
                    cislo=cislo_1,
                    typ=TypDokladu.INTERNI_DOKLAD,
                    datum_vystaveni=datum,
                    castka_celkem=castka_zk,
                    popis="Upsání základního kapitálu",
                )
                drepo.add(d1)
                loaded_1 = drepo.get_by_cislo(cislo_1)

                predpis_1 = UctovyPredpis(
                    doklad_id=loaded_1.id,
                    zaznamy=(
                        UcetniZaznam(
                            doklad_id=loaded_1.id,
                            datum=datum,
                            md_ucet="353",
                            dal_ucet="411",
                            castka=castka_zk,
                            popis="Upsání ZK",
                        ),
                    ),
                )
                denik.zauctuj(predpis_1)
                loaded_1.zauctuj()
                drepo.update(loaded_1)
                created_ids.append(loaded_1.id)

            # 2. ID doklad: Splacení ZK (MD bankovni_ucet / Dal 353)
            cislo_2 = f"ID-{rok}-002"
            if not drepo.existuje_cislo(cislo_2):
                d2 = Doklad(
                    cislo=cislo_2,
                    typ=TypDokladu.INTERNI_DOKLAD,
                    datum_vystaveni=datum,
                    castka_celkem=castka_zk,
                    popis="Splacení základního kapitálu na bankovní účet",
                )
                drepo.add(d2)
                loaded_2 = drepo.get_by_cislo(cislo_2)

                predpis_2 = UctovyPredpis(
                    doklad_id=loaded_2.id,
                    zaznamy=(
                        UcetniZaznam(
                            doklad_id=loaded_2.id,
                            datum=datum,
                            md_ucet=bankovni_ucet,
                            dal_ucet="353",
                            castka=castka_zk,
                            popis="Splacení ZK na bankovní účet",
                        ),
                    ),
                )
                denik.zauctuj(predpis_2)
                loaded_2.zauctuj()
                drepo.update(loaded_2)
                created_ids.append(loaded_2.id)

            uow.commit()
        return created_ids
