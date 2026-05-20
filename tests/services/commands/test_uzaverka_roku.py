"""Testy UzaverkaRokuCommand — bilance, idempotence, je_zaverka flag."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.errors import ConflictError
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from scripts.seed_chart_of_accounts import seed_chart_of_accounts
from services.commands.uzaverka_roku import UzaverkaRokuCommand
from services.queries.vykazy_query import VykazyQuery


MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "infrastructure" / "database" / "migrations" / "sql"
)


@pytest.fixture
def factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    f = ConnectionFactory(db_path)
    MigrationRunner(f, MIGRATIONS_SQL_DIR).migrate()
    seed_chart_of_accounts(f)
    return f


@pytest.fixture
def cmd(factory) -> UzaverkaRokuCommand:
    uow_factory = lambda: SqliteUnitOfWork(factory)
    return UzaverkaRokuCommand(
        uow_factory=uow_factory,
        vykazy_query=VykazyQuery(uow_factory),
    )


_CITAC = [0]


def _zauctuj(
    factory: ConnectionFactory,
    cislo: str,
    datum: date,
    zapisy: list[tuple[str, str, int]],
) -> None:
    _CITAC[0] += 1
    uow = SqliteUnitOfWork(factory)
    with uow:
        drepo = SqliteDokladyRepository(uow)
        celkem = sum(hal for _, _, hal in zapisy)
        doklad = Doklad(
            cislo=cislo,
            typ=TypDokladu.INTERNI_DOKLAD,
            datum_vystaveni=datum,
            castka_celkem=Money(celkem),
        )
        drepo.add(doklad)
        loaded = drepo.get_by_cislo(cislo)
        denik = SqliteUcetniDenikRepository(uow)
        zz = tuple(
            UcetniZaznam(
                doklad_id=loaded.id, datum=datum,
                md_ucet=md, dal_ucet=dal, castka=Money(hal),
            )
            for md, dal, hal in zapisy
        )
        denik.zauctuj(UctovyPredpis(doklad_id=loaded.id, zaznamy=zz))
        loaded.zauctuj()
        drepo.update(loaded)
        uow.commit()


def _zustatek_uctu(factory, ucet: str, rok: int) -> tuple[int, int]:
    """Vrátí (md, dal) obrat na účtu za rok — VŠETNĚ uzavíracích."""
    od = f"{rok}-01-01"
    do = f"{rok}-12-31"
    uow = SqliteUnitOfWork(factory)
    with uow:
        md = uow.connection.execute(
            "SELECT COALESCE(SUM(castka), 0) AS s FROM ucetni_zaznamy "
            "WHERE datum >= ? AND datum <= ? AND md_ucet = ?",
            (od, do, ucet),
        ).fetchone()["s"] or 0
        dal = uow.connection.execute(
            "SELECT COALESCE(SUM(castka), 0) AS s FROM ucetni_zaznamy "
            "WHERE datum >= ? AND datum <= ? AND dal_ucet = ?",
            (od, do, ucet),
        ).fetchone()["s"] or 0
    return md, dal


class TestUzaverkaZtratovyRok:
    """Rok se ztrátou (PRAUT-style)."""

    def test_vystavi_z1_z2_z3(self, factory, cmd):
        # Tržba 500, náklad 1000 → ztráta 500
        _zauctuj(factory, "ID-A", date(2025, 6, 1),
                 [("311", "602", 50000)])  # tržba 500 Kč (A311/V602)
        _zauctuj(factory, "ID-B", date(2025, 7, 1),
                 [("518", "321", 100000)])  # náklad 1000 Kč (N518/P321)

        res = cmd.execute(2025)

        assert res.rok == 2025
        assert res.vh == Money(-50000)  # ztráta 500 Kč
        assert res.z1_doklad_id > 0
        assert res.z2_doklad_id > 0
        assert res.z3_doklad_id > 0

    def test_z1_bilancuje(self, factory, cmd):
        _zauctuj(factory, "ID-A", date(2025, 6, 1),
                 [("311", "602", 50000)])  # tržba 500 Kč (A311/V602)
        _zauctuj(factory, "ID-B", date(2025, 7, 1),
                 [("518", "321", 100000)])  # náklad 1000 Kč (N518/P321)

        cmd.execute(2025)

        # Po Z1: 5xx a 6xx mají MD = DAL = 0
        md, dal = _zustatek_uctu(factory, "518", 2025)
        assert md == dal
        md, dal = _zustatek_uctu(factory, "602", 2025)
        assert md == dal

        # 710.100 obraty: MD=500 (z N), DAL=500 (z V), saldo po Z2 = 0
        md, dal = _zustatek_uctu(factory, "710.100", 2025)
        # Po Z1+Z2 musí být vyrovnané (ztráta 500: Z1 MD 100k Z1 DAL 50k Z2 DAL 50k)
        assert md == dal

    def test_z2_castka_je_vh(self, factory, cmd):
        _zauctuj(factory, "ID-A", date(2025, 6, 1),
                 [("311", "602", 50000)])  # tržba 500 Kč (A311/V602)
        _zauctuj(factory, "ID-B", date(2025, 7, 1),
                 [("518", "321", 100000)])  # náklad 1000 Kč (N518/P321)

        res = cmd.execute(2025)

        # Z2 zapsal 500 Kč na 431
        md, dal = _zustatek_uctu(factory, "431.100", 2025)
        # Po Z2 jen MD 500 (ztráta), pak Z3 přidalo DAL 500 → saldo 0
        assert md == dal == 50000

    def test_z3_bilancuje(self, factory, cmd):
        _zauctuj(factory, "ID-A", date(2025, 6, 1),
                 [("311", "602", 50000)])  # tržba 500 Kč (A311/V602)
        _zauctuj(factory, "ID-B", date(2025, 7, 1),
                 [("518", "321", 100000)])  # náklad 1000 Kč (N518/P321)

        cmd.execute(2025)

        # Po Z3: 702.100 MD = DAL
        md, dal = _zustatek_uctu(factory, "702.100", 2025)
        assert md == dal
        # Rozvahové účty 311, 321, 431 mají MD = DAL po uzavření
        for u in ["311", "321", "431.100"]:
            md, dal = _zustatek_uctu(factory, u, 2025)
            assert md == dal, f"Účet {u} nebilancuje: MD {md} vs DAL {dal}"

    def test_vsechny_doklady_maji_je_zaverka(self, factory, cmd):
        _zauctuj(factory, "ID-A", date(2025, 6, 1),
                 [("311", "602", 50000)])

        cmd.execute(2025)

        uow = SqliteUnitOfWork(factory)
        with uow:
            rows = uow.connection.execute(
                "SELECT cislo, je_zaverka FROM doklady WHERE cislo LIKE 'ID-2025-Z%'"
            ).fetchall()
            assert len(rows) == 3
            for r in rows:
                assert r["je_zaverka"] == 1, f"{r['cislo']} nemá je_zaverka=1"


class TestUzaverkaZiskovyRok:

    def test_zisk_z2_jde_md_710_dal_431(self, factory, cmd):
        # Tržba 1000, náklad 300 → zisk 700
        _zauctuj(factory, "ID-A", date(2025, 6, 1),
                 [("311", "602", 100000)])
        _zauctuj(factory, "ID-B", date(2025, 7, 1),
                 [("518", "321", 30000)])

        res = cmd.execute(2025)

        assert res.vh == Money(70000)  # zisk

        # Z2 zapis: MD 710 / DAL 431
        uow = SqliteUnitOfWork(factory)
        with uow:
            row = uow.connection.execute(
                "SELECT md_ucet, dal_ucet, castka FROM ucetni_zaznamy "
                "WHERE doklad_id = ?",
                (res.z2_doklad_id,),
            ).fetchone()
            assert row["md_ucet"] == "710.100"
            assert row["dal_ucet"] == "431.100"
            assert row["castka"] == 70000


class TestIdempotence:

    def test_druhe_volani_raise(self, factory, cmd):
        _zauctuj(factory, "ID-A", date(2025, 6, 1),
                 [("311", "602", 50000)])

        cmd.execute(2025)

        with pytest.raises(ConflictError, match=r"už existuje"):
            cmd.execute(2025)

    def test_zadne_duplicitni_doklady(self, factory, cmd):
        _zauctuj(factory, "ID-A", date(2025, 6, 1),
                 [("311", "602", 50000)])
        cmd.execute(2025)
        try:
            cmd.execute(2025)
        except ConflictError:
            pass

        uow = SqliteUnitOfWork(factory)
        with uow:
            count = uow.connection.execute(
                "SELECT COUNT(*) AS c FROM doklady WHERE cislo LIKE 'ID-2025-Z%'"
            ).fetchone()["c"]
            assert count == 3  # Z1, Z2, Z3


class TestKonzistenceSvVykazy:
    """UzaverkaRokuCommand počítá s vcetne_zaverky=False (jako Rozvaha/VZZ)."""

    def test_konzistence_se_storno(self, factory, cmd):
        # Originál + storno (musí se vyrušit, ne dvojkrát)
        _zauctuj(factory, "ID-OK", date(2025, 6, 1),
                 [("311", "602", 100000)])  # tržba

        # Stornovaný doklad na nákladovém účtu — VykazyQuery to ignoruje
        # (storno protizápis se započítává spolu s originálem → rušení)
        _zauctuj(factory, "ID-STORNO", date(2025, 7, 1),
                 [("518", "321", 50000)])
        # Manuálně přidat storno protizápis (je_storno=1)
        uow = SqliteUnitOfWork(factory)
        with uow:
            doklad_id = uow.connection.execute(
                "SELECT id FROM doklady WHERE cislo='ID-STORNO'"
            ).fetchone()["id"]
            orig_id = uow.connection.execute(
                "SELECT id FROM ucetni_zaznamy WHERE doklad_id=?",
                (doklad_id,),
            ).fetchone()["id"]
            uow.connection.execute(
                "INSERT INTO ucetni_zaznamy "
                "(doklad_id, datum, md_ucet, dal_ucet, castka, "
                "je_storno, stornuje_zaznam_id) "
                "VALUES (?, '2025-07-01', '321', '518', 50000, 1, ?)",
                (doklad_id, orig_id),
            )
            uow.connection.execute(
                "UPDATE doklady SET stav='stornovany' WHERE id=?",
                (doklad_id,),
            )
            uow.commit()

        res = cmd.execute(2025)
        # VH = tržba 1000 - 0 nákladu (storno se vyrušilo) = +1000 zisk
        assert res.vh == Money(100000)
