"""Testy pro 001_init_schema.sql — ověření, že schema je korektní."""

import sqlite3
from pathlib import Path

import pytest

from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner


SQL_DIR = Path(__file__).parent.parent.parent.parent / "infrastructure" / "database" / "migrations" / "sql"


@pytest.fixture
def migrated_factory(tmp_path) -> ConnectionFactory:
    """Factory s aplikovanou migrací 001."""
    factory = ConnectionFactory(tmp_path / "test.db")
    runner = MigrationRunner(factory, SQL_DIR)
    runner.migrate()
    return factory


class TestTabulkyExistuji:

    def test_partneri_existuje(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='partneri'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()

    def test_uctova_osnova_existuje(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='uctova_osnova'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()

    def test_doklady_existuje(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='doklady'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()

    def test_ucetni_zaznamy_existuje(self, migrated_factory):
        conn = migrated_factory.create()
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ucetni_zaznamy'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()


class TestTypySloupcu:

    def test_doklady_castka_celkem_integer(self, migrated_factory):
        """doklady.castka_celkem má typ INTEGER."""
        conn = migrated_factory.create()
        try:
            columns = conn.execute("PRAGMA table_info(doklady)").fetchall()
            castka_col = next(c for c in columns if c["name"] == "castka_celkem")
            assert castka_col["type"] == "INTEGER"
        finally:
            conn.close()

    def test_ucetni_zaznamy_castka_integer(self, migrated_factory):
        """ucetni_zaznamy.castka má typ INTEGER."""
        conn = migrated_factory.create()
        try:
            columns = conn.execute("PRAGMA table_info(ucetni_zaznamy)").fetchall()
            castka_col = next(c for c in columns if c["name"] == "castka")
            assert castka_col["type"] == "INTEGER"
        finally:
            conn.close()


class TestForeignKeys:

    def test_ucetni_zaznamy_fk_doklad_id(self, migrated_factory):
        """FK constraint: ucetni_zaznamy s neexistujícím doklad_id → IntegrityError."""
        conn = migrated_factory.create()
        try:
            conn.execute("BEGIN")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO ucetni_zaznamy (doklad_id, datum, md_ucet, dal_ucet, castka) "
                    "VALUES (999, '2026-01-01', '211', '321', 10000)"
                )
        finally:
            conn.close()

    def test_doklady_fk_partner_id(self, migrated_factory):
        """FK constraint: doklady s neexistujícím partner_id → IntegrityError."""
        conn = migrated_factory.create()
        try:
            conn.execute("BEGIN")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO doklady (cislo, typ, datum_vystaveni, partner_id) "
                    "VALUES ('FV-001', 'FV', '2026-01-01', 999)"
                )
        finally:
            conn.close()


class TestCheckConstraints:

    def test_uctova_osnova_typ_neplatny(self, migrated_factory):
        """CHECK constraint: uctova_osnova.typ = 'X' → IntegrityError."""
        conn = migrated_factory.create()
        try:
            conn.execute("BEGIN")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO uctova_osnova (cislo, nazev, typ) VALUES ('999', 'Bad', 'X')"
                )
        finally:
            conn.close()

    def test_partneri_typ_neplatny(self, migrated_factory):
        """CHECK constraint: partneri.typ neplatný → IntegrityError."""
        conn = migrated_factory.create()
        try:
            conn.execute("BEGIN")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO partneri (nazev, typ) VALUES ('Test', 'neplatny')"
                )
        finally:
            conn.close()

    def test_doklady_typ_neplatny(self, migrated_factory):
        """CHECK constraint: doklady.typ neplatný → IntegrityError."""
        conn = migrated_factory.create()
        try:
            conn.execute("BEGIN")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO doklady (cislo, typ, datum_vystaveni) "
                    "VALUES ('XX-001', 'XX', '2026-01-01')"
                )
        finally:
            conn.close()

    def test_doklady_stav_neplatny(self, migrated_factory):
        """CHECK constraint: doklady.stav neplatný → IntegrityError."""
        conn = migrated_factory.create()
        try:
            conn.execute("BEGIN")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO doklady (cislo, typ, datum_vystaveni, stav) "
                    "VALUES ('FV-001', 'FV', '2026-01-01', 'neplatny')"
                )
        finally:
            conn.close()

    def test_ucetni_zaznamy_castka_nula(self, migrated_factory):
        """CHECK constraint: ucetni_zaznamy.castka musí být > 0."""
        conn = migrated_factory.create()
        try:
            # Účty 211, 321 už existují ze seedu (migrace 002)
            conn.execute("BEGIN")
            conn.execute(
                "INSERT INTO doklady (cislo, typ, datum_vystaveni) "
                "VALUES ('FV-001', 'FV', '2026-01-01')"
            )
            conn.execute("COMMIT")

            conn.execute("BEGIN")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO ucetni_zaznamy (doklad_id, datum, md_ucet, dal_ucet, castka) "
                    "VALUES (1, '2026-01-01', '211', '321', 0)"
                )
        finally:
            conn.close()

    def test_ucetni_zaznamy_castka_zaporna(self, migrated_factory):
        """CHECK constraint: ucetni_zaznamy.castka záporná → IntegrityError."""
        conn = migrated_factory.create()
        try:
            # Účty 211, 321 už existují ze seedu (migrace 002)
            conn.execute("BEGIN")
            conn.execute(
                "INSERT INTO doklady (cislo, typ, datum_vystaveni) "
                "VALUES ('FV-001', 'FV', '2026-01-01')"
            )
            conn.execute("COMMIT")

            conn.execute("BEGIN")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO ucetni_zaznamy (doklad_id, datum, md_ucet, dal_ucet, castka) "
                    "VALUES (1, '2026-01-01', '211', '321', -100)"
                )
        finally:
            conn.close()


class TestValidniZaznamy:

    def test_vloz_a_vycti_vsechny_tabulky(self, migrated_factory):
        """Vlož validní záznamy do všech tabulek a vyčti je zpátky."""
        conn = migrated_factory.create()
        try:
            conn.execute("BEGIN")

            # Partner
            conn.execute(
                "INSERT INTO partneri (nazev, ico, typ) "
                "VALUES ('Firma s.r.o.', '12345678', 'dodavatel')"
            )

            # Účty 321, 518 už existují ze seedu (migrace 002)

            # Doklad
            conn.execute(
                "INSERT INTO doklady (cislo, typ, datum_vystaveni, partner_id, castka_celkem) "
                "VALUES ('FP-2026-001', 'FP', '2026-01-15', 1, 121000)"
            )

            # Účetní záznam (1210 Kč = 121000 haléřů)
            conn.execute(
                "INSERT INTO ucetni_zaznamy (doklad_id, datum, md_ucet, dal_ucet, castka, popis) "
                "VALUES (1, '2026-01-15', '518', '321', 121000, 'Služby od Firma s.r.o.')"
            )

            conn.execute("COMMIT")

            # Vyčtení
            partner = conn.execute("SELECT * FROM partneri WHERE id=1").fetchone()
            assert partner["nazev"] == "Firma s.r.o."
            assert partner["ico"] == "12345678"

            doklad = conn.execute("SELECT * FROM doklady WHERE id=1").fetchone()
            assert doklad["cislo"] == "FP-2026-001"
            assert doklad["castka_celkem"] == 121000
            assert doklad["stav"] == "novy"

            zaznam = conn.execute("SELECT * FROM ucetni_zaznamy WHERE id=1").fetchone()
            assert zaznam["castka"] == 121000
            assert zaznam["md_ucet"] == "518"
            assert zaznam["dal_ucet"] == "321"
        finally:
            conn.close()
