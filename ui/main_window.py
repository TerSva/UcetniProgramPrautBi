"""MainWindow — hlavní okno aplikace.

Struktura:
    ┌───────────────────────────────────┐
    │ Sidebar │ QStackedWidget (pages)  │
    │ (260px) │                         │
    └───────────────────────────────────┘

Přepínání stránek: Sidebar emituje `page_selected` → MainWindow přepne stack.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from ui.pages import DashboardPage, DokladyPage, NastaveniPage
from ui.widgets import Sidebar


#: Mapování klíče stránky na index v QStackedWidget. Pořadí musí odpovídat
#: pořadí, ve kterém se stránky přidávají do stacku v `_build_ui`.
_PAGE_INDEX: dict[str, int] = {
    "dashboard": 0,
    "doklady": 1,
    "nastaveni": 2,
}


class MainWindow(QMainWindow):
    """Hlavní okno s levým sidebarem a přepínatelným stackem stránek."""

    DEFAULT_WIDTH: int = 1280
    DEFAULT_HEIGHT: int = 800

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Účetní program")
        self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

        self._sidebar: Sidebar
        self._stack: QStackedWidget
        self._build_ui()

        # Výchozí stránka = dashboard
        self._sidebar.set_active("dashboard")
        self._stack.setCurrentIndex(_PAGE_INDEX["dashboard"])

    # ────────────────────────────────────────────────
    # Public API (používané testy)
    # ────────────────────────────────────────────────

    @property
    def sidebar(self) -> Sidebar:
        return self._sidebar

    @property
    def stack(self) -> QStackedWidget:
        return self._stack

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
        self._stack.addWidget(DashboardPage(self._stack))  # index 0
        self._stack.addWidget(DokladyPage(self._stack))  # index 1
        self._stack.addWidget(NastaveniPage(self._stack))  # index 2

        layout.addWidget(self._sidebar)
        layout.addWidget(self._stack, stretch=1)

        self._sidebar.page_selected.connect(self._on_page_selected)

        self.setCentralWidget(central)

    def _on_page_selected(self, page_key: str) -> None:
        index = _PAGE_INDEX.get(page_key)
        if index is None:
            return
        self._stack.setCurrentIndex(index)
