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

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from domain.doklady.priloha import PrilohaDokladu
from domain.doklady.typy import TypDokladu
from domain.shared.money import Money
from services.queries.doklady_list import DokladyFilter, DokladyListItem
from ui.design_tokens import Spacing
from ui.dialogs.doklad_detail_dialog import DokladDetailDialog
from ui.dialogs.doklad_form_dialog import DokladFormDialog
from ui.dialogs.zauctovani_dialog import ZauctovaniDialog
from ui.viewmodels import DokladyListViewModel
from ui.viewmodels.doklad_detail_vm import DokladDetailViewModel
from ui.viewmodels.doklad_form_vm import DokladFormViewModel
from ui.viewmodels.zauctovani_vm import ZauctovaniViewModel
from ui.widgets.doklady_table import DokladyTable
from ui.widgets.filter_bar import FilterBar


#: Per-type subtitles
_SUBTITLE_BY_TYP: dict[TypDokladu, str] = {
    TypDokladu.FAKTURA_VYDANA: "Faktury vydané klientům.",
    TypDokladu.FAKTURA_PRIJATA: "Faktury přijaté od dodavatelů.",
    TypDokladu.POKLADNI_DOKLAD: "Pokladní doklady — příjmové a výdajové.",
    TypDokladu.INTERNI_DOKLAD: "Interní doklady — vklady kapitálu, přeúčtování, opravné položky.",
    TypDokladu.OPRAVNY_DOKLAD: "Opravné doklady ke stávajícím fakturám.",
}

#: Index stránek v interním QStackedWidget pro přepínání obsah vs. empty state.
_STACK_CONTENT = 0
_STACK_EMPTY = 1


def _czech_plural_filtry(count: int) -> str:
    """Česká množná čísla pro slovo „filtr".

    1 filtr / 2-4 filtry / 5+ nebo 0 filtrů.
    """
    if count == 1:
        return "1 filtr aktivní"
    if 2 <= count <= 4:
        return f"{count} filtry aktivní"
    return f"{count} filtrů aktivní"


def _czech_plural_dokladu(count: int) -> str:
    """Česká „dokladů" — skloňuje se stejně pro všechny počty v genitivu plurálu.

    „Zobrazeno X z Y **dokladů**" — nezáleží na X ani Y, vždy genitiv pl.
    """
    return "dokladů"


