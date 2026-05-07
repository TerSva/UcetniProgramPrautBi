"""Testy RozparovatPlatbuCommand."""

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
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
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
from services.commands.rozparovat_platbu import RozparovatPlatbuCommand


@pytest.fixture
def db_factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    factory = ConnectionFactory(db_path)
    runner = MigrationRunner(
        factory,
        Path("infrastructure/database/migrations/sql"),
    )
    runner.migrate()
    return factory


def _create_paired_setup(factory, fp_castka_halire: int = 56403):
    """Vytvoří FP zaúčtovanou + BV doklad + transakci spárovanou s úhradovým
    zápisem v deníku. Vrátí (fp_id, tx_id, zapis_uhrady_id, bv_id)."""
    uow = SqliteUnitOfWork(factory)
    with uow:
        drepo = SqliteDokladyRepository(uow)
        denik = SqliteUcetniDenikRepository(uow)
        ucet_repo = SqliteBankovniUcetRepository(uow)
        vypis_repo = SqliteBankovniVypisRepository(uow)
        tx_repo = SqliteBankovniTransakceRepository(uow)

        # FP doklad ZAUCTOVANY
        fp = drepo.add(Doklad(
            cislo="FP-2025-038",
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2025, 9, 9),
            castka_celkem=Money(fp_castka_halire),
            stav=StavDokladu.ZAUCTOVANY,
        ))
        # Hlavní zaúčtování FP (MD 518/Dal 321)
        denik.add(UcetniZaznam(
            doklad_id=fp.id, datum=date(2025, 9, 9),
            md_ucet="518", dal_ucet="321.002",
            castka=Money(fp_castka_halire),
        ))

        # Bankovní účet + výpis + BV doklad
        from domain.doklady.typy import Mena
        u_id = ucet_repo.add(BankovniUcet(
            nazev="Test EUR",
            cislo_uctu="000000-0000000000/0800",
            ucet_kod="221.002",
            mena=Mena.EUR,
            format_csv=FormatCsv.CESKA_SPORITELNA,
        ))
        bv = drepo.add(Doklad(
            cislo="BV-2025-005",
            typ=TypDokladu.BANKOVNI_VYPIS,
            datum_vystaveni=date(2025, 9, 30),
            castka_celkem=Money(0),
        ))
        v_id = vypis_repo.add(BankovniVypis(
            bankovni_ucet_id=u_id,
            cislo_vypisu="005/2025",
            rok=2025, mesic=9,
            pocatecni_stav=Money.zero(),
            konecny_stav=Money.zero(),
            pdf_path="/tmp/x.pdf",
            datum_od=date(2025, 9, 1), datum_do=date(2025, 9, 30),
            bv_doklad_id=bv.id,
        ))

        # Účetní zápis úhrady (MD 321 / Dal 221)
        zapis_id = denik.add(UcetniZaznam(
            doklad_id=bv.id, datum=date(2025, 9, 7),
            md_ucet="321.002", dal_ucet="221.002",
            castka=Money(54873),
            popis="Úhrada FP-2025-038",
        ))

        # Kurzový rozdíl (zisk)
        denik.add(UcetniZaznam(
            doklad_id=bv.id, datum=date(2025, 9, 7),
            md_ucet="321.002", dal_ucet="663.100",
            castka=Money(1530),
            popis="Kurzový zisk FP-2025-038",
        ))

        # Bankovní transakce SPAROVANO
        tx_id = tx_repo.add(BankovniTransakce(
            bankovni_vypis_id=v_id,
            datum_transakce=date(2025, 9, 7),
            datum_zauctovani=date(2025, 9, 7),
            castka=Money(-54873),
            smer="V",
            row_hash="hash1",
            popis="Anthropic",
            stav=StavTransakce.SPAROVANO,
            sparovany_doklad_id=fp.id,
            ucetni_zapis_id=zapis_id,
        ))

        # Po spárování doklad UHRAZENY
        fp_doklad = drepo.get_by_id(fp.id)
        fp_doklad.oznac_uhrazeny()
        drepo.update(fp_doklad)

        uow.commit()
    return fp.id, tx_id, zapis_id, bv.id


