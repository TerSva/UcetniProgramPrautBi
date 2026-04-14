"""Integration testy pro DokladyListQuery (query + filtry + DTO)."""

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.doklady_list import (
    DokladyFilter,
    DokladyListItem,
    DokladyListQuery,
    KDoreseniFilter,
)


# ──────────────────────────────────────────────────────────────────────
# Helpers — seed DB
# ──────────────────────────────────────────────────────────────────────


def _add(
    db_factory,
    cislo: str,
    typ: TypDokladu,
    datum: date,
    castka: str,
    stav: StavDokladu = StavDokladu.NOVY,
    k_doreseni: bool = False,
    poznamka: str | None = None,
) -> int:
    uow = SqliteUnitOfWork(db_factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(
            cislo=cislo,
            typ=typ,
            datum_vystaveni=datum,
            castka_celkem=Money.from_koruny(castka),
            k_doreseni=k_doreseni,
            poznamka_doreseni=poznamka,
        ))
        # případná změna stavu
        if stav == StavDokladu.ZAUCTOVANY:
            d.zauctuj()
            repo.update(d)
        uow.commit()
    return d.id  # type: ignore[return-value]


def _build_query(db_factory) -> DokladyListQuery:
    return DokladyListQuery(
        uow_factory=lambda: SqliteUnitOfWork(db_factory),
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
    )


# ──────────────────────────────────────────────────────────────────────
# DokladyFilter DTO
# ──────────────────────────────────────────────────────────────────────


class TestDokladyFilter:

    def test_defaulty(self):
        f = DokladyFilter()
        assert f.rok is None
        assert f.typ is None
        assert f.stav is None
        assert f.k_doreseni == KDoreseniFilter.SKRYT

    def test_je_vychozi_true_pri_defaultech(self):
        assert DokladyFilter().je_vychozi is True

    def test_je_vychozi_false_kdyz_rok_set(self):
        assert DokladyFilter(rok=2026).je_vychozi is False

    def test_je_vychozi_false_kdyz_typ_set(self):
        assert DokladyFilter(typ=TypDokladu.FAKTURA_VYDANA).je_vychozi is False

    def test_je_vychozi_false_kdyz_k_doreseni_pouze(self):
        f = DokladyFilter(k_doreseni=KDoreseniFilter.POUZE)
        assert f.je_vychozi is False

    def test_je_vychozi_false_kdyz_k_doreseni_vse(self):
        f = DokladyFilter(k_doreseni=KDoreseniFilter.VSE)
        assert f.je_vychozi is False

    def test_je_frozen(self):
        f = DokladyFilter()
        with pytest.raises(Exception):
            f.rok = 2026  # type: ignore[misc]


# ──────────────────────────────────────────────────────────────────────
# DokladyListItem DTO
# ──────────────────────────────────────────────────────────────────────


class TestDokladyListItem:

    def test_from_domain_mapping(self):
        d = Doklad(
            cislo="FV-001",
            typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2026, 2, 1),
            castka_celkem=Money.from_koruny("1000"),
            id=42,
        )
        item = DokladyListItem.from_domain(d)
        assert item.id == 42
        assert item.cislo == "FV-001"
        assert item.typ == TypDokladu.FAKTURA_VYDANA
        assert item.castka_celkem == Money.from_koruny("1000")
        assert item.k_doreseni is False
        assert item.partner_nazev is None
        assert item.stav == StavDokladu.NOVY

    def test_from_domain_vyhodi_bez_id(self):
        d = Doklad(
            cislo="FV-002",
            typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2026, 2, 1),
            castka_celkem=Money.from_koruny("100"),
        )
        with pytest.raises(ValueError):
            DokladyListItem.from_domain(d)


# ──────────────────────────────────────────────────────────────────────
# DokladyListQuery — empty DB
# ──────────────────────────────────────────────────────────────────────


class TestQueryPrazdnaDb:

    def test_prazdny_seznam_defaultni_filter(self, db_factory):
        q = _build_query(db_factory)
        assert q.execute(DokladyFilter()) == []

    def test_prazdny_seznam_s_filtry(self, db_factory):
        q = _build_query(db_factory)
        f = DokladyFilter(rok=2026, typ=TypDokladu.FAKTURA_VYDANA)
        assert q.execute(f) == []


# ──────────────────────────────────────────────────────────────────────
# DokladyListQuery — filtrování
# ──────────────────────────────────────────────────────────────────────


