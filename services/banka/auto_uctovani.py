"""AutoUctovaniBankyCommand — automatické zaúčtování bankovních transakcí.

Pravidla:
    1. Poplatky (popis obsahuje "Poplatek"/"Fee") → MD 568 / Dal 221.xxx
    2. Úroky (popis obsahuje "Úrok připsaný") → MD 221.xxx / Dal 662
    3. Daň z úroků (popis obsahuje "Daň z úroků") → MD 591 / Dal 221.xxx
    4. VS matching — najde FP/FV s odpovídajícím VS:
       - FP úhrada: MD 321 / Dal 221.xxx
       - FV úhrada: MD 221.xxx / Dal 311
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Literal

from domain.banka.bankovni_transakce import BankovniTransakce, StavTransakce
from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
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
class AutoUctovaniResult:
    """Výsledek automatického zaúčtování."""

    pocet_zauctovano: int = 0
    pocet_sparovano: int = 0
    pocet_preskoceno: int = 0
    chyby: list[str] | None = None


#: Klíčová slova pro auto-accounting pravidla.
_POPLATEK_KEYWORDS = ("poplatek", "fee", "správa účtu", "vedení účtu")
_UROK_KEYWORDS = ("úrok připsaný", "kreditní úrok", "připsaný úrok")
_DAN_KEYWORDS = ("daň z úroků", "srážková daň")


class AutoUctovaniBankyCommand:
    """Automatické zaúčtování transakcí z bankovního výpisu."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(self, vypis_id: int) -> AutoUctovaniResult:
        """Zpracuje nespárované transakce daného výpisu."""
        uow = self._uow_factory()
        zauctovano = 0
        sparovano = 0
        preskoceno = 0
        chyby: list[str] = []

        with uow:
            tx_repo = SqliteBankovniTransakceRepository(uow)
            vypis_repo = SqliteBankovniVypisRepository(uow)
            doklady_repo = SqliteDokladyRepository(uow)
            denik_repo = SqliteUcetniDenikRepository(uow)

            vypis = vypis_repo.get(vypis_id)
            if vypis is None:
                return AutoUctovaniResult(chyby=["Výpis nenalezen"])

            # Get the ucet_kod for the 221 account
            from infrastructure.database.repositories.banka_repository import (
                SqliteBankovniUcetRepository,
            )
            ucet_repo = SqliteBankovniUcetRepository(uow)
            ucet = ucet_repo.get(vypis.bankovni_ucet_id)
            if ucet is None:
                return AutoUctovaniResult(chyby=["Bankovní účet nenalezen"])
            ucet_221 = ucet.ucet_kod  # e.g. "221.001"

            transakce = tx_repo.list_by_vypis(
                vypis_id, stav=StavTransakce.NESPAROVANO,
            )

            for tx in transakce:
                result = self._process_transaction(
                    tx, ucet_221, doklady_repo, denik_repo, tx_repo,
                )
                if result == "zauctovano":
                    zauctovano += 1
                elif result == "sparovano":
                    sparovano += 1
                else:
                    preskoceno += 1

            uow.commit()

        return AutoUctovaniResult(
            pocet_zauctovano=zauctovano,
            pocet_sparovano=sparovano,
            pocet_preskoceno=preskoceno,
            chyby=chyby if chyby else None,
        )

    def _process_transaction(
        self,
        tx: BankovniTransakce,
        ucet_221: str,
        doklady_repo: SqliteDokladyRepository,
        denik_repo: SqliteUcetniDenikRepository,
        tx_repo: SqliteBankovniTransakceRepository,
    ) -> Literal["zauctovano", "sparovano", "preskoceno"]:
        """Zpracuj jednu transakci. Vrací typ výsledku."""
        popis_lower = (tx.popis or "").lower()

        # 1. Poplatek → MD 568 / Dal 221
        if any(kw in popis_lower for kw in _POPLATEK_KEYWORDS):
            castka = tx.castka if tx.castka.is_positive else Money(-tx.castka.to_halire())
            zaznam = UcetniZaznam(
                doklad_id=self._get_bv_doklad_id(tx, tx_repo),
                datum=tx.datum_zauctovani,
                md_ucet="568",
                dal_ucet=ucet_221,
                castka=castka,
                popis=f"Bankovní poplatek: {tx.popis}",
            )
            zapis_id = denik_repo.add(zaznam)
            tx.auto_zauctuj(zapis_id)
            tx_repo.update(tx)
            return "zauctovano"

        # 2. Úrok připsaný → MD 221 / Dal 662
        if any(kw in popis_lower for kw in _UROK_KEYWORDS):
            castka = tx.castka if tx.castka.is_positive else Money(-tx.castka.to_halire())
            zaznam = UcetniZaznam(
                doklad_id=self._get_bv_doklad_id(tx, tx_repo),
                datum=tx.datum_zauctovani,
                md_ucet=ucet_221,
                dal_ucet="662",
                castka=castka,
                popis=f"Úrok připsaný: {tx.popis}",
            )
            zapis_id = denik_repo.add(zaznam)
            tx.auto_zauctuj(zapis_id)
            tx_repo.update(tx)
            return "zauctovano"

        # 3. Daň z úroků → MD 591 / Dal 221
        if any(kw in popis_lower for kw in _DAN_KEYWORDS):
            castka = tx.castka if tx.castka.is_positive else Money(-tx.castka.to_halire())
            zaznam = UcetniZaznam(
                doklad_id=self._get_bv_doklad_id(tx, tx_repo),
                datum=tx.datum_zauctovani,
                md_ucet="591",
                dal_ucet=ucet_221,
                castka=castka,
                popis=f"Daň z úroků: {tx.popis}",
            )
            zapis_id = denik_repo.add(zaznam)
            tx.auto_zauctuj(zapis_id)
            tx_repo.update(tx)
            return "zauctovano"

        # 4. VS matching — hledej FP/FV
        if tx.variabilni_symbol:
            doklad = doklady_repo.find_by_vs(tx.variabilni_symbol)
            if doklad is not None and doklad.stav == StavDokladu.ZAUCTOVANY:
                castka = tx.castka if tx.castka.is_positive else Money(-tx.castka.to_halire())
                if doklad.typ == TypDokladu.FAKTURA_PRIJATA:
                    # FP úhrada: MD 321 / Dal 221
                    md, dal = "321", ucet_221
                elif doklad.typ == TypDokladu.FAKTURA_VYDANA:
                    # FV úhrada: MD 221 / Dal 311
                    md, dal = ucet_221, "311"
                else:
                    return "preskoceno"

                zaznam = UcetniZaznam(
                    doklad_id=doklad.id,
                    datum=tx.datum_zauctovani,
                    md_ucet=md,
                    dal_ucet=dal,
                    castka=castka,
                    popis=f"Úhrada {doklad.cislo} (VS {tx.variabilni_symbol})",
                )
                zapis_id = denik_repo.add(zaznam)
                tx.sparuj(doklad.id)
                tx.ucetni_zapis_id = zapis_id
                tx_repo.update(tx)
                return "sparovano"

        return "preskoceno"

    @staticmethod
    def _get_bv_doklad_id(
        tx: BankovniTransakce,
        tx_repo: SqliteBankovniTransakceRepository,
    ) -> int:
        """Získej BV doklad_id z výpisu transakce."""
        from infrastructure.database.repositories.banka_repository import (
            SqliteBankovniVypisRepository,
        )
        # We need to get bv_doklad_id from the vypis
        # Since we're in the same UoW, access connection through tx_repo
        row = tx_repo._uow.connection.execute(
            "SELECT bv_doklad_id FROM bankovni_vypisy WHERE id = ?",
            (tx.bankovni_vypis_id,),
        ).fetchone()
        return row["bv_doklad_id"] if row else 1
