"""Testy get_minimum_priloha — sestavení minimální přílohy z Firma + Partneri."""

from datetime import date
from pathlib import Path
import tempfile

import pytest

from domain.firma.firma import Firma
from domain.shared.money import Money
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.firma_repository import (
    SqliteFirmaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.vykazy_query import VykazyQuery


@pytest.fixture()
def factory():
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "test.db"
    f = ConnectionFactory(db_path)
    migrations_dir = Path("infrastructure/database/migrations/sql")
    MigrationRunner(f, migrations_dir).migrate()
    return f


def _seed_firma(factory, **kwargs) -> None:
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteFirmaRepository(uow)
        firma = Firma(**kwargs)
        repo.upsert(firma)
        uow.commit()


def _seed_spolecnik(factory, nazev: str, podil: float | None) -> None:
    uow = SqliteUnitOfWork(factory)
    with uow:
        conn = uow.connection
        conn.execute(
            "INSERT INTO partneri (nazev, kategorie, podil_procent, je_aktivni) "
            "VALUES (?, 'spolecnik', ?, 1)",
            (nazev, podil),
        )
        uow.commit()


class TestMinimumPriloha:

    def test_no_firma_returns_placeholder(self, factory):
        q = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        priloha = q.get_minimum_priloha(
            rok=2025,
            rozvahovy_den=date(2025, 12, 31),
            datum_sestaveni=date(2026, 3, 1),
        )
        assert priloha.nazev == "—"
        assert priloha.rozvahovy_den == date(2025, 12, 31)
        assert priloha.datum_sestaveni == date(2026, 3, 1)

    def test_full_firma_data(self, factory):
        _seed_firma(
            factory,
            nazev="PRAUT s.r.o.",
            ico="22545107",
            dic="CZ22545107",
            sidlo="Tršnice 36, Skalná",
            pravni_forma="s.r.o.",
            datum_zalozeni=date(2024, 6, 15),
            zakladni_kapital=Money(2000000),  # 20 000 Kč
            kategorie_uj="mikro",
            je_identifikovana_osoba_dph=True,
            predmet_cinnosti="Obchodní činnost",
            statutarni_organ="Jan Novák — jednatel",
            zpusob_oceneni="pořizovacími cenami",
            odpisovy_plan="lineární",
            prumerny_pocet_zamestnancu=0,
        )
        q = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        priloha = q.get_minimum_priloha(
            rok=2025,
            rozvahovy_den=date(2025, 12, 31),
            datum_sestaveni=date(2026, 3, 15),
        )
        assert priloha.nazev == "PRAUT s.r.o."
        assert priloha.ico == "22545107"
        assert priloha.dic == "CZ22545107"
        assert priloha.predmet_cinnosti == "Obchodní činnost"
        assert priloha.statutarni_organ == "Jan Novák — jednatel"
        assert priloha.zpusob_oceneni == "pořizovacími cenami"
        assert priloha.odpisovy_plan == "lineární"
        assert priloha.je_identifikovana_osoba_dph is True
        assert priloha.zakladni_kapital == Money(2000000)
        assert priloha.spolecnici == ()

    def test_loads_spolecnici(self, factory):
        _seed_firma(factory, nazev="PRAUT s.r.o.")
        _seed_spolecnik(factory, "Jan Novák", 50.0)
        _seed_spolecnik(factory, "Petra Nováková", 50.0)
        q = VykazyQuery(lambda: SqliteUnitOfWork(factory))
        priloha = q.get_minimum_priloha(
            rok=2025,
            rozvahovy_den=date(2025, 12, 31),
            datum_sestaveni=date(2026, 3, 15),
        )
        assert len(priloha.spolecnici) == 2
        assert priloha.spolecnici[0][0] in ("Jan Novák", "Petra Nováková")
