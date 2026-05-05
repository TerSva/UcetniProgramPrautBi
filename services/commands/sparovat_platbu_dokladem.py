"""SparovatPlatbuDoklademCommand — spáruje bankovní transakci s dokladem.

Vytvoří účetní zápisy na BV doklad. Účet závazku/pohledávky se
převezme z původního zaúčtování dokladu (libovolný účet třídy 3 —
321, 379, 365, 311, …), případně lze předat explicitně přes
``md_ucet_override`` / ``dal_ucet_override`` (z dialogu zaúčtování).

  FP úhrada: MD <ucet_zavazku> / Dal 221.xxx
  FV úhrada: MD 221.xxx / Dal <ucet_pohledavky>

Kurzové rozdíly (pokud doklad v cizí měně):
  Ztráta: MD 563[.xxx] / Dal <ucet_protistrany>
  Zisk:   MD <ucet_protistrany> / Dal 663[.xxx]
  Pokud existuje aktivní analytika 563.x / 663.x v osnově, použije se;
  jinak fallback na syntetický 563 / 663.

Rozdíl částek (pokud uživatel zaškrtl, jen CZK doklady):
  Zaplaceno víc:  MD 568 / Dal <ucet_protistrany>
  Zaplaceno méně: MD <ucet_protistrany> / Dal 663
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
    """Výsledek spárování platby s dokladem.

    ``doklad_uhrazen`` je True jen pokud po této úhradě dosáhl součet
    všech úhrad částky dokladu (UHRAZENY). Při částečné platbě je False
    a doklad zůstává v CASTECNE_UHRAZENY (umožní párovat další platby).
    """

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
        md_ucet_override: str | None = None,
        dal_ucet_override: str | None = None,
        popis_override: str | None = None,
        rozdil_zauctovat: bool = False,
        castka_override: Money | None = None,
    ) -> SparovaniResult:
        """Spáruje transakci s dokladem.

        1. Ověří stav transakce (NESPAROVANO) a dokladu (ZAUCTOVANY/CASTECNE)
        2. Zjistí BV doklad z výpisu + účet 221.xxx z bankovního účtu
        3. Vytvoří účetní zápis MD/Dal — buď z overrides (z dialogu)
           nebo z původního zaúčtování dokladu (účet třídy 3)
        4. Řeší kurzové rozdíly pro cizí měny
        5. Pokud rozdil_zauctovat=True a tx_castka != doklad částka,
           přidá řádek MD/Dal 568/663 pro rozdíl
        6. Změní stav dokladu na UHRAZENY, transakci na SPAROVANO
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

            # Částka — preferuj override z dialogu (umožňuje částečnou
            # úhradu — user zadá kolik z transakce zaúčtovat na tento
            # doklad). Bez override vezmi celou tx částku (abs).
            if castka_override is not None and castka_override.is_positive:
                tx_castka = castka_override
            else:
                tx_castka = (
                    tx.castka
                    if tx.castka.is_positive
                    else Money(-tx.castka.to_halire())
                )

            # Účty podle typu dokladu — preferuj override (z dialogu),
            # jinak najdi reálný účet závazku/pohledávky z původního
            # zaúčtování (jakýkoli účet třídy 3 — 321, 379, 365, …)
            if doklad.typ == TypDokladu.FAKTURA_PRIJATA:
                if md_ucet_override and dal_ucet_override:
                    md_ucet, dal_ucet = md_ucet_override, dal_ucet_override
                else:
                    ucet_zavazku = _najdi_ucet_zavazku(
                        uow, doklad_id, "dal_ucet",
                    ) or "321"
                    md_ucet, dal_ucet = ucet_zavazku, ucet_221
                ucet_protistrany = md_ucet
            else:
                if md_ucet_override and dal_ucet_override:
                    md_ucet, dal_ucet = md_ucet_override, dal_ucet_override
                else:
                    ucet_pohledavky = _najdi_ucet_zavazku(
                        uow, doklad_id, "md_ucet",
                    ) or "311"
                    md_ucet, dal_ucet = ucet_221, ucet_pohledavky
                ucet_protistrany = dal_ucet

            popis_zapisu = popis_override or f"Úhrada {doklad.cislo}"

            # Hlavní účetní zápis
            zaznam = UcetniZaznam(
                doklad_id=bv_doklad_id,
                datum=tx.datum_zauctovani,
                md_ucet=md_ucet,
                dal_ucet=dal_ucet,
                castka=tx_castka,
                popis=popis_zapisu,
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

                    # Preferuj analytiku 563.x / 663.x pokud existuje;
                    # fallback na syntetický 563 / 663.
                    ucet_563 = _najdi_aktivni_ucet(uow, "563")
                    ucet_663 = _najdi_aktivni_ucet(uow, "663")

                    if rozdil.is_positive:
                        # Kurzová ztráta — zaplatili jsme víc
                        kurz_zaznam = UcetniZaznam(
                            doklad_id=bv_doklad_id,
                            datum=tx.datum_zauctovani,
                            md_ucet=ucet_563,
                            dal_ucet=ucet_protistrany,
                            castka=abs_rozdil,
                            popis=f"Kurzová ztráta {doklad.cislo}",
                        )
                    else:
                        # Kurzový zisk — zaplatili jsme méně
                        kurz_zaznam = UcetniZaznam(
                            doklad_id=bv_doklad_id,
                            datum=tx.datum_zauctovani,
                            md_ucet=ucet_protistrany,
                            dal_ucet=ucet_663,
                            castka=abs_rozdil,
                            popis=f"Kurzový zisk {doklad.cislo}",
                        )
                    kurz_id = denik_repo.add(kurz_zaznam)
                    zaznam_ids.append(kurz_id)

            # Rozdíl mezi částkou transakce a dokladem (CZK doklady)
            # — uživatel v dialogu zaškrtl "Přidat řádek pro rozdíl"
            elif rozdil_zauctovat and doklad.mena.value == "CZK":
                rozdil = tx_castka - doklad.castka_celkem
                if rozdil != Money.zero():
                    abs_rozdil = (
                        rozdil
                        if rozdil.is_positive
                        else Money(-rozdil.to_halire())
                    )
                    if rozdil.is_positive:
                        # Zaplaceno víc → ztráta (568) na MD,
                        # protistranový účet (321/311/…) na Dal
                        rozdil_zaznam = UcetniZaznam(
                            doklad_id=bv_doklad_id,
                            datum=tx.datum_zauctovani,
                            md_ucet="568",
                            dal_ucet=ucet_protistrany,
                            castka=abs_rozdil,
                            popis=f"Rozdíl úhrady {doklad.cislo}",
                        )
                    else:
                        # Zaplaceno méně → zisk (663) na Dal,
                        # protistranový účet na MD (doplatek závazku/pohl.)
                        rozdil_zaznam = UcetniZaznam(
                            doklad_id=bv_doklad_id,
                            datum=tx.datum_zauctovani,
                            md_ucet=ucet_protistrany,
                            dal_ucet="663",
                            castka=abs_rozdil,
                            popis=f"Rozdíl úhrady {doklad.cislo}",
                        )
                    rozdil_id = denik_repo.add(rozdil_zaznam)
                    zaznam_ids.append(rozdil_id)

            # Spáruj transakci
            tx.sparuj(doklad_id)
            tx.ucetni_zapis_id = zapis_id
            tx_repo.update(tx)

            # Spočítej celkovou úhradu (vč. právě přidané) a rozhodni o stavu.
            # Při částečné úhradě → CASTECNE_UHRAZENY (umožní další párování),
            # při plné/nadúhrazení → UHRAZENY.
            uhrazeno_celkem = _spocitej_uhrazeno_celkem(
                uow, doklad_id, doklad.cislo,
            )
            doklad_uhrazen = (
                uhrazeno_celkem.to_halire() >= doklad.castka_celkem.to_halire()
            )
            if doklad_uhrazen:
                doklad.oznac_uhrazeny()
            else:
                # Z NOVY/ZAUCTOVANY → CASTECNE; pokud už je CASTECNE,
                # přechod není potřeba (zůstává).
                if doklad.stav == StavDokladu.ZAUCTOVANY:
                    doklad.oznac_castecne_uhrazeny()
            doklady_repo.update(doklad)

            uow.commit()

        return SparovaniResult(
            ucetni_zaznam_ids=zaznam_ids,
            kurzovy_rozdil=kurzovy_rozdil,
            doklad_uhrazen=doklad_uhrazen,
        )


def _spocitej_uhrazeno_celkem(
    uow: SqliteUnitOfWork,
    doklad_id: int,
    doklad_cislo: str,
) -> Money:
    """Vrátí celkovou již zaúčtovanou úhradu pro doklad (FP/FV).

    Sčítá:
      - úhradové zápisy navázané přes bankovni_transakce.ucetni_zapis_id
        (sparovany_doklad_id = doklad_id)
      - úhradové zápisy v PD/ID dokladech, kde popis začíná „Úhrada "
        a obsahuje číslo dokladu (hotovostní/interní úhrady)

    Záměrně **nezahrnuje** kurzové rozdíly (popis „Kurzov…") ani
    rozdílové zápisy úhrady (568/663) — ty mají vlastní logiku a
    nepatří do bilance saldokonta.
    """
    rows = uow.connection.execute(
        """
        SELECT uz.id, uz.castka
        FROM ucetni_zaznamy uz
        JOIN bankovni_transakce bt ON bt.ucetni_zapis_id = uz.id
        WHERE bt.sparovany_doklad_id = ?
          AND uz.je_storno = 0

        UNION

        SELECT uz.id, uz.castka
        FROM ucetni_zaznamy uz
        JOIN doklady d ON d.id = uz.doklad_id
        WHERE uz.popis LIKE ?
          AND uz.je_storno = 0
          AND uz.doklad_id != ?
          AND d.typ IN ('PD', 'ID')
          AND uz.popis LIKE 'Úhrada%'
        """,
        (doklad_id, f"%{doklad_cislo}%", doklad_id),
    ).fetchall()

    seen: set[int] = set()
    total = 0
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        total += r["castka"]
    return Money(total)


def _najdi_aktivni_ucet(
    uow: SqliteUnitOfWork,
    syntetic: str,
) -> str:
    """Vrátí preferovaný účet pro daný syntetický kód.

    Pokud existuje aspoň jedna aktivní analytika syntetika (např. ``563.100``
    pro ``563``), vrátí ji (nejnižší podle čísla). Jinak vrátí samotný
    syntetický kód jako fallback. Neexistující syntetika vrátí jak je —
    případná chyba se objeví až při zaúčtování.
    """
    row = uow.connection.execute(
        "SELECT cislo FROM uctova_osnova "
        "WHERE parent_kod = ? AND je_aktivni = 1 "
        "ORDER BY cislo ASC LIMIT 1",
        (syntetic,),
    ).fetchone()
    return row[0] if row else syntetic


def _najdi_ucet_zavazku(
    uow: SqliteUnitOfWork,
    doklad_id: int,
    sloupec: str,
) -> str | None:
    """Najde reálný účet závazku/pohledávky z původního zaúčtování dokladu.

    Hledá libovolný účet třídy 3 (321, 379, 365, 311, 315, …) — třída 3
    obsahuje zúčtovací vztahy (pohledávky a závazky).

    Pro FP (úhrada závazku) se volá s ``sloupec="dal_ucet"`` — strana
    Dal původního zaúčtování drží závazek (např. ``Dal 379.100``).
    Pro FV (úhrada pohledávky) se volá s ``sloupec="md_ucet"`` — strana
    MD drží pohledávku (např. ``MD 311``).

    Vrátí ``None``, pokud nenajde žádný takový účet (volající si pak
    zvolí default 321/311).
    """
    row = uow.connection.execute(
        f"SELECT {sloupec} FROM ucetni_zaznamy "  # noqa: S608
        f"WHERE doklad_id = ? AND {sloupec} LIKE '3%' "
        "ORDER BY id LIMIT 1",
        (doklad_id,),
    ).fetchone()
    return row[0] if row else None
