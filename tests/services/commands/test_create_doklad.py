"""Integration testy pro CreateDokladCommand."""

from datetime import date

import pytest

from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import ConflictError, ValidationError
from domain.shared.money import Money
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.commands.create_doklad import (
    CreateDokladCommand,
    CreateDokladInput,
)


def _build(db_factory) -> CreateDokladCommand:
    return CreateDokladCommand(
        uow_factory=lambda: SqliteUnitOfWork(db_factory),
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
    )


class TestCreateDokladCommand:

    def test_vytvori_novy_doklad(self, db_factory):
        cmd = _build(db_factory)
        item = cmd.execute(CreateDokladInput(
            cislo="FV-2026-001",
            typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2026, 3, 1),
            castka_celkem=Money.from_koruny("12100"),
            datum_splatnosti=date(2026, 3, 15),
            popis="Konzultace",
        ))
        assert item.id is not None
        assert item.cislo == "FV-2026-001"
        assert item.stav == StavDokladu.NOVY
        assert item.castka_celkem == Money.from_koruny("12100")
        assert item.datum_splatnosti == date(2026, 3, 15)
        assert item.popis == "Konzultace"

    def test_persistuje_do_db(self, db_factory):
        cmd = _build(db_factory)
        cmd.execute(CreateDokladInput(
            cislo="FV-2026-002",
            typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2026, 3, 1),
            castka_celkem=Money.from_koruny("500"),
        ))

        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            loaded = repo.get_by_cislo("FV-2026-002")
        assert loaded.cislo == "FV-2026-002"

    def test_duplicitni_cislo_vyhodi_conflict(self, db_factory):
        cmd = _build(db_factory)
        cmd.execute(CreateDokladInput(
            cislo="FV-2026-003",
            typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2026, 3, 1),
            castka_celkem=Money.from_koruny("100"),
        ))
        with pytest.raises(ConflictError):
            cmd.execute(CreateDokladInput(
                cislo="FV-2026-003",
                typ=TypDokladu.FAKTURA_VYDANA,
                datum_vystaveni=date(2026, 4, 1),
                castka_celkem=Money.from_koruny("200"),
            ))

    def test_spatna_splatnost_vyhodi_validation(self, db_factory):
        cmd = _build(db_factory)
        with pytest.raises(ValidationError):
            cmd.execute(CreateDokladInput(
                cislo="FV-2026-004",
                typ=TypDokladu.FAKTURA_VYDANA,
                datum_vystaveni=date(2026, 3, 10),
                castka_celkem=Money.from_koruny("100"),
                datum_splatnosti=date(2026, 3, 5),  # před vystavením
            ))

    def test_bez_splatnosti_a_popisu(self, db_factory):
        cmd = _build(db_factory)
        item = cmd.execute(CreateDokladInput(
            cislo="ID-2026-001",
            typ=TypDokladu.INTERNI_DOKLAD,
            datum_vystaveni=date(2026, 3, 1),
            castka_celkem=Money.from_koruny("1000"),
        ))
        assert item.datum_splatnosti is None
        assert item.popis is None
