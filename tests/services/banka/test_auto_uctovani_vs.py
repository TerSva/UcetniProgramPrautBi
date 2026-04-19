"""Testy pro VS matching v AutoUctovaniBankyCommand."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from domain.banka.bankovni_transakce import BankovniTransakce, StavTransakce
from domain.banka.bankovni_ucet import BankovniUcet, FormatCsv
from domain.banka.bankovni_vypis import BankovniVypis
from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
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
from services.banka.auto_uctovani import AutoUctovaniBankyCommand


@pytest.fixture
def db_factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    factory = ConnectionFactory(db_path)
    migrations_dir = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "infrastructure"
        / "database"
        / "migrations"
        / "sql"
    )
    runner = MigrationRunner(factory, migrations_dir)
    runner.migrate()
    return factory


def _setup_base(db_factory) -> dict:
    """Vytvoří účet, BV doklad, výpis. Vrátí {vypis_id, ucet_id, bv_doklad_id}."""
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        ucet_repo = SqliteBankovniUcetRepository(uow)
        ucet_id = ucet_repo.add(BankovniUcet(
            nazev="Money Banka",
            cislo_uctu="670100-2213456789/6210",
            ucet_kod="221.001",
            format_csv=FormatCsv.MONEY_BANKA,
        ))

        doklady_repo = SqliteDokladyRepository(uow)
        bv_doklad = doklady_repo.add(Doklad(
            cislo="BV-2025-03",
            typ=TypDokladu.BANKOVNI_VYPIS,
            datum_vystaveni=date(2025, 3, 1),
            castka_celkem=Money(0),
        ))

        vypis_repo = SqliteBankovniVypisRepository(uow)
        vypis_id = vypis_repo.add(BankovniVypis(
            bankovni_ucet_id=ucet_id,
            rok=2025,
            mesic=3,
            pocatecni_stav=Money(10000000),
            konecny_stav=Money(12350050),
            pdf_path="/uploads/banka/test.pdf",
            bv_doklad_id=bv_doklad.id,
        ))

        uow.commit()
    return {
        "vypis_id": vypis_id,
        "ucet_id": ucet_id,
        "bv_doklad_id": bv_doklad.id,
    }


def _add_tx(db_factory, vypis_id: int, vs: str | None, castka: int) -> int:
    """Přidá transakci s daným VS a částkou (haléře). Vrátí tx_id."""
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        tx_repo = SqliteBankovniTransakceRepository(uow)
        tx_id = tx_repo.add(BankovniTransakce(
            bankovni_vypis_id=vypis_id,
            datum_transakce=date(2025, 3, 20),
            datum_zauctovani=date(2025, 3, 20),
            castka=Money(castka),
            smer="V" if castka < 0 else "P",
            popis="Platba faktura",
            variabilni_symbol=vs,
            row_hash=f"hash_vs_{vs}_{castka}",
        ))
        uow.commit()
    return tx_id


def _add_doklad(db_factory, cislo: str, typ: TypDokladu,
                castka: int, vs: str | None = None,
                stav: StavDokladu = StavDokladu.ZAUCTOVANY) -> int:
    """Přidá doklad. Vrátí doklad_id."""
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = Doklad(
            cislo=cislo,
            typ=typ,
            datum_vystaveni=date(2025, 3, 1),
            castka_celkem=Money(castka),
            variabilni_symbol=vs,
            stav=stav,
        )
        novy = repo.add(d)
        uow.commit()
    return novy.id


class TestVSMatching:

    def test_fp_uhrada_vs_match(self, db_factory):
        """Transakce s VS najde odpovídající FP → MD 321 / Dal 221."""
        base = _setup_base(db_factory)
        _add_doklad(
            db_factory, "FP-001", TypDokladu.FAKTURA_PRIJATA,
            50000, vs="20250044",
        )
        _add_tx(db_factory, base["vypis_id"], "20250044", -50000)

        cmd = AutoUctovaniBankyCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(base["vypis_id"])
        assert result.pocet_sparovano == 1
        assert result.pocet_preskoceno == 0

    def test_fv_uhrada_vs_match(self, db_factory):
        """Transakce s VS najde odpovídající FV → MD 221 / Dal 311."""
        base = _setup_base(db_factory)
        _add_doklad(
            db_factory, "FV-001", TypDokladu.FAKTURA_VYDANA,
            75000, vs="99887766",
        )
        _add_tx(db_factory, base["vypis_id"], "99887766", 75000)

        cmd = AutoUctovaniBankyCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(base["vypis_id"])
        assert result.pocet_sparovano == 1

    def test_vs_no_match_skips(self, db_factory):
        """Transakce s VS bez odpovídajícího dokladu → přeskočeno."""
        base = _setup_base(db_factory)
        _add_tx(db_factory, base["vypis_id"], "11111111", -10000)

        cmd = AutoUctovaniBankyCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(base["vypis_id"])
        assert result.pocet_preskoceno == 1
        assert result.pocet_sparovano == 0

    def test_vs_match_only_zauctovany(self, db_factory):
        """VS matching ignoruje NOVY doklady — hledá jen ZAUCTOVANY."""
        base = _setup_base(db_factory)
        _add_doklad(
            db_factory, "FP-001", TypDokladu.FAKTURA_PRIJATA,
            50000, vs="123", stav=StavDokladu.NOVY,
        )
        _add_tx(db_factory, base["vypis_id"], "123", -50000)

        cmd = AutoUctovaniBankyCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(base["vypis_id"])
        assert result.pocet_sparovano == 0
        assert result.pocet_preskoceno == 1

    def test_vs_tiebreaker_castka(self, db_factory):
        """Více dokladů se stejným VS → preferuje shodu částky."""
        base = _setup_base(db_factory)
        _add_doklad(
            db_factory, "FP-001", TypDokladu.FAKTURA_PRIJATA,
            99999, vs="555",
        )
        _add_doklad(
            db_factory, "FP-002", TypDokladu.FAKTURA_PRIJATA,
            25000, vs="555",
        )
        _add_tx(db_factory, base["vypis_id"], "555", -25000)

        cmd = AutoUctovaniBankyCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(base["vypis_id"])
        assert result.pocet_sparovano == 1

        # Ověř, že se spároval s dokladem FP-002 (castka 25000)
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            tx_repo = SqliteBankovniTransakceRepository(uow)
            txs = tx_repo.list_by_vypis(base["vypis_id"])
            matched_tx = [t for t in txs if t.stav == StavTransakce.SPAROVANO]
            assert len(matched_tx) == 1
            repo = SqliteDokladyRepository(uow)
            doklad = repo.get_by_id(matched_tx[0].sparovany_doklad_id)
            assert doklad.cislo == "FP-002"

    def test_castecne_uhrazeny_je_matchovatelny(self, db_factory):
        """Doklad ve stavu CASTECNE_UHRAZENY je matchovatelný pro další platbu."""
        base = _setup_base(db_factory)
        _add_doklad(
            db_factory, "FP-001", TypDokladu.FAKTURA_PRIJATA,
            100000, vs="12345", stav=StavDokladu.CASTECNE_UHRAZENY,
        )
        _add_tx(db_factory, base["vypis_id"], "12345", -50000)

        cmd = AutoUctovaniBankyCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(base["vypis_id"])
        assert result.pocet_sparovano == 1
        assert result.pocet_preskoceno == 0

    def test_tx_bez_vs_preskoceno(self, db_factory):
        """Transakce bez VS (a bez keyword match) → přeskočeno."""
        base = _setup_base(db_factory)
        _add_tx(db_factory, base["vypis_id"], None, -30000)

        cmd = AutoUctovaniBankyCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(base["vypis_id"])
        assert result.pocet_preskoceno == 1
