"""DuplikovatDokladCommand — připraví data pro duplikát dokladu.

Neukládá do DB — pouze načte zdrojový doklad, vygeneruje nové číslo
a vrátí DokladyListItem s předvyplněnými daty. Skutečné uložení
probíhá přes DokladFormDialog → CreateDokladCommand.

Zkopíruje: typ, partner_id, castka_celkem, mena, kurz, castka_mena,
dph_rezim, popis.

Resetuje: cislo (auto-generované), datum (dnes), datum_splatnosti (None),
variabilni_symbol (None), stav (NOVY), k_doreseni (True + poznámka).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable

from domain.doklady.repository import DokladyRepository
from domain.doklady.typy import DphRezim, Mena, TypDokladu
from domain.shared.errors import ValidationError
from domain.shared.money import Money
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.next_doklad_number import NextDokladNumberQuery


@dataclass(frozen=True)
class DuplikatData:
    """Data z zdrojového dokladu pro předvyplnění formuláře."""

    zdrojove_cislo: str
    nove_cislo: str
    typ: TypDokladu
    datum_vystaveni: date
    partner_id: int | None
    castka_celkem: Money
    mena: Mena
    castka_mena: Money | None
    kurz: Decimal | None
    dph_rezim: DphRezim
    popis: str | None


class DuplikovatDokladCommand:
    """Připraví data pro duplikát dokladu (bez uložení do DB)."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
        next_number_query: NextDokladNumberQuery,
    ) -> None:
        self._uow_factory = uow_factory
        self._doklady_repo_factory = doklady_repo_factory
        self._next_number_query = next_number_query

    def execute(self, zdrojovy_doklad_id: int) -> DuplikatData:
        """Načte zdrojový doklad a připraví data pro duplikát.

        Raises:
            ValidationError: zdrojový doklad neexistuje.
        """
        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            zdroj = repo.get_by_id(zdrojovy_doklad_id)
            if zdroj is None:
                raise ValidationError(
                    f"Zdrojový doklad s id={zdrojovy_doklad_id} neexistuje."
                )

        # Rok z účetního období zdrojového dokladu (ne dnešní)
        rok = zdroj.datum_vystaveni.year
        nove_cislo = self._next_number_query.execute(zdroj.typ, rok)

        return DuplikatData(
            zdrojove_cislo=zdroj.cislo,
            nove_cislo=nove_cislo,
            typ=zdroj.typ,
            datum_vystaveni=zdroj.datum_vystaveni,
            partner_id=zdroj.partner_id,
            castka_celkem=zdroj.castka_celkem,
            mena=zdroj.mena,
            castka_mena=zdroj.castka_mena,
            kurz=zdroj.kurz,
            dph_rezim=zdroj.dph_rezim,
            popis=zdroj.popis,
        )
