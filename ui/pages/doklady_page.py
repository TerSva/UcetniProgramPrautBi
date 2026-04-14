"""Doklady — seznam dokladů s filtry a read-only detailem.

Layout:
    Title + subtitle                                     [+ Nový doklad]*
    ┌── FilterBar ────────────────────────────────────────────────┐
    │ [Rok▾] [Typ▾] [Stav▾] [K dořešení▾]    [Vymazat filtry]     │
    └─────────────────────────────────────────────────────────────┘
    [error-text když VM.error]
    ┌── DokladyTable ────────────────────────────────────────────┐
    │ Číslo  Typ  Datum  Splatnost  Partner  Částka  Stav  🔔    │
    └─────────────────────────────────────────────────────────────┘
    Empty state (když items=[])

    * Tlačítko „+ Nový doklad" je v Kroku 3 disabled (wizard přijde později).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from services.queries.doklady_list import DokladyFilter
from ui.design_tokens import Spacing
from ui.dialogs.doklad_detail_dialog import DokladDetailDialog
from ui.viewmodels import DokladyListViewModel
from ui.widgets.doklady_table import DokladyTable
from ui.widgets.filter_bar import FilterBar


#: Index stránek v interním QStackedWidget pro přepínání obsah vs. empty state.
_STACK_CONTENT = 0
_STACK_EMPTY = 1


class DokladyPage(QWidget):
    """Doklady stránka — filtr + tabulka + detail dialog."""

    def __init__(
        self,
        view_model: DokladyListViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model

        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._build_ui()
        self._wire_signals()
        self.refresh()

    # ────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload data z VM a překresli UI."""
        self._vm.load()
        self._sync_ui_with_vm()

    def apply_k_doreseni_filter(self) -> None:
        """Vyvolané Dashboardem — VM přepne na „jen k dořešení" a sync UI."""
        self._vm.set_k_doreseni_only()
        self._filter_bar.set_filter(self._vm.filter)
        self._sync_ui_with_vm()

    # ────────────────────────────────────────────────
    # Test-only accessors (underscore = interní)
    # ────────────────────────────────────────────────

    @property
    def _filter_bar_widget(self) -> FilterBar:
        return self._filter_bar

    @property
    def _table_widget(self) -> DokladyTable:
        return self._table

    @property
    def _empty_widget(self) -> QWidget:
        return self._empty_container

    @property
    def _empty_label_widget(self) -> QLabel:
        return self._empty_label

    @property
    def _error_label_widget(self) -> QLabel:
        return self._error_label

    @property
    def _title_widget(self) -> QLabel:
        return self._title

    @property
    def _novy_button(self) -> QPushButton:
        return self._button_novy

    # ────────────────────────────────────────────────
    # Build
    # ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8,
        )
        root.setSpacing(Spacing.S4)

        # Header
        self._title = QLabel("Doklady", self)
        self._title.setProperty("class", "page-title")

        subtitle = QLabel(
            "Přijaté a vydané faktury, příjmové a výdajové doklady.", self
        )
        subtitle.setProperty("class", "page-subtitle")

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(Spacing.S1)
        title_box.addWidget(self._title)
        title_box.addWidget(subtitle)

        self._button_novy = QPushButton("+ Nový doklad", self)
        self._button_novy.setProperty("class", "primary")
        self._button_novy.setEnabled(False)
        self._button_novy.setToolTip("Přijde v dalším kroku")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(Spacing.S5)
        header.addLayout(title_box)
        header.addStretch(1)
        header.addWidget(
            self._button_novy, alignment=Qt.AlignmentFlag.AlignTop,
        )

        # Filter bar
        self._filter_bar = FilterBar(self)

        # Error label
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "error-text")
        self._error_label.setVisible(False)
        self._error_label.setWordWrap(True)

        # Content / empty stack
        self._stack = QStackedWidget(self)
        self._table = DokladyTable(self)
        self._stack.addWidget(self._table)             # _STACK_CONTENT = 0

        self._empty_container = self._build_empty_state()
        self._stack.addWidget(self._empty_container)   # _STACK_EMPTY = 1

        root.addLayout(header)
        root.addWidget(self._filter_bar)
        root.addWidget(self._error_label)
        root.addWidget(self._stack, stretch=1)

    def _build_empty_state(self) -> QWidget:
        container = QWidget(self)
        container.setProperty("class", "empty-state")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8,
        )
        layout.setSpacing(Spacing.S2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._empty_label = QLabel("", container)
        self._empty_label.setProperty("class", "empty-state-text")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        layout.addWidget(self._empty_label)

        self._empty_clear_button = QPushButton("Vymazat filtry", container)
        self._empty_clear_button.setProperty("class", "secondary")
        self._empty_clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._empty_clear_button.setVisible(False)
        self._empty_clear_button.clicked.connect(self._on_clear_filters)
        layout.addWidget(
            self._empty_clear_button, alignment=Qt.AlignmentFlag.AlignCenter,
        )

        return container

    def _wire_signals(self) -> None:
        self._filter_bar.filters_changed.connect(self._on_filters_changed)
        self._filter_bar.clear_requested.connect(self._on_clear_filters)
        self._table.row_activated.connect(self._on_row_activated)

    # ────────────────────────────────────────────────
    # Slots
    # ────────────────────────────────────────────────

    def _on_filters_changed(
        self,
        rok: object,
        typ: object,
        stav: object,
        k_doreseni: object,
    ) -> None:
        new_filter = DokladyFilter(
            rok=rok,
            typ=typ,
            stav=stav,
            k_doreseni=k_doreseni,
        )
        self._vm.apply_filters(new_filter)
        self._sync_ui_with_vm()

    def _on_clear_filters(self) -> None:
        self._vm.clear_filters()
        self._filter_bar.set_filter(self._vm.filter)
        self._sync_ui_with_vm()

    def _on_row_activated(self, doklad_id: int) -> None:
        for item in self._vm.items:
            if item.id == doklad_id:
                dialog = DokladDetailDialog(item, parent=self)
                dialog.exec()
                return

    # ────────────────────────────────────────────────
    # Internals
    # ────────────────────────────────────────────────

    def _sync_ui_with_vm(self) -> None:
        # Error state
        if self._vm.error is not None:
            self._error_label.setText(
                f"Chyba načítání dokladů: {self._vm.error}"
            )
            self._error_label.setVisible(True)
            self._table.set_items([])
            self._stack.setCurrentIndex(_STACK_EMPTY)
            self._empty_label.setText("Data nejsou k dispozici.")
            self._empty_clear_button.setVisible(False)
            return

        self._error_label.setVisible(False)

        items = self._vm.items
        if not items:
            self._stack.setCurrentIndex(_STACK_EMPTY)
            if self._vm.is_empty_because_of_filter:
                self._empty_label.setText(
                    "Žádné doklady neodpovídají zvoleným filtrům."
                )
                self._empty_clear_button.setVisible(True)
            else:
                self._empty_label.setText(
                    "Zatím tu nejsou žádné doklady.\n"
                    "Nový doklad můžete přidat tlačítkem nahoře."
                )
                self._empty_clear_button.setVisible(False)
            return

        self._table.set_items(items)
        self._stack.setCurrentIndex(_STACK_CONTENT)
