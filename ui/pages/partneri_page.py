"""PartneriPage — stránka evidence partnerů s CRUD a filtry.

Layout:
    Partneři                                          [+ Nový]
    Evidence odběratelů, dodavatelů a společníků

    [Kategorie: Všechny ▼] [🔍 Hledat...]

    ┌────────┬──────────┬────────┬────────┬────────────┐
    │ NÁZEV  │ KATEGORIE│  IČO   │  DIČ   │  ADRESA    │
    └────────┴──────────┴────────┴────────┴────────────┘
"""

from __future__ import annotations

from typing import Callable, Protocol

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from domain.partneri.partner import KategoriePartnera
from services.queries.partneri_list import PartneriListItem
from ui.design_tokens import Spacing
from ui.dialogs.partner_dialog import PartnerDialog, PartnerDialogResult
from ui.widgets.labeled_inputs import LabeledComboBox


_KAT_LABELS: dict[KategoriePartnera, str] = {
    KategoriePartnera.ODBERATEL: "Odběratel",
    KategoriePartnera.DODAVATEL: "Dodavatel",
    KategoriePartnera.SPOLECNIK: "Společník",
    KategoriePartnera.KOMBINOVANY: "Kombinovaný",
}


class _PartneriVM(Protocol):
    @property
    def items(self) -> list[PartneriListItem]: ...
    @property
    def error(self) -> str | None: ...
    def load(
        self, kategorie: KategoriePartnera | None = None,
    ) -> None: ...
    def create(self, data: PartnerDialogResult) -> bool: ...
    def update(self, partner_id: int, data: PartnerDialogResult) -> bool: ...
    def deactivate(self, partner_id: int) -> bool: ...


class PartneriPage(QWidget):
    """Stránka evidence partnerů."""

    def __init__(
        self,
        view_model: _PartneriVM,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model

        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._table: QTableWidget
        self._search_input: QLineEdit
        self._kategorie_combo: LabeledComboBox
        self._error_label: QLabel

        self._build_ui()
        self._wire_signals()
        self.refresh()

    def refresh(self) -> None:
        kat = self._kategorie_combo.value()
        self._vm.load(
            kategorie=kat if isinstance(kat, KategoriePartnera) else None,
        )
        self._sync_ui()

    # ─── Test accessors ──────────────────────────────────

    @property
    def _table_widget(self) -> QTableWidget:
        return self._table

    @property
    def _new_button_widget(self) -> QPushButton:
        return self._new_button

    # ─── Build ───────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8,
        )
        root.setSpacing(Spacing.S4)

        # Header
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(Spacing.S1)

        title = QLabel("Partneři", self)
        title.setProperty("class", "page-title")
        subtitle = QLabel(
            "Evidence odběratelů, dodavatelů a společníků.", self,
        )
        subtitle.setProperty("class", "page-subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self._new_button = QPushButton("+ Nový", self)
        self._new_button.setProperty("class", "primary")
        self._new_button.setCursor(Qt.CursorShape.PointingHandCursor)

        header.addLayout(title_box)
        header.addStretch(1)
        header.addWidget(
            self._new_button, alignment=Qt.AlignmentFlag.AlignTop,
        )
        root.addLayout(header)

        # Error
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "error-text")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        # Filter bar
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(Spacing.S3)

        self._kategorie_combo = LabeledComboBox("Kategorie", self)
        self._kategorie_combo.add_item("Všechny", None)
        for kat, label in _KAT_LABELS.items():
            self._kategorie_combo.add_item(label, kat)
        self._kategorie_combo.set_value(None)
        filter_row.addWidget(self._kategorie_combo)

        self._search_input = QLineEdit(self)
        self._search_input.setPlaceholderText("Hledat v názvu nebo IČO...")
        self._search_input.setProperty("class", "search-input")
        filter_row.addWidget(self._search_input, stretch=1)

        root.addLayout(filter_row)

        # Table
        self._table = QTableWidget(self)
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Název", "Kategorie", "IČO", "DIČ", "Adresa"],
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)

        hdr = self._table.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        root.addWidget(self._table, stretch=1)

    def _wire_signals(self) -> None:
        self._new_button.clicked.connect(self._on_new)
        self._kategorie_combo.current_value_changed.connect(
            lambda _: self.refresh(),
        )
        self._search_input.textChanged.connect(self._on_search)
        self._table.cellDoubleClicked.connect(self._on_row_double_click)

    # ─── Slots ───────────────────────────────────────────

    def _on_new(self) -> None:
        dialog = PartnerDialog(parent=self)
        if dialog.exec() and dialog.result is not None:
            self._vm.create(dialog.result)
            self.refresh()

    def _on_row_double_click(self, row: int, _col: int) -> None:
        if row >= len(self._filtered_items):
            return
        item = self._filtered_items[row]
        edit_data = PartnerDialogResult(
            nazev=item.nazev,
            kategorie=item.kategorie,
            ico=item.ico,
            dic=item.dic,
            adresa=item.adresa,
            podil_procent=item.podil_procent,
        )
        dialog = PartnerDialog(parent=self, edit_data=edit_data)
        if dialog.exec() and dialog.result is not None:
            self._vm.update(item.id, dialog.result)
            self.refresh()

    def _on_search(self, text: str) -> None:
        self._sync_ui()

    # ─── Sync ────────────────────────────────────────────

    def _sync_ui(self) -> None:
        if self._vm.error:
            self._error_label.setText(self._vm.error)
            self._error_label.setVisible(True)
        else:
            self._error_label.setVisible(False)

        # Filter by search
        q = self._search_input.text().strip().lower()
        items = self._vm.items
        if q:
            items = [
                i for i in items
                if q in i.nazev.lower()
                or (i.ico and q in i.ico)
            ]
        self._filtered_items = items

        self._table.setRowCount(len(items))
        for row, item in enumerate(items):
            self._table.setItem(row, 0, QTableWidgetItem(item.nazev))

            kat_text = _KAT_LABELS.get(item.kategorie, item.kategorie.value)
            if item.podil_procent is not None:
                kat_text += f" ({item.podil_procent}%)"
            self._table.setItem(row, 1, QTableWidgetItem(kat_text))

            self._table.setItem(
                row, 2, QTableWidgetItem(item.ico or ""),
            )
            self._table.setItem(
                row, 3, QTableWidgetItem(item.dic or ""),
            )
            self._table.setItem(
                row, 4, QTableWidgetItem(item.adresa or ""),
            )
