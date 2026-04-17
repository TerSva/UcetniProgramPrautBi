"""Screenshoty pro Fázi 13 — Banka modul.

Produkuje 8 PNG:
  1. faze_13_sidebar_banka_expanded  — Sidebar s rozbalenou sekcí Banka
  2. faze_13_import_step1           — Import výpisu: výběr účtu a souborů
  3. faze_13_import_validation      — Import výpisu: výsledek validace
  4. faze_13_import_success         — Import výpisu: úspěšný import
  5. faze_13_vypisy_list            — Seznam bankovních výpisů
  6. faze_13_transakce_detail       — Detail transakcí výpisu
  7. faze_13_auto_zauctovani        — Po auto-zaúčtování (barevné stavy)
  8. faze_13_vypisy_filter          — Filtr podle účtu a stavu

Run:
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m scripts.screenshots_faze_13
"""

from __future__ import annotations

import os
import sys
from datetime import date
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
    print(f"  \u2713 {path}")


def _build_seeded_db(tmp_dir: str):
    """Build a temporary DB with seed data."""
    from infrastructure.database.connection import ConnectionFactory
    from infrastructure.database.migrations.runner import MigrationRunner

    migrations_dir = (
        Path(__file__).resolve().parent.parent
        / "infrastructure" / "database" / "migrations" / "sql"
    )
    db_path = Path(tmp_dir) / "screenshot.db"
    factory = ConnectionFactory(db_path)
    MigrationRunner(factory, migrations_dir).migrate()

    # Seed extended chart of accounts if available
    try:
        from scripts.seed_chart_of_accounts import (
            seed_chart_of_accounts,
            seed_praut_active_accounts,
            seed_praut_analytiky,
        )
        seed_chart_of_accounts(factory)
        seed_praut_active_accounts(factory)
        seed_praut_analytiky(factory)
    except Exception:
        pass

    return factory


def _seed_bank_data(factory):
    """Seed bank výpis with transactions for screenshots."""
    from domain.banka.bankovni_transakce import BankovniTransakce, StavTransakce
    from domain.banka.bankovni_vypis import BankovniVypis
    from domain.doklady.doklad import Doklad
    from domain.doklady.typy import TypDokladu
    from domain.shared.money import Money
    from infrastructure.database.repositories.banka_repository import (
        SqliteBankovniTransakceRepository,
        SqliteBankovniUcetRepository,
        SqliteBankovniVypisRepository,
    )
    from infrastructure.database.repositories.doklady_repository import (
        SqliteDokladyRepository,
    )
    from infrastructure.database.unit_of_work import SqliteUnitOfWork

    uow = SqliteUnitOfWork(factory)
    with uow:
        ucet_repo = SqliteBankovniUcetRepository(uow)
        ucty = ucet_repo.list_aktivni()
        ucet = ucty[0]  # Money Banka from seed

        doklady_repo = SqliteDokladyRepository(uow)
        bv_doklad = doklady_repo.add(Doklad(
            cislo="BV-2025-03",
            typ=TypDokladu.BANKOVNI_VYPIS,
            datum_vystaveni=date(2025, 3, 1),
            castka_celkem=Money(4800000),
            popis=f"Bankovn\u00ed v\u00fdpis {ucet.nazev} 03/2025",
        ))

        vypis_repo = SqliteBankovniVypisRepository(uow)
        vypis_id = vypis_repo.add(BankovniVypis(
            bankovni_ucet_id=ucet.id,
            rok=2025,
            mesic=3,
            pocatecni_stav=Money(15000000),
            konecny_stav=Money(14652350),
            pdf_path="/uploads/banka/221.001_2025_03.pdf",
            bv_doklad_id=bv_doklad.id,
        ))

        tx_repo = SqliteBankovniTransakceRepository(uow)
        txs_data = [
            (date(2025, 3, 1), Money(-15000), "V", "Poplatek za veden\u00ed \u00fa\u010dtu", None, StavTransakce.NESPAROVANO),
            (date(2025, 3, 3), Money(2500050), "P", "P\u0159ijat\u00e1 platba FV-2025-008", "2025008", StavTransakce.NESPAROVANO),
            (date(2025, 3, 5), Money(-1850000), "V", "\u00dahrada FP-2025-012", "2025012", StavTransakce.NESPAROVANO),
            (date(2025, 3, 10), Money(500), "P", "\u00darok p\u0159ipsan\u00fd", None, StavTransakce.NESPAROVANO),
            (date(2025, 3, 10), Money(-75), "V", "Da\u0148 z \u00farok\u016f", None, StavTransakce.NESPAROVANO),
            (date(2025, 3, 15), Money(-350000), "V", "P\u0159evod na spo\u0159ic\u00ed \u00fa\u010det", None, StavTransakce.NESPAROVANO),
            (date(2025, 3, 20), Money(1500000), "P", "P\u0159ijat\u00e1 platba FV-2025-009", "2025009", StavTransakce.NESPAROVANO),
            (date(2025, 3, 25), Money(-132125), "V", "N\u00e1kup kancel\u00e1\u0159sk\u00fdch pot\u0159eb", "555111", StavTransakce.NESPAROVANO),
        ]
        for i, (dt, castka, smer, popis, vs, stav) in enumerate(txs_data):
            tx_repo.add(BankovniTransakce(
                bankovni_vypis_id=vypis_id,
                datum_transakce=dt,
                datum_zauctovani=dt,
                castka=castka,
                smer=smer,
                popis=popis,
                variabilni_symbol=vs,
                row_hash=f"hash_screenshot_{i}",
                stav=stav,
            ))

        uow.commit()

    return ucet, vypis_id