class DokladyPage(QWidget):
    """Doklady stránka — filtr + tabulka + detail dialog."""

    def __init__(
        self,
        view_model: DokladyListViewModel,
        form_vm_factory: Callable[[], DokladFormViewModel] | None = None,
        detail_vm_factory: Callable[
            [DokladyListItem], DokladDetailViewModel
        ] | None = None,
        zauctovani_vm_factory: Callable[
            [DokladyListItem], ZauctovaniViewModel
        ] | None = None,
        priloha_loader: Callable[[int], list[PrilohaDokladu]] | None = None,
        priloha_uploader: Callable[
            [int, Path, str], PrilohaDokladu
        ] | None = None,
        priloha_full_path: Callable[[str], Path] | None = None,
        uhrazeno_query: Callable[[int], Money] | None = None,
        pdf_parser: object = None,
        form_priloha_uploader: object = None,
        preset_typ: TypDokladu | None = None,
        preset_title: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._form_vm_factory = form_vm_factory
        self._detail_vm_factory = detail_vm_factory
        self._zauctovani_vm_factory = zauctovani_vm_factory
        self._priloha_loader = priloha_loader
        self._priloha_uploader = priloha_uploader
        self._priloha_full_path = priloha_full_path
        self._uhrazeno_query = uhrazeno_query
        self._pdf_parser = pdf_parser
        self._form_priloha_uploader = form_priloha_uploader
        self._preset_typ = preset_typ
        self._preset_title = preset_title or "Doklady"
        self._preset_subtitle = _SUBTITLE_BY_TYP.get(
            preset_typ, "Přijaté a vydané faktury, příjmové a výdajové doklady.",
        ) if preset_typ else "Přijaté a vydané faktury, příjmové a výdajové doklady."

        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._build_ui()
        self._wire_signals()

        # Apply preset typ filter
        if self._preset_typ is not None:
            self._vm.set_typ_filter(self._preset_typ)
            self._filter_bar.set_filter(self._vm.filter)
            self._filter_bar.hide_typ_combo()

        self.refresh()

    # ────────────────────────────────────────────────
    # Event overrides
    # ────────────────────────────────────────────────

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Re-apply preset typ filter every time the page becomes visible.

        Multiple DokladyPage instances share one VM — without this,
        switching pages shows stale data from the previously active page.
        """
        super().showEvent(event)
        if self._preset_typ is not None:
            self._vm.set_typ_filter(self._preset_typ)
            self._filter_bar.set_filter(self._vm.filter)
            self._sync_ui_with_vm()

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

    def apply_typ_filter(self, typ: TypDokladu) -> None:
        """Fáze 6.7: Dashboard drill → filtr na konkrétní typ dokladu.

        Používá se pro karty Pohledávky (FV) a Závazky (FP). VM resetuje
        ostatní filtry a aplikuje jen ``typ``, FilterBar se zresynchronizuje.
        """
        self._vm.set_typ_filter(typ)
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

    @property
    def _status_bar_widget(self) -> QLabel:
        return self._status_bar

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
        self._title = QLabel(self._preset_title, self)
        self._title.setProperty("class", "page-title")

        subtitle = QLabel(self._preset_subtitle, self)
        subtitle.setProperty("class", "page-subtitle")

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(Spacing.S1)
        title_box.addWidget(self._title)
        title_box.addWidget(subtitle)

        self._button_novy = QPushButton("+ Nový doklad", self)
        self._button_novy.setProperty("class", "primary")
        # Tlačítko je enabled pouze pokud máme factory pro form VM
        # (fallback na starší testy, které factory nedodávají).
        self._button_novy.setEnabled(self._form_vm_factory is not None)
        self._button_novy.setCursor(Qt.CursorShape.PointingHandCursor)

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

        # Fáze 6.7: status bar pod tabulkou — „Zobrazeno X z Y dokladů
        # · N filtrů aktivní"
        self._status_bar = QLabel("", self)
        self._status_bar.setProperty("class", "doklady-status-bar")
        self._status_bar.setVisible(False)

        root.addLayout(header)
        root.addWidget(self._filter_bar)
        root.addWidget(self._error_label)
        root.addWidget(self._stack, stretch=1)
        root.addWidget(self._status_bar)

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
        self._button_novy.clicked.connect(self._on_novy_clicked)

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
        # Preset typ takes priority — ignore user's typ selection
        effective_typ = self._preset_typ if self._preset_typ is not None else typ
        new_filter = DokladyFilter(
            rok=rok,
            typ=effective_typ,
            stav=stav,
            k_doreseni=k_doreseni,
        )
        self._vm.apply_filters(new_filter)
        self._sync_ui_with_vm()

    def _on_clear_filters(self) -> None:
        if self._preset_typ is not None:
            # Keep preset typ, clear everything else
            self._vm.set_typ_filter(self._preset_typ)
        else:
            self._vm.clear_filters()
        self._filter_bar.set_filter(self._vm.filter)
        self._sync_ui_with_vm()

    def _on_row_activated(self, doklad_id: int) -> None:
        for item in self._vm.items:
            if item.id == doklad_id:
                self._open_detail(item)
                return

    def _open_detail(self, item: DokladyListItem) -> None:
        """Otevře detail dialog. Pokud nemáme factory (legacy testy),
        fallbackuje na read-only dialog bez VM."""
        if self._detail_vm_factory is None:
            return
        vm = self._detail_vm_factory(item)
        dialog = DokladDetailDialog(
            vm,
            priloha_loader=self._priloha_loader,
            priloha_uploader=self._priloha_uploader,
            priloha_full_path=self._priloha_full_path,
            uhrazeno_query=self._uhrazeno_query,
            parent=self,
        )
        dialog.zauctovat_requested.connect(
            lambda current_item: self._open_zauctovani(dialog, current_item)
        )
        dialog.exec()
        self.refresh()

    def _open_zauctovani(
        self,
        parent_dialog: DokladDetailDialog,
        item: DokladyListItem,
    ) -> None:
        if self._zauctovani_vm_factory is None:
            return
        vm = self._zauctovani_vm_factory(item)
        dialog = ZauctovaniDialog(vm, parent=parent_dialog)
        if dialog.exec() and dialog.posted_item is not None:
            parent_dialog.refresh_after_zauctovani(dialog.posted_item)

    def _on_novy_clicked(self) -> None:
        if self._form_vm_factory is None:
            return
        vm = self._form_vm_factory()
        dialog = DokladFormDialog(
            vm,
            preset_typ=self._preset_typ,
            pdf_parser=self._pdf_parser,
            priloha_uploader=self._form_priloha_uploader,
            parent=self,
        )
        if dialog.exec() and dialog.created_item is not None:
            self.refresh()
            # Otevři detail pro nově vytvořený doklad → umožní okamžitě
            # zaúčtovat.
            self._open_detail(dialog.created_item)

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
            self._status_bar.setVisible(False)
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
            self._status_bar.setVisible(False)
            return

        self._table.set_items(items)
        self._stack.setCurrentIndex(_STACK_CONTENT)
        self._update_status_bar()

    def _update_status_bar(self) -> None:
        """Aktualizuj status bar: „Zobrazeno X z Y dokladů · N filtrů aktivní".

        Skryje se, pokud není k dispozici ``total_count`` z VM (legacy
        testy bez count_query).
        """
        visible = self._vm.visible_count
        total = self._vm.total_count
        if total <= 0:
            self._status_bar.setVisible(False)
            return
        parts = [
            f"Zobrazeno {visible} z {total} {_czech_plural_dokladu(total)}",
        ]
        n_active = self._filter_bar.active_filters_count()
        if n_active > 0:
            parts.append(_czech_plural_filtry(n_active))
        self._status_bar.setText(" · ".join(parts))
        self._status_bar.setVisible(True)
