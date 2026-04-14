"""Application bootstrap — registrace fontů, aplikace QSS, spuštění.

Jediné místo, kde se volá QApplication.setStyleSheet(). Ostatní widgety
NIKDY nevolají setStyleSheet() — barvy a typografie jdou přes QSS class
properties.

DI bootstrap: poskládá ConnectionFactory → UoW factory → repo factories →
DashboardDataQuery → DashboardViewModel → MainWindow.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication

from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.repositories.uctova_osnova_repository import (
    SqliteUctovaOsnovaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.dashboard import DashboardDataQuery
from services.queries.doklady_list import DokladyListQuery
from ui.main_window import MainWindow
from ui.theme import build_stylesheet
from ui.viewmodels import DashboardViewModel, DokladyListViewModel


_FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

#: Výchozí umístění uživatelské DB — vedle kódu, gitignored.
DEFAULT_DB_PATH: Path = (
    Path(__file__).resolve().parent.parent / "ucetni.db"
)

#: Adresář s SQL migracemi.
MIGRATIONS_DIR: Path = (
    Path(__file__).resolve().parent.parent
    / "infrastructure"
    / "database"
    / "migrations"
    / "sql"
)


def register_fonts() -> list[str]:
    """Načti všechny TTF soubory z ui/assets/fonts/.

    Returns:
        Seznam registrovaných font families (unikátní, seřazený).
    """
    families: set[str] = set()
    for font_path in sorted(_FONTS_DIR.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id == -1:
            continue
        families.update(QFontDatabase.applicationFontFamilies(font_id))
    return sorted(families)


def _setup_database(db_path: Path) -> ConnectionFactory:
    """Vyrobí ConnectionFactory a aplikuje všechny migrace."""
    factory = ConnectionFactory(db_path)
    runner = MigrationRunner(factory, MIGRATIONS_DIR)
    runner.migrate()
    return factory


def _build_dashboard_vm(factory: ConnectionFactory) -> DashboardViewModel:
    """Sestaví DashboardViewModel s injectovaným DashboardDataQuery."""
    query = DashboardDataQuery(
        uow_factory=lambda: SqliteUnitOfWork(factory),
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
        denik_repo_factory=lambda uow: SqliteUcetniDenikRepository(uow),
        osnova_repo_factory=lambda uow: SqliteUctovaOsnovaRepository(uow),
    )
    return DashboardViewModel(query)


def _build_doklady_list_vm(
    factory: ConnectionFactory,
) -> DokladyListViewModel:
    """Sestaví DokladyListViewModel s injectovaným DokladyListQuery."""
    query = DokladyListQuery(
        uow_factory=lambda: SqliteUnitOfWork(factory),
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
    )
    return DokladyListViewModel(query)


def run(db_path: Path | None = None) -> int:
    """Spusť aplikaci. Vrací exit code z QApplication.exec().

    Args:
        db_path: cesta k SQLite DB. None → DEFAULT_DB_PATH.
    """
    app = QApplication(sys.argv)

    register_fonts()
    app.setStyleSheet(build_stylesheet())

    factory = _setup_database(db_path or DEFAULT_DB_PATH)
    dashboard_vm = _build_dashboard_vm(factory)
    doklady_list_vm = _build_doklady_list_vm(factory)

    window = MainWindow(
        dashboard_vm=dashboard_vm,
        doklady_list_vm=doklady_list_vm,
    )
    window.show()

    return app.exec()