def _build_main_window(factory):
    """Build MainWindow with bank VMs for screenshots."""
    from infrastructure.database.repositories.doklady_repository import SqliteDokladyRepository
    from infrastructure.database.repositories.ucetni_denik_repository import SqliteUcetniDenikRepository
    from infrastructure.database.repositories.uctova_osnova_repository import SqliteUctovaOsnovaRepository
    from infrastructure.database.unit_of_work import SqliteUnitOfWork
    from services.banka.auto_uctovani import AutoUctovaniBankyCommand
    from services.banka.import_vypisu import ImportVypisuCommand
    from services.queries.banka import BankovniTransakceQuery, BankovniUctyQuery, BankovniVypisyQuery
    from services.queries.dashboard import DashboardDataQuery
    from services.queries.doklady_list import DokladyListQuery
    from ui.main_window import MainWindow
    from ui.viewmodels import DashboardViewModel, DokladyListViewModel
    from ui.viewmodels.bankovni_vypisy_vm import BankovniVypisyViewModel
    from ui.viewmodels.import_vypisu_vm import ImportVypisuViewModel

    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
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
    import_vm = ImportVypisuViewModel(
        ucty_query=BankovniUctyQuery(uow_factory=uow_factory),
        import_cmd=ImportVypisuCommand(
            uow_factory=uow_factory,
            upload_dir=Path("/tmp/banka_uploads"),
        ),
    )
    vypisy_vm = BankovniVypisyViewModel(
        ucty_query=BankovniUctyQuery(uow_factory=uow_factory),
        vypisy_query=BankovniVypisyQuery(uow_factory=uow_factory),
        transakce_query=BankovniTransakceQuery(uow_factory=uow_factory),
        auto_uctovani_cmd=AutoUctovaniBankyCommand(uow_factory=uow_factory),
    )
    return MainWindow(
        dashboard_vm=DashboardViewModel(dash_query),
        doklady_list_vm=DokladyListViewModel(list_query),
        import_vypisu_vm=import_vm,
        bankovni_vypisy_vm=vypisy_vm,
    )


def shot_sidebar_expanded(factory):
    """Screenshot 1: Sidebar s rozbalenou Banka sekc\u00ed."""
    window = _build_main_window(factory)
    # Expand banka sub-menu
    if "banka" in window.sidebar._parent_buttons:
        window.sidebar._parent_buttons["banka"].click()
    window.sidebar.set_active("banka_import")
    window.sidebar.page_selected.emit("banka_import")
    _grab(window, "faze_13_sidebar_banka_expanded")


def shot_import_step1(factory):
    """Screenshot 2: Import v\u00fdpisu \u2014 krok 1 (v\u00fdb\u011br \u00fa\u010dtu)."""
    from infrastructure.database.unit_of_work import SqliteUnitOfWork
    from services.banka.import_vypisu import ImportVypisuCommand
    from services.queries.banka import BankovniUctyQuery
    from ui.pages.banka_import_page import BankaImportPage
    from ui.viewmodels.import_vypisu_vm import ImportVypisuViewModel

    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    vm = ImportVypisuViewModel(
        ucty_query=BankovniUctyQuery(uow_factory=uow_factory),
        import_cmd=ImportVypisuCommand(
            uow_factory=uow_factory,
            upload_dir=Path("/tmp/banka_uploads"),
        ),
    )
    page = BankaImportPage(view_model=vm)
    _grab(page, "faze_13_import_step1")


