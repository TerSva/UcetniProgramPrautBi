"""Integration testy pro NextDokladNumberQuery."""

from datetime import date

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.money import Money
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.next_doklad_number import NextDokladNumberQuery


def _add(db_factory, cislo: str, typ: TypDokladu, datum: date) -> None:
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        repo.add(Doklad(
            cislo=cislo,
            typ=typ,
            datum_vystaveni=datum,
            castka_celkem=Money.from_koruny("100"),
        ))
        uow.commit()


def _build_query(db_factory) -> NextDokladNumberQuery:
    return NextDokladNumberQuery(
        uow_factory=lambda: SqliteUnitOfWork(db_factory),
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
    )


class TestNextDokladNumberQuery:

    def test_prazdna_db_vrati_001(self, db_factory):
        q = _build_query(db_factory)
        assert q.execute(TypDokladu.FAKTURA_VYDANA, 2026) == "FV-2026-001"

    def test_pokracuje_od_maxima(self, db_factory):
        _add(db_factory, "FV-2026-001", TypDokladu.FAKTURA_VYDANA,
             date(2026, 1, 5))
        _add(db_factory, "FV-2026-002", TypDokladu.FAKTURA_VYDANA,
             date(2026, 2, 5))

        q = _build_query(db_factory)
        assert q.execute(TypDokladu.FAKTURA_VYDANA, 2026) == "FV-2026-003"

    def test_diry_v_cislovani_vrati_max_plus_1(self, db_factory):
        _add(db_factory, "FV-2026-001", TypDokladu.FAKTURA_VYDANA,
             date(2026, 1, 5))
        _add(db_factory, "FV-2026-005", TypDokladu.FAKTURA_VYDANA,
             date(2026, 2, 5))

        q = _build_query(db_factory)
        assert q.execute(TypDokladu.FAKTURA_VYDANA, 2026) == "FV-2026-006"

    def test_jine_typy_ignorovany(self, db_factory):
        _add(db_factory, "FP-2026-001", TypDokladu.FAKTURA_PRIJATA,
             date(2026, 1, 5))
        _add(db_factory, "FP-2026-007", TypDokladu.FAKTURA_PRIJATA,
             date(2026, 2, 5))

        q = _build_query(db_factory)
        assert q.execute(TypDokladu.FAKTURA_VYDANA, 2026) == "FV-2026-001"

    def test_jine_roky_ignorovany(self, db_factory):
        _add(db_factory, "FV-2025-042", TypDokladu.FAKTURA_VYDANA,
             date(2025, 6, 5))

        q = _build_query(db_factory)
        assert q.execute(TypDokladu.FAKTURA_VYDANA, 2026) == "FV-2026-001"

    def test_nestandardni_cisla_ignorovana(self, db_factory):
        # Legacy doklad s nestandardním formátem — regex ho přeskočí.
        _add(db_factory, "FAK-001", TypDokladu.FAKTURA_VYDANA,
             date(2026, 1, 5))

        q = _build_query(db_factory)
        assert q.execute(TypDokladu.FAKTURA_VYDANA, 2026) == "FV-2026-001"

    def test_velke_cislo_padding(self, db_factory):
        _add(db_factory, "FV-2026-099", TypDokladu.FAKTURA_VYDANA,
             date(2026, 1, 5))

        q = _build_query(db_factory)
        assert q.execute(TypDokladu.FAKTURA_VYDANA, 2026) == "FV-2026-100"

    def test_format_pro_jiny_typ(self, db_factory):
        q = _build_query(db_factory)
        assert q.execute(TypDokladu.FAKTURA_PRIJATA, 2026) == "FP-2026-001"
