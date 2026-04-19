"""MainWindow — hlavní okno aplikace.

Struktura:
    ┌───────────────────────────────────┐
    │ Sidebar │ QStackedWidget (pages)  │
    │ (260px) │                         │
    └───────────────────────────────────┘

Fáze 8: kompletní routing — 16 stránek (dashboard, 6 typových dokladů,
účtová osnova, 7 placeholderů, nastavení).
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from domain.doklady.typy import TypDokladu
from services.queries.doklady_list import DokladyListItem
from ui.pages import (
    BankaImportPage,
    BankaVypisyPage,
    ChartOfAccountsPage,
    DashboardPage,
    DokladyPage,
    DphPage,
    NahratDokladyPage,
    NastaveniPage,
    PartneriPage,
    PlaceholderPage,
    PocatecniStavyPage,
)
from ui.viewmodels import (
    ChartOfAccountsViewModel,
    DashboardViewModel,
    DokladyListViewModel,
    PartneriViewModel,
)
from ui.viewmodels.dph_vm import DphViewModel
from ui.viewmodels.doklad_detail_vm import DokladDetailViewModel
from ui.viewmodels.doklad_form_vm import DokladFormViewModel
from ui.viewmodels.nastaveni_vm import NastaveniViewModel
from ui.viewmodels.bankovni_vypisy_vm import BankovniVypisyViewModel
from ui.viewmodels.import_vypisu_vm import ImportVypisuViewModel
from ui.viewmodels.ocr_inbox_vm import OcrInboxViewModel
from ui.viewmodels.pocatecni_stavy_vm import PocatecniStavyViewModel
from ui.viewmodels.zauctovani_vm import ZauctovaniViewModel
from ui.widgets import Sidebar


#: Definice typových stránek Doklady (key, TypDokladu, titulek).
_DOKLADY_TYP_PAGES: tuple[tuple[str, TypDokladu, str], ...] = (
    ("doklady_fv", TypDokladu.FAKTURA_VYDANA, "Vydané faktury"),
    ("doklady_fp", TypDokladu.FAKTURA_PRIJATA, "Přijaté faktury"),
    ("doklady_pd", TypDokladu.POKLADNI_DOKLAD, "Pokladní doklady"),
    ("doklady_id", TypDokladu.INTERNI_DOKLAD, "Interní doklady"),
    ("doklady_od", TypDokladu.OPRAVNY_DOKLAD, "Opravné doklady"),
)

#: Definice placeholder stránek (key, title, subtitle, phase, phase_name).
_PLACEHOLDER_PAGES: tuple[tuple[str, str, str, int | None, str], ...] = (
    # banka — replaced by BankaImportPage + BankaVypisyPage in Fáze 13
    (
        "ucetni_denik", "Účetní deník",
        "Seznam všech účetních zápisů.",
        13, "Účetní deník",
    ),
    (
        "vykazy", "Výkazy",
        "Rozvaha, výkaz zisku a ztráty — PDF export.",
        15, "Výkazy + PDF export",
    ),
    # DPH page — replaced by real DphPage in Fáze 11
    (
        "saldokonto", "Saldokonto",
        "Pohledávky a závazky podle partnerů.",
        15, "Saldokonto",
    ),
    (
        "mzdy", "Mzdy",
        "Mzdy zaměstnanců, DPP, DPČ a odvody.",
        16, "Mzdy a DPP",
    ),
    # Nastavení — replaced by real NastaveniPage in Fáze 14
)


class MainWindow(QMainWindow):
    """Hlavní okno s levým sidebarem a přepínatelným stackem stránek."""

    DEFAULT_WIDTH: int = 1280
    DEFAULT_HEIGHT: int = 800

    def __init__(
        self,
        dashboard_vm: DashboardViewModel,
        doklady_list_vm: DokladyListViewModel,
        form_vm_factory: Callable[[], DokladFormViewModel] | None = None,
        detail_vm_factory: Callable[
            [DokladyListItem], DokladDetailViewModel
        ] | None = None,
        zauctovani_vm_factory: Callable[
            [DokladyListItem], ZauctovaniViewModel
        ] | None = None,
        chart_of_accounts_vm: ChartOfAccountsViewModel | None = None,
        partneri_vm: PartneriViewModel | None = None,
        dph_vm: DphViewModel | None = None,
        nastaveni_vm: NastaveniViewModel | None = None,
        pocatecni_stavy_vm: PocatecniStavyViewModel | None = None,
        ocr_inbox_vm: OcrInboxViewModel | None = None,
        import_vypisu_vm: ImportVypisuViewModel | None = None,
        bankovni_vypisy_vm: BankovniVypisyViewModel | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Účetní program")
        self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

        self._dashboard_vm = dashboard_vm
        self._doklady_list_vm = doklady_list_vm
        self._form_vm_factory = form_vm_factory
        self._detail_vm_factory = detail_vm_factory
        self._zauctovani_vm_factory = zauctovani_vm_factory
        self._chart_of_accounts_vm = chart_of_accounts_vm
        self._partneri_vm = partneri_vm
        self._dph_vm = dph_vm
        self._nastaveni_vm = nastaveni_vm
        self._pocatecni_stavy_vm = pocatecni_stavy_vm
        self._ocr_inbox_vm = ocr_inbox_vm
        self._import_vypisu_vm = import_vypisu_vm
        self._bankovni_vypisy_vm = bankovni_vypisy_vm

        self._sidebar: Sidebar
        self._stack: QStackedWidget
        self._dashboard_page: DashboardPage
        self._page_index: dict[str, int] = {}
        # Keep reference to "all doklady" page for dashboard drill-down
        self._all_doklady_page: DokladyPage

        self._build_ui()

        # Výchozí stránka = dashboard
        self._sidebar.set_active("dashboard")
        self._stack.setCurrentIndex(self._page_index["dashboard"])

    # ────────────────────────────────────────────────
    # Public API (používané testy)
    # ────────────────────────────────────────────────

    @property
    def sidebar(self) -> Sidebar:
        return self._sidebar

    @property
    def stack(self) -> QStackedWidget:
        return self._stack

    @property
    def page_index(self) -> dict[str, int]:
        return dict(self._page_index)

    # ────────────────────────────────────────────────
    # Build
    # ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._sidebar = Sidebar(central)
        self._stack = QStackedWidget(central)

        # 1. Dashboard
        ocr_count_fn = None
        if self._ocr_inbox_vm is not None:
            def _ocr_count():
                self._ocr_inbox_vm.load()
                return self._ocr_inbox_vm.pocet_nezpracovanych
            ocr_count_fn = _ocr_count
        self._dashboard_page = DashboardPage(
            self._dashboard_vm,
            ocr_count_fn=ocr_count_fn,
            parent=self._stack,
        )
        self._add_page("dashboard", self._dashboard_page)

        # 2. Six typed Doklady pages
        for key, typ, title in _DOKLADY_TYP_PAGES:
            page = DokladyPage(
                self._doklady_list_vm,
                form_vm_factory=self._form_vm_factory,
                detail_vm_factory=self._detail_vm_factory,
                zauctovani_vm_factory=self._zauctovani_vm_factory,
                preset_typ=typ,
                preset_title=title,
                parent=self._stack,
            )
            self._add_page(key, page)

        # 3. Účtová osnova
        if self._chart_of_accounts_vm is not None:
            osnova_page: QWidget = ChartOfAccountsPage(
                self._chart_of_accounts_vm, parent=self._stack,
            )
        else:
            osnova_page = QWidget(self._stack)
        self._add_page("osnova", osnova_page)

        # 4. Partneři (Fáze 9)
        if self._partneri_vm is not None:
            partneri_page: QWidget = PartneriPage(
                self._partneri_vm, parent=self._stack,
            )
        else:
            partneri_page = QWidget(self._stack)
        self._add_page("partneri", partneri_page)

        # 5. DPH page (Fáze 11)
        if self._dph_vm is not None:
            dph_page: QWidget = DphPage(self._dph_vm, parent=self._stack)
        else:
            dph_page = PlaceholderPage(
                title="DPH",
                subtitle="Reverse charge výpočet a výkaz DPH.",
                phase_number=11,
                phase_name="DPH + Reverse charge",
                parent=self._stack,
            )
        self._add_page("dph", dph_page)

        # 6. Počáteční stavy page (Fáze 14)
        if self._pocatecni_stavy_vm is not None:
            ps_page: QWidget = PocatecniStavyPage(
                self._pocatecni_stavy_vm, parent=self._stack,
            )
        else:
            ps_page = PlaceholderPage(
                title="Počáteční stavy",
                subtitle="Počáteční zůstatky účtů.",
                phase_number=14,
                phase_name="Počáteční stavy",
                parent=self._stack,
            )
        self._add_page("pocatecni_stavy", ps_page)

        # 7. Nastavení page (Fáze 14)
        if self._nastaveni_vm is not None:
            nastaveni_page: QWidget = NastaveniPage(
                self._nastaveni_vm, parent=self._stack,
            )
        else:
            nastaveni_page = PlaceholderPage(
                title="Nastavení",
                subtitle="Firemní údaje, účetní období, DPH.",
                phase_number=None,
                phase_name="Nastavení",
                parent=self._stack,
            )
        self._add_page("nastaveni", nastaveni_page)

        # 8. Nahrát doklady page (Fáze 12)
        if self._ocr_inbox_vm is not None:
            nahrat_page: QWidget = NahratDokladyPage(
                self._ocr_inbox_vm, parent=self._stack,
            )
        else:
            nahrat_page = PlaceholderPage(
                title="Nahrát doklady",
                subtitle="Hromadné zpracování dokladů přes OCR.",
                phase_number=12,
                phase_name="OCR + Inbox",
                parent=self._stack,
            )
        self._add_page("nahrat_doklady", nahrat_page)

        # 9. Banka pages (Fáze 13)
        if self._import_vypisu_vm is not None:
            banka_import_page: QWidget = BankaImportPage(
                self._import_vypisu_vm, parent=self._stack,
            )
        else:
            banka_import_page = PlaceholderPage(
                title="Import výpisu",
                subtitle="CSV import bankovních výpisů.",
                phase_number=13,
                phase_name="Banka + CSV Import",
                parent=self._stack,
            )
        self._add_page("banka_import", banka_import_page)

        if self._bankovni_vypisy_vm is not None:
            banka_vypisy_page: QWidget = BankaVypisyPage(
                self._bankovni_vypisy_vm, parent=self._stack,
            )
        else:
            banka_vypisy_page = PlaceholderPage(
                title="Bankovní výpisy",
                subtitle="Přehled výpisů a párování transakcí.",
                phase_number=13,
                phase_name="Banka + Párování",
                parent=self._stack,
            )
        self._add_page("banka_vypisy", banka_vypisy_page)

        # 10. Placeholder pages
        for key, title, subtitle, phase, phase_name in _PLACEHOLDER_PAGES:
            page = PlaceholderPage(
                title=title,
                subtitle=subtitle,
                phase_number=phase,
                phase_name=phase_name,
                parent=self._stack,
            )
            self._add_page(key, page)

        # 5. Hidden "all doklady" page for dashboard drill-down
        self._all_doklady_page = DokladyPage(
            self._doklady_list_vm,
            form_vm_factory=self._form_vm_factory,
            detail_vm_factory=self._detail_vm_factory,
            zauctovani_vm_factory=self._zauctovani_vm_factory,
            parent=self._stack,
        )
        self._add_page("_doklady_all", self._all_doklady_page)

        layout.addWidget(self._sidebar)
        layout.addWidget(self._stack, stretch=1)

        self._sidebar.page_selected.connect(self._on_page_selected)
        self._dashboard_page.navigate_to_doklady_k_doreseni.connect(
            self._on_navigate_k_doreseni
        )
        self._dashboard_page.navigate_to_doklady_with_typ.connect(
            self._on_navigate_with_typ
        )
        self._dashboard_page.navigate_to_nahrat_doklady.connect(
            self._on_navigate_nahrat_doklady
        )

        self.setCentralWidget(central)

    def _add_page(self, key: str, widget: QWidget) -> None:
        idx = self._stack.addWidget(widget)
        self._page_index[key] = idx

    def _on_page_selected(self, page_key: str) -> None:
        index = self._page_index.get(page_key)
        if index is None:
            return
        self._stack.setCurrentIndex(index)

    def _on_navigate_k_doreseni(self) -> None:
        """Dashboard drill → přepni na all-Doklady + aplikuj filter POUZE."""
        self._sidebar.set_active("doklady_fv")  # visual hint
        self._stack.setCurrentIndex(self._page_index["_doklady_all"])
        self._all_doklady_page.apply_k_doreseni_filter()

    def _on_navigate_with_typ(self, typ: object) -> None:
        """Dashboard drill Pohledávky/Závazky → typová stránka."""
        if not isinstance(typ, TypDokladu):
            return
        # Map TypDokladu to page key
        key_map = {t: k for k, t, _ in _DOKLADY_TYP_PAGES}
        page_key = key_map.get(typ)
        if page_key is None:
            return
        self._sidebar.set_active(page_key)
        self._stack.setCurrentIndex(self._page_index[page_key])

    def _on_navigate_nahrat_doklady(self) -> None:
        """Dashboard OCR notifikace → přepni na Nahrát doklady."""
        page_key = "nahrat_doklady"
        if page_key in self._page_index:
            self._sidebar.set_active(page_key)
            self._stack.setCurrentIndex(self._page_index[page_key])
