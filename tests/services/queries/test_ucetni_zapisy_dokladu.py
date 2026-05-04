"""Testy UcetniZapisyDokladuQuery — detail účetních zápisů dokladu."""

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
from services.queries.ucetni_zapisy_dokladu import UcetniZapisyDokladuQuery


@pytest.fixture
def factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    f = ConnectionFactory(db_path)
    runner = MigrationRunner(
        f,
        Path("infrastructure/database/migrations/sql"),
    )
    runner.migrate()
    return f


def _query(factory) -> UcetniZapisyDokladuQuery:
    return UcetniZapisyDokladuQuery(
        uow_factory=lambda: SqliteUnitOfWork(factory),
    )


class TestListByDoklad:

    def test_zapisy_primo_na_dokladu(self, factory):
        """Zápisy s doklad_id == doklad_id se vrátí z branch 1."""
        uow = SqliteUnitOfWork(factory)
        with uow:
            drepo = SqliteDokladyRepository(uow)
            d = drepo.add(Doklad(
                cislo="FP-001",
                typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2025, 5, 1),
                castka_celkem=Money(100000),
            ))
            denik = SqliteUcetniDenikRepository(uow)
            denik.add(UcetniZaznam(
                doklad_id=d.id, datum=date(2025, 5, 1),
                md_ucet="518", dal_ucet="321",
                castka=Money(100000),
            ))
            uow.commit()
        result = _query(factory).list_by_doklad(d.id)
        assert len(result) == 1
        assert result[0].md_ucet == "518"

    def test_kurzovy_rozdil_na_bv_se_zobrazi_v_detailu_fp(self, factory):
        """Kurzový rozdíl je zaúčtován na BV doklad s popisem obsahujícím
        číslo FP — query ho musí najít přes branch 3 (typ='BV')."""
        uow = SqliteUnitOfWork(factory)
        with uow:
            drepo = SqliteDokladyRepository(uow)
            denik = SqliteUcetniDenikRepository(uow)
            # FP doklad
            fp = drepo.add(Doklad(
                cislo="FPR-2025-001",
                typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2025, 5, 1),
                castka_celkem=Money(250000),
                stav=StavDokladu.UHRAZENY,
            ))
            # BV doklad pro úhradu
            bv = drepo.add(Doklad(
                cislo="BV-2025-05",
                typ=TypDokladu.BANKOVNI_VYPIS,
                datum_vystaveni=date(2025, 5, 5),
                castka_celkem=Money(0),
            ))
            # Úhradový zápis na BV
            denik.add(UcetniZaznam(
                doklad_id=bv.id, datum=date(2025, 5, 5),
                md_ucet="321", dal_ucet="221.001",
                castka=Money(260000),
                popis="Úhrada FPR-2025-001",
            ))
            # Kurzový rozdíl na BV (typ='BV')
            denik.add(UcetniZaznam(
                doklad_id=bv.id, datum=date(2025, 5, 5),
                md_ucet="563.100", dal_ucet="321",
                castka=Money(10000),
                popis="Kurzová ztráta FPR-2025-001",
            ))
            uow.commit()

        result = _query(factory).list_by_doklad(fp.id)
        # 0 přímých + 2 přes popis (úhrada + kurzový rozdíl)
        assert len(result) == 2
        popisy = [r.popis for r in result]
        assert any("Úhrada" in p for p in popisy if p)
        assert any("Kurzov" in p for p in popisy if p)
        # Kurzový zápis je na analytice 563.100
        kurz = [r for r in result if r.popis and "Kurzov" in r.popis][0]
        assert kurz.md_ucet == "563.100"

    def test_pd_id_uhrady_pres_popis(self, factory):
        """Pokladní/interní doklad s popisem obsahujícím číslo se najde."""
        uow = SqliteUnitOfWork(factory)
        with uow:
            drepo = SqliteDokladyRepository(uow)
            denik = SqliteUcetniDenikRepository(uow)
            fp = drepo.add(Doklad(
                cislo="FP-2025-007",
                typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2025, 5, 1),
                castka_celkem=Money(100000),
            ))
            pd = drepo.add(Doklad(
                cislo="PD-2025-001",
                typ=TypDokladu.POKLADNI_DOKLAD,
                datum_vystaveni=date(2025, 5, 5),
                castka_celkem=Money(100000),
            ))
            denik.add(UcetniZaznam(
                doklad_id=pd.id, datum=date(2025, 5, 5),
                md_ucet="321", dal_ucet="211",
                castka=Money(100000),
                popis="Hotovostní úhrada FP-2025-007",
            ))
            uow.commit()

        result = _query(factory).list_by_doklad(fp.id)
        assert len(result) == 1
        assert result[0].zdroj_doklad == "PD-2025-001"
