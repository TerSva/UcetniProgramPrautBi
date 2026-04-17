"""SqliteFirmaRepository — CRUD pro singleton záznam firmy."""

from __future__ import annotations

import sqlite3
from datetime import date

from domain.firma.firma import Firma
from domain.shared.money import Money
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class SqliteFirmaRepository:
    """Singleton firma — get/upsert."""

    def __init__(self, uow: SqliteUnitOfWork) -> None:
        self._uow = uow

    @property
    def _conn(self) -> sqlite3.Connection:
        return self._uow.connection

    def get(self) -> Firma | None:
        row = self._conn.execute(
            "SELECT * FROM firma WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        return self._row_to_firma(row)

    def upsert(self, firma: Firma) -> None:
        zk = firma.zakladni_kapital.to_halire() if firma.zakladni_kapital else None
        dz = firma.datum_zalozeni.isoformat() if firma.datum_zalozeni else None
        self._conn.execute(
            """
            INSERT INTO firma (
                id, nazev, ico, dic, sidlo, pravni_forma,
                datum_zalozeni, rok_zacatku_uctovani, zakladni_kapital,
                kategorie_uj, je_identifikovana_osoba_dph, je_platce_dph,
                bankovni_ucet_1, bankovni_ucet_2
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                nazev = excluded.nazev,
                ico = excluded.ico,
                dic = excluded.dic,
                sidlo = excluded.sidlo,
                pravni_forma = excluded.pravni_forma,
                datum_zalozeni = excluded.datum_zalozeni,
                rok_zacatku_uctovani = excluded.rok_zacatku_uctovani,
                zakladni_kapital = excluded.zakladni_kapital,
                kategorie_uj = excluded.kategorie_uj,
                je_identifikovana_osoba_dph = excluded.je_identifikovana_osoba_dph,
                je_platce_dph = excluded.je_platce_dph,
                bankovni_ucet_1 = excluded.bankovni_ucet_1,
                bankovni_ucet_2 = excluded.bankovni_ucet_2
            """,
            (
                firma.nazev, firma.ico, firma.dic, firma.sidlo,
                firma.pravni_forma, dz,
                firma.rok_zacatku_uctovani, zk,
                firma.kategorie_uj,
                1 if firma.je_identifikovana_osoba_dph else 0,
                1 if firma.je_platce_dph else 0,
                firma.bankovni_ucet_1, firma.bankovni_ucet_2,
            ),
        )

    def _row_to_firma(self, row: sqlite3.Row) -> Firma:
        dz = date.fromisoformat(row["datum_zalozeni"]) if row["datum_zalozeni"] else None
        zk = Money(row["zakladni_kapital"]) if row["zakladni_kapital"] else None
        return Firma(
            id=row["id"],
            nazev=row["nazev"],
            ico=row["ico"],
            dic=row["dic"],
            sidlo=row["sidlo"],
            pravni_forma=row["pravni_forma"],
            datum_zalozeni=dz,
            rok_zacatku_uctovani=row["rok_zacatku_uctovani"],
            zakladni_kapital=zk,
            kategorie_uj=row["kategorie_uj"],
            je_identifikovana_osoba_dph=bool(row["je_identifikovana_osoba_dph"]),
            je_platce_dph=bool(row["je_platce_dph"]),
            bankovni_ucet_1=row["bankovni_ucet_1"],
            bankovni_ucet_2=row["bankovni_ucet_2"],
        )
