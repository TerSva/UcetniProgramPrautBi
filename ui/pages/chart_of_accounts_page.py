"""Účtová osnova — strom syntetických a analytických účtů.

Layout:
    Účtová osnova                                       [☑ Zobrazit neaktivní]
    Spravuj účty podle vyhlášky 500/2002 Sb.
    [error-text]
    ┌───────────────────────────────────────────────────────┐
    │ ▾ Třída 0 — Dlouhodobý majetek (5/30 aktivních)       │
    │   ☑ 012 — Nehmotné výsledky výzkumu a vývoje          │
    │   ☑ 013 — Software                                    │
    │     └─ 013.100 — Vývojový software  [✎]               │
    │     [+ Přidat analytiku]                               │
    │ ▸ Třída 1 — Zásoby (0/15 aktivních)                    │
    │ ...                                                    │
    └───────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import Spacing
from ui.dialogs.analytika_dialog import AnalytikaDialog
from ui.dialogs.ucet_edit_dialog import UcetEditDialog
from ui.viewmodels.chart_of_accounts_vm import ChartOfAccountsViewModel


class ChartOfAccountsPage(QWidget):
    """Stránka Účtová osnova — strom účtů s aktivací a analytikami."""

    def __init__(
        self,
        view_model: ChartOfAccountsViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model

        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._error_label: QLabel
        self._show_inactive_check: QCheckBox
        self._tree_container: QWidget
        self._tree_layout: QVBoxLayout
        self._expanded_tridy: set[int] = set()

        self._build_ui()
        self._wire_signals()
        self.refresh()

    # ─── Public API ───────────────────────────────────

    def refresh(self) -> None:
        self._vm.load()
        self._sync_ui()

    # ─── Test accessors ───────────────────────────────

    @property
    def _error_label_widget(self) -> QLabel:
        return self._error_label

    @property
    def _show_inactive_widget(self) -> QCheckBox:
        return self._show_inactive_check

    @property
    def _tree_container_widget(self) -> QWidget:
        return self._tree_container

    # ─── Build ────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8,
        )
        root.setSpacing(Spacing.S4)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(Spacing.S1)

        title = QLabel("Účtová osnova", self)
        title.setProperty("class", "page-title")
        subtitle = QLabel(
            "Spravuj účty podle vyhlášky 500/2002 Sb.", self,
        )
        subtitle.setProperty("class", "page-subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self._show_inactive_check = QCheckBox("Zobrazit neaktivní", self)
        self._show_inactive_check.setChecked(True)
        self._show_inactive_check.setCursor(Qt.CursorShape.PointingHandCursor)

        header.addLayout(title_box)
        header.addStretch(1)
        header.addWidget(
            self._show_inactive_check, alignment=Qt.AlignmentFlag.AlignTop,
        )

        # Error label
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "error-text")
        self._error_label.setVisible(False)
        self._error_label.setWordWrap(True)

        # Scroll area for tree
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setProperty("class", "osnova-scroll")
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

        self._tree_container = QWidget()
        self._tree_container.setProperty("class", "osnova-tree")
        self._tree_container.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, True,
        )
        self._tree_layout = QVBoxLayout(self._tree_container)
        self._tree_layout.setContentsMargins(
            Spacing.S4, Spacing.S4, Spacing.S4, Spacing.S4,
        )
        self._tree_layout.setSpacing(0)
        scroll.setWidget(self._tree_container)

        root.addLayout(header)
        root.addWidget(self._error_label)
        root.addWidget(scroll, stretch=1)

    def _wire_signals(self) -> None:
        self._show_inactive_check.toggled.connect(self._on_toggle_inactive)

    # ─── Slots ────────────────────────────────────────

    def _on_toggle_inactive(self, checked: bool) -> None:
        if checked != self._vm.show_inactive:
            self._vm.toggle_show_inactive()
            self._sync_ui()

    def _on_checkbox_toggled(self, cislo: str, checked: bool) -> None:
        if checked:
            self._vm.activate_ucet(cislo)
        else:
            self._vm.deactivate_ucet(cislo)
        self._sync_ui()

    def _on_add_analytika(self, syntetic_kod: str, syntetic_nazev: str) -> None:
        dialog = AnalytikaDialog(
            syntetic_kod, syntetic_nazev, parent=self,
        )
        if dialog.exec() and dialog.result is not None:
            r = dialog.result
            self._vm.add_analytika(syntetic_kod, r.suffix, r.nazev, r.popis)
            self._sync_ui()

    def _on_edit_analytika(
        self, cislo: str, nazev: str, popis: str | None,
        syntetic_kod: str, syntetic_nazev: str,
    ) -> None:
        dialog = AnalytikaDialog(
            syntetic_kod, syntetic_nazev,
            edit_cislo=cislo, edit_nazev=nazev, edit_popis=popis,
            parent=self,
        )
        if dialog.exec() and dialog.result is not None:
            r = dialog.result
            self._vm.update_analytika(cislo, r.nazev, r.popis)
            self._sync_ui()

    def _on_edit_ucet(
        self, cislo: str, nazev: str, popis: str | None,
    ) -> None:
        dialog = UcetEditDialog(cislo, nazev, popis, parent=self)
        if dialog.exec() and dialog.result is not None:
            r = dialog.result
            self._vm.update_ucet(cislo, r.nazev, r.popis)
            self._sync_ui()

    # ─── Sync ─────────────────────────────────────────

    def _sync_ui(self) -> None:
        # Error
        if self._vm.error is not None:
            self._error_label.setText(self._vm.error)
            self._error_label.setVisible(True)
        else:
            self._error_label.setVisible(False)

        # Checkbox sync
        self._show_inactive_check.blockSignals(True)
        self._show_inactive_check.setChecked(self._vm.show_inactive)
        self._show_inactive_check.blockSignals(False)

        # Clear tree — setParent(None) to detach immediately
        # (deleteLater defers destruction, old signals can fire and corrupt state)
        while self._tree_layout.count():
            child = self._tree_layout.takeAt(0)
            w = child.widget()
            if w:
                w.blockSignals(True)
                w.setParent(None)

        # Rebuild tree
        for trida in self._vm.tridy:
            self._add_trida_group(trida)

        self._tree_layout.addStretch(1)

    def _add_trida_group(self, trida) -> None:
        """Přidej collapsible skupinu třídy."""
        # Header třídy
        header = QPushButton(
            f"Třída {trida.trida} — {trida.nazev} "
            f"({trida.active_count}/{trida.total_count} aktivních)",
            self._tree_container,
        )
        header.setProperty("class", "osnova-trida-header")
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setCheckable(True)

        was_expanded = trida.trida in self._expanded_tridy
        header.setChecked(was_expanded)

        # Container pro účty
        content = QWidget(self._tree_container)
        content.setProperty("class", "osnova-trida-content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(Spacing.S4, 0, 0, 0)
        content_layout.setSpacing(2)
        content.setVisible(was_expanded)

        for item in trida.ucty:
            self._add_ucet_row(content_layout, item)

        def _on_toggled(checked: bool, t=trida.trida) -> None:
            content.setVisible(checked)
            if checked:
                self._expanded_tridy.add(t)
            else:
                self._expanded_tridy.discard(t)

        header.toggled.connect(_on_toggled)

        self._tree_layout.addWidget(header)
        self._tree_layout.addWidget(content)

    def _add_ucet_row(self, layout: QVBoxLayout, item) -> None:
        """Přidej řádek syntetického účtu + jeho analytiky."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(Spacing.S2)

        # Checkbox pro aktivaci
        checkbox = QCheckBox(row)
        checkbox.setChecked(item.is_active)
        checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        checkbox.toggled.connect(
            lambda checked, c=item.cislo: self._on_checkbox_toggled(c, checked)
        )

        label = QLabel(f"{item.cislo} — {item.nazev}", row)
        if not item.is_active:
            label.setProperty("class", "osnova-ucet-inactive")
        else:
            label.setProperty("class", "osnova-ucet")

        edit_btn = QPushButton("✎", row)
        edit_btn.setProperty("class", "osnova-edit-btn")
        edit_btn.setFixedSize(24, 24)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setToolTip("Upravit účet")
        edit_btn.clicked.connect(
            lambda _checked, ci=item.cislo, na=item.nazev, po=item.popis:
                self._on_edit_ucet(ci, na, po)
        )

        row_layout.addWidget(checkbox)
        row_layout.addWidget(label, stretch=1)
        row_layout.addWidget(edit_btn)
        layout.addWidget(row)

        # Analytiky
        for a in item.analytiky:
            a_row = QWidget()
            a_layout = QHBoxLayout(a_row)
            a_layout.setContentsMargins(Spacing.S8, 1, 0, 1)
            a_layout.setSpacing(Spacing.S2)

            a_check = QCheckBox(a_row)
            a_check.setChecked(a.is_active)
            a_check.setCursor(Qt.CursorShape.PointingHandCursor)
            a_check.toggled.connect(
                lambda checked, c=a.cislo: self._on_checkbox_toggled(c, checked)
            )

            a_label = QLabel(f"└─ {a.cislo} — {a.nazev}", a_row)
            if not a.is_active:
                a_label.setProperty("class", "osnova-ucet-inactive")
            else:
                a_label.setProperty("class", "osnova-analytika")

            edit_btn = QPushButton("✎", a_row)
            edit_btn.setProperty("class", "osnova-edit-btn")
            edit_btn.setFixedSize(24, 24)
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setToolTip("Upravit analytiku")
            edit_btn.clicked.connect(
                lambda _checked, ci=a.cislo, na=a.nazev, po=a.popis:
                    self._on_edit_ucet(ci, na, po)
            )

            a_layout.addWidget(a_check)
            a_layout.addWidget(a_label, stretch=1)
            a_layout.addWidget(edit_btn)
            layout.addWidget(a_row)

        # Tlačítko "+ Přidat analytiku" (jen pro aktivní syntetické)
        if item.is_active and not item.is_analytic:
            add_btn = QPushButton("+ Přidat analytiku", row)
            add_btn.setProperty("class", "osnova-add-analytika")
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_btn.clicked.connect(
                lambda _checked, sk=item.cislo, sn=item.nazev:
                    self._on_add_analytika(sk, sn)
            )
            add_row = QWidget()
            add_layout = QHBoxLayout(add_row)
            add_layout.setContentsMargins(Spacing.S8, 0, 0, 0)
            add_layout.addWidget(add_btn)
            add_layout.addStretch(1)
            layout.addWidget(add_row)
