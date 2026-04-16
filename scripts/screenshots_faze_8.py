"""Screenshoty pro Fázi 8 — Sidebar + Struktura.

Produkuje 5 PNG:
  1. faze_8_sidebar_expanded     — Sidebar s rozbalenými Doklady sub-items
  2. faze_8_sidebar_collapsed    — Sidebar se zabalenými Doklady
  3. faze_8_page_fv              — Typová stránka "Vydané faktury"
  4. faze_8_placeholder_partneri — Placeholder stránka Partneři
  5. faze_8_placeholder_banka    — Placeholder stránka Banka

Run:
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m scripts.screenshots_faze_8
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QFontDatabase  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.pages.placeholder_page import PlaceholderPage  # noqa: E402
from ui.theme import build_stylesheet  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "screenshots"
FONTS = Path(__file__).resolve().parent.parent / "ui" / "assets" / "fonts"


def _setup() -> QApplication:
    app = QApplication.instance() or QApplication(sys.argv)
    for fp in sorted(FONTS.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyleSheet(build_stylesheet())
    return app


def _grab(widget, name: str, width=1100, height=700) -> None:
    widget.resize(width, height)
    widget.show()
    widget.repaint()
    pixmap = widget.grab()
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{name}.png"
    pixmap.save(str(path))
    print(f"  ✓ {path}")


def _build_main_window():
    """Build a MainWindow with mock VMs (similar to conftest)."""
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
    from services.commands.manage_chart_of_accounts import (
        ManageChartOfAccountsCommand,
    )
    from services.queries.chart_of_accounts import ChartOfAccountsQuery
    from services.queries.dashboard import DashboardDataQuery
    from services.queries.doklady_list import DokladyListQuery
    from ui.main_window import MainWindow
    from ui.viewmodels import (
        ChartOfAccountsViewModel,
        DashboardViewModel,
        DokladyListViewModel,
        PartneriViewModel,
    )

    import tempfile
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "screenshot.db"
    factory = ConnectionFactory(db_path)
    migrations_dir = Path("infrastructure/database/migrations/sql")
    MigrationRunner(factory, migrations_dir).migrate()

    # Seed chart of accounts so the page has data
    from scripts.seed_chart_of_accounts import (
        seed_chart_of_accounts,
        seed_praut_active_accounts,
        seed_praut_analytiky,
        seed_praut_partneri,
    )
    seed_chart_of_accounts(factory)
    seed_praut_active_accounts(factory)
    seed_praut_analytiky(factory)
    seed_praut_partneri(factory)

    from infrastructure.database.repositories.partneri_repository import (
        SqlitePartneriRepository,
    )
    from services.commands.manage_partneri import ManagePartneriCommand
    from services.queries.partneri_list import PartneriListQuery

    uow_factory = lambda: SqliteUnitOfWork(factory)
    doklady_repo_factory = lambda uow: SqliteDokladyRepository(uow)
    osnova_repo_factory = lambda uow: SqliteUctovaOsnovaRepository(uow)
    partneri_repo_factory = lambda uow: SqlitePartneriRepository(uow)

    dashboard_query = DashboardDataQuery(
        uow_factory=uow_factory,
        doklady_repo_factory=doklady_repo_factory,
        denik_repo_factory=lambda uow: SqliteUcetniDenikRepository(uow),
        osnova_repo_factory=osnova_repo_factory,
    )
    doklady_query = DokladyListQuery(
        uow_factory=uow_factory,
        doklady_repo_factory=doklady_repo_factory,
        partneri_repo_factory=partneri_repo_factory,
    )
    chart_query = ChartOfAccountsQuery(
        uow_factory=uow_factory,
        osnova_repo_factory=osnova_repo_factory,
    )
    chart_command = ManageChartOfAccountsCommand(
        uow_factory=uow_factory,
        osnova_repo_factory=osnova_repo_factory,
    )

    partneri_query = PartneriListQuery(
        uow_factory=uow_factory,
        partneri_repo_factory=partneri_repo_factory,
    )
    partneri_command = ManagePartneriCommand(
        uow_factory=uow_factory,
        partneri_repo_factory=partneri_repo_factory,
    )

    return MainWindow(
        dashboard_vm=DashboardViewModel(dashboard_query),
        doklady_list_vm=DokladyListViewModel(doklady_query),
        chart_of_accounts_vm=ChartOfAccountsViewModel(
            chart_query, chart_command,
        ),
        partneri_vm=PartneriViewModel(partneri_query, partneri_command),
    )


def main() -> None:
    app = _setup()

    window = _build_main_window()

    # 1. Sidebar expanded — click doklady parent to expand
    parent_btn = window.sidebar._parent_buttons.get("doklady")
    if parent_btn:
        parent_btn.click()
    _grab(window, "faze_8_sidebar_expanded")
    print("1/5 Sidebar expanded")

    # 2. Sidebar collapsed — click again to collapse
    if parent_btn:
        parent_btn.click()
    _grab(window, "faze_8_sidebar_collapsed")
    print("2/5 Sidebar collapsed")

    # 3. Typová stránka FV — navigate to doklady_fv
    if parent_btn:
        parent_btn.click()  # expand again
    fv_btn = window.sidebar._buttons.get("doklady_fv")
    if fv_btn:
        fv_btn.click()
    _grab(window, "faze_8_page_fv")
    print("3/5 Page FV")

    # 4. Placeholder Partneři
    partneri_btn = window.sidebar._buttons.get("partneri")
    if partneri_btn:
        partneri_btn.click()
    _grab(window, "faze_8_placeholder_partneri")
    print("4/5 Placeholder Partneři")

    # 5. Placeholder Banka
    banka_btn = window.sidebar._buttons.get("banka")
    if banka_btn:
        banka_btn.click()
    _grab(window, "faze_8_placeholder_banka")
    print("5/5 Placeholder Banka")

    print(f"\nHotovo! {len(list(OUT.glob('faze_8_*.png')))} screenshotů v {OUT}/")


if __name__ == "__main__":
    main()
