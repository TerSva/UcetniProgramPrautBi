"""Testy SqlitePartneriRepository — CRUD, search, constraints."""

from decimal import Decimal

import pytest

from domain.partneri.partner import KategoriePartnera, Partner
from domain.shared.errors import NotFoundError
from infrastructure.database.repositories.partneri_repository import (
    SqlitePartneriRepository,
)


class TestPartneriCRUD:

    def test_add_and_get(self, db_factory, uow):
        partner = Partner(
            nazev="iStyle CZ",
            kategorie=KategoriePartnera.DODAVATEL,
            ico="27583368",
        )
        with uow:
            repo = SqlitePartneriRepository(uow)
            saved = repo.add(partner)
            uow.commit()

        assert saved.id is not None
        assert saved.nazev == "iStyle CZ"

        with uow:
            repo = SqlitePartneriRepository(uow)
            loaded = repo.get_by_id(saved.id)

        assert loaded.nazev == "iStyle CZ"
        assert loaded.ico == "27583368"
        assert loaded.kategorie == KategoriePartnera.DODAVATEL

    def test_update(self, db_factory, uow):
        with uow:
            repo = SqlitePartneriRepository(uow)
            saved = repo.add(Partner(
                nazev="Old", kategorie=KategoriePartnera.DODAVATEL,
            ))
            uow.commit()

        with uow:
            repo = SqlitePartneriRepository(uow)
            partner = repo.get_by_id(saved.id)
            partner.uprav(nazev="New")
            repo.update(partner)
            uow.commit()

        with uow:
            repo = SqlitePartneriRepository(uow)
            updated = repo.get_by_id(saved.id)

        assert updated.nazev == "New"

    def test_get_by_ico(self, db_factory, uow):
        with uow:
            repo = SqlitePartneriRepository(uow)
            repo.add(Partner(
                nazev="Firma", kategorie=KategoriePartnera.DODAVATEL,
                ico="11111111",
            ))
            uow.commit()

        with uow:
            repo = SqlitePartneriRepository(uow)
            found = repo.get_by_ico("11111111")
            not_found = repo.get_by_ico("99999999")

        assert found is not None
        assert found.nazev == "Firma"
        assert not_found is None

    def test_get_by_id_not_found(self, db_factory, uow):
        with uow:
            repo = SqlitePartneriRepository(uow)
            with pytest.raises(NotFoundError):
                repo.get_by_id(999)


class TestPartneriSearch:

    def test_search_by_nazev(self, db_factory, uow):
        with uow:
            repo = SqlitePartneriRepository(uow)
            repo.add(Partner(
                nazev="iStyle CZ", kategorie=KategoriePartnera.DODAVATEL,
            ))
            repo.add(Partner(
                nazev="Meta Platforms", kategorie=KategoriePartnera.DODAVATEL,
            ))
            uow.commit()

        with uow:
            repo = SqlitePartneriRepository(uow)
            results = repo.search("ist")

        assert len(results) == 1
        assert results[0].nazev == "iStyle CZ"

    def test_search_by_ico(self, db_factory, uow):
        with uow:
            repo = SqlitePartneriRepository(uow)
            repo.add(Partner(
                nazev="Firma", kategorie=KategoriePartnera.DODAVATEL,
                ico="27583368",
            ))
            uow.commit()

        with uow:
            repo = SqlitePartneriRepository(uow)
            results = repo.search("2758")

        assert len(results) == 1


class TestPartneriList:

    def test_list_all(self, db_factory, uow):
        with uow:
            repo = SqlitePartneriRepository(uow)
            repo.add(Partner(
                nazev="A", kategorie=KategoriePartnera.DODAVATEL,
            ))
            repo.add(Partner(
                nazev="B", kategorie=KategoriePartnera.ODBERATEL,
            ))
            uow.commit()

        with uow:
            repo = SqlitePartneriRepository(uow)
            all_ = repo.list_all()
            dod = repo.list_all(kategorie=KategoriePartnera.DODAVATEL)

        assert len(all_) == 2
        assert len(dod) == 1

    def test_list_spolecnici(self, db_factory, uow):
        with uow:
            repo = SqlitePartneriRepository(uow)
            repo.add(Partner(
                nazev="Martin", kategorie=KategoriePartnera.SPOLECNIK,
                podil_procent=Decimal("90"),
            ))
            repo.add(Partner(
                nazev="Firma", kategorie=KategoriePartnera.DODAVATEL,
            ))
            uow.commit()

        with uow:
            repo = SqlitePartneriRepository(uow)
            spol = repo.list_spolecnici()

        assert len(spol) == 1
        assert spol[0].nazev == "Martin"

    def test_list_jen_aktivni(self, db_factory, uow):
        with uow:
            repo = SqlitePartneriRepository(uow)
            saved = repo.add(Partner(
                nazev="Inactive", kategorie=KategoriePartnera.DODAVATEL,
            ))
            partner = repo.get_by_id(saved.id)
            partner.deaktivuj()
            repo.update(partner)
            uow.commit()

        with uow:
            repo = SqlitePartneriRepository(uow)
            active = repo.list_all(jen_aktivni=True)
            all_ = repo.list_all(jen_aktivni=False)

        assert len(active) == 0
        assert len(all_) == 1
