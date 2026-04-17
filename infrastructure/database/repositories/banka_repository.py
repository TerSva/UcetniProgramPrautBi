"""Repositories pro bankovní modul — účty, výpisy, transakce."""

from __future__ import annotations

from datetime import date, datetime

from domain.banka.bankovni_transakce import BankovniTransakce, StavTransakce
from domain.banka.bankovni_ucet import BankovniUcet, FormatCsv
from domain.banka.bankovni_vypis import BankovniVypis
from domain.doklady.typy import Mena
from domain.shared.money import Money
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class SqliteBankovniUcetRepository:
    """CRUD pro bankovní účty."""

    def __init__(self, uow: SqliteUnitOfWork) -> None:
        self._uow = uow

    def add(self, ucet: BankovniUcet) -> int:
        cur = self._uow.connection.execute(
            """INSERT INTO bankovni_ucty
               (nazev, cislo_uctu, ucet_kod, format_csv, mena, je_aktivni, poznamka)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                ucet.nazev, ucet.cislo_uctu, ucet.ucet_kod,
                ucet.format_csv.value, ucet.mena.value,
                1 if ucet.je_aktivni else 0, ucet.poznamka,
            ),
        )
        ucet.id = cur.lastrowid
        return ucet.id

    def get(self, id: int) -> BankovniUcet | None:
        row = self._uow.connection.execute(
            "SELECT * FROM bankovni_ucty WHERE id = ?", (id,),
        ).fetchone()
        return self._map(row) if row else None

    def list_aktivni(self) -> list[BankovniUcet]:
        rows = self._uow.connection.execute(
            "SELECT * FROM bankovni_ucty WHERE je_aktivni = 1 ORDER BY nazev",
        ).fetchall()
        return [self._map(r) for r in rows]

    def list_all(self) -> list[BankovniUcet]:
        rows = self._uow.connection.execute(
            "SELECT * FROM bankovni_ucty ORDER BY nazev",
        ).fetchall()
        return [self._map(r) for r in rows]

    @staticmethod
    def _map(row) -> BankovniUcet:
        return BankovniUcet(
            id=row["id"],
            nazev=row["nazev"],
            cislo_uctu=row["cislo_uctu"],
            ucet_kod=row["ucet_kod"],
            format_csv=FormatCsv(row["format_csv"]),
            mena=Mena(row["mena"]),
            je_aktivni=bool(row["je_aktivni"]),
            poznamka=row["poznamka"],
        )


class SqliteBankovniVypisRepository:
    """CRUD pro bankovní výpisy."""

    def __init__(self, uow: SqliteUnitOfWork) -> None:
        self._uow = uow

    def add(self, vypis: BankovniVypis) -> int:
        cur = self._uow.connection.execute(
            """INSERT INTO bankovni_vypisy
               (bankovni_ucet_id, rok, mesic, pocatecni_stav, konecny_stav,
                pdf_path, csv_path, bv_doklad_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                vypis.bankovni_ucet_id, vypis.rok, vypis.mesic,
                vypis.pocatecni_stav.to_halire(),
                vypis.konecny_stav.to_halire(),
                vypis.pdf_path, vypis.csv_path,
                vypis.bv_doklad_id,
            ),
        )
        vypis.id = cur.lastrowid
        return vypis.id

    def get(self, id: int) -> BankovniVypis | None:
        row = self._uow.connection.execute(
            "SELECT * FROM bankovni_vypisy WHERE id = ?", (id,),
        ).fetchone()
        return self._map(row) if row else None

    def get_by_ucet_mesic(
        self, ucet_id: int, rok: int, mesic: int,
    ) -> BankovniVypis | None:
        row = self._uow.connection.execute(
            """SELECT * FROM bankovni_vypisy
               WHERE bankovni_ucet_id = ? AND rok = ? AND mesic = ?""",
            (ucet_id, rok, mesic),
        ).fetchone()
        return self._map(row) if row else None

    def list_by_ucet(self, ucet_id: int) -> list[BankovniVypis]:
        rows = self._uow.connection.execute(
            """SELECT * FROM bankovni_vypisy
               WHERE bankovni_ucet_id = ?
               ORDER BY rok DESC, mesic DESC""",
            (ucet_id,),
        ).fetchall()
        return [self._map(r) for r in rows]

    @staticmethod
    def _map(row) -> BankovniVypis:
        return BankovniVypis(
            id=row["id"],
            bankovni_ucet_id=row["bankovni_ucet_id"],
            rok=row["rok"],
            mesic=row["mesic"],
            pocatecni_stav=Money(row["pocatecni_stav"]),
            konecny_stav=Money(row["konecny_stav"]),
            pdf_path=row["pdf_path"],
            csv_path=row["csv_path"],
            bv_doklad_id=row["bv_doklad_id"],
        )