def shot_import_validation(factory):
    """Screenshot 3: Import v\u00fdpisu \u2014 v\u00fdsledek validace (fake data)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QTableWidgetItem

    from infrastructure.database.unit_of_work import SqliteUnitOfWork
    from services.banka.import_vypisu import ImportVypisuCommand
    from services.queries.banka import BankovniUctyQuery
    from ui.pages.banka_import_page import BankaImportPage
    from ui.viewmodels.import_vypisu_vm import ImportVypisuViewModel

    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    vm = ImportVypisuViewModel(
        ucty_query=BankovniUctyQuery(uow_factory=uow_factory),
        import_cmd=ImportVypisuCommand(
            uow_factory=uow_factory,
            upload_dir=Path("/tmp/banka_uploads"),
        ),
    )
    page = BankaImportPage(view_model=vm)

    # Simulate validation result display
    page._csv_label.setText("CSV soubor: money_banka_2025_03.csv")
    page._pdf_label.setText("PDF soubor: vypis_2025_03.pdf")
    page._status_label.setText(
        "PS: 150\u00a0000,00\u00a0K\u010d | KS: 146\u00a0523,50\u00a0K\u010d | "
        "Shoda: 7 | Pouze CSV: 1 | Pouze PDF: 0"
    )

    # Populate validation table
    table = page._report_table
    rows = [
        ("01.03.2025", "-150,00 K\u010d", "", "Shoda"),
        ("03.03.2025", "25\u00a0000,50 K\u010d", "2025008", "Shoda"),
        ("05.03.2025", "-18\u00a0500,00 K\u010d", "2025012", "Shoda"),
        ("10.03.2025", "5,00 K\u010d", "", "Shoda"),
        ("10.03.2025", "-0,75 K\u010d", "", "Shoda"),
        ("15.03.2025", "-3\u00a0500,00 K\u010d", "", "Shoda"),
        ("20.03.2025", "15\u00a0000,00 K\u010d", "2025009", "Shoda"),
        ("25.03.2025", "-1\u00a0321,25 K\u010d", "555111", "Pouze v CSV"),
    ]
    table.setRowCount(len(rows))
    for i, (dt, castka, vs, stav) in enumerate(rows):
        table.setItem(i, 0, QTableWidgetItem(dt))
        table.setItem(i, 1, QTableWidgetItem(castka))
        table.setItem(i, 2, QTableWidgetItem(vs))
        item = QTableWidgetItem(stav)
        if stav == "Shoda":
            item.setForeground(Qt.GlobalColor.darkGreen)
        elif "CSV" in stav:
            item.setForeground(Qt.GlobalColor.darkYellow)
        table.setItem(i, 3, item)

    page._import_btn.setEnabled(True)
    _grab(page, "faze_13_import_validation")


def shot_import_success(factory):
    """Screenshot 4: Import v\u00fdpisu \u2014 \u00fasp\u011b\u0161n\u00fd v\u00fdsledek."""
    from infrastructure.database.unit_of_work import SqliteUnitOfWork
    from services.banka.import_vypisu import ImportVypisuCommand
    from services.queries.banka import BankovniUctyQuery
    from ui.pages.banka_import_page import BankaImportPage
    from ui.viewmodels.import_vypisu_vm import ImportVypisuViewModel

    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    vm = ImportVypisuViewModel(
        ucty_query=BankovniUctyQuery(uow_factory=uow_factory),
        import_cmd=ImportVypisuCommand(
            uow_factory=uow_factory,
            upload_dir=Path("/tmp/banka_uploads"),
        ),
    )
    page = BankaImportPage(view_model=vm)
    page._status_label.setText(
        "\u2705 Import dokon\u010den: 8 transakc\u00ed importov\u00e1no. "
        "Doklad: BV-2025-03"
    )
    page._import_btn.setEnabled(False)
    _grab(page, "faze_13_import_success")


def shot_vypisy_list(factory, vypis_id):
    """Screenshot 5: Seznam bankovn\u00edch v\u00fdpis\u016f."""
    from infrastructure.database.unit_of_work import SqliteUnitOfWork
    from services.banka.auto_uctovani import AutoUctovaniBankyCommand
    from services.queries.banka import (
        BankovniTransakceQuery,
        BankovniUctyQuery,
        BankovniVypisyQuery,
    )
    from ui.pages.banka_vypisy_page import BankaVypisyPage
    from ui.viewmodels.bankovni_vypisy_vm import BankovniVypisyViewModel

    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    vm = BankovniVypisyViewModel(
        ucty_query=BankovniUctyQuery(uow_factory=uow_factory),
        vypisy_query=BankovniVypisyQuery(uow_factory=uow_factory),
        transakce_query=BankovniTransakceQuery(uow_factory=uow_factory),
        auto_uctovani_cmd=AutoUctovaniBankyCommand(uow_factory=uow_factory),
    )
    page = BankaVypisyPage(view_model=vm)
    _grab(page, "faze_13_vypisy_list")


def shot_transakce_detail(factory, vypis_id):
    """Screenshot 6: Detail transakc\u00ed v\u00fdpisu."""
    from infrastructure.database.unit_of_work import SqliteUnitOfWork
    from services.banka.auto_uctovani import AutoUctovaniBankyCommand
    from services.queries.banka import (
        BankovniTransakceQuery,
        BankovniUctyQuery,
        BankovniVypisyQuery,
    )
    from ui.pages.banka_vypisy_page import BankaVypisyPage
    from ui.viewmodels.bankovni_vypisy_vm import BankovniVypisyViewModel

    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    vm = BankovniVypisyViewModel(
        ucty_query=BankovniUctyQuery(uow_factory=uow_factory),
        vypisy_query=BankovniVypisyQuery(uow_factory=uow_factory),
        transakce_query=BankovniTransakceQuery(uow_factory=uow_factory),
        auto_uctovani_cmd=AutoUctovaniBankyCommand(uow_factory=uow_factory),
    )
    page = BankaVypisyPage(view_model=vm)
    # Select first vypis
    if vm.vypisy:
        page._vypisy_table.setCurrentCell(0, 0)
    _grab(page, "faze_13_transakce_detail")


def shot_auto_zauctovani(factory, vypis_id):
    """Screenshot 7: Po auto-za\u00fa\u010dtov\u00e1n\u00ed (barevn\u00e9 stavy)."""
    from infrastructure.database.unit_of_work import SqliteUnitOfWork
    from services.banka.auto_uctovani import AutoUctovaniBankyCommand
    from services.queries.banka import (
        BankovniTransakceQuery,
        BankovniUctyQuery,
        BankovniVypisyQuery,
    )
    from ui.pages.banka_vypisy_page import BankaVypisyPage
    from ui.viewmodels.bankovni_vypisy_vm import BankovniVypisyViewModel

    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    # Run auto-zauctovani first
    auto_cmd = AutoUctovaniBankyCommand(uow_factory=uow_factory)
    auto_cmd.execute(vypis_id)

    vm = BankovniVypisyViewModel(
        ucty_query=BankovniUctyQuery(uow_factory=uow_factory),
        vypisy_query=BankovniVypisyQuery(uow_factory=uow_factory),
        transakce_query=BankovniTransakceQuery(uow_factory=uow_factory),
        auto_uctovani_cmd=auto_cmd,
    )
    page = BankaVypisyPage(view_model=vm)
    if vm.vypisy:
        page._vypisy_table.setCurrentCell(0, 0)
    _grab(page, "faze_13_auto_zauctovani")


def shot_filter(factory, vypis_id):
    """Screenshot 8: Filtr podle stavu."""
    from domain.banka.bankovni_transakce import StavTransakce
    from infrastructure.database.unit_of_work import SqliteUnitOfWork
    from services.banka.auto_uctovani import AutoUctovaniBankyCommand
    from services.queries.banka import (
        BankovniTransakceQuery,
        BankovniUctyQuery,
        BankovniVypisyQuery,
    )
    from ui.pages.banka_vypisy_page import BankaVypisyPage
    from ui.viewmodels.bankovni_vypisy_vm import BankovniVypisyViewModel

    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    vm = BankovniVypisyViewModel(
        ucty_query=BankovniUctyQuery(uow_factory=uow_factory),
        vypisy_query=BankovniVypisyQuery(uow_factory=uow_factory),
        transakce_query=BankovniTransakceQuery(uow_factory=uow_factory),
        auto_uctovani_cmd=AutoUctovaniBankyCommand(uow_factory=uow_factory),
    )
    page = BankaVypisyPage(view_model=vm)
    # Set filter to "Nesparovano"
    page._stav_combo.set_value(StavTransakce.NESPAROVANO)
    if vm.vypisy:
        page._vypisy_table.setCurrentCell(0, 0)
    _grab(page, "faze_13_vypisy_filter")


def main() -> int:
    import tempfile
    app = _setup()
    tmp = tempfile.mkdtemp()
    factory = _build_seeded_db(tmp)
    ucet, vypis_id = _seed_bank_data(factory)

    print("Screenshoty F\u00e1ze 13:")
    shot_sidebar_expanded(factory)
    shot_import_step1(factory)
    shot_import_validation(factory)
    shot_import_success(factory)
    shot_vypisy_list(factory, vypis_id)
    shot_transakce_detail(factory, vypis_id)
    shot_auto_zauctovani(factory, vypis_id)
    shot_filter(factory, vypis_id)

    print(f"\nV\u0161echny screenshoty v: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
