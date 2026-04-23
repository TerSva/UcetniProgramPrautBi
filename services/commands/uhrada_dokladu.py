"""UhradaDokladuCommand — úhrada FP/FV pokladnou nebo interním dokladem.

Pokladnou:
  FP: Vytvoří PD doklad, zaúčtuje MD 321 / Dal 211
  FV: Vytvoří PD doklad, zaúčtuje MD 211 / Dal 311

Interním dokladem (pytlování):
  FP: Vytvoří ID doklad, zaúčtuje MD 321 / Dal 365.xxx
  FV: Vytvoří ID doklad, zaúčtuje MD 365.xxx / Dal 311
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import ValidationError
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork


@dataclass(frozen=True)
class UhradaResult:
    """Výsledek úhrady dokladu."""

    novy_doklad_id: int
    novy_doklad_cislo: str
    ucetni_zaznam_id: int


class UhradaPokladnouCommand:
    """Úhrada FP/FV pokladnou — vytvoří PD doklad + účetní zápis."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(
        self,
        doklad_id: int,
        datum_uhrady: date,
        cislo_pd: str,
        popis: str | None = None,
    ) -> UhradaResult:
        uow = self._uow_factory()
        with uow:
            doklady_repo = SqliteDokladyRepository(uow)
            denik_repo = SqliteUcetniDenikRepository(uow)

            doklad = doklady_repo.get_by_id(doklad_id)
            self._validate(doklad)

            # Vytvoř PD doklad
            pd = Doklad(
                cislo=cislo_pd,
                typ=TypDokladu.POKLADNI_DOKLAD,
                datum_vystaveni=datum_uhrady,
                castka_celkem=doklad.castka_celkem,
                partner_id=doklad.partner_id,
                popis=popis or f"Úhrada {doklad.cislo} pokladnou",
                stav=StavDokladu.ZAUCTOVANY,
            )
            pd = doklady_repo.add(pd)

            # Účtování
            if doklad.typ == TypDokladu.FAKTURA_PRIJATA:
                md_ucet, dal_ucet = "321", "211"
            else:
                md_ucet, dal_ucet = "211", "311"

            zaznam = UcetniZaznam(
                doklad_id=pd.id,
                datum=datum_uhrady,
                md_ucet=md_ucet,
                dal_ucet=dal_ucet,
                castka=doklad.castka_celkem,
                popis=popis or f"Úhrada {doklad.cislo} pokladnou",
            )
            zapis_id = denik_repo.add(zaznam)

            # Označ původní doklad jako uhrazený
            doklad.oznac_uhrazeny()
            doklady_repo.update(doklad)

            uow.commit()

        return UhradaResult(
            novy_doklad_id=pd.id,
            novy_doklad_cislo=cislo_pd,
            ucetni_zaznam_id=zapis_id,
        )

    @staticmethod
    def _validate(doklad: Doklad) -> None:
        if doklad.typ not in (
            TypDokladu.FAKTURA_PRIJATA,
            TypDokladu.FAKTURA_VYDANA,
        ):
            raise ValidationError(
                f"Úhradu pokladnou lze provést jen pro FP/FV, "
                f"ne {doklad.typ.value}.",
            )
        if doklad.stav not in (
            StavDokladu.ZAUCTOVANY,
            StavDokladu.CASTECNE_UHRAZENY,
        ):
            raise ValidationError(
                f"Doklad {doklad.cislo} je ve stavu {doklad.stav.value} "
                f"— úhradu lze provést jen u zaúčtovaných dokladů.",
            )


class UhradaIntDoklademCommand:
    """Úhrada FP/FV interním dokladem (pytlování přes 365.xxx)."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(
        self,
        doklad_id: int,
        datum_uhrady: date,
        cislo_id: str,
        ucet_spolecnika: str,
        popis: str | None = None,
    ) -> UhradaResult:
        """
        Args:
            ucet_spolecnika: analytika 365.xxx (např. "365.001").
        """
        uow = self._uow_factory()
        with uow:
            doklady_repo = SqliteDokladyRepository(uow)
            denik_repo = SqliteUcetniDenikRepository(uow)

            doklad = doklady_repo.get_by_id(doklad_id)
            self._validate(doklad)

            # Vytvoř ID doklad
            id_doklad = Doklad(
                cislo=cislo_id,
                typ=TypDokladu.INTERNI_DOKLAD,
                datum_vystaveni=datum_uhrady,
                castka_celkem=doklad.castka_celkem,
                partner_id=doklad.partner_id,
                popis=popis or f"Úhrada {doklad.cislo} ze soukromé karty",
                stav=StavDokladu.ZAUCTOVANY,
            )
            id_doklad = doklady_repo.add(id_doklad)

            # Účtování — pytlování přes 365
            if doklad.typ == TypDokladu.FAKTURA_PRIJATA:
                md_ucet, dal_ucet = "321", ucet_spolecnika
            else:
                md_ucet, dal_ucet = ucet_spolecnika, "311"

            zaznam = UcetniZaznam(
                doklad_id=id_doklad.id,
                datum=datum_uhrady,
                md_ucet=md_ucet,
                dal_ucet=dal_ucet,
                castka=doklad.castka_celkem,
                popis=popis or f"Úhrada {doklad.cislo} ze soukromé karty",
            )
            zapis_id = denik_repo.add(zaznam)

            # Označ původní doklad jako uhrazený
            doklad.oznac_uhrazeny()
            doklady_repo.update(doklad)

            uow.commit()

        return UhradaResult(
            novy_doklad_id=id_doklad.id,
            novy_doklad_cislo=cislo_id,
            ucetni_zaznam_id=zapis_id,
        )

    @staticmethod
    def _validate(doklad: Doklad) -> None:
        if doklad.typ not in (
            TypDokladu.FAKTURA_PRIJATA,
            TypDokladu.FAKTURA_VYDANA,
        ):
            raise ValidationError(
                f"Úhradu interním dokladem lze provést jen pro FP/FV.",
            )
        if doklad.stav not in (
            StavDokladu.ZAUCTOVANY,
            StavDokladu.CASTECNE_UHRAZENY,
        ):
            raise ValidationError(
                f"Doklad {doklad.cislo} je ve stavu {doklad.stav.value}.",
            )
