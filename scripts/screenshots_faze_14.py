"""Screenshoty pro Fázi 14 — Počáteční stavy + Vklad ZK + Nastavení.

Produkuje 4 PNG:
  1. faze_14_pocatecni_stavy  — Stránka se zůstatky MD/DAL
  2. faze_14_wizard_vklad_zk  — VkladZK wizard krok 1
  3. faze_14_nastaveni_firma  — Nastavení s vyplněnou firmou
  4. faze_14_id_doklad_701    — Interní doklady s PS dokladem

Run:
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m scripts.screenshots_faze_14
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QFontDatabase  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

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


def _build_seeded_db(tmp_dir: str):
    """Build a temporary DB with seed data including firma."""
    from infrastructure.database.connection import ConnectionFactory
    from infrastructure.database.migrations.runner import MigrationRunner
    from infrastructure.database.unit_of_work import SqliteUnitOfWork
    from scripts.seed_chart_of_accounts import (
        seed_chart_of_accounts,
        seed_praut_active_accounts,
        seed_praut_analytiky,
        seed_praut_firma,
    )

    migrations_dir = (
        Path(__file__).resolve().parent.parent
        / "infrastructure" / "database" / "migrations" / "sql"
    )
    db_path = Path(tmp_dir) / "screenshot.db"
    factory = ConnectionFactory(db_path)
    MigrationRunner(factory, migrations_dir).migrate()

    seed_chart_of_accounts(factory)
    seed_praut_active_accounts(factory)
    seed_praut_analytiky(factory)
    seed_praut_firma(factory)

    return factory


def shot_pocatecni_stavy(factory):
    """Screenshot 1: Počáteční stavy page with some entries."""
    from domain.shared.money import Money
    from infrastructure.database.unit_of_work import SqliteUnitOfWork
    from services.commands.pocatecni_stavy import PocatecniStavyCommand
    from services.commands.vklad_zk import VkladZKCommand
    from ui.pages.pocatecni_stavy_page import PocatecniStavyPage
    from ui.viewmodels.pocatecni_stavy_vm import PocatecniStavyViewModel

    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    ps_cmd = PocatecniStavyCommand(uow_factory=uow_factory)
    vklad_cmd = VkladZKCommand(uow_factory=uow_factory)

    # Seed some počáteční stavy
    ps_cmd.pridat(rok=2025, ucet_kod="221.001", castka=Money(15000000), strana="MD",
                  poznamka="Money Banka")
    ps_cmd.pridat(rok=2025, ucet_kod="211", castka=Money(500000), strana="MD",
                  poznamka="Pokladna")
    ps_cmd.pridat(rok=2025, ucet_kod="411", castka=Money(20000000), strana="DAL",
                  poznamka="Základní kapitál")
    ps_cmd.pridat(rok=2025, ucet_kod="353", castka=Money(4500000), strana="MD",
                  poznamka="Nesplacený ZK")

    vm = PocatecniStavyViewModel(
        pocatecni_cmd=ps_cmd,
        vklad_zk_cmd=vklad_cmd,
        firma_loader=lambda: None,
    )
    page = PocatecniStavyPage(view_model=vm)
    _grab(page, "faze_14_pocatecni_stavy")


def shot_wizard_vklad_zk(factory):
    """Screenshot 2: VkladZK wizard — krok 1."""
    from domain.shared.money import Money
    from infrastructure.database.unit_of_work import SqliteUnitOfWork
    from services.commands.pocatecni_stavy import PocatecniStavyCommand
    from services.commands.vklad_zk import VkladZKCommand
    from ui.dialogs.vklad_zk_dialog import VkladZKDialog
    from ui.viewmodels.pocatecni_stavy_vm import PocatecniStavyViewModel

    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    vm = PocatecniStavyViewModel(
        pocatecni_cmd=PocatecniStavyCommand(uow_factory=uow_factory),
        vklad_zk_cmd=VkladZKCommand(uow_factory=uow_factory),
        firma_loader=lambda: None,
    )
    dlg = VkladZKDialog(view_model=vm)
    dlg._castka_input.set_value(Money(20000000))
    _grab(dlg, "faze_14_wizard_vklad_zk", width=550, height=400)


def shot_nastaveni(factory):
    """Screenshot 3: Nastavení with pre-filled firma."""
    from infrastructure.database.unit_of_work import SqliteUnitOfWork
    from ui.pages.nastaveni_page import NastaveniPage
    from ui.viewmodels.nastaveni_vm import NastaveniViewModel

    vm = NastaveniViewModel(uow_factory=lambda: SqliteUnitOfWork(factory))
    page = NastaveniPage(view_model=vm)
    _grab(page, "faze_14_nastaveni_firma")


def shot_id_doklad_701(factory):
    """Screenshot 4: Interní doklady with 701 doklad."""
    from domain.shared.money import Money
    from infrastructure.database.unit_of_work import SqliteUnitOfWork
    from services.commands.pocatecni_stavy import PocatecniStavyCommand

    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    ps_cmd = PocatecniStavyCommand(uow_factory=uow_factory)

    # Make sure stavy exist (may already be seeded from shot_pocatecni_stavy)
    stavy = ps_cmd.list_by_rok(2025)
    if not stavy:
        ps_cmd.pridat(rok=2025, ucet_kod="221", castka=Money(100000), strana="MD")
        ps_cmd.pridat(rok=2025, ucet_kod="411", castka=Money(100000), strana="DAL")

    ps_cmd.generovat_id_doklad(2025)

    # Build MainWindow to show ID doklady page
    from infrastructure.database.repositories.doklady_repository import (
        SqliteDokladyRepository,
    )
    from infrastructure.database.repositories.ucetni_denik_repository import (
        SqliteUcetniDenikRepository,
    )
    from infrastructure.database.repositories.uctova_osnova_repository import (
        SqliteUctovaOsnovaRepository,
    )
    from services.queries.dashboard import DashboardDataQuery
    from services.queries.doklady_list import DokladyListQuery
    from ui.main_window import MainWindow
    from ui.viewmodels import DashboardViewModel, DokladyListViewModel

    dash_query = DashboardDataQuery(
        uow_factory=uow_factory,
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
        denik_repo_factory=lambda uow: SqliteUcetniDenikRepository(uow),
        osnova_repo_factory=lambda uow: SqliteUctovaOsnovaRepository(uow),
    )
    list_query = DokladyListQuery(
        uow_factory=uow_factory,
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
        denik_repo_factory=lambda uow: SqliteUcetniDenikRepository(uow),
    )

    dash_vm = DashboardViewModel(dash_query)
    list_vm = DokladyListViewModel(list_query)

    window = MainWindow(
        dashboard_vm=dash_vm,
        doklady_list_vm=list_vm,
    )
    # Navigate to ID doklady
    window.sidebar.page_selected.emit("doklady_id")
    _grab(window, "faze_14_id_doklad_701")


def main() -> int:
    import tempfile
    app = _setup()
    tmp = tempfile.mkdtemp()
    factory = _build_seeded_db(tmp)

    print("Screenshoty Fáze 14:")
    shot_pocatecni_stavy(factory)
    shot_wizard_vklad_zk(factory)
    shot_nastaveni(factory)
    shot_id_doklad_701(factory)

    print(f"\nVšechny screenshoty v: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