class TestQueryFiltrovani:

    def test_defaultni_filter_vraci_vsechno_bez_flagnutych(self, db_factory):
        _add(db_factory, "A-1", TypDokladu.FAKTURA_VYDANA,
             date(2026, 2, 1), "100")
        _add(db_factory, "A-2", TypDokladu.FAKTURA_PRIJATA,
             date(2026, 3, 1), "200", k_doreseni=True, poznamka="pz")

        q = _build_query(db_factory)
        items = q.execute(DokladyFilter())
        assert len(items) == 1
        assert items[0].cislo == "A-1"

    def test_k_doreseni_vse_vraci_i_flagnute(self, db_factory):
        _add(db_factory, "A-1", TypDokladu.FAKTURA_VYDANA,
             date(2026, 2, 1), "100")
        _add(db_factory, "A-2", TypDokladu.FAKTURA_PRIJATA,
             date(2026, 3, 1), "200", k_doreseni=True, poznamka="pz")

        q = _build_query(db_factory)
        items = q.execute(DokladyFilter(k_doreseni=KDoreseniFilter.VSE))
        assert len(items) == 2

    def test_k_doreseni_pouze_vraci_jen_flagnute(self, db_factory):
        _add(db_factory, "A-1", TypDokladu.FAKTURA_VYDANA,
             date(2026, 2, 1), "100")
        _add(db_factory, "A-2", TypDokladu.FAKTURA_PRIJATA,
             date(2026, 3, 1), "200", k_doreseni=True, poznamka="pz")

        q = _build_query(db_factory)
        items = q.execute(DokladyFilter(k_doreseni=KDoreseniFilter.POUZE))
        assert len(items) == 1
        assert items[0].cislo == "A-2"
        assert items[0].k_doreseni is True

    def test_filter_typ(self, db_factory):
        _add(db_factory, "F-1", TypDokladu.FAKTURA_VYDANA,
             date(2026, 2, 1), "100")
        _add(db_factory, "F-2", TypDokladu.FAKTURA_PRIJATA,
             date(2026, 2, 2), "200")

        q = _build_query(db_factory)
        items = q.execute(DokladyFilter(typ=TypDokladu.FAKTURA_VYDANA))
        assert len(items) == 1
        assert items[0].cislo == "F-1"

    def test_filter_stav(self, db_factory):
        _add(db_factory, "S-1", TypDokladu.FAKTURA_VYDANA,
             date(2026, 2, 1), "100", stav=StavDokladu.NOVY)
        _add(db_factory, "S-2", TypDokladu.FAKTURA_VYDANA,
             date(2026, 3, 1), "200", stav=StavDokladu.ZAUCTOVANY)

        q = _build_query(db_factory)
        items = q.execute(DokladyFilter(stav=StavDokladu.NOVY))
        assert len(items) == 1
        assert items[0].cislo == "S-1"

    def test_filter_rok_vyfiltruje_datum(self, db_factory):
        _add(db_factory, "R-2025", TypDokladu.FAKTURA_VYDANA,
             date(2025, 6, 1), "100")
        _add(db_factory, "R-2026", TypDokladu.FAKTURA_VYDANA,
             date(2026, 6, 1), "200")

        q = _build_query(db_factory)
        items = q.execute(DokladyFilter(rok=2025))
        assert len(items) == 1
        assert items[0].cislo == "R-2025"

    def test_razeni_datum_desc(self, db_factory):
        _add(db_factory, "OLD", TypDokladu.FAKTURA_VYDANA,
             date(2026, 1, 1), "100")
        _add(db_factory, "NEW", TypDokladu.FAKTURA_VYDANA,
             date(2026, 6, 1), "200")

        q = _build_query(db_factory)
        items = q.execute(DokladyFilter())
        assert [i.cislo for i in items] == ["NEW", "OLD"]

    def test_kombinace_typ_a_stav(self, db_factory):
        _add(db_factory, "X-1", TypDokladu.FAKTURA_VYDANA,
             date(2026, 2, 1), "100", stav=StavDokladu.NOVY)
        _add(db_factory, "X-2", TypDokladu.FAKTURA_VYDANA,
             date(2026, 3, 1), "200", stav=StavDokladu.ZAUCTOVANY)
        _add(db_factory, "X-3", TypDokladu.FAKTURA_PRIJATA,
             date(2026, 4, 1), "300", stav=StavDokladu.NOVY)

        q = _build_query(db_factory)
        items = q.execute(DokladyFilter(
            typ=TypDokladu.FAKTURA_VYDANA,
            stav=StavDokladu.ZAUCTOVANY,
        ))
        assert len(items) == 1
        assert items[0].cislo == "X-2"
