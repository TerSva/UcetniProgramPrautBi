"""Test fixtures pro UI vrstvu.

`main_window` fixture vytváří MainWindow s načtenými fonty a aplikovaným QSS,
jak by ho viděl uživatel. qtbot zajistí automatický cleanup.
"""

from __future__ import annotations

from pathlib import Path

import pytest
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
from ui.app import register_fonts
from ui.main_window import MainWindow
from ui.theme import build_stylesheet
from ui.viewmodels import DashboardViewModel


MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent
    / "infrastructure"
    / "database"
    / "migrations"
    / "sql"
)


@pytest.fixture
def db_factory(tmp_path) -> ConnectionFactory:
    """Connection factory s tempfile DB + aplikovanými migracemi."""
    db_path = tmp_path / "test.db"
    factory = ConnectionFactory(db_path)
    runner = MigrationRunner(factory, MIGRATIONS_SQL_DIR)
    runner.migrate()
    return factory


@pytest.fixture
def dashboard_vm(db_factory) -> DashboardViewModel:
    """Plně zapojený DashboardViewModel s reálnou (prázdnou) DB."""
    query = DashboardDataQuery(
        uow_factory=lambda: SqliteUnitOfWork(db_factory),
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
        denik_repo_factory=lambda uow: SqliteUcetniDenikRepository(uow),
        osnova_repo_factory=lambda uow: SqliteUctovaOsnovaRepository(uow),
    )
    return DashboardViewModel(query)


@pytest.fixture
def main_window(qtbot, dashboard_vm):
    """Vytvoř MainWindow s kompletním theme setup.

    Vrací hotové okno po `show()`, po testu ho qtbot automaticky uklidí.
    """
    app = QApplication.instance()
    assert app is not None, "qtbot měl vytvořit QApplication"

    register_fonts()
    app.setStyleSheet(build_stylesheet())

    window = MainWindow(dashboard_vm=dashboard_vm)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    return window
