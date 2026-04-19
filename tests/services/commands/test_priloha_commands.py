"""Testy pro PrilohaCommands."""

from datetime import date
from pathlib import Path

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.errors import NotFoundError
from domain.shared.money import Money
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.priloha_repository import (
    SqlitePrilohaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from infrastructure.storage.priloha_storage import PrilohaStorage
from services.commands.priloha_commands import PrilohaCommands


class TestPrilohaCommands:
    """Připojení PDF k dokladu přes command."""

    @pytest.fixture
    def setup(self, service_factories, tmp_path):
        db_factory = service_factories["db_factory"]
        storage_root = tmp_path / "doklady"
        storage = PrilohaStorage(root=storage_root)
        commands = PrilohaCommands(
            uow_factory=lambda: SqliteUnitOfWork(db_factory),
            storage=storage,
        )

        # Vytvoř doklad
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            drepo = SqliteDokladyRepository(uow)
            doklad = drepo.add(Doklad(
                cislo="FP-2025-0001",
                typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2025, 1, 15),
                castka_celkem=Money(100_00),
            ))
            uow.commit()

        # Vytvoř sample PDF
        pdf = tmp_path / "source.pdf"
        pdf.write_bytes(b"%PDF-1.4 test content")

        return {
            "commands": commands,
            "doklad": doklad,
            "pdf": pdf,
            "db_factory": db_factory,
            "storage_root": storage_root,
        }

    def test_priloz_pdf_creates_record_and_file(self, setup):
        result = setup["commands"].priloz_pdf_k_dokladu(
            doklad_id=setup["doklad"].id,
            source_path=setup["pdf"],
            original_name="faktura.pdf",
        )
        assert result.id is not None
        assert result.nazev_souboru == "faktura.pdf"
        assert result.velikost_bytes > 0
        assert "doklady/2025/FP/" in result.relativni_cesta

        # Ověř fyzický soubor
        physical = setup["storage_root"].parent / result.relativni_cesta
        assert physical.exists()

    def test_priloz_pdf_to_nonexistent_doklad_raises(self, setup):
        with pytest.raises(NotFoundError):
            setup["commands"].priloz_pdf_k_dokladu(
                doklad_id=9999,
                source_path=setup["pdf"],
                original_name="faktura.pdf",
            )

    def test_priloz_stores_original_name_in_db(self, setup):
        result = setup["commands"].priloz_pdf_k_dokladu(
            doklad_id=setup["doklad"].id,
            source_path=setup["pdf"],
            original_name="RCH0002:25.pdf",
        )
        # DB má originální název
        assert result.nazev_souboru == "RCH0002:25.pdf"
        # Ale fyzická cesta má sanitizovaný název
        assert "RCH0002_25.pdf" in result.relativni_cesta
