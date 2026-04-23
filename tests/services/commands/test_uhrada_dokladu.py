"""Testy pro UhradaPokladnouCommand a UhradaIntDoklademCommand."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import ValidationError
from domain.shared.money import Money
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.commands.uhrada_dokladu import (
    UhradaIntDoklademCommand,
    UhradaPokladnouCommand,
)


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


@pytest.fixture
def zauctovana_fp(db_factory) -> int:
    """Vytvoří zaúčtovanou FP a vrátí její ID."""
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(
            cislo="FP-2025-010",
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2025, 3, 1),
            castka_celkem=Money(250000),
            stav=StavDokladu.ZAUCTOVANY,
        ))
        uow.commit()
    return d.id


@pytest.fixture
def zauctovana_fv(db_factory) -> int:
    """Vytvoří zaúčtovanou FV a vrátí její ID."""
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(
            cislo="FV-2025-005",
            typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2025, 3, 1),
            castka_celkem=Money(180000),
            stav=StavDokladu.ZAUCTOVANY,
        ))
        uow.commit()
    return d.id


class TestUhradaPokladnouCommand:

    def test_uhrada_fp_pokladnou(self, db_factory, zauctovana_fp):
        cmd = UhradaPokladnouCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(
            doklad_id=zauctovana_fp,
            datum_uhrady=date(2025, 3, 15),
            cislo_pd="PD-2025-001",
            popis="Úhrada pokladnou",
        )

        assert result.novy_doklad_cislo == "PD-2025-001"

        # Ověř nový PD doklad
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            pd = repo.get_by_id(result.novy_doklad_id)
            assert pd.typ == TypDokladu.POKLADNI_DOKLAD
            assert pd.stav == StavDokladu.ZAUCTOVANY
            assert pd.castka_celkem == Money(250000)

        # Ověř původní doklad je uhrazený
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            fp = repo.get_by_id(zauctovana_fp)
            assert fp.stav == StavDokladu.UHRAZENY

        # Ověř účetní záznam MD 321 / Dal 211
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            denik = SqliteUcetniDenikRepository(uow)
            zaznamy = denik.list_by_doklad(result.novy_doklad_id)
            assert len(zaznamy) == 1
            z = zaznamy[0]
            assert z.md_ucet == "321"
            assert z.dal_ucet == "211"
            assert z.castka == Money(250000)

    def test_uhrada_fv_pokladnou(self, db_factory, zauctovana_fv):
        cmd = UhradaPokladnouCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(
            doklad_id=zauctovana_fv,
            datum_uhrady=date(2025, 3, 15),
            cislo_pd="PD-2025-002",
        )

        # Ověř účetní záznam MD 211 / Dal 311
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            denik = SqliteUcetniDenikRepository(uow)
            zaznamy = denik.list_by_doklad(result.novy_doklad_id)
            assert len(zaznamy) == 1
            z = zaznamy[0]
            assert z.md_ucet == "211"
            assert z.dal_ucet == "311"

    def test_uhrada_novy_doklad_rejects(self, db_factory):
        """Nelze uhradit NOVY doklad."""
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            d = repo.add(Doklad(
                cislo="FP-2025-099",
                typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2025, 3, 1),
                castka_celkem=Money(100000),
                stav=StavDokladu.NOVY,
            ))
            uow.commit()

        cmd = UhradaPokladnouCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        with pytest.raises(ValidationError, match="zaúčtovaných"):
            cmd.execute(d.id, date(2025, 3, 15), "PD-2025-099")

    def test_uhrada_pd_rejects(self, db_factory):
        """Nelze uhradit PD doklad."""
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            d = repo.add(Doklad(
                cislo="PD-2025-099",
                typ=TypDokladu.POKLADNI_DOKLAD,
                datum_vystaveni=date(2025, 3, 1),
                castka_celkem=Money(100000),
                stav=StavDokladu.ZAUCTOVANY,
            ))
            uow.commit()

        cmd = UhradaPokladnouCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        with pytest.raises(ValidationError, match="FP/FV"):
            cmd.execute(d.id, date(2025, 3, 15), "PD-2025-100")


class TestUhradaIntDoklademCommand:

    def test_uhrada_fp_pytlovani(self, db_factory, zauctovana_fp):
        cmd = UhradaIntDoklademCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(
            doklad_id=zauctovana_fp,
            datum_uhrady=date(2025, 3, 20),
            cislo_id="ID-2025-001",
            ucet_spolecnika="365.001",
            popis="Pytlování ze soukromé karty",
        )

        assert result.novy_doklad_cislo == "ID-2025-001"

        # Ověř nový ID doklad
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            id_dok = repo.get_by_id(result.novy_doklad_id)
            assert id_dok.typ == TypDokladu.INTERNI_DOKLAD
            assert id_dok.stav == StavDokladu.ZAUCTOVANY

        # Ověř původní doklad je uhrazený
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            fp = repo.get_by_id(zauctovana_fp)
            assert fp.stav == StavDokladu.UHRAZENY

        # Ověř účetní záznam FP: MD 321 / Dal 365.001
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            denik = SqliteUcetniDenikRepository(uow)
            zaznamy = denik.list_by_doklad(result.novy_doklad_id)
            assert len(zaznamy) == 1
            z = zaznamy[0]
            assert z.md_ucet == "321"
            assert z.dal_ucet == "365.001"

    def test_uhrada_fv_pytlovani(self, db_factory, zauctovana_fv):
        cmd = UhradaIntDoklademCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(
            doklad_id=zauctovana_fv,
            datum_uhrady=date(2025, 3, 20),
            cislo_id="ID-2025-002",
            ucet_spolecnika="365.002",
        )

        # Ověř účetní záznam FV: MD 365.002 / Dal 311
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            denik = SqliteUcetniDenikRepository(uow)
            zaznamy = denik.list_by_doklad(result.novy_doklad_id)
            assert len(zaznamy) == 1
            z = zaznamy[0]
            assert z.md_ucet == "365.002"
            assert z.dal_ucet == "311"
