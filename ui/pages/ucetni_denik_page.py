"""UcetniDenikPage — stránka Účetní deník.

Tabulka všech účetních zápisů s filtry: období (DateRangeFilter),
fulltext hledání, toggle „Skrýt storno". Auto-apply (debounce 300 ms).
Sloupce: Datum, Doklad, MD účet, D účet, Částka, Popis.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import Colors, Spacing
from ui.viewmodels.ucetni_denik_vm import UcetniDenikRow, UcetniDenikViewModel
from ui.widgets.date_range_filter import DateRangeFilter


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
    """Účetní deník — auto-apply filtry s debounce 300 ms."""

    SEARCH_DEBOUNCE_MS = 300

    def __init__(
        self,
        view_model: UcetniDenikViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._date_range: DateRangeFilter
        self._search_input: QLineEdit
        self._skryt_storno_check: QCheckBox
        self._clear_button: QPushButton
        self._count_label: QLabel
        self._error_label: QLabel
        self._search_timer: QTimer
        self._table: QTableView
        self._model: _DenikTableModel

        # Aktuální stav filtrů (None = bez ohraničení)
        self._od: date | None = None
        self._do: date | None = None
        self._search: str = ""
        self._skryt_storno: bool = False

        self._build_ui()
        self._wire_signals()
        # První load podle defaultu DateRangeFilter ("Tento rok")
        self._od, self._do = self._date_range.current_range()
        self._reload()

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

        # Filter bar — Date range + search + toggle
        self._date_range = DateRangeFilter(year=self._vm.ucetni_rok, parent=self)
        root.addWidget(self._date_range)

        # Druhý řádek: hledání + storno toggle + Vymazat
        bar2 = QHBoxLayout()
        bar2.setContentsMargins(0, 0, 0, 0)
        bar2.setSpacing(Spacing.S3)

        search_label = QLabel("Hledat:", self)
        search_label.setProperty("class", "field-label")
        bar2.addWidget(search_label)

        self._search_input = QLineEdit(self)
        self._search_input.setPlaceholderText(
            "Číslo dokladu, účet (311…), nebo text v popisu",
        )
        self._search_input.setMinimumWidth(280)
        bar2.addWidget(self._search_input)

        self._skryt_storno_check = QCheckBox("Skrýt storno", self)
        self._skryt_storno_check.setProperty("class", "form-check")
        self._skryt_storno_check.setCursor(Qt.CursorShape.PointingHandCursor)
        bar2.addWidget(self._skryt_storno_check)

        self._clear_button = QPushButton("Vymazat filtry", self)
        self._clear_button.setProperty("class", "secondary")
        self._clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        bar2.addWidget(self._clear_button)

        bar2.addStretch(1)

        self._count_label = QLabel("", self)
        self._count_label.setProperty("class", "form-help")
        bar2.addWidget(self._count_label)

        root.addLayout(bar2)

        # Error label
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        # Search debounce timer
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(self.SEARCH_DEBOUNCE_MS)

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
        self._date_range.range_changed.connect(self._on_date_range_changed)
        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._search_timer.timeout.connect(self._reload)
        self._skryt_storno_check.toggled.connect(self._on_storno_toggled)
        self._clear_button.clicked.connect(self._on_clear_filters)

    def _on_date_range_changed(
        self, od: date | None, do: date | None,
    ) -> None:
        self._od = od
        self._do = do
        self._reload()

    def _on_search_text_changed(self, text: str) -> None:
        self._search = text
        self._search_timer.start()  # debounce

    def _on_storno_toggled(self, checked: bool) -> None:
        self._skryt_storno = checked
        self._reload()

    def _on_clear_filters(self) -> None:
        self._search_input.clear()
        self._skryt_storno_check.setChecked(False)
        self._date_range._apply_preset("Tento rok", emit=True)  # noqa: SLF001
        # _apply_preset emits range_changed → _reload() will fire

    def _reload(self) -> None:
        self._vm.load(
            od=self._od,
            do=self._do,
            search=self._search,
            skryt_storno=self._skryt_storno,
        )
        if self._vm.error:
            self._error_label.setText(self._vm.error)
            self._error_label.setVisible(True)
            self._model.set_items([])
            self._count_label.setText("")
        else:
            self._error_label.setVisible(False)
            self._model.set_items(self._vm.items)
            count = len(self._vm.items)
            self._count_label.setText(
                f"{count} zápisů" if count else "Žádné zápisy",
            )
