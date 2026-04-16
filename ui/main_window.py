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
    ChartOfAccountsPage,
    DashboardPage,
    DokladyPage,
    PartneriPage,
    PlaceholderPage,
)
from ui.viewmodels import (
    ChartOfAccountsViewModel,
    DashboardViewModel,
    DokladyListViewModel,
    PartneriViewModel,
)
from ui.viewmodels.doklad_detail_vm import DokladDetailViewModel
from ui.viewmodels.doklad_form_vm import DokladFormViewModel
from ui.viewmodels.zauctovani_vm import ZauctovaniViewModel
from ui.widgets import Sidebar


#: Definice typových stránek Doklady (key, TypDokladu, titulek).
_DOKLADY_TYP_PAGES: tuple[tuple[str, TypDokladu, str], ...] = (
    ("doklady_fv", TypDokladu.FAKTURA_VYDANA, "Vydané faktury"),
    ("doklady_fp", TypDokladu.FAKTURA_PRIJATA, "Přijaté faktury"),
    ("doklady_pd", TypDokladu.POKLADNI_DOKLAD, "Pokladní doklady"),
    ("doklady_bv", TypDokladu.BANKOVNI_VYPIS, "Bankovní výpisy"),
    ("doklady_id", TypDokladu.INTERNI_DOKLAD, "Interní doklady"),
    ("doklady_od", TypDokladu.OPRAVNY_DOKLAD, "Opravné doklady"),
)

#: Definice placeholder stránek (key, title, subtitle, phase, phase_name).
_PLACEHOLDER_PAGES: tuple[tuple[str, str, str, int | None, str], ...] = (
    (
        "nahrat_doklady", "Nahrát doklady",
        "Hromadné zpracování dokladů přes OCR.",
        12, "OCR + Inbox",
    ),
    (
        "banka", "Banka",
        "CSV import bankovních výpisů a párování plateb.",
        13, "Banka + CSV Import + Párování",
    ),
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
    (
        "dph", "DPH",
        "Reverse charge výpočet a výkaz DPH.",
        11, "DPH + Reverse charge",
    ),
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
    (
        "nastaveni", "Nastavení",
        "Firemní údaje, účetní období, DPH a uživatelská nastavení.",
        None, "Obecná nastavení aplikace",
    ),
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
        self._dashboard_page = DashboardPage(self._dashboard_vm, self._stack)
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

        # 5. Placeholder pages
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
