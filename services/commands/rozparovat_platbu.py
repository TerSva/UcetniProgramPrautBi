"""RozparovatPlatbuCommand — zruší spárování bankovní transakce s dokladem.

Audit-friendly přístup: žádné zápisy se nemažou, místo toho se ke každému
úhradovému/kurzovému zápisu vytvoří **storno protizápis** (prohozené
strany, ``je_storno=1``, ``stornuje_zaznam_id`` na originál). Tím zůstává
historie v deníku zachovaná pro audit.

Po storne:
  * stav transakce → NESPAROVANO, ``sparovany_doklad_id`` a
    ``ucetni_zapis_id`` se vynulují
  * stav dokladu se přepočítá:
      - po stornu zbývá úhrada == 0 → ZAUCTOVANY (resp. NOVY pro ZF)
      - 0 < zbývá < castka_celkem → CASTECNE_UHRAZENY
      - zbývá == castka_celkem → UHRAZENY (jiné úhrady stále kryjí celek)

Vše v jedné UoW transakci — selhání kteréhokoli kroku → rollback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from domain.banka.bankovni_transakce import StavTransakce
from domain.doklady.typy import StavDokladu
from domain.shared.errors import ValidationError
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from infrastructure.database.repositories.banka_repository import (
    SqliteBankovniTransakceRepository,
)
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork


@dataclass(frozen=True)
class RozparovaniResult:
    """Výsledek rozpárování."""

    stornovane_zapis_ids: list[int]   # ID původních zápisů, k nimž vznikl storno
    storno_zapis_ids: list[int]        # ID nově vytvořených storno protizápisů
    novy_stav_dokladu: StavDokladu


class RozparovatPlatbuCommand:
    """Rozpáruje spárovanou bankovní transakci s dokladem."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def execute(self, transakce_id: int) -> RozparovaniResult:
        uow = self._uow_factory()
        with uow:
            tx_repo = SqliteBankovniTransakceRepository(uow)
            doklady_repo = SqliteDokladyRepository(uow)
            denik_repo = SqliteUcetniDenikRepository(uow)

            tx = tx_repo.get(transakce_id)
            if tx is None:
                raise ValidationError(
                    f"Transakce {transakce_id} nenalezena.",
                )
            if tx.stav not in (
                StavTransakce.SPAROVANO,
                StavTransakce.AUTO_ZAUCTOVANO,
            ):
                raise ValidationError(
                    f"Transakce je ve stavu {tx.stav.value} — rozpárovat "
                    f"lze jen spárovanou.",
                )
            if tx.sparovany_doklad_id is None:
                raise ValidationError(
                    "Transakce nemá vazbu na doklad — nelze rozpárovat.",
                )
            if tx.ucetni_zapis_id is None:
                raise ValidationError(
                    "Transakce nemá účetní zápis — nelze rozpárovat.",
                )

            doklad = doklady_repo.get_by_id(tx.sparovany_doklad_id)

            # Najdi úhradový zápis a všechny související zápisy
            # (kurzový rozdíl, rozdíl 568/663) ve stejném BV dokladu
            # s popisem obsahujícím číslo dokladu.
            zapis_uhrady = self._nacti_zapis(uow, tx.ucetni_zapis_id)
            if zapis_uhrady is None:
                raise ValidationError(
                    f"Účetní zápis {tx.ucetni_zapis_id} pro transakci "
                    f"nenalezen.",
                )
            bv_doklad_id = zapis_uhrady["doklad_id"]

            kandidati = uow.connection.execute(
                """
                SELECT id, doklad_id, datum, md_ucet, dal_ucet,
                       castka, popis
                FROM ucetni_zaznamy
                WHERE doklad_id = ?
                  AND popis LIKE ?
                  AND je_storno = 0
                  AND id NOT IN (
                    SELECT stornuje_zaznam_id FROM ucetni_zaznamy
                    WHERE je_storno = 1 AND stornuje_zaznam_id IS NOT NULL
                  )
                ORDER BY id
                """,
                (bv_doklad_id, f"%{doklad.cislo}%"),
            ).fetchall()

            stornovane_ids: list[int] = []
            storno_ids: list[int] = []
            for r in kandidati:
                # Storno protizápis: prohozené MD/Dal, je_storno=1
                storno = UcetniZaznam(
                    doklad_id=r["doklad_id"],
                    datum=zapis_uhrady["datum_obj"],
                    md_ucet=r["dal_ucet"],
                    dal_ucet=r["md_ucet"],
                    castka=Money(r["castka"]),
                    popis=f"Storno: {r['popis'] or ''} (rozpárování)".strip(),
                    je_storno=True,
                    stornuje_zaznam_id=r["id"],
                )
                novy_id = denik_repo.add(storno)
                stornovane_ids.append(r["id"])
                storno_ids.append(novy_id)

            # Reset transakce
            tx.rozparuj()
            tx_repo.update(tx)

            # Spočítej zbývající úhrady (po stornu) a podle toho přepočítej stav
            zbyva_uhrazeno = self._spocitej_uhrazeno(
                uow, doklad.id, doklad.cislo,
            )
            castka_celkem = doklad.castka_celkem.to_halire()
            if zbyva_uhrazeno.to_halire() <= 0:
                doklad.zrus_uhradu()
            elif zbyva_uhrazeno.to_halire() >= castka_celkem:
                # Stále plně kryto — stav zůstane UHRAZENY (žádný přechod)
                pass
            else:
                # Po stornu zbývá částečná úhrada
                if doklad.stav == StavDokladu.UHRAZENY:
                    doklad.oznac_castecne_uhrazeny()
                # Pokud už byl CASTECNE, zůstává

            doklady_repo.update(doklad)
            uow.commit()

        return RozparovaniResult(
            stornovane_zapis_ids=stornovane_ids,
            storno_zapis_ids=storno_ids,
            novy_stav_dokladu=doklad.stav,
        )

    @staticmethod
    def _nacti_zapis(uow: SqliteUnitOfWork, zapis_id: int) -> dict | None:
        from datetime import date as _date
        row = uow.connection.execute(
            "SELECT id, doklad_id, datum, md_ucet, dal_ucet, castka, popis "
            "FROM ucetni_zaznamy WHERE id = ?",
            (zapis_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "doklad_id": row["doklad_id"],
            "datum_obj": _date.fromisoformat(row["datum"]),
            "md_ucet": row["md_ucet"],
            "dal_ucet": row["dal_ucet"],
            "castka": row["castka"],
            "popis": row["popis"],
        }

    @staticmethod
    def _spocitej_uhrazeno(
        uow: SqliteUnitOfWork,
        doklad_id: int,
        doklad_cislo: str,
    ) -> Money:
        """Součet aktivních (ne-storno) úhrad pro doklad.

        Stejná logika jako v ``sparovat_platbu_dokladem._spocitej_uhrazeno_celkem``:
        sčítá úhrady přes bankovni_transakce.ucetni_zapis_id (sparovane)
        a přes hotovostní/interní úhrady (popis "Úhrada …" v PD/ID dokladech).
        """
        rows = uow.connection.execute(
            """
            SELECT uz.id, uz.castka
            FROM ucetni_zaznamy uz
            JOIN bankovni_transakce bt ON bt.ucetni_zapis_id = uz.id
            WHERE bt.sparovany_doklad_id = ?
              AND uz.je_storno = 0
              AND uz.id NOT IN (
                SELECT stornuje_zaznam_id FROM ucetni_zaznamy
                WHERE je_storno = 1 AND stornuje_zaznam_id IS NOT NULL
              )

            UNION

            SELECT uz.id, uz.castka
            FROM ucetni_zaznamy uz
            JOIN doklady d ON d.id = uz.doklad_id
            WHERE uz.popis LIKE ?
              AND uz.je_storno = 0
              AND uz.doklad_id != ?
              AND d.typ IN ('PD', 'ID')
              AND uz.popis LIKE 'Úhrada%'
              AND uz.id NOT IN (
                SELECT stornuje_zaznam_id FROM ucetni_zaznamy
                WHERE je_storno = 1 AND stornuje_zaznam_id IS NOT NULL
              )
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

        # Kurzové rozdíly k dokladu — popis „Kurzov…{cislo}", filtrovat
        # storna i jejich originály (aby po stornu kurz zase odešel).
        kurz_rows = uow.connection.execute(
            """
            SELECT uz.id, uz.castka, uz.md_ucet, uz.dal_ucet
            FROM ucetni_zaznamy uz
            WHERE uz.popis LIKE 'Kurzov%'
              AND uz.popis LIKE ?
              AND uz.je_storno = 0
              AND uz.id NOT IN (
                SELECT stornuje_zaznam_id FROM ucetni_zaznamy
                WHERE je_storno = 1 AND stornuje_zaznam_id IS NOT NULL
              )
            """,
            (f"%{doklad_cislo}%",),
        ).fetchall()
        for r in kurz_rows:
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            md = r["md_ucet"] or ""
            dal = r["dal_ucet"] or ""
            is_md_pohl_zav = md.startswith("321") or md.startswith("311")
            is_dal_pohl_zav = dal.startswith("321") or dal.startswith("311")
            if is_md_pohl_zav and not is_dal_pohl_zav:
                total += r["castka"]
            elif is_dal_pohl_zav and not is_md_pohl_zav:
                total -= r["castka"]
        return Money(total)
