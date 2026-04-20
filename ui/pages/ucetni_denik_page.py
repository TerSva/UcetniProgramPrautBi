"""UcetniDenikPage — stránka Účetní deník.

Tabulka všech účetních zápisů s filtrem podle období.
Sloupce: Datum, Doklad, MD účet, D účet, Částka, Popis, Storno.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import Colors, Spacing
from ui.viewmodels.ucetni_denik_vm import UcetniDenikRow, UcetniDenikViewModel
from ui.widgets.labeled_inputs import LabeledDateEdit


# ══════════════════════════════════════════════
# Sloupce
# ══════════════════════════════════════════════

_COL_DATUM = 0
_COL_DOKLAD = 1
_COL_MD = 2
_COL_DAL = 3
_COL_CASTKA = 4
_COL_POPIS = 5

_COLUMN_HEADERS = ("Datum", "Doklad", "MD účet", "D účet", "Částka", "Popis")


def _format_date(d: date) -> str:
    return f"{d.day:02d}. {d.month:02d}. {d.year}"


# ══════════════════════════════════════════════
# Model
# ══════════════════════════════════════════════


class _DenikTableModel(QAbstractTableModel):
    """Read-only model pro účetní deník."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[UcetniDenikRow] = []

    def set_items(self, items: list[UcetniDenikRow]) -> None:
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def item_at(self, row: int) -> UcetniDenikRow:
        return self._items[row]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_COLUMN_HEADERS)

    def headerData(
        self, section: int, orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return _COLUMN_HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._items):
            return None
        item = self._items[row]

        if role == Qt.ItemDataRole.DisplayRole:
            if col == _COL_DATUM:
                return _format_date(item.datum)
            if col == _COL_DOKLAD:
                return item.doklad_cislo
            if col == _COL_MD:
                return item.md_ucet
            if col == _COL_DAL:
                return item.dal_ucet
            if col == _COL_CASTKA:
                return item.castka.format_cz()
            if col == _COL_POPIS:
                text = item.popis or ""
                if item.je_storno:
                    text = f"[STORNO] {text}" if text else "[STORNO]"
                return text
            return None

        if role == Qt.ItemDataRole.ForegroundRole:
            if item.je_storno:
                return QBrush(QColor(Colors.ERROR_700))
            return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col == _COL_CASTKA:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        return None


# ══════════════════════════════════════════════
# Page
# ══════════════════════════════════════════════


class UcetniDenikPage(QWidget):
    """Stránka Účetní deník."""

    def __init__(
        self,
        view_model: UcetniDenikViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._build_ui()
        self._wire_signals()
        self._on_load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6)
        root.setSpacing(Spacing.S4)

        # Header
        title = QLabel("Účetní deník", self)
        title.setProperty("class", "page-title")
        root.addWidget(title)

        subtitle = QLabel("Seznam všech účetních zápisů.", self)
        subtitle.setProperty("class", "page-subtitle")
        root.addWidget(subtitle)

        # Filter bar
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(Spacing.S3)

        today = date.today()
        rok_start = date(self._vm.ucetni_rok, 1, 1)

        self._od_date = LabeledDateEdit("Od", parent=self)
        self._od_date.set_value(rok_start)
        filter_row.addWidget(self._od_date)

        self._do_date = LabeledDateEdit("Do", parent=self)
        self._do_date.set_value(today)
        filter_row.addWidget(self._do_date)

        self._load_btn = QPushButton("Načíst", self)
        self._load_btn.setProperty("class", "primary")
        self._load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        filter_row.addWidget(self._load_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        filter_row.addStretch(1)

        self._count_label = QLabel("", self)
        self._count_label.setProperty("class", "form-help")
        filter_row.addWidget(self._count_label, alignment=Qt.AlignmentFlag.AlignBottom)

        root.addLayout(filter_row)

        # Error label
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        # Table
        self._table = QTableView(self)
        self._table.setProperty("class", "doklady-table")
        self._model = _DenikTableModel(self._table)
        self._table.setModel(self._model)

        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(32)

        h = self._table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(_COL_POPIS, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(_COL_CASTKA, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(_COL_CASTKA, 160)
        h.setHighlightSections(False)

        root.addWidget(self._table, stretch=1)

    def _wire_signals(self) -> None:
        self._load_btn.clicked.connect(self._on_load)

    def _on_load(self) -> None:
        od = self._od_date.value()
        do = self._do_date.value()
        if od is None or do is None:
            return
        self._vm.load(od, do)
        if self._vm.error:
            self._error_label.setText(self._vm.error)
            self._error_label.setVisible(True)
            self._model.set_items([])
            self._count_label.setText("")
        else:
            self._error_label.setVisible(False)
            self._model.set_items(self._vm.items)
            count = len(self._vm.items)
            self._count_label.setText(f"{count} zápisů")
