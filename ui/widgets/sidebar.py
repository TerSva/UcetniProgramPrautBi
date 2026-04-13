"""Sidebar — levý navigační panel s logem, sekcemi a 10 položkami.

Aktivní stránky (Fáze 6 Krok 1): dashboard, doklady, nastaveni.
Ostatní položky jsou disabled s tooltipem "Přijde v další fázi".

Aktivní stav se řídí QSS přes property `active="true"`. Po změně property
voláme `style().unpolish()/polish()` pro vynucený refresh.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ui.design_tokens import Colors, Spacing
from ui.widgets.icon import load_icon


#: Klíče stránek, které jsou v této fázi aktivní (mají implementovanou stránku).
ACTIVE_KEYS: tuple[str, ...] = ("dashboard", "doklady", "nastaveni")


@dataclass(frozen=True)
class SidebarItem:
    """Definice jedné položky v sidebaru."""

    key: str
    label: str
    icon: str
    section: str


#: 5 sekcí × 11 položek celkem (3 aktivní + 8 disabled).
_ITEMS: tuple[SidebarItem, ...] = (
    # Přehled
    SidebarItem("dashboard", "Dashboard", "layout-dashboard", "Přehled"),
    # Účetnictví
    SidebarItem("doklady", "Doklady", "file-text", "Účetnictví"),
    SidebarItem("banka", "Banka", "landmark", "Účetnictví"),
    SidebarItem("pokladna", "Pokladna", "wallet", "Účetnictví"),
    SidebarItem("denik", "Účetní deník", "book-open", "Účetnictví"),
    # Evidence
    SidebarItem("partneri", "Partneři", "users", "Evidence"),
    SidebarItem("majetek", "Majetek", "package", "Evidence"),
    SidebarItem("mzdy", "Mzdy", "banknote", "Evidence"),
    # Výstupy
    SidebarItem("vykazy", "Výkazy", "chart-bar", "Výstupy"),
    SidebarItem("dph", "DPH", "percent", "Výstupy"),
    # Systém
    SidebarItem("nastaveni", "Nastavení", "settings", "Systém"),
)


class Sidebar(QWidget):
    """Levý navigační panel — fixní šířka 260 px, tmavě teal pozadí."""

    #: Signál vyvolán při kliknutí na aktivní (enabled) položku.
    page_selected = pyqtSignal(str)

    WIDTH: int = 260

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(self.WIDTH)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._buttons: dict[str, QPushButton] = {}
        self._build_ui()

    # ────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────

    def set_active(self, page_key: str) -> None:
        """Nastav vizuálně aktivní položku. Nevyvolá page_selected signál.

        Používá se při inicializaci i při programmatickém přepnutí stránky.
        """
        for key, button in self._buttons.items():
            is_active = key == page_key
            button.setProperty("active", "true" if is_active else "false")
            # Vynucený refresh QSS property-based selectoru
            button.style().unpolish(button)
            button.style().polish(button)

    # ────────────────────────────────────────────────
    # Build
    # ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, Spacing.S4)
        layout.setSpacing(0)

        # Logo
        logo = QLabel("Účetní program", self)
        logo.setObjectName("SidebarLogo")
        layout.addWidget(logo)

        # Položky seskupené podle sekcí (zachovává pořadí v _ITEMS)
        current_section: str | None = None
        for item in _ITEMS:
            if item.section != current_section:
                current_section = item.section
                section_label = QLabel(item.section.upper(), self)
                section_label.setProperty("class", "sidebar-section")
                layout.addWidget(section_label)

            button = self._build_item(item)
            layout.addWidget(button)
            self._buttons[item.key] = button

        layout.addStretch(1)

    def _build_item(self, item: SidebarItem) -> QPushButton:
        button = QPushButton(f"  {item.label}", self)
        button.setProperty("class", "sidebar-item")
        button.setProperty("active", "false")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(load_icon(item.icon, color=Colors.WHITE, size=18))
        button.setIconSize(QSize(18, 18))

        if item.key in ACTIVE_KEYS:
            button.clicked.connect(lambda _checked, k=item.key: self._on_clicked(k))
        else:
            button.setEnabled(False)
            button.setToolTip("Přijde v další fázi")

        return button

    def _on_clicked(self, page_key: str) -> None:
        self.set_active(page_key)
        self.page_selected.emit(page_key)
