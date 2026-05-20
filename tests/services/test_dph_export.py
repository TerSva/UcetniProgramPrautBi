"""Testy DphExportService — HTML rendering a rozsah měsíců."""

from datetime import date
from pathlib import Path
import tempfile

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.export.dph_export import (
    DphExportRozsah,
    DphExportService,
)
from services.queries.dph_prehled import DphMesicDetailQuery, DphPrehledQuery


@pytest.fixture()
def factory():
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "test.db"
    f = ConnectionFactory(db_path)
    migrations_dir = Path("infrastructure/database/migrations/sql")
    MigrationRunner(f, migrations_dir).migrate()
    conn = f.create()
    conn.execute(
        "INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES "
        "('518', 'Ostatní služby', 'N', 1),"
        "('321', 'Dodavatelé', 'P', 1),"
        "('343', 'DPH', 'P', 1)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni, parent_kod) VALUES "
        "('343.100', 'DPH vstup', 'P', 1, '343'),"
        "('343.200', 'DPH výstup', 'P', 1, '343'),"
        "('518.100', 'Reklama', 'N', 1, '518'),"
        "('321.002', 'Meta Platforms', 'P', 1, '321')"
    )
    conn.commit()
    conn.close()
    return f


def _seed_rc_doklad(factory, cislo, datum, castka_halire):
    uow = SqliteUnitOfWork(factory)
    with uow:
        drepo = SqliteDokladyRepository(uow)
        doklad = Doklad(
            cislo=cislo,
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=datum,
            castka_celkem=Money(castka_halire),
        )
        drepo.add(doklad)
        uow.commit()

    uow2 = SqliteUnitOfWork(factory)
    with uow2:
        drepo2 = SqliteDokladyRepository(uow2)
        loaded = drepo2.get_by_cislo(cislo)
        dph_halire = round(castka_halire * 21 / 100)
        predpis = UctovyPredpis(
            doklad_id=loaded.id,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=loaded.id, datum=datum,
                    md_ucet="518.100", dal_ucet="321.002",
                    castka=Money(castka_halire),
                ),
                UcetniZaznam(
                    doklad_id=loaded.id, datum=datum,
                    md_ucet="343.100", dal_ucet="343.200",
                    castka=Money(dph_halire),
                ),
            ),
        )
        SqliteUcetniDenikRepository(uow2).zauctuj(predpis)
        loaded.zauctuj()
        drepo2.update(loaded)
        uow2.commit()


def _service(factory) -> DphExportService:
    uow_factory = lambda: SqliteUnitOfWork(factory)
    return DphExportService(
        uow_factory=uow_factory,
        prehled_query=DphPrehledQuery(uow_factory),
        detail_query=DphMesicDetailQuery(uow_factory),
    )


class TestRozsahIter:

    def test_jeden_mesic(self):
        r = DphExportRozsah(2025, 5, 2025, 5)
        assert r.iter_mesice() == [(2025, 5)]

    def test_rozsah_v_jednom_roce(self):
        r = DphExportRozsah(2025, 4, 2025, 6)
        assert r.iter_mesice() == [(2025, 4), (2025, 5), (2025, 6)]

    def test_pres_konec_roku(self):
        r = DphExportRozsah(2025, 11, 2026, 2)
        assert r.iter_mesice() == [
            (2025, 11), (2025, 12), (2026, 1), (2026, 2),
        ]


class TestDphExportService:

    def test_prazdny_rozsah_nevyhodi_chybu(self, factory):
        svc = _service(factory)
        html, zahrnute = svc.render_html(
            DphExportRozsah(2025, 1, 2025, 12),
        )
        assert "nebyly nalezeny" in html
        assert zahrnute == []

    def test_jeden_mesic_jedna_sekce(self, factory):
        _seed_rc_doklad(factory, "FP-2025-001", date(2025, 5, 5), 5000)
        svc = _service(factory)
        html, zahrnute = svc.render_html(
            DphExportRozsah(2025, 5, 2025, 5),
        )
        assert zahrnute == [(2025, 5)]
        assert html.count('class="mesic"') == 1
        assert "Květen 2025" in html

    def test_vynechani_prazdnych_mesicu(self, factory):
        # Doklady v dubnu a září
        _seed_rc_doklad(factory, "FP-2025-001", date(2025, 4, 5), 5000)
        _seed_rc_doklad(factory, "FP-2025-002", date(2025, 9, 5), 5000)
        svc = _service(factory)
        html, zahrnute = svc.render_html(
            DphExportRozsah(2025, 1, 2025, 12),
        )
        assert zahrnute == [(2025, 4), (2025, 9)]
        # Žádné jiné měsíce
        assert "Květen 2025" not in html
        assert "Srpen 2025" not in html
        assert "Duben 2025" in html
        assert "Září 2025" in html

    def test_rozsah_napric_roky(self, factory):
        _seed_rc_doklad(factory, "FP-2025-A", date(2025, 12, 5), 5000)
        _seed_rc_doklad(factory, "FP-2026-A", date(2026, 1, 5), 5000)
        svc = _service(factory)
        html, zahrnute = svc.render_html(
            DphExportRozsah(2025, 11, 2026, 2),
        )
        assert zahrnute == [(2025, 12), (2026, 1)]
        assert "Prosinec 2025" in html
        assert "Leden 2026" in html

    def test_html_obsahuje_epo_radky(self, factory):
        _seed_rc_doklad(factory, "FP-2025-001", date(2025, 5, 5), 10000)
        svc = _service(factory)
        html, _ = svc.render_html(DphExportRozsah(2025, 5, 2025, 5))
        assert "Řádek 9" in html
        assert "Řádek 43" in html
        assert "Řádek 66" in html

    def test_html_obsahuje_rc_tabulku(self, factory):
        _seed_rc_doklad(factory, "FP-2025-001", date(2025, 5, 5), 10000)
        svc = _service(factory)
        html, _ = svc.render_html(DphExportRozsah(2025, 5, 2025, 5))
        assert "FP-2025-001" in html
        assert "CELKEM" in html

    def test_html_je_validni_dokument(self, factory):
        _seed_rc_doklad(factory, "FP-2025-001", date(2025, 5, 5), 10000)
        svc = _service(factory)
        html, _ = svc.render_html(DphExportRozsah(2025, 5, 2025, 5))
        assert html.startswith("<!DOCTYPE html>")
        assert "<html" in html
        assert "</html>" in html

    def test_export_pdf_vytvori_soubor(self, factory, tmp_path):
        _seed_rc_doklad(factory, "FP-2025-001", date(2025, 5, 5), 10000)
        svc = _service(factory)
        out = tmp_path / "test_dph.pdf"
        result_path, zahrnute = svc.export_pdf(
            DphExportRozsah(2025, 5, 2025, 5), out,
        )
        assert result_path == out
        assert out.exists()
        assert out.stat().st_size > 1000  # má nějaký obsah
        assert zahrnute == [(2025, 5)]
