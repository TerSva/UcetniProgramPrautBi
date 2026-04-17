"""Screenshoty pro Fázi 10 — Cizoměnové doklady + ID doklad + Společník.

Produkuje 5 PNG:
  1. faze_10_form_eur          — Formulář s EUR měnou (castka_mena + kurz)
  2. faze_10_form_spolecnik    — Formulář s checkboxem "Placeno společníkem"
  3. faze_10_detail_eur        — Detail cizoměnového dokladu
  4. faze_10_doklady_list_mena — Seznam dokladů s EUR formátováním
  5. faze_10_id_doklad         — Interní doklady s ID-2026-001

Run:
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m scripts.screenshots_faze_10
"""

from __future__ import annotations

import os
import sys
import tempfile
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


def _build_db_and_window():
    """Build MainWindow with seeded demo data (including demo doklady)."""
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
    from infrastructure.database.repositories.partneri_repository import (
        SqlitePartneriRepository,
    )
    from infrastructure.database.unit_of_work import SqliteUnitOfWork
    from services.commands.manage_chart_of_accounts import (
        ManageChartOfAccountsCommand,
    )
    from services.commands.manage_partneri import ManagePartneriCommand
    from services.queries.chart_of_accounts import ChartOfAccountsQuery
    from services.queries.dashboard import DashboardDataQuery
    from services.queries.doklady_list import DokladyListQuery
    from services.queries.partneri_list import PartneriListQuery
    from ui.main_window import MainWindow
    from ui.viewmodels import (
        ChartOfAccountsViewModel,
        DashboardViewModel,
        DokladyListViewModel,
        PartneriViewModel,
    )

    from scripts.seed_chart_of_accounts import (
        seed_chart_of_accounts,
        seed_praut_active_accounts,
        seed_praut_analytiky,
        seed_praut_partneri,
        seed_praut_demo_doklady,
    )

    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "screenshot.db"
    factory = ConnectionFactory(db_path)
    migrations_dir = Path("infrastructure/database/migrations/sql")
    MigrationRunner(factory, migrations_dir).migrate()

    # Seed ALL data BEFORE building window
    seed_chart_of_accounts(factory)
    seed_praut_active_accounts(factory)
    seed_praut_analytiky(factory)
    seed_praut_partneri(factory)
    seed_praut_demo_doklady(factory)

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

    window = MainWindow(
        dashboard_vm=DashboardViewModel(dashboard_query),
        doklady_list_vm=DokladyListViewModel(doklady_query),
        chart_of_accounts_vm=ChartOfAccountsViewModel(
            chart_query, chart_command,
        ),
        partneri_vm=PartneriViewModel(partneri_query, partneri_command),
    )
    return window, factory, partneri_query


def main() -> None:
    app = _setup()

    window, factory, partneri_query = _build_db_and_window()

    # ── 1. Form s EUR ──
    from datetime import date
    from decimal import Decimal
    from unittest.mock import MagicMock

    from domain.doklady.typy import Mena, TypDokladu
    from domain.shared.money import Money
    from services.queries.doklady_list import DokladyListItem
    from ui.dialogs.doklad_form_dialog import DokladFormDialog
    from ui.viewmodels.doklad_form_vm import DokladFormViewModel

    next_q = MagicMock()
    next_q.execute.return_value = "FP-2026-002"
    create_cmd = MagicMock()
    create_cmd.execute.return_value = DokladyListItem(
        id=99, cislo="FP-2026-002", typ=TypDokladu.FAKTURA_PRIJATA,
        datum_vystaveni=date(2026, 4, 10), datum_splatnosti=None,
        partner_id=None, partner_nazev=None,
        castka_celkem=Money(25100), stav=MagicMock(),
        k_doreseni=False, poznamka_doreseni=None, popis=None,
    )
    partner_items = partneri_query.execute()
    form_vm = DokladFormViewModel(next_q, create_cmd)
    form = DokladFormDialog(form_vm, partner_items=partner_items)
    form._typ_combo.set_value(TypDokladu.FAKTURA_PRIJATA)
    form._mena_combo.set_value(Mena.EUR)
    form._castka_mena_input.set_value(Money(1000))  # 10,00 EUR
    form._kurz_input.set_value("25,100")
    form._on_foreign_amount_changed()
    _grab(form, "faze_10_form_eur", width=500, height=650)
    print("1/5 Form EUR")

    # ── 2. Form se společníkem ──
    form2 = DokladFormDialog(form_vm, partner_items=partner_items)
    form2._typ_combo.set_value(TypDokladu.FAKTURA_PRIJATA)
    form2._spolecnik_check.setChecked(True)
    _grab(form2, "faze_10_form_spolecnik", width=500, height=650)
    print("2/5 Form Společník")

    # ── 3. Detail EUR dokladu ──
    from ui.dialogs.doklad_detail_dialog import DokladDetailDialog
    from ui.viewmodels.doklad_detail_vm import DokladDetailViewModel
    from domain.doklady.typy import StavDokladu

    detail_item = DokladyListItem(
        id=2, cislo="FP-2026-001", typ=TypDokladu.FAKTURA_PRIJATA,
        datum_vystaveni=date(2026, 4, 1), datum_splatnosti=date(2026, 4, 15),
        partner_id=None, partner_nazev=None,
        castka_celkem=Money(25100), stav=StavDokladu.NOVY,
        k_doreseni=False, poznamka_doreseni=None,
        popis="Hetzner Cloud server - duben 2026",
        mena=Mena.EUR, castka_mena=Money(1000), kurz=Decimal("25.10"),
    )
    detail_vm = DokladDetailViewModel(detail_item, MagicMock())
    detail = DokladDetailDialog(detail_vm)
    _grab(detail, "faze_10_detail_eur", width=500, height=500)
    print("3/5 Detail EUR")

    # ── 4. Seznam dokladů s měnou ──
    # Navigate to FP page
    parent_btn = window.sidebar._parent_buttons.get("doklady")
    if parent_btn:
        parent_btn.click()
    fp_btn = window.sidebar._buttons.get("doklady_fp")
    if fp_btn:
        fp_btn.click()
    _grab(window, "faze_10_doklady_list_mena")
    print("4/5 Seznam FP s měnou")

    # ── 5. ID doklad ──
    id_btn = window.sidebar._buttons.get("doklady_id")
    if id_btn:
        id_btn.click()
    _grab(window, "faze_10_id_doklad")
    print("5/5 ID doklad")

    print(f"\nHotovo! {len(list(OUT.glob('faze_10_*.png')))} screenshotů v {OUT}/")


if __name__ == "__main__":
    main()
