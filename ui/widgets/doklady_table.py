"""DokladyTable — QTableView + model + delegate pro seznam dokladů.

8 sloupců:
    0  Číslo
    1  Typ           — display: "FV", "FP", ... (badge color via ForegroundRole)
    2  Datum         — datum_vystaveni ve formátu DD. MM. YYYY
    3  Splatnost     — datum_splatnosti nebo "—"
    4  Partner       — partner_nazev nebo "—" (stretch)
    5  Částka        — format_cz() (right-align, mono font)
    6  Stav          — display: "Nový", "Zaúčtovaný", ... (badge color)
    7  (prázdné)     — 🔔 Lucide bell ikona pro k_doreseni=True

Indikátor k_doreseni používá `KDoreseniIconDelegate` — tzn. reálná SVG
ikona z Lucide (WARNING_600 barva), ne emoji. Tooltip s poznámkou
vrací model přes `ToolTipRole`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QSize,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QBrush, QColor, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QWidget,
)

from domain.doklady.typy import Mena
from services.queries.doklady_list import DokladyListItem
from ui.design_tokens import Colors
from ui.widgets.badge import (
    BadgeVariant,
    badge_variant_for_stav,
    badge_variant_for_typ,
    stav_display_text,
    typ_display_text,
)
from ui.widgets.icon import load_icon


# ══════════════════════════════════════════════
# Sloupce
# ══════════════════════════════════════════════


_COL_CISLO = 0
_COL_TYP = 1
_COL_DATUM = 2
_COL_SPLATNOST = 3
_COL_PARTNER = 4
_COL_CASTKA = 5
_COL_STAV = 6
_COL_DORESENI = 7


_COLUMN_HEADERS: tuple[str, ...] = (
    "Číslo",
    "Typ",
    "Datum",
    "Splatnost",
    "Partner",
    "Částka",
    "Stav",
    "",
)


#: Badge variant → barva textu v buňce tabulky (tabulka je read-only, badge
#: widget do tabulky nenaháníme — jen barvíme text přes ForegroundRole).
_VARIANT_TEXT_COLOR: dict[BadgeVariant, str] = {
    BadgeVariant.NEUTRAL: Colors.GRAY_700,
    BadgeVariant.PRIMARY: Colors.PRIMARY_700,
    BadgeVariant.SUCCESS: Colors.SUCCESS_700,
    BadgeVariant.WARNING: Colors.WARNING_700,
    BadgeVariant.ERROR: Colors.ERROR_700,
    BadgeVariant.INFO: Colors.INFO_700,
}


def _format_date_short(d: date) -> str:
    """'05. 02. 2026' — česká standardní zkratka."""
    return f"{d.day:02d}. {d.month:02d}. {d.year}"


# ══════════════════════════════════════════════
# Model
# ══════════════════════════════════════════════


class DokladyTableModel(QAbstractTableModel):
    """Read-only model pro seznam DokladyListItem."""

    COLUMNS: tuple[str, ...] = _COLUMN_HEADERS

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[DokladyListItem] = []

    # ────────────────────────────────────────────────
    # Public
    # ────────────────────────────────────────────────

    def set_items(self, items: list[DokladyListItem]) -> None:
        """Replace celý seznam. beginResetModel/endResetModel."""
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def item_at(self, row: int) -> DokladyListItem:
        return self._items[row]

    # ────────────────────────────────────────────────
    # QAbstractTableModel interface
    # ────────────────────────────────────────────────

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(_COLUMN_HEADERS)

    def headerData(  # noqa: N802 (Qt API)
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return _COLUMN_HEADERS[section]
        return None

    def data(  # noqa: C901 — rozvětvení podle role+col je čitelné inline
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._items):
            return None
        item = self._items[row]

        # ── Display ──
        if role == Qt.ItemDataRole.DisplayRole:
            if col == _COL_CISLO:
                return item.cislo
            if col == _COL_TYP:
                return typ_display_text(item.typ)
            if col == _COL_DATUM:
                return _format_date_short(item.datum_vystaveni)
            if col == _COL_SPLATNOST:
                return (
                    _format_date_short(item.datum_splatnosti)
                    if item.datum_splatnosti is not None
                    else "—"
                )
            if col == _COL_PARTNER:
                return item.partner_nazev or "—"
            if col == _COL_CASTKA:
                if item.mena != Mena.CZK and item.castka_mena is not None:
                    foreign = item.castka_mena.to_koruny()
                    return (
                        f"{foreign:,.2f}\u00a0{item.mena.value} "
                        f"({item.castka_celkem.format_cz()})"
                    ).replace(",", "\u00a0").replace(".", ",")
                return item.castka_celkem.format_cz()
            if col == _COL_STAV:
                return stav_display_text(item.stav)
            if col == _COL_DORESENI:
                # Delegate kreslí ikonu — text je prázdný.
                return ""
            return None

        # ── Foreground (badge color) ──
        if role == Qt.ItemDataRole.ForegroundRole:
            if col == _COL_TYP:
                variant = badge_variant_for_typ(item.typ)
                return QBrush(QColor(_VARIANT_TEXT_COLOR[variant]))
            if col == _COL_STAV:
                variant = badge_variant_for_stav(item.stav)
                return QBrush(QColor(_VARIANT_TEXT_COLOR[variant]))
            return None

        # ── Alignment ──
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col == _COL_CASTKA:
                return int(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            if col == _COL_DORESENI:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

        # ── UserRole = bool pro delegate ──
        if role == Qt.ItemDataRole.UserRole:
            if col == _COL_DORESENI:
                return item.k_doreseni
            return None

        # ── Tooltip pro k_doreseni sloupec ──
        if role == Qt.ItemDataRole.ToolTipRole:
            if col == _COL_DORESENI and item.k_doreseni:
                return item.poznamka_doreseni or "Označeno k dořešení"
            return None

        return None


# ══════════════════════════════════════════════
# Delegate — Lucide bell ikona v k_doreseni sloupci
# ══════════════════════════════════════════════


class KDoreseniIconDelegate(QStyledItemDelegate):
    """Vykreslí Lucide bell ikonu v buňce, když je k_doreseni=True."""

    ICON_SIZE: int = 16

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # Pre-load ikonu jednou — render do QIcon drží QPixmap v cache.
        self._icon = load_icon(
            "bell", color=Colors.WARNING_600, size=self.ICON_SIZE,
        )

    def paint(  # noqa: N802 (Qt API)
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        # Selection / hover pozadí nakresli standardně.
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget is not None else None
        if style is not None:
            style.drawControl(
                style.ControlElement.CE_ItemViewItem, opt, painter, widget,
            )

        # Data z modelu
        flagged = index.data(Qt.ItemDataRole.UserRole)
        if not flagged:
            return

        # Vycentruj ikonu v buňce
        rect = option.rect
        x = rect.x() + (rect.width() - self.ICON_SIZE) // 2
        y = rect.y() + (rect.height() - self.ICON_SIZE) // 2
        from PyQt6.QtCore import QRect
        icon_rect = QRect(x, y, self.ICON_SIZE, self.ICON_SIZE)
        self._icon.paint(painter, icon_rect)

    def sizeHint(  # noqa: N802 (Qt API)
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> QSize:
        return QSize(40, 28)


# ══════════════════════════════════════════════
# View
# ══════════════════════════════════════════════


class DokladyTable(QTableView):
    """QTableView s vypnutými grid lines, alternate-row barvami a delegatem."""

    #: Emitováno při double-click / Enter — doklad_id z modelu.
    row_activated = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "doklady-table")

        self._model_adapter_inst = DokladyTableModel(self)
        self.setModel(self._model_adapter_inst)

        self._doreseni_delegate = KDoreseniIconDelegate(self)
        self.setItemDelegateForColumn(_COL_DORESENI, self._doreseni_delegate)

        self._configure_view()
        self._wire_signals()

    # ────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────

    def set_items(self, items: list[DokladyListItem]) -> None:
        self._model_adapter_inst.set_items(items)

    # ────────────────────────────────────────────────
    # Test-only accessors (underscore = interní)
    # ────────────────────────────────────────────────

    @property
    def _model_adapter(self) -> DokladyTableModel:
        return self._model_adapter_inst

    @property
    def _doreseni_delegate_inst(self) -> KDoreseniIconDelegate:
        return self._doreseni_delegate

    # ────────────────────────────────────────────────
    # Build
    # ────────────────────────────────────────────────

    def _configure_view(self) -> None:
        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(False)  # řazení drží query (DESC datum, DESC id)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(36)

        h = self.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(_COL_PARTNER, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(_COL_CASTKA, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(_COL_CASTKA, 180)
        h.setSectionResizeMode(_COL_DORESENI, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(_COL_DORESENI, 44)
        h.setHighlightSections(False)

    def _wire_signals(self) -> None:
        self.doubleClicked.connect(self._on_double_clicked)
        self.activated.connect(self._on_activated)

    def _on_double_clicked(self, index: QModelIndex) -> None:
        self._emit_row_activated(index)

    def _on_activated(self, index: QModelIndex) -> None:
        self._emit_row_activated(index)

    def _emit_row_activated(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        item = self._model_adapter_inst.item_at(index.row())
        self.row_activated.emit(item.id)
