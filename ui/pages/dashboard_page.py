"""Dashboard — stránka s reálnými KPI kartami napojenými na backend.

Layout:
    Title + subtitle                                       Datum (vpravo)
    ┌──────────────┬──────────────┐
    │ Doklady      │ Hrubý zisk   │  ← actionable + pozitivní nahoru
    ├──────────────┼──────────────┤
    │ Pohledávky   │ Závazky      │  ← referenční hodnoty dole
    └──────────────┴──────────────┘

Stránka jen zobrazuje data z `DashboardViewModel` — žádné dotazy do DB,
žádné import z `infrastructure/` ani `services/queries`.
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import Spacing
from ui.viewmodels import DashboardViewModel
from ui.widgets import KpiCard


_CZECH_DAYS = [
    "Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle",
]
_CZECH_MONTHS = [
    "", "ledna", "února", "března", "dubna", "května", "června",
    "července", "srpna", "září", "října", "listopadu", "prosince",
]


def _format_date_cz(d: date) -> str:
    """Český formát: 'Pondělí, 13. dubna 2026'."""
    return f"{_CZECH_DAYS[d.weekday()]}, {d.day}. {_CZECH_MONTHS[d.month]} {d.year}"


class DashboardPage(QWidget):
    """Dashboard s 4 KPI kartami v 2×2 mřížce."""

    def __init__(
        self,
        view_model: DashboardViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model

        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._build_ui()
        self.refresh()

    # ────────────────────────────────────────────────
    # Build
    # ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8
        )
        root.setSpacing(Spacing.S5)

        self._title = QLabel("Dashboard", self)
        self._title.setProperty("class", "page-title")

        self._subtitle = QLabel(
            "Přehled klíčových ukazatelů firmy.", self
        )
        self._subtitle.setProperty("class", "page-subtitle")

        # Header: title+subtitle vlevo, datum vpravo nahoře
        self._date_label = QLabel(_format_date_cz(date.today()), self)
        self._date_label.setProperty("class", "page-date")
        self._date_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(Spacing.S1)
        title_box.addWidget(self._title)
        title_box.addWidget(self._subtitle)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(Spacing.S5)
        header.addLayout(title_box)
        header.addStretch(1)
        header.addWidget(
            self._date_label, alignment=Qt.AlignmentFlag.AlignTop,
        )

        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "error-text")
        self._error_label.setVisible(False)
        self._error_label.setWordWrap(True)

        # 2×2 grid karet — actionable nahoře, referenční dole
        self._card_doklady = KpiCard("Doklady letos", "—", parent=self)
        self._card_zisk = KpiCard(
            "Hrubý zisk", "—", subtitle=None, parent=self,
        )
        self._card_pohledavky = KpiCard(
            "Pohledávky", "—", subtitle=None, parent=self,
        )
        self._card_zavazky = KpiCard(
            "Závazky", "—", subtitle=None, parent=self,
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(Spacing.S5)
        grid.setVerticalSpacing(Spacing.S5)
        grid.addWidget(self._card_doklady, 0, 0)
        grid.addWidget(self._card_zisk, 0, 1)
        grid.addWidget(self._card_pohledavky, 1, 0)
        grid.addWidget(self._card_zavazky, 1, 1)

        root.addLayout(header)
        root.addWidget(self._error_label)
        root.addLayout(grid)
        root.addStretch(1)

    # ────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload dat ze ViewModelu a překresli karty."""
        self._vm.load()

        if self._vm.error is not None:
            self._show_error(self._vm.error)
            return

        data = self._vm.data
        if data is None:
            # Bezpečnostní fallback — nemělo by nastat (load() vždy nastaví
            # data nebo error), ale UI musí být tolerantní.
            self._show_error("Neznámá chyba načítání dat.")
            return

        self._error_label.setVisible(False)

        # Doklady
        self._card_doklady.set_value(str(data.doklady_celkem))
        sub_doklady_parts = [
            f"{data.doklady_k_zauctovani} k zaúčtování",
        ]
        if data.ma_doklady_k_doreseni:
            sub_doklady_parts.append(
                f"{data.doklady_k_doreseni} k dořešení"
            )
        self._card_doklady.set_subtitle(" · ".join(sub_doklady_parts))

        # Pohledávky / Závazky
        self._card_pohledavky.set_value(data.pohledavky.format_cz())
        self._card_pohledavky.set_subtitle("účet 311 — neuhrazené")

        self._card_zavazky.set_value(data.zavazky.format_cz())
        self._card_zavazky.set_subtitle("účet 321 — k úhradě")

        # Hrubý zisk
        self._card_zisk.set_value(data.hruby_zisk.format_cz())
        sub_zisk = (
            f"{data.rok}: výnosy {data.vynosy.format_cz()} · "
            f"náklady {data.naklady.format_cz()} · "
            f"odhad daně {data.odhad_dane.format_cz()}"
        )
        self._card_zisk.set_subtitle(sub_zisk)
        self._card_zisk.set_positive(
            data.hruby_zisk.is_positive and not data.je_ve_ztrate
        )

    # ────────────────────────────────────────────────
    # Test-friendly accessors
    # ────────────────────────────────────────────────

    @property
    def card_doklady(self) -> KpiCard:
        return self._card_doklady

    @property
    def card_pohledavky(self) -> KpiCard:
        return self._card_pohledavky

    @property
    def card_zavazky(self) -> KpiCard:
        return self._card_zavazky

    @property
    def card_zisk(self) -> KpiCard:
        return self._card_zisk

    @property
    def error_label(self) -> QLabel:
        return self._error_label

    @property
    def date_label(self) -> QLabel:
        return self._date_label

    # ────────────────────────────────────────────────
    # Internals
    # ────────────────────────────────────────────────

    def _show_error(self, message: str) -> None:
        self._error_label.setText(f"Chyba načítání dashboardu: {message}")
        self._error_label.setVisible(True)
        for card in (
            self._card_doklady,
            self._card_pohledavky,
            self._card_zavazky,
            self._card_zisk,
        ):
            card.set_value("—")
            card.set_subtitle(None)
