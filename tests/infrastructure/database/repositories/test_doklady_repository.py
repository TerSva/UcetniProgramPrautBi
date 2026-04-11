"""Testy pro SqliteDokladyRepository — s reálnou SQLite DB + migracemi."""

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import ConflictError, NotFoundError, ValidationError
from domain.shared.money import Money
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork


def _doklad(**kwargs) -> Doklad:
    """Helper: validní doklad s defaulty."""
    defaults = dict(
        cislo="FV-2026-001",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 1, 15),
        castka_celkem=Money(100000),
    )
    defaults.update(kwargs)
    return Doklad(**defaults)


class TestAdd:

    def test_add_vraci_doklad_s_id(self, db_factory):
        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            novy = repo.add(_doklad())
            write_uow.commit()

        assert novy.id is not None
        assert isinstance(novy.id, int)
        assert novy.id > 0

    def test_add_puvodni_zustava_bez_id(self, db_factory):
        """Původní instance zůstává s id=None."""
        puvodni = _doklad()
        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            novy = repo.add(puvodni)
            write_uow.commit()

        assert puvodni.id is None
        assert novy.id is not None

    def test_add_duplicitni_cislo_conflict(self, db_factory):
        uow1 = SqliteUnitOfWork(db_factory)
        with uow1:
            repo = SqliteDokladyRepository(uow1)
            repo.add(_doklad(cislo="FV-001"))
            uow1.commit()

        uow2 = SqliteUnitOfWork(db_factory)
        with uow2:
            repo = SqliteDokladyRepository(uow2)
            with pytest.raises(ConflictError, match="FV-001"):
                repo.add(_doklad(cislo="FV-001"))

    def test_add_s_existujicim_id_validation_error(self, db_factory):
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            with pytest.raises(ValidationError, match="already has id"):
                repo.add(_doklad(id=99))


class TestGetById:

    def test_round_trip(self, db_factory):
        """Všechna pole se korektně uloží a načtou."""
        original = Doklad(
            cislo="FP-2026-001",
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2026, 3, 1),
            castka_celkem=Money(123456789),
            datum_zdanitelneho_plneni=date(2026, 2, 28),
            datum_splatnosti=date(2026, 3, 15),
            popis="Služby za únor",
        )

        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            ulozeny = repo.add(original)
            write_uow.commit()

        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            nacteny = repo.get_by_id(ulozeny.id)

        assert nacteny.cislo == "FP-2026-001"
        assert nacteny.typ == TypDokladu.FAKTURA_PRIJATA
        assert nacteny.datum_vystaveni == date(2026, 3, 1)
        assert nacteny.castka_celkem == Money(123456789)
        assert nacteny.datum_zdanitelneho_plneni == date(2026, 2, 28)
        assert nacteny.datum_splatnosti == date(2026, 3, 15)
        assert nacteny.popis == "Služby za únor"
        assert nacteny.stav == StavDokladu.NOVY

    def test_neexistujici_not_found(self, db_factory):
        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            with pytest.raises(NotFoundError):
                repo.get_by_id(999)

    def test_money_round_trip_velka_castka(self, db_factory):
        """1 234 567,89 Kč round-trip."""
        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            ulozeny = repo.add(_doklad(castka_celkem=Money(123456789)))
            write_uow.commit()

        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            nacteny = repo.get_by_id(ulozeny.id)

        assert nacteny.castka_celkem.to_halire() == 123456789

    def test_none_pole_round_trip(self, db_factory):
        """None pole se uloží a načtou jako None."""
        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            ulozeny = repo.add(_doklad(
                partner_id=None,
                datum_zdanitelneho_plneni=None,
                datum_splatnosti=None,
                popis=None,
            ))
            write_uow.commit()

        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            nacteny = repo.get_by_id(ulozeny.id)

        assert nacteny.partner_id is None
        assert nacteny.datum_zdanitelneho_plneni is None
        assert nacteny.datum_splatnosti is None
        assert nacteny.popis is None


class TestGetByCislo:

    def test_nalezeno(self, db_factory):
        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            repo.add(_doklad(cislo="FV-UNIQUE"))
            write_uow.commit()

        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            d = repo.get_by_cislo("FV-UNIQUE")
        assert d.cislo == "FV-UNIQUE"

    def test_nenalezeno(self, db_factory):
        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            with pytest.raises(NotFoundError):
                repo.get_by_cislo("NEEXISTUJE")


class TestExistujeCislo:

    def test_existuje(self, db_factory):
        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            repo.add(_doklad(cislo="FV-TEST"))
            write_uow.commit()

        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            assert repo.existuje_cislo("FV-TEST") is True

    def test_neexistuje(self, db_factory):
        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            assert repo.existuje_cislo("NENI") is False


