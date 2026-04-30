"""SaldokontoPage — samostatná stránka v sidebaru pro saldokonto.

Zobrazuje 4 sekce: 311 (odběratelé), 321 (dodavatelé),
355 (pohledávky vůči společníkům), 365 (závazky vůči společníkům).
311/321 z neuhrazených FV/FP, 355/365 ze sumy účetních zápisů
(MD−Dal, resp. Dal−MD pro pasivní účet).
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from domain.shared.money import Money
from services.queries.vykazy_query import (
    SaldokontoUcetSekce,
    VykazyQuery,
)
from ui.design_tokens import Colors, Spacing


def _format_date(d: date) -> str:
    return f"{d.day:02d}. {d.month:02d}. {d.year}"


def _make_table(cols: tuple[str, ...]) -> QTableWidget:
    t = QTableWidget(0, len(cols))
    t.setHorizontalHeaderLabels(list(cols))
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    t.horizontalHeader().setStretchLastSection(False)
    return t


def _set_text_cell(
    table: QTableWidget, row: int, col: int, text: str,
    bold: bool = False,
) -> None:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if bold:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    table.setItem(row, col, item)


def _set_money_cell(
    table: QTableWidget, row: int, col: int, m: Money,
    bold: bool = False,
) -> None:
    item = QTableWidgetItem(m.format_cz())
    item.setTextAlignment(int(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    ))
    if m.is_negative:
        item.setForeground(QBrush(QColor(Colors.ERROR_700)))
    if bold:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    table.setItem(row, col, item)


class SaldokontoPage(QWidget):
    """Saldokonto k rozvahovému dni — 4 sekce po účtech."""

    def __init__(
        self,
        vykazy_query: VykazyQuery,
        rok_default: int = 2025,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._query = vykazy_query
        self._rok = rok_default

        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._rok_combo: QComboBox
        self._saldo_311: QTableWidget
        self._saldo_321: QTableWidget
        self._saldo_355: QTableWidget
        self._saldo_365: QTableWidget

        self._build_ui()
        self._reload()

    # ─── UI ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        title = QLabel("Saldokonto", self)
        title.setProperty("class", "page-title")
        root.addWidget(title)

        subtitle = QLabel(
            "Pohledávky a závazky k rozvahovému dni — podle účtů "
            "311 / 321 / 355 / 365.",
            self,
        )
        subtitle.setProperty("class", "page-subtitle")
        root.addWidget(subtitle)

        # Rok selector
        controls = QHBoxLayout()
        controls.setSpacing(Spacing.S3)
        controls.addWidget(QLabel("Účetní rok:", self))
        self._rok_combo = QComboBox(self)
        for r in (2025, 2026, 2027):
            self._rok_combo.addItem(str(r), r)
        idx = self._rok_combo.findData(self._rok)
        if idx >= 0:
            self._rok_combo.setCurrentIndex(idx)
        self._rok_combo.currentIndexChanged.connect(self._on_rok_changed)
        controls.addWidget(self._rok_combo)
        controls.addStretch(1)
        root.addLayout(controls)

        info = QLabel(
            "311/321 se sestaví z neuhrazených faktur (FV/FP). "
            "355/365 se sestaví ze sumy účetních zápisů na analytikách "
            "společníků.",
            self,
        )
        info.setWordWrap(True)
        info.setProperty("class", "info-banner")
        root.addWidget(info)

        # 311
        sec1 = QLabel("Pohledávky z obchodního styku (311)", self)
        sec1.setProperty("class", "section-title")
        root.addWidget(sec1)
        cols_doklady = (
            "Doklad", "Partner", "Datum", "Částka", "Uhrazeno", "Zbývá",
        )
        self._saldo_311 = _make_table(cols_doklady)
        root.addWidget(self._saldo_311)

        # 321
        sec2 = QLabel("Závazky z obchodního styku (321)", self)
        sec2.setProperty("class", "section-title")
        root.addWidget(sec2)
        self._saldo_321 = _make_table(cols_doklady)
        root.addWidget(self._saldo_321)

        # 355
        sec3 = QLabel("Pohledávky za společníky (355)", self)
        sec3.setProperty("class", "section-title")
        root.addWidget(sec3)
        cols_ucty = ("Účet", "Název / partner", "Saldo")
        self._saldo_355 = _make_table(cols_ucty)
        root.addWidget(self._saldo_355)

        # 365
        sec4 = QLabel("Závazky vůči společníkům (365)", self)
        sec4.setProperty("class", "section-title")
        root.addWidget(sec4)
        self._saldo_365 = _make_table(cols_ucty)
        root.addWidget(self._saldo_365)

        root.addStretch(1)

    # ─── Loading ─────────────────────────────────────────────────

    def _on_rok_changed(self) -> None:
        rok = self._rok_combo.currentData()
        if isinstance(rok, int):
            self._rok = rok
            self._reload()

    def _reload(self) -> None:
        try:
            sekce = self._query.get_saldokonto_per_ucet(self._rok)
        except Exception:  # noqa: BLE001
            return
        sekce_map = {s.ucet: s for s in sekce}
        self._fill_doklady(self._saldo_311, sekce_map.get("311"))
        self._fill_doklady(self._saldo_321, sekce_map.get("321"))
        self._fill_ucty(self._saldo_355, sekce_map.get("355"))
        self._fill_ucty(self._saldo_365, sekce_map.get("365"))

    def _fill_doklady(
        self,
        table: QTableWidget,
        sekce: SaldokontoUcetSekce | None,
    ) -> None:
        radky = sekce.radky if sekce else ()
        if not radky:
            table.setRowCount(1)
            _set_text_cell(table, 0, 0, "— žádné otevřené položky —")
            for c in range(1, table.columnCount()):
                _set_text_cell(table, 0, c, "")
            table.resizeColumnsToContents()
            h = table.horizontalHeader()
            h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            return
        table.setRowCount(len(radky) + 1)
        for i, r in enumerate(radky):
            _set_text_cell(table, i, 0, r.cislo_dokladu)
            _set_text_cell(table, i, 1, r.partner_nazev or "—")
            _set_text_cell(table, i, 2, _format_date(r.datum))
            _set_money_cell(table, i, 3, r.castka)
            _set_money_cell(table, i, 4, r.uhrazeno)
            _set_money_cell(table, i, 5, r.zbyva)
        last = len(radky)
        _set_text_cell(table, last, 0, "CELKEM", bold=True)
        for c in range(1, 5):
            _set_text_cell(table, last, c, "")
        _set_money_cell(table, last, 5, sekce.celkem, bold=True)
        table.resizeColumnsToContents()
        h = table.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    def _fill_ucty(
        self,
        table: QTableWidget,
        sekce: SaldokontoUcetSekce | None,
    ) -> None:
        radky = sekce.radky if sekce else ()
        if not radky:
            table.setRowCount(1)
            _set_text_cell(table, 0, 0, "— bez pohybu —")
            for c in range(1, table.columnCount()):
                _set_text_cell(table, 0, c, "")
            table.resizeColumnsToContents()
            h = table.horizontalHeader()
            h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            return
        table.setRowCount(len(radky) + 1)
        for i, r in enumerate(radky):
            _set_text_cell(table, i, 0, r.ucet)
            _set_text_cell(table, i, 1, r.partner_nazev or "—")
            _set_money_cell(table, i, 2, r.saldo)
        last = len(radky)
        _set_text_cell(table, last, 0, "CELKEM", bold=True)
        _set_text_cell(table, last, 1, "")
        _set_money_cell(table, last, 2, sekce.celkem, bold=True)
        table.resizeColumnsToContents()
        h = table.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    # ─── Test-only accessors ─────────────────────────────────────

    @property
    def _table_311(self) -> QTableWidget:
        return self._saldo_311

    @property
    def _table_321(self) -> QTableWidget:
        return self._saldo_321

    @property
    def _table_355(self) -> QTableWidget:
        return self._saldo_355

    @property
    def _table_365(self) -> QTableWidget:
        return self._saldo_365
