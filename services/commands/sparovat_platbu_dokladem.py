"""SparovatPlatbuDoklademCommand — spáruje bankovní transakci s dokladem.

Vytvoří účetní zápisy na BV doklad:
  FP úhrada: MD 321 / Dal 221.xxx
  FV úhrada: MD 221.xxx / Dal 311

Kurzové rozdíly (pokud doklad v cizí měně):
  Ztráta: MD 563 / Dal 321 (nebo 311)
  Zisk: MD 321 (nebo 311) / Dal 663
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from domain.banka.bankovni_transakce import StavTransakce
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import ValidationError
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from infrastructure.database.repositories.banka_repository import (
    SqliteBankovniTransakceRepository,
    SqliteBankovniUcetRepository,
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
class SparovaniResult:
    """Výsledek spárování platby s dokladem."""

    ucetni_zaznam_ids: list[int]
    kurzovy_rozdil: Money | None
    doklad_uhrazen: bool


class SparovatPlatbuDoklademCommand:
    """Spáruje bankovní transakci s dokladem a vytvoří účetní zápisy."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(
        self,
        transakce_id: int,
        doklad_id: int,
    ) -> SparovaniResult:
        """Spáruje transakci s dokladem.

        1. Ověří stav transakce (NESPAROVANO) a dokladu (ZAUCTOVANY/CASTECNE)
        2. Zjistí BV doklad z výpisu + účet 221.xxx z bankovního účtu
        3. Vytvoří účetní zápis MD 321/Dal 221 (FP) nebo MD 221/Dal 311 (FV)
        4. Řeší kurzové rozdíly pro cizí měny
        5. Změní stav dokladu na UHRAZENY, transakci na SPAROVANO
        """
        uow = self._uow_factory()
        zaznam_ids: list[int] = []
        kurzovy_rozdil: Money | None = None

        with uow:
            tx_repo = SqliteBankovniTransakceRepository(uow)
            doklady_repo = SqliteDokladyRepository(uow)
            denik_repo = SqliteUcetniDenikRepository(uow)
            vypis_repo = SqliteBankovniVypisRepository(uow)
            ucet_repo = SqliteBankovniUcetRepository(uow)

            # Načti transakci
            tx = tx_repo.get(transakce_id)
            if tx is None:
                raise ValidationError(
                    f"Transakce {transakce_id} nenalezena.",
                )
            if tx.stav != StavTransakce.NESPAROVANO:
                raise ValidationError(
                    f"Transakce je ve stavu {tx.stav.value} — "
                    f"lze párovat jen nespárované.",
                )

            # Načti doklad
            doklad = doklady_repo.get_by_id(doklad_id)
            if doklad.stav not in (
                StavDokladu.ZAUCTOVANY,
                StavDokladu.CASTECNE_UHRAZENY,
            ):
                raise ValidationError(
                    f"Doklad {doklad.cislo} je ve stavu {doklad.stav.value} "
                    f"— lze párovat jen zaúčtované doklady.",
                )
            if doklad.typ not in (
                TypDokladu.FAKTURA_PRIJATA,
                TypDokladu.FAKTURA_VYDANA,
            ):
                raise ValidationError(
                    f"Doklad {doklad.cislo} je typu {doklad.typ.value} "
                    f"— párovat lze jen FP/FV.",
                )

            # Zjisti BV doklad a účet 221
            vypis = vypis_repo.get(tx.bankovni_vypis_id)
            if vypis is None:
                raise ValidationError("Výpis transakce nenalezen.")
            bv_doklad_id = vypis.bv_doklad_id

            ucet = ucet_repo.get(vypis.bankovni_ucet_id)
            if ucet is None:
                raise ValidationError("Bankovní účet nenalezen.")
            ucet_221 = ucet.ucet_kod  # e.g. "221.001"

            # Částka (absolutní hodnota)
            tx_castka = (
                tx.castka
                if tx.castka.is_positive
                else Money(-tx.castka.to_halire())
            )

            # Účty podle typu dokladu
            if doklad.typ == TypDokladu.FAKTURA_PRIJATA:
                md_ucet, dal_ucet = "321", ucet_221
            else:
                md_ucet, dal_ucet = ucet_221, "311"

            # Hlavní účetní zápis
            zaznam = UcetniZaznam(
                doklad_id=bv_doklad_id,
                datum=tx.datum_zauctovani,
                md_ucet=md_ucet,
                dal_ucet=dal_ucet,
                castka=tx_castka,
                popis=f"Úhrada {doklad.cislo}",
            )
            zapis_id = denik_repo.add(zaznam)
            zaznam_ids.append(zapis_id)

            # Kurzový rozdíl (cizí měna)
            if (
                doklad.castka_mena is not None
                and doklad.kurz is not None
                and doklad.mena.value != "CZK"
            ):
                # Účetní hodnota dokladu v CZK
                doklad_czk = doklad.castka_celkem
                # Skutečná platba v CZK (z banky)
                platba_czk = tx_castka
                rozdil = platba_czk - doklad_czk

                if rozdil != Money.zero():
                    kurzovy_rozdil = rozdil
                    abs_rozdil = (
                        rozdil
                        if rozdil.is_positive
                        else Money(-rozdil.to_halire())
                    )

                    if rozdil.is_positive:
                        # Kurzová ztráta — zaplatili jsme víc
                        kurz_zaznam = UcetniZaznam(
                            doklad_id=bv_doklad_id,
                            datum=tx.datum_zauctovani,
                            md_ucet="563",
                            dal_ucet=md_ucet if doklad.typ == TypDokladu.FAKTURA_PRIJATA else dal_ucet,
                            castka=abs_rozdil,
                            popis=f"Kurzová ztráta {doklad.cislo}",
                        )
                    else:
                        # Kurzový zisk — zaplatili jsme méně
                        kurz_zaznam = UcetniZaznam(
                            doklad_id=bv_doklad_id,
                            datum=tx.datum_zauctovani,
                            md_ucet=md_ucet if doklad.typ == TypDokladu.FAKTURA_PRIJATA else dal_ucet,
                            dal_ucet="663",
                            castka=abs_rozdil,
                            popis=f"Kurzový zisk {doklad.cislo}",
                        )
                    kurz_id = denik_repo.add(kurz_zaznam)
                    zaznam_ids.append(kurz_id)

            # Spáruj transakci
            tx.sparuj(doklad_id)
            tx.ucetni_zapis_id = zapis_id
            tx_repo.update(tx)

            # Změň stav dokladu na UHRAZENY
            doklad.oznac_uhrazeny()
            doklady_repo.update(doklad)

            uow.commit()

        return SparovaniResult(
            ucetni_zaznam_ids=zaznam_ids,
            kurzovy_rozdil=kurzovy_rozdil,
            doklad_uhrazen=True,
        )
