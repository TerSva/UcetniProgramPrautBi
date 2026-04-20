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
from infrastructure.database.repositories.partneri_repository import (
    SqlitePartneriRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.repositories.uctova_osnova_repository import (
    SqliteUctovaOsnovaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.commands.create_doklad import CreateDokladCommand
from services.commands.doklad_actions import DokladActionsCommand
from services.commands.manage_chart_of_accounts import (
    ManageChartOfAccountsCommand,
)
from services.commands.manage_partneri import ManagePartneriCommand
from services.commands.zauctovat_doklad import ZauctovatDokladCommand
from services.queries.chart_of_accounts import ChartOfAccountsQuery
from services.queries.count_all_doklady import CountAllDokladyQuery
from services.queries.dashboard import DashboardDataQuery
from services.queries.doklady_list import DokladyListItem, DokladyListQuery
from services.queries.partneri_list import PartneriListQuery
from services.queries.next_doklad_number import NextDokladNumberQuery
from services.queries.uctova_osnova import UctovaOsnovaQuery
from services.commands.ocr_upload import OcrUploadCommand
from services.commands.priloha_commands import PrilohaCommands
from infrastructure.database.repositories.priloha_repository import (
    SqlitePrilohaRepository,
)
from infrastructure.storage.priloha_storage import PrilohaStorage
from services.commands.pocatecni_stavy import PocatecniStavyCommand
from services.commands.vklad_zk import VkladZKCommand
from services.queries.ocr_inbox import OcrInboxQuery
from services.banka.auto_uctovani import AutoUctovaniBankyCommand
from services.banka.import_vypisu import ImportVypisuCommand
from services.banka.smazat_vypis import SmazatVypisCommand
from services.queries.banka import (
    BankovniTransakceQuery,
    BankovniUctyQuery,
    BankovniVypisyQuery,
)
from services.zauctovani_service import ZauctovaniDokladuService
from ui.main_window import MainWindow
from ui.theme import build_stylesheet
from ui.viewmodels import (
    ChartOfAccountsViewModel,
    DashboardViewModel,
    DokladyListViewModel,
    PartneriViewModel,
)
from ui.viewmodels.bankovni_vypisy_vm import BankovniVypisyViewModel
from ui.viewmodels.doklad_detail_vm import DokladDetailViewModel
from ui.viewmodels.doklad_form_vm import DokladFormViewModel
from ui.viewmodels.import_vypisu_vm import ImportVypisuViewModel
from ui.viewmodels.nastaveni_vm import NastaveniViewModel
from ui.viewmodels.ocr_inbox_vm import OcrInboxViewModel
from ui.viewmodels.pocatecni_stavy_vm import PocatecniStavyViewModel
from ui.viewmodels.zauctovani_vm import ZauctovaniViewModel


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
    """Sestaví DokladyListViewModel s injectovaným DokladyListQuery.

    Fáze 6.7: injectuje i CountAllDokladyQuery pro status bar
    „Zobrazeno X z Y dokladů".
    """
    query = DokladyListQuery(
        uow_factory=lambda: SqliteUnitOfWork(factory),
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
        denik_repo_factory=lambda uow: SqliteUcetniDenikRepository(uow),
        partneri_repo_factory=lambda uow: SqlitePartneriRepository(uow),
    )
    count_query = CountAllDokladyQuery(
        uow_factory=lambda: SqliteUnitOfWork(factory),
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
    )
    return DokladyListViewModel(query, count_query=count_query)


def _build_chart_of_accounts_vm(
    factory: ConnectionFactory,
) -> ChartOfAccountsViewModel:
    """Sestaví ChartOfAccountsViewModel s query + command."""
    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    osnova_repo_factory = lambda uow: SqliteUctovaOsnovaRepository(uow)  # noqa: E731

    query = ChartOfAccountsQuery(
        uow_factory=uow_factory,
        osnova_repo_factory=osnova_repo_factory,
    )
    command = ManageChartOfAccountsCommand(
        uow_factory=uow_factory,
        osnova_repo_factory=osnova_repo_factory,
    )
    return ChartOfAccountsViewModel(query, command)


def _build_partneri_vm(factory: ConnectionFactory) -> PartneriViewModel:
    """Sestaví PartneriViewModel."""
    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    partneri_repo_factory = lambda uow: SqlitePartneriRepository(uow)  # noqa: E731

    query = PartneriListQuery(
        uow_factory=uow_factory,
        partneri_repo_factory=partneri_repo_factory,
    )
    command = ManagePartneriCommand(
        uow_factory=uow_factory,
        partneri_repo_factory=partneri_repo_factory,
    )
    return PartneriViewModel(query, command)


def _build_factories(factory: ConnectionFactory, nastaveni_vm: NastaveniViewModel | None = None):
    """Postaví queries + commands → VM factories pro Doklady page."""
    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    doklady_repo_factory = lambda uow: SqliteDokladyRepository(uow)  # noqa: E731
    denik_repo_factory = lambda uow: SqliteUcetniDenikRepository(uow)  # noqa: E731
    osnova_repo_factory = lambda uow: SqliteUctovaOsnovaRepository(uow)  # noqa: E731

    next_number_query = NextDokladNumberQuery(
        uow_factory=uow_factory,
        doklady_repo_factory=doklady_repo_factory,
    )
    uctova_osnova_query = UctovaOsnovaQuery(
        uow_factory=uow_factory,
        osnova_repo_factory=osnova_repo_factory,
    )

    create_cmd = CreateDokladCommand(
        uow_factory=uow_factory,
        doklady_repo_factory=doklady_repo_factory,
    )
    zauctovani_service = ZauctovaniDokladuService(
        uow_factory=uow_factory,
        doklady_repo_factory=doklady_repo_factory,
        denik_repo_factory=denik_repo_factory,
    )
    actions_cmd = DokladActionsCommand(
        uow_factory=uow_factory,
        doklady_repo_factory=doklady_repo_factory,
        zauctovani_service=zauctovani_service,
    )
    zauctovat_cmd = ZauctovatDokladCommand(
        uow_factory=uow_factory,
        doklady_repo_factory=doklady_repo_factory,
        denik_repo_factory=denik_repo_factory,
    )

    def form_vm_factory() -> DokladFormViewModel:
        ucetni_rok = None
        if nastaveni_vm is not None:
            nastaveni_vm.load()
            if nastaveni_vm.firma is not None:
                ucetni_rok = nastaveni_vm.firma.rok_zacatku_uctovani
        return DokladFormViewModel(
            next_number_query=next_number_query,
            create_command=create_cmd,
            actions_command=actions_cmd,
            ucetni_rok=ucetni_rok,
        )

    def detail_vm_factory(item: DokladyListItem) -> DokladDetailViewModel:
        return DokladDetailViewModel(
            doklad=item,
            actions_command=actions_cmd,
        )

    def zauctovani_vm_factory(item: DokladyListItem) -> ZauctovaniViewModel:
        return ZauctovaniViewModel(
            doklad=item,
            uctova_osnova_query=uctova_osnova_query,
            zauctovat_command=zauctovat_cmd,
        )

    return form_vm_factory, detail_vm_factory, zauctovani_vm_factory


def _build_ocr_inbox_vm(factory: ConnectionFactory) -> OcrInboxViewModel:
    """Sestaví OcrInboxViewModel."""
    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    upload_dir = Path(__file__).resolve().parent.parent / "uploads" / "ocr_inbox"
    upload_cmd = OcrUploadCommand(
        uow_factory=uow_factory,
        upload_dir=upload_dir,
    )
    inbox_query = OcrInboxQuery(uow_factory=uow_factory)
    return OcrInboxViewModel(upload_cmd=upload_cmd, inbox_query=inbox_query)


def _build_nastaveni_vm(factory: ConnectionFactory) -> NastaveniViewModel:
    """Sestaví NastaveniViewModel."""
    return NastaveniViewModel(
        uow_factory=lambda: SqliteUnitOfWork(factory),
    )


def _build_pocatecni_stavy_vm(
    factory: ConnectionFactory,
    nastaveni_vm: NastaveniViewModel,
) -> PocatecniStavyViewModel:
    """Sestaví PocatecniStavyViewModel."""
    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    ps_cmd = PocatecniStavyCommand(uow_factory=uow_factory)
    vklad_cmd = VkladZKCommand(uow_factory=uow_factory)

    def firma_loader():
        nastaveni_vm.load()
        return nastaveni_vm.firma

    return PocatecniStavyViewModel(
        pocatecni_cmd=ps_cmd,
        vklad_zk_cmd=vklad_cmd,
        firma_loader=firma_loader,
    )


def _build_import_vypisu_vm(factory: ConnectionFactory) -> ImportVypisuViewModel:
    """Sestaví ImportVypisuViewModel."""
    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    ucty_query = BankovniUctyQuery(uow_factory=uow_factory)
    upload_dir = Path(__file__).resolve().parent.parent / "uploads" / "banka"
    import_cmd = ImportVypisuCommand(
        uow_factory=uow_factory,
        upload_dir=upload_dir,
    )
    return ImportVypisuViewModel(
        ucty_query=ucty_query,
        import_cmd=import_cmd,
        uow_factory=uow_factory,
    )


def _build_bankovni_vypisy_vm(
    factory: ConnectionFactory,
) -> BankovniVypisyViewModel:
    """Sestaví BankovniVypisyViewModel."""
    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    ucty_query = BankovniUctyQuery(uow_factory=uow_factory)
    vypisy_query = BankovniVypisyQuery(uow_factory=uow_factory)
    transakce_query = BankovniTransakceQuery(uow_factory=uow_factory)
    auto_cmd = AutoUctovaniBankyCommand(uow_factory=uow_factory)
    smazat_cmd = SmazatVypisCommand(uow_factory=uow_factory)
    return BankovniVypisyViewModel(
        ucty_query=ucty_query,
        vypisy_query=vypisy_query,
        transakce_query=transakce_query,
        auto_uctovani_cmd=auto_cmd,
        smazat_cmd=smazat_cmd,
        uow_factory=uow_factory,
    )


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
    chart_of_accounts_vm = _build_chart_of_accounts_vm(factory)
    partneri_vm = _build_partneri_vm(factory)
    nastaveni_vm = _build_nastaveni_vm(factory)
    pocatecni_stavy_vm = _build_pocatecni_stavy_vm(factory, nastaveni_vm)
    ocr_inbox_vm = _build_ocr_inbox_vm(factory)
    form_vm_factory, detail_vm_factory, zauctovani_vm_factory = (
        _build_factories(factory, nastaveni_vm)
    )
    import_vypisu_vm = _build_import_vypisu_vm(factory)
    bankovni_vypisy_vm = _build_bankovni_vypisy_vm(factory)

    # Účetní deník VM
    from ui.viewmodels.ucetni_denik_vm import UcetniDenikViewModel
    _denik_rok = None
    if nastaveni_vm is not None:
        nastaveni_vm.load()
        if nastaveni_vm.firma is not None:
            _denik_rok = nastaveni_vm.firma.rok_zacatku_uctovani
    ucetni_denik_vm = UcetniDenikViewModel(
        uow_factory=lambda: SqliteUnitOfWork(factory),
        ucetni_rok=_denik_rok,
    )

    # Přílohy DI
    uow_factory = lambda: SqliteUnitOfWork(factory)  # noqa: E731
    priloha_storage = PrilohaStorage()
    priloha_cmd = PrilohaCommands(uow_factory=uow_factory, storage=priloha_storage)

    def _priloha_loader(doklad_id: int):
        uow = uow_factory()
        with uow:
            return SqlitePrilohaRepository(uow).list_by_doklad(doklad_id)

    def _priloha_uploader(doklad_id, source_path, original_name):
        return priloha_cmd.priloz_pdf_k_dokladu(doklad_id, source_path, original_name)

    def _priloha_full_path(relativni_cesta):
        return priloha_storage.full_path(relativni_cesta)

    def _uhrazeno_query(doklad_id: int):
        from domain.shared.money import Money
        uow = uow_factory()
        with uow:
            row = uow.connection.execute(
                "SELECT COALESCE(SUM(castka), 0) AS total "
                "FROM ucetni_zaznamy "
                "WHERE doklad_id = ? AND md_ucet LIKE '221%'",
                (doklad_id,),
            ).fetchone()
            return Money(int(row["total"])) if row else Money.zero()

    # PDF parser pro auto-fill ve formuláři nového dokladu
    from infrastructure.ocr.ocr_engine import OcrEngine
    from infrastructure.ocr.invoice_parser import InvoiceParser
    _ocr_engine = OcrEngine()
    _invoice_parser = InvoiceParser()

    def _pdf_parser(path: str):
        from pathlib import Path as _P
        try:
            result = _ocr_engine.extract_text(_P(path))
            if not result.text.strip():
                return None
            return _invoice_parser.parse(result.text)
        except Exception:
            return None

    def _form_priloha_uploader(doklad_id: int, path: str):
        from pathlib import Path as _P
        priloha_cmd.priloz_pdf_k_dokladu(
            doklad_id, _P(path), _P(path).name,
        )

    window = MainWindow(
        dashboard_vm=dashboard_vm,
        doklady_list_vm=doklady_list_vm,
        form_vm_factory=form_vm_factory,
        detail_vm_factory=detail_vm_factory,
        zauctovani_vm_factory=zauctovani_vm_factory,
        chart_of_accounts_vm=chart_of_accounts_vm,
        partneri_vm=partneri_vm,
        nastaveni_vm=nastaveni_vm,
        pocatecni_stavy_vm=pocatecni_stavy_vm,
        ocr_inbox_vm=ocr_inbox_vm,
        import_vypisu_vm=import_vypisu_vm,
        bankovni_vypisy_vm=bankovni_vypisy_vm,
        ucetni_denik_vm=ucetni_denik_vm,
        priloha_loader=_priloha_loader,
        priloha_uploader=_priloha_uploader,
        priloha_full_path=_priloha_full_path,
        uhrazeno_query=_uhrazeno_query,
        pdf_parser=_pdf_parser,
        form_priloha_uploader=_form_priloha_uploader,
    )
    window.show()

    return app.exec()