class SqliteBankovniTransakceRepository:
    """CRUD pro bankovní transakce."""

    def __init__(self, uow: SqliteUnitOfWork) -> None:
        self._uow = uow

    def add(self, tx: BankovniTransakce) -> int:
        cur = self._uow.connection.execute(
            """INSERT INTO bankovni_transakce
               (bankovni_vypis_id, datum_transakce, datum_zauctovani,
                castka, smer, variabilni_symbol, konstantni_symbol,
                specificky_symbol, protiucet, popis, stav,
                sparovany_doklad_id, ucetni_zapis_id, row_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tx.bankovni_vypis_id,
                tx.datum_transakce.isoformat(),
                tx.datum_zauctovani.isoformat(),
                tx.castka.to_halire(),
                tx.smer,
                tx.variabilni_symbol, tx.konstantni_symbol,
                tx.specificky_symbol, tx.protiucet, tx.popis,
                tx.stav.value,
                tx.sparovany_doklad_id, tx.ucetni_zapis_id,
                tx.row_hash,
            ),
        )
        tx.id = cur.lastrowid
        return tx.id

    def add_batch(self, transakce: list[BankovniTransakce]) -> list[int]:
        ids: list[int] = []
        for tx in transakce:
            ids.append(self.add(tx))
        return ids

    def get(self, id: int) -> BankovniTransakce | None:
        row = self._uow.connection.execute(
            "SELECT * FROM bankovni_transakce WHERE id = ?", (id,),
        ).fetchone()
        return self._map(row) if row else None

    def update(self, tx: BankovniTransakce) -> None:
        self._uow.connection.execute(
            """UPDATE bankovni_transakce
               SET stav = ?, sparovany_doklad_id = ?, ucetni_zapis_id = ?
               WHERE id = ?""",
            (tx.stav.value, tx.sparovany_doklad_id, tx.ucetni_zapis_id, tx.id),
        )

    def list_by_vypis(
        self, vypis_id: int, stav: StavTransakce | None = None,
    ) -> list[BankovniTransakce]:
        if stav:
            rows = self._uow.connection.execute(
                """SELECT * FROM bankovni_transakce
                   WHERE bankovni_vypis_id = ? AND stav = ?
                   ORDER BY datum_zauctovani""",
                (vypis_id, stav.value),
            ).fetchall()
        else:
            rows = self._uow.connection.execute(
                """SELECT * FROM bankovni_transakce
                   WHERE bankovni_vypis_id = ?
                   ORDER BY datum_zauctovani""",
                (vypis_id,),
            ).fetchall()
        return [self._map(r) for r in rows]

    def count_by_stav(
        self, vypis_id: int, stav: StavTransakce,
    ) -> int:
        row = self._uow.connection.execute(
            """SELECT COUNT(*) as cnt FROM bankovni_transakce
               WHERE bankovni_vypis_id = ? AND stav = ?""",
            (vypis_id, stav.value),
        ).fetchone()
        return row["cnt"]

    def exists_hash(self, row_hash: str) -> bool:
        row = self._uow.connection.execute(
            "SELECT 1 FROM bankovni_transakce WHERE row_hash = ?",
            (row_hash,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _map(row) -> BankovniTransakce:
        return BankovniTransakce(
            id=row["id"],
            bankovni_vypis_id=row["bankovni_vypis_id"],
            datum_transakce=date.fromisoformat(row["datum_transakce"]),
            datum_zauctovani=date.fromisoformat(row["datum_zauctovani"]),
            castka=Money(row["castka"]),
            smer=row["smer"],
            variabilni_symbol=row["variabilni_symbol"],
            konstantni_symbol=row["konstantni_symbol"],
            specificky_symbol=row["specificky_symbol"],
            protiucet=row["protiucet"],
            popis=row["popis"],
            stav=StavTransakce(row["stav"]),
            sparovany_doklad_id=row["sparovany_doklad_id"],
            ucetni_zapis_id=row["ucetni_zapis_id"],
            row_hash=row["row_hash"],
        )