class TestRozparovatPlatbu:

    def test_rozparuje_jednoduche(self, db_factory):
        """Spárovaná úhrada FP — rozpárování stornuje úhradu i kurz,
        doklad zpět ZAUCTOVANY, transakce NESPAROVANO."""
        fp_id, tx_id, zapis_id, bv_id = _create_paired_setup(db_factory)

        cmd = RozparovatPlatbuCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(transakce_id=tx_id)

        assert result.novy_stav_dokladu == StavDokladu.ZAUCTOVANY
        # Stornovány 2 zápisy: úhrada + kurzový rozdíl
        assert len(result.storno_zapis_ids) == 2

        # Verify TX state
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            tx_repo = SqliteBankovniTransakceRepository(uow)
            tx = tx_repo.get(tx_id)
            assert tx.stav == StavTransakce.NESPAROVANO
            assert tx.sparovany_doklad_id is None
            assert tx.ucetni_zapis_id is None

        # Verify doklad state
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            drepo = SqliteDokladyRepository(uow)
            fp = drepo.get_by_id(fp_id)
            assert fp.stav == StavDokladu.ZAUCTOVANY

        # Verify storno zápisy v deníku (audit trail)
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            rows = uow.connection.execute(
                "SELECT id, md_ucet, dal_ucet, castka, je_storno, "
                "stornuje_zaznam_id FROM ucetni_zaznamy "
                "WHERE je_storno=1 AND doklad_id=? ORDER BY id",
                (bv_id,),
            ).fetchall()
            assert len(rows) == 2
            # Storno úhrady — prohozené strany
            assert rows[0]["md_ucet"] == "221.002"
            assert rows[0]["dal_ucet"] == "321.002"
            assert rows[0]["castka"] == 54873
            # Storno kurzového rozdílu
            assert rows[1]["md_ucet"] == "663.100"
            assert rows[1]["dal_ucet"] == "321.002"

    def test_nesparovana_tx_rejected(self, db_factory):
        """Nelze rozpárovat nespárovanou transakci."""
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            ucet_repo = SqliteBankovniUcetRepository(uow)
            vypis_repo = SqliteBankovniVypisRepository(uow)
            tx_repo = SqliteBankovniTransakceRepository(uow)
            drepo = SqliteDokladyRepository(uow)

            u_id = ucet_repo.add(BankovniUcet(
                nazev="T", cislo_uctu="123/0800", ucet_kod="221.001",
                format_csv=FormatCsv.CESKA_SPORITELNA,
            ))
            bv = drepo.add(Doklad(
                cislo="BV-X", typ=TypDokladu.BANKOVNI_VYPIS,
                datum_vystaveni=date(2025, 1, 1),
                castka_celkem=Money(0),
            ))
            v_id = vypis_repo.add(BankovniVypis(
                bankovni_ucet_id=u_id, cislo_vypisu="x", rok=2025, mesic=1,
                pocatecni_stav=Money.zero(), konecny_stav=Money.zero(),
                pdf_path="/tmp/x.pdf",
                datum_od=date(2025, 1, 1), datum_do=date(2025, 1, 31),
                bv_doklad_id=bv.id,
            ))
            tx_id = tx_repo.add(BankovniTransakce(
                bankovni_vypis_id=v_id,
                datum_transakce=date(2025, 1, 1),
                datum_zauctovani=date(2025, 1, 1),
                castka=Money(1000), smer="P", row_hash="h",
            ))
            uow.commit()

        cmd = RozparovatPlatbuCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        with pytest.raises(ValidationError, match="rozpárovat"):
            cmd.execute(transakce_id=tx_id)

    def test_rozparuje_rucne_zauctovanou_bez_dokladu(self, db_factory):
        """AUTO_ZAUCTOVANO bez vazby na doklad — stornuje jen účetní zápis."""
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            ucet_repo = SqliteBankovniUcetRepository(uow)
            vypis_repo = SqliteBankovniVypisRepository(uow)
            tx_repo = SqliteBankovniTransakceRepository(uow)
            drepo = SqliteDokladyRepository(uow)
            denik = SqliteUcetniDenikRepository(uow)

            u_id = ucet_repo.add(BankovniUcet(
                nazev="T", cislo_uctu="123/0800", ucet_kod="221.001",
                format_csv=FormatCsv.CESKA_SPORITELNA,
            ))
            bv = drepo.add(Doklad(
                cislo="BV-X", typ=TypDokladu.BANKOVNI_VYPIS,
                datum_vystaveni=date(2025, 1, 1),
                castka_celkem=Money(0),
            ))
            v_id = vypis_repo.add(BankovniVypis(
                bankovni_ucet_id=u_id, cislo_vypisu="x", rok=2025, mesic=1,
                pocatecni_stav=Money.zero(), konecny_stav=Money.zero(),
                pdf_path="/tmp/x.pdf",
                datum_od=date(2025, 1, 1), datum_do=date(2025, 1, 31),
                bv_doklad_id=bv.id,
            ))
            zapis_id = denik.add(UcetniZaznam(
                doklad_id=bv.id, datum=date(2025, 1, 1),
                md_ucet="518.200", dal_ucet="221.001",
                castka=Money(50000),
                popis="Platba kartou — Náklad XYZ",
            ))
            tx_id = tx_repo.add(BankovniTransakce(
                bankovni_vypis_id=v_id,
                datum_transakce=date(2025, 1, 1),
                datum_zauctovani=date(2025, 1, 1),
                castka=Money(-50000), smer="V", row_hash="h-rucni",
                stav=StavTransakce.AUTO_ZAUCTOVANO,
                ucetni_zapis_id=zapis_id,
                # sparovany_doklad_id zůstane None — ručně zaúčtovaná
            ))
            uow.commit()

        cmd = RozparovatPlatbuCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        result = cmd.execute(transakce_id=tx_id)

        assert result.novy_stav_dokladu is None
        assert len(result.storno_zapis_ids) == 1

        # TX zpět NESPAROVANO + bez vazby na zápis
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            tx_repo = SqliteBankovniTransakceRepository(uow)
            tx = tx_repo.get(tx_id)
            assert tx.stav == StavTransakce.NESPAROVANO
            assert tx.ucetni_zapis_id is None

        # Storno protizápis v deníku — prohozené strany
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            row = uow.connection.execute(
                "SELECT md_ucet, dal_ucet, castka, je_storno, "
                "stornuje_zaznam_id FROM ucetni_zaznamy "
                "WHERE id = ?",
                (result.storno_zapis_ids[0],),
            ).fetchone()
            assert row["md_ucet"] == "221.001"  # prohozené
            assert row["dal_ucet"] == "518.200"
            assert row["je_storno"] == 1
            assert row["stornuje_zaznam_id"] == zapis_id

    def test_idempotence_dvojite_rozparovani(self, db_factory):
        """Druhé volání rozpárování na stejné TX selže (už NESPAROVANO)."""
        fp_id, tx_id, _, _ = _create_paired_setup(db_factory)
        cmd = RozparovatPlatbuCommand(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
        )
        cmd.execute(transakce_id=tx_id)
        with pytest.raises(ValidationError, match="rozpárovat"):
            cmd.execute(transakce_id=tx_id)