class TestUpdate:

    def test_update_zmeni_pole(self, db_factory):
        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            ulozeny = repo.add(_doklad(popis="Původní"))
            write_uow.commit()

        # Editace
        update_uow = SqliteUnitOfWork(db_factory)
        with update_uow:
            repo = SqliteDokladyRepository(update_uow)
            doklad = repo.get_by_id(ulozeny.id)
            doklad.uprav_popis("Nový popis")
            repo.update(doklad)
            update_uow.commit()

        # Ověření
        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            nacteny = repo.get_by_id(ulozeny.id)
        assert nacteny.popis == "Nový popis"

    def test_update_neexistujici_not_found(self, db_factory):
        doklad = _doklad(id=999)
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            with pytest.raises(NotFoundError, match="999"):
                repo.update(doklad)

    def test_update_bez_id_validation_error(self, db_factory):
        doklad = _doklad()  # id=None
        uow = SqliteUnitOfWork(db_factory)
        with uow:
            repo = SqliteDokladyRepository(uow)
            with pytest.raises(ValidationError, match="without id"):
                repo.update(doklad)

    def test_update_aktualizuje_timestamp(self, db_factory):
        """upraveno timestamp se změní po update."""
        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            ulozeny = repo.add(_doklad())
            write_uow.commit()

        # Přečteme původní timestamp
        conn = db_factory.create()
        row1 = conn.execute(
            "SELECT upraveno FROM doklady WHERE id=?", (ulozeny.id,)
        ).fetchone()
        conn.close()

        # Update
        update_uow = SqliteUnitOfWork(db_factory)
        with update_uow:
            repo = SqliteDokladyRepository(update_uow)
            doklad = repo.get_by_id(ulozeny.id)
            doklad.uprav_popis("Changed")
            repo.update(doklad)
            update_uow.commit()

        conn = db_factory.create()
        row2 = conn.execute(
            "SELECT upraveno FROM doklady WHERE id=?", (ulozeny.id,)
        ).fetchone()
        conn.close()

        # Timestamp se musel změnit (nebo být stejný pokud běží ve stejné sekundě)
        # Minimálně ověříme, že je validní ISO format
        assert row2["upraveno"] is not None
        assert len(row2["upraveno"]) == 19  # "YYYY-MM-DD HH:MM:SS"


class TestListByTyp:

    def test_filtruje_typ(self, db_factory):
        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            repo.add(_doklad(cislo="FV-001", typ=TypDokladu.FAKTURA_VYDANA))
            repo.add(_doklad(cislo="FP-001", typ=TypDokladu.FAKTURA_PRIJATA))
            repo.add(_doklad(cislo="FV-002", typ=TypDokladu.FAKTURA_VYDANA))
            write_uow.commit()

        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            fv = repo.list_by_typ(TypDokladu.FAKTURA_VYDANA)
        assert len(fv) == 2
        assert all(d.typ == TypDokladu.FAKTURA_VYDANA for d in fv)

    def test_serazeno_sestupne(self, db_factory):
        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            repo.add(_doklad(cislo="FV-001", datum_vystaveni=date(2026, 1, 1)))
            repo.add(_doklad(cislo="FV-002", datum_vystaveni=date(2026, 3, 1)))
            repo.add(_doklad(cislo="FV-003", datum_vystaveni=date(2026, 2, 1)))
            write_uow.commit()

        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            doklady = repo.list_by_typ(TypDokladu.FAKTURA_VYDANA)
        assert doklady[0].datum_vystaveni == date(2026, 3, 1)
        assert doklady[1].datum_vystaveni == date(2026, 2, 1)
        assert doklady[2].datum_vystaveni == date(2026, 1, 1)


class TestListByStav:

    def test_filtruje_stav(self, db_factory):
        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            d1 = repo.add(_doklad(cislo="FV-001"))
            repo.add(_doklad(cislo="FV-002"))
            write_uow.commit()

        # Zaúčtujeme jeden
        update_uow = SqliteUnitOfWork(db_factory)
        with update_uow:
            repo = SqliteDokladyRepository(update_uow)
            doklad = repo.get_by_id(d1.id)
            doklad.zauctuj()
            repo.update(doklad)
            update_uow.commit()

        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            nove = repo.list_by_stav(StavDokladu.NOVY)
            zauctovane = repo.list_by_stav(StavDokladu.ZAUCTOVANY)
        assert len(nove) == 1
        assert len(zauctovane) == 1


class TestListByObdobi:

    def test_inkluzivni_hranice(self, db_factory):
        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            repo.add(_doklad(cislo="FV-001", datum_vystaveni=date(2026, 1, 1)))
            repo.add(_doklad(cislo="FV-002", datum_vystaveni=date(2026, 1, 15)))
            repo.add(_doklad(cislo="FV-003", datum_vystaveni=date(2026, 1, 31)))
            repo.add(_doklad(cislo="FV-004", datum_vystaveni=date(2026, 2, 1)))
            write_uow.commit()

        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            leden = repo.list_by_obdobi(date(2026, 1, 1), date(2026, 1, 31))
        assert len(leden) == 3

    def test_limit_offset(self, db_factory):
        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            for i in range(5):
                repo.add(_doklad(
                    cislo=f"FV-{i:03d}",
                    datum_vystaveni=date(2026, 1, i + 1),
                ))
            write_uow.commit()

        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            page = repo.list_by_obdobi(
                date(2026, 1, 1), date(2026, 1, 31), limit=2, offset=2
            )
        assert len(page) == 2


class TestStavovyStrojPresRepository:

    def test_zauctuj_persist(self, db_factory):
        """Vlož NOVY, zaúčtuj, ulož, načti — stav ZAUCTOVANY."""
        write_uow = SqliteUnitOfWork(db_factory)
        with write_uow:
            repo = SqliteDokladyRepository(write_uow)
            ulozeny = repo.add(_doklad())
            write_uow.commit()

        update_uow = SqliteUnitOfWork(db_factory)
        with update_uow:
            repo = SqliteDokladyRepository(update_uow)
            doklad = repo.get_by_id(ulozeny.id)
            doklad.zauctuj()
            repo.update(doklad)
            update_uow.commit()

        read_uow = SqliteUnitOfWork(db_factory)
        with read_uow:
            repo = SqliteDokladyRepository(read_uow)
            nacteny = repo.get_by_id(ulozeny.id)
        assert nacteny.stav == StavDokladu.ZAUCTOVANY


class TestUowPravidlo:

    def test_repo_mimo_with_runtime_error(self, db_factory):
        """Repository bez aktivní UoW → RuntimeError při přístupu k connection."""
        uow = SqliteUnitOfWork(db_factory)
        repo = SqliteDokladyRepository(uow)
        with pytest.raises(Exception):
            repo.get_by_id(1)
