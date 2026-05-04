"""Testy pro SparovatPlatbuDoklademCommand."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from domain.banka.bankovni_transakce import BankovniTransakce, StavTransakce
from domain.banka.bankovni_ucet import BankovniUcet, FormatCsv
from domain.banka.bankovni_vypis import BankovniVypis
from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import ValidationError
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
from services.commands.sparovat_platbu_dokladem import (
    SparovatPlatbuDoklademCommand,
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
def setup_fp(db_factory):
    """Účet + BV doklad + výpis + nespárovaná transakce + FP doklad."""
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
            castka_celkem=Money(500000),
        ))

        fp_doklad = doklady_repo.add(Doklad(
            cislo="FP-2025-001",
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2025, 3, 10),
            castka_celkem=Money(500000),
            stav=StavDokladu.ZAUCTOVANY,
            variabilni_symbol="202500001",
        ))

        vypis_repo = SqliteBankovniVypisRepository(uow)
        vypis_id = vypis_repo.add(BankovniVypis(
            bankovni_ucet_id=ucet_id,
            rok=2025,
            mesic=3,
            pocatecni_stav=Money(10000000),
            konecny_stav=Money(9500000),
            pdf_path="/uploads/banka/test.pdf",
            bv_doklad_id=bv_doklad.id,
        ))

        tx_repo = SqliteBankovniTransakceRepository(uow)
        tx_id = tx_repo.add(BankovniTransakce(
            bankovni_vypis_id=vypis_id,
            datum_transakce=date(2025, 3, 15),
            datum_zauctovani=date(2025, 3, 15),
            castka=Money(-500000),
            smer="V",
            popis="Platba dodavateli",
            variabilni_symbol="202500001",
            row_hash="hash_fp_uhrada",
        ))

        uow.commit()

    return {
        "tx_id": tx_id,
        "fp_id": fp_doklad.id,
        "bv_doklad_id": bv_doklad.id,
        "vypis_id": vypis_id,
    }


class TestSparovatPlatbuDoklademCommand:

    def test_sparovani_fp_success(self, db_factory, setup_fp):
        cmd = SparovatPlatbuDoklademCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(setup_fp["tx_id"], setup_fp["fp_id"])

        assert result.doklad_uhrazen is True
        assert len(result.ucetni_zaznam_ids) == 1
        assert result.kurzovy_rozdil is None

        # Ověř stav transakce
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            tx_repo = SqliteBankovniTransakceRepository(uow)
            tx = tx_repo.get(setup_fp["tx_id"])
            assert tx.stav == StavTransakce.SPAROVANO
            assert tx.sparovany_doklad_id == setup_fp["fp_id"]

        # Ověř stav dokladu
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            doklady_repo = SqliteDokladyRepository(uow)
            dok = doklady_repo.get_by_id(setup_fp["fp_id"])
            assert dok.stav == StavDokladu.UHRAZENY

        # Ověř účetní záznam (MD 321 / Dal 221.001)
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            denik_repo = SqliteUcetniDenikRepository(uow)
            zaznamy = denik_repo.list_by_doklad(setup_fp["bv_doklad_id"])
            assert len(zaznamy) == 1
            z = zaznamy[0]
            assert z.md_ucet == "321"
            assert z.dal_ucet == "221.001"
            assert z.castka == Money(500000)

    def test_sparovani_uz_sparovane_rejects(self, db_factory, setup_fp):
        cmd = SparovatPlatbuDoklademCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        # First match succeeds
        cmd.execute(setup_fp["tx_id"], setup_fp["fp_id"])

        # Second attempt fails
        with pytest.raises(ValidationError, match="stavu"):
            cmd.execute(setup_fp["tx_id"], setup_fp["fp_id"])

    def test_kurzovy_rozdil_pouziva_analytiku_563_pokud_existuje(
        self, db_factory, setup_fp,
    ):
        """Když existuje aktivní analytika 563.100, kurzová ztráta jde tam."""
        from decimal import Decimal as _D
        from domain.doklady.typy import Mena

        # Nastavme EUR fakturu místo CZK + zaúčtuj na 321 (MD 518/Dal 321)
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            doklady_repo = SqliteDokladyRepository(uow)
            denik_repo = SqliteUcetniDenikRepository(uow)
            from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
            # Vytvoř analytiku 563.100
            uow.connection.execute(
                "INSERT OR IGNORE INTO uctova_osnova "
                "(cislo, nazev, typ, je_aktivni, parent_kod) VALUES "
                "('563.100', 'Kurzové ztráty bankovní', 'N', 1, '563')"
            )
            # Sestav EUR doklad — castka_celkem=2500 CZK (přepočet),
            # 100 EUR, kurz 25
            eur_doklad = doklady_repo.add(Doklad(
                cislo="FP-EUR-001",
                typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2025, 3, 10),
                castka_celkem=Money(250000),
                mena=Mena.EUR,
                castka_mena=Money(10000),
                kurz=_D("25.00"),
                stav=StavDokladu.ZAUCTOVANY,
                variabilni_symbol="202500999",
            ))
            # Zaúčtuj originál: MD 518 / Dal 321 za 2500 CZK
            denik_repo.add(UcetniZaznam(
                doklad_id=eur_doklad.id,
                datum=date(2025, 3, 10),
                md_ucet="518",
                dal_ucet="321",
                castka=Money(250000),
            ))
            # Nová transakce v EUR — banka stáhla 260000 hal (2600 CZK,
            # tj. 100 ztráta v CZK kvůli horšímu kurzu)
            tx_repo = SqliteBankovniTransakceRepository(uow)
            eur_tx_id = tx_repo.add(BankovniTransakce(
                bankovni_vypis_id=setup_fp["vypis_id"],
                datum_transakce=date(2025, 3, 20),
                datum_zauctovani=date(2025, 3, 20),
                castka=Money(-260000),
                smer="V",
                popis="EUR platba",
                variabilni_symbol="202500999",
                row_hash="hash_eur",
            ))
            uow.commit()

        cmd = SparovatPlatbuDoklademCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(eur_tx_id, eur_doklad.id)
        assert result.kurzovy_rozdil is not None

        # Najdi kurzový záznam — md_ucet by měl být 563.100, ne 563
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            denik_repo = SqliteUcetniDenikRepository(uow)
            zaznamy = denik_repo.list_by_doklad(setup_fp["bv_doklad_id"])
            kurz_zaznamy = [
                z for z in zaznamy
                if z.popis and "Kurzov" in z.popis
            ]
            assert len(kurz_zaznamy) == 1
            assert kurz_zaznamy[0].md_ucet == "563.100"

    def test_kurzovy_rozdil_fallback_na_syntetic_pokud_neni_analytika(
        self, db_factory, setup_fp,
    ):
        """Když analytika 663.x neexistuje, kurzový zisk jde na syntetický 663."""
        from decimal import Decimal as _D
        from domain.doklady.typy import Mena
        from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            # Zruš VŠECHNY analytiky 663 (db migrace + seedy z fixtur)
            uow.connection.execute(
                "DELETE FROM uctova_osnova WHERE parent_kod = '663'"
            )
            doklady_repo = SqliteDokladyRepository(uow)
            denik_repo = SqliteUcetniDenikRepository(uow)
            eur_doklad = doklady_repo.add(Doklad(
                cislo="FP-EUR-002",
                typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2025, 3, 10),
                castka_celkem=Money(250000),
                mena=Mena.EUR,
                castka_mena=Money(10000),
                kurz=_D("25.00"),
                stav=StavDokladu.ZAUCTOVANY,
                variabilni_symbol="202500998",
            ))
            denik_repo.add(UcetniZaznam(
                doklad_id=eur_doklad.id,
                datum=date(2025, 3, 10),
                md_ucet="518",
                dal_ucet="321",
                castka=Money(250000),
            ))
            # Banka stáhla MÉNĚ → kurzový zisk
            tx_repo = SqliteBankovniTransakceRepository(uow)
            eur_tx_id = tx_repo.add(BankovniTransakce(
                bankovni_vypis_id=setup_fp["vypis_id"],
                datum_transakce=date(2025, 3, 20),
                datum_zauctovani=date(2025, 3, 20),
                castka=Money(-240000),
                smer="V",
                popis="EUR platba (zisk)",
                variabilni_symbol="202500998",
                row_hash="hash_eur_zisk",
            ))
            uow.commit()

        cmd = SparovatPlatbuDoklademCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        cmd.execute(eur_tx_id, eur_doklad.id)

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            denik_repo = SqliteUcetniDenikRepository(uow)
            zaznamy = denik_repo.list_by_doklad(setup_fp["bv_doklad_id"])
            kurz = [z for z in zaznamy if z.popis and "Kurzov" in z.popis]
            assert len(kurz) == 1
            # Bez analytiky → fallback na syntetický 663
            assert kurz[0].dal_ucet == "663"

    def test_sparovani_novy_doklad_rejects(self, db_factory, setup_fp):
        """Nelze spárovat s NOVY dokladem."""
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            doklady_repo = SqliteDokladyRepository(uow)
            novy = doklady_repo.add(Doklad(
                cislo="FP-2025-999",
                typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2025, 3, 10),
                castka_celkem=Money(100000),
                stav=StavDokladu.NOVY,
            ))
            uow.commit()

        cmd = SparovatPlatbuDoklademCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        with pytest.raises(ValidationError, match="zaúčtované"):
            cmd.execute(setup_fp["tx_id"], novy.id)
