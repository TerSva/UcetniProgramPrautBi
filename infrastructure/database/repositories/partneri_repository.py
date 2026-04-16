"""SqlitePartneriRepository — SQLite implementace PartneriRepository."""

from __future__ import annotations

from decimal import Decimal

from domain.partneri.partner import KategoriePartnera, Partner
from domain.partneri.repository import PartneriRepository
from domain.shared.errors import NotFoundError
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class SqlitePartneriRepository(PartneriRepository):
    """SQLite implementace."""

    def __init__(self, uow: SqliteUnitOfWork) -> None:
        self._uow = uow

    def add(self, partner: Partner) -> Partner:
        cursor = self._uow.connection.execute(
            """
            INSERT INTO partneri
                (nazev, kategorie, ico, dic, adresa, bankovni_ucet,
                 email, telefon, poznamka, je_aktivni,
                 podil_procent, ucet_pohledavka, ucet_zavazek)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                partner.nazev,
                partner.kategorie.value,
                partner.ico,
                partner.dic,
                partner.adresa,
                partner.bankovni_ucet,
                partner.email,
                partner.telefon,
                partner.poznamka,
                1 if partner.je_aktivni else 0,
                float(partner.podil_procent)
                if partner.podil_procent is not None
                else None,
                partner.ucet_pohledavka,
                partner.ucet_zavazek,
            ),
        )
        return Partner(
            id=cursor.lastrowid,
            nazev=partner.nazev,
            kategorie=partner.kategorie,
            ico=partner.ico,
            dic=partner.dic,
            adresa=partner.adresa,
            bankovni_ucet=partner.bankovni_ucet,
            email=partner.email,
            telefon=partner.telefon,
            poznamka=partner.poznamka,
            je_aktivni=partner.je_aktivni,
            podil_procent=partner.podil_procent,
            ucet_pohledavka=partner.ucet_pohledavka,
            ucet_zavazek=partner.ucet_zavazek,
        )

    def update(self, partner: Partner) -> None:
        if partner.id is None:
            raise ValueError("Partner nemá id.")
        self._uow.connection.execute(
            """
            UPDATE partneri SET
                nazev = ?, kategorie = ?, ico = ?, dic = ?,
                adresa = ?, bankovni_ucet = ?, email = ?, telefon = ?,
                poznamka = ?, je_aktivni = ?,
                podil_procent = ?, ucet_pohledavka = ?, ucet_zavazek = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                partner.nazev,
                partner.kategorie.value,
                partner.ico,
                partner.dic,
                partner.adresa,
                partner.bankovni_ucet,
                partner.email,
                partner.telefon,
                partner.poznamka,
                1 if partner.je_aktivni else 0,
                float(partner.podil_procent)
                if partner.podil_procent is not None
                else None,
                partner.ucet_pohledavka,
                partner.ucet_zavazek,
                partner.id,
            ),
        )

    def get_by_id(self, partner_id: int) -> Partner:
        row = self._uow.connection.execute(
            "SELECT * FROM partneri WHERE id = ?", (partner_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Partner id={partner_id} nenalezen.")
        return self._row_to_partner(row)

    def get_by_ico(self, ico: str) -> Partner | None:
        row = self._uow.connection.execute(
            "SELECT * FROM partneri WHERE ico = ? AND je_aktivni = 1",
            (ico,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_partner(row)

    def list_all(
        self,
        kategorie: KategoriePartnera | None = None,
        jen_aktivni: bool = True,
    ) -> list[Partner]:
        sql = "SELECT * FROM partneri WHERE 1=1"
        params: list = []
        if jen_aktivni:
            sql += " AND je_aktivni = 1"
        if kategorie is not None:
            sql += " AND kategorie = ?"
            params.append(kategorie.value)
        sql += " ORDER BY nazev"
        rows = self._uow.connection.execute(sql, params).fetchall()
        return [self._row_to_partner(r) for r in rows]

    def search(self, query: str, limit: int = 10) -> list[Partner]:
        q = f"%{query}%"
        rows = self._uow.connection.execute(
            """
            SELECT * FROM partneri
            WHERE je_aktivni = 1
              AND (nazev LIKE ? OR ico LIKE ?)
            ORDER BY nazev
            LIMIT ?
            """,
            (q, q, limit),
        ).fetchall()
        return [self._row_to_partner(r) for r in rows]

    def list_spolecnici(self) -> list[Partner]:
        rows = self._uow.connection.execute(
            """
            SELECT * FROM partneri
            WHERE kategorie = 'spolecnik' AND je_aktivni = 1
            ORDER BY nazev
            """,
        ).fetchall()
        return [self._row_to_partner(r) for r in rows]

    @staticmethod
    def _row_to_partner(row) -> Partner:
        podil = row["podil_procent"]
        return Partner(
            id=row["id"],
            nazev=row["nazev"],
            kategorie=KategoriePartnera(row["kategorie"]),
            ico=row["ico"],
            dic=row["dic"],
            adresa=row["adresa"],
            bankovni_ucet=row["bankovni_ucet"],
            email=row["email"],
            telefon=row["telefon"],
            poznamka=row["poznamka"],
            je_aktivni=bool(row["je_aktivni"]),
            podil_procent=Decimal(str(podil)) if podil is not None else None,
            ucet_pohledavka=row["ucet_pohledavka"],
            ucet_zavazek=row["ucet_zavazek"],
        )
