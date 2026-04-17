"""Sidebar — levý navigační panel se sekcemi, sub-menu a routing.

Fáze 8: kompletní navigační struktura se 5 sekcemi a rozklikávacím
sub-menu pro Doklady (FV/FP/PD/BV/ID/OD).

Aktivní stav se řídí QSS přes property `active="true"`. Po změně property
voláme `style().unpolish()/polish()` pro vynucený refresh.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import Colors, Spacing
from ui.widgets.icon import load_icon


@dataclass(frozen=True)
class SidebarItem:
    """Definice jedné položky v sidebaru."""

    key: str
    label: str
    icon: str
    section: str
    sub_items: tuple["SidebarItem", ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SidebarSection:
    """Sekce sidebaru."""

    title: str
    items: tuple[SidebarItem, ...]


#: Kompletní struktura sidebaru (Fáze 8).
SIDEBAR_STRUCTURE: tuple[SidebarSection, ...] = (
    SidebarSection(
        title="Přehled",
        items=(
            SidebarItem("dashboard", "Dashboard", "layout-dashboard", "Přehled"),
        ),
    ),
    SidebarSection(
        title="Účetnictví",
        items=(
            SidebarItem("nahrat_doklady", "Nahrát doklady", "inbox", "Účetnictví"),
            SidebarItem(
                "doklady", "Doklady", "file-text", "Účetnictví",
                sub_items=(
                    SidebarItem("doklady_fv", "Vydané faktury (FV)", "file-text", "Účetnictví"),
                    SidebarItem("doklady_fp", "Přijaté faktury (FP)", "file-input", "Účetnictví"),
                    SidebarItem("doklady_pd", "Pokladní doklady (PD)", "wallet", "Účetnictví"),
                    SidebarItem("doklady_bv", "Bankovní výpisy (BV)", "credit-card", "Účetnictví"),
                    SidebarItem("doklady_id", "Interní doklady (ID)", "file-edit", "Účetnictví"),
                    SidebarItem("doklady_od", "Opravné doklady (OD)", "refresh-ccw", "Účetnictví"),
                ),
            ),
            SidebarItem("banka", "Banka", "landmark", "Účetnictví"),
            SidebarItem("ucetni_denik", "Účetní deník", "book-open", "Účetnictví"),
        ),
    ),
    SidebarSection(
        title="Evidence",
        items=(
            SidebarItem("partneri", "Partneři", "users", "Evidence"),
            SidebarItem("osnova", "Účtová osnova", "book-open", "Evidence"),
            SidebarItem("pocatecni_stavy", "Počáteční stavy", "clipboard", "Evidence"),
            SidebarItem("mzdy", "Mzdy", "banknote", "Evidence"),
        ),
    ),
    SidebarSection(
        title="Výstupy",
        items=(
            SidebarItem("vykazy", "Výkazy", "chart-bar", "Výstupy"),
            SidebarItem("dph", "DPH", "percent", "Výstupy"),
            SidebarItem("saldokonto", "Saldokonto", "scale", "Výstupy"),
        ),
    ),
    SidebarSection(
        title="Systém",
        items=(
            SidebarItem("nastaveni", "Nastavení", "settings", "Systém"),
        ),
    ),
)


def _all_nav_keys() -> tuple[str, ...]:
    """Všechny navigovatelné klíče (bez parent-only keys jako 'doklady')."""
    keys: list[str] = []
    for section in SIDEBAR_STRUCTURE:
        for item in section.items:
            if item.sub_items:
                for sub in item.sub_items:
                    keys.append(sub.key)
            else:
                keys.append(item.key)
    return tuple(keys)


#: Klíče stránek, které mají implementovanou stránku (všechny v Fázi 8).
ACTIVE_KEYS: tuple[str, ...] = _all_nav_keys()


class Sidebar(QWidget):
    """Levý navigační panel — fixní šířka 260 px, tmavě teal pozadí."""

    #: Signál vyvolán při kliknutí na navigovatelnou položku.
    page_selected = pyqtSignal(str)

    WIDTH: int = 260

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(self.WIDTH)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._buttons: dict[str, QPushButton] = {}
        self._sub_containers: dict[str, QWidget] = {}
        self._parent_buttons: dict[str, QPushButton] = {}
        self._build_ui()

    # ────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────

    def set_active(self, page_key: str) -> None:
        """Nastav vizuálně aktivní položku. Nevyvolá page_selected signál."""
        for key, button in self._buttons.items():
            is_active = key == page_key
            button.setProperty("active", "true" if is_active else "false")
            button.style().unpolish(button)
            button.style().polish(button)

        # Highlight parent pokud je aktivní sub-item
        for parent_key, parent_btn in self._parent_buttons.items():
            container = self._sub_containers.get(parent_key)
            if container is None:
                continue
            # Check if active key is one of the sub-items
            has_active_child = any(
                page_key == key
                for key in self._buttons
                if key.startswith(f"{parent_key}_")
            )
            parent_btn.setProperty(
                "active", "true" if has_active_child else "false",
            )
            parent_btn.style().unpolish(parent_btn)
            parent_btn.style().polish(parent_btn)
            # Auto-expand parent when navigating to sub-item
            if has_active_child:
                container.setVisible(True)
                self._update_chevron(parent_btn, expanded=True)

    # ────────────────────────────────────────────────
    # Build
    # ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Logo (above scroll area)
        logo = QLabel("Účetní program", self)
        logo.setObjectName("SidebarLogo")
        outer.addWidget(logo)

        # Scrollable content
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        scroll.setProperty("class", "sidebar-scroll")
        scroll.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        scroll_content = QWidget()
        scroll_content.setProperty("class", "sidebar-scroll-content")
        scroll_content.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, True,
        )
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(0, 0, 0, Spacing.S4)
        layout.setSpacing(0)

        for section in SIDEBAR_STRUCTURE:
            section_label = QLabel(section.title.upper(), self)
            section_label.setProperty("class", "sidebar-section")
            layout.addWidget(section_label)

            for item in section.items:
                if item.sub_items:
                    self._build_parent_item(layout, item)
                else:
                    button = self._build_item(item)
                    layout.addWidget(button)
                    self._buttons[item.key] = button

        layout.addStretch(1)
        scroll.setWidget(scroll_content)
        outer.addWidget(scroll, stretch=1)

    def _build_item(
        self, item: SidebarItem, is_sub: bool = False,
    ) -> QPushButton:
        prefix = "    " if is_sub else "  "
        button = QPushButton(f"{prefix}{item.label}", self)
        button.setProperty("class", "sidebar-sub-item" if is_sub else "sidebar-item")
        button.setProperty("active", "false")
        button.setCursor(Qt.CursorShape.PointingHandCursor)

        try:
            icon = load_icon(item.icon, color=Colors.WHITE, size=16 if is_sub else 18)
            button.setIcon(icon)
            button.setIconSize(QSize(16 if is_sub else 18, 16 if is_sub else 18))
        except FileNotFoundError:
            pass

        button.clicked.connect(
            lambda _checked, k=item.key: self._on_clicked(k)
        )
        return button

    def _build_parent_item(
        self, layout: QVBoxLayout, item: SidebarItem,
    ) -> None:
        """Postav parent položku s expand/collapse sub-menu."""
        button = QPushButton(f"  {item.label}", self)
        button.setProperty("class", "sidebar-item")
        button.setProperty("active", "false")
        button.setCursor(Qt.CursorShape.PointingHandCursor)

        try:
            icon = load_icon(item.icon, color=Colors.WHITE, size=18)
            button.setIcon(icon)
            button.setIconSize(QSize(18, 18))
        except FileNotFoundError:
            pass

        # Sub-items container (initially collapsed)
        container = QWidget(self)
        container.setProperty("class", "sidebar-sub-container")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sub_layout = QVBoxLayout(container)
        sub_layout.setContentsMargins(Spacing.S4, 0, 0, 0)
        sub_layout.setSpacing(0)
        container.setVisible(False)

        for sub in item.sub_items:
            sub_btn = self._build_item(sub, is_sub=True)
            sub_layout.addWidget(sub_btn)
            self._buttons[sub.key] = sub_btn

        # Toggle sub-menu on click
        button.clicked.connect(
            lambda _checked, k=item.key: self._toggle_sub_menu(k)
        )

        self._parent_buttons[item.key] = button
        self._sub_containers[item.key] = container
        self._update_chevron(button, expanded=False)

        layout.addWidget(button)
        layout.addWidget(container)

    def _toggle_sub_menu(self, parent_key: str) -> None:
        container = self._sub_containers.get(parent_key)
        if container is None:
            return
        expanded = not container.isVisible()
        container.setVisible(expanded)
        parent_btn = self._parent_buttons.get(parent_key)
        if parent_btn:
            self._update_chevron(parent_btn, expanded)

    def _update_chevron(self, button: QPushButton, expanded: bool) -> None:
        """Vizuální indikátor expand/collapse stavu."""
        text = button.text().rstrip(" ▾▸")
        button.setText(f"{text} {'▾' if expanded else '▸'}")

    def _on_clicked(self, page_key: str) -> None:
        self.set_active(page_key)
        self.page_selected.emit(page_key)
