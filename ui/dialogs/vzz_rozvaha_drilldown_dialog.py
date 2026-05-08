"""Drilldown dialog pro VZZ a rozvahu — seznam zápisů tvořících
částku konkrétního řádku výkazu. Audit/kontrola.
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from domain.shared.money import Money
from services.queries.vykazy_query import DrilldownZapis
from ui.design_tokens import Spacing


def _format_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


class VzzRozvahaDrilldownDialog(QDialog):
    """Modální dialog se seznamem zápisů přispívajících k řádku výkazu."""

    def __init__(
        self,
        nazev_radku: str,
        rok: int,
        zapisy: tuple[DrilldownZapis, ...],
        ocekavany_soucet: Money | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._nazev = nazev_radku
        self._rok = rok
        self._zapisy = zapisy
        self._ocekavany_soucet = ocekavany_soucet

        self.setWindowTitle(f"Detail — {nazev_radku} ({rok})")
        self.setMinimumWidth(900)
        self.setMinimumHeight(500)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        # Header
        header = QLabel(
            f"<b>{self._nazev}</b> — {self._rok}<br>"
            f"<span style='color: #6B7280'>"
            f"{len(self._zapisy)} účetních zápisů</span>",
            self,
        )
        header.setProperty("class", "dialog-title")
        root.addWidget(header)

        # Tabulka
        self._table = QTableWidget(self)
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Datum", "Doklad", "MD účet", "Dal účet",
            "Částka", "± efekt", "Popis",
        ])
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows,
        )
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )
        self._table.verticalHeader().setVisible(False)
        self._fill_table()
        root.addWidget(self._table)

        # Footer — součet
        soucet_halire = sum(
            z.castka.to_halire() * z.znamenko for z in self._zapisy
        )
        soucet = Money(soucet_halire)
        soucet_text = f"Součet zápisů (s ohledem na ± efekt): <b>{soucet.format_cz()}</b>"
        if self._ocekavany_soucet is not None:
            shoda = "✓" if soucet == self._ocekavany_soucet else "⚠"
            soucet_text += (
                f" &nbsp;|&nbsp; výkaz hlásí: {self._ocekavany_soucet.format_cz()} {shoda}"
            )
        soucet_lbl = QLabel(soucet_text, self)
        soucet_lbl.setProperty("class", "form-help")
        root.addWidget(soucet_lbl)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close = QPushButton("Zavřít", self)
        close.setProperty("class", "primary")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.accept)
        btn_row.addWidget(close)
        root.addLayout(btn_row)

    def _fill_table(self) -> None:
        self._table.setRowCount(len(self._zapisy))
        # Šedá pro storna (audit kontext)
        storno_color = QColor("#9CA3AF")
        for i, z in enumerate(self._zapisy):
            row_color = storno_color if z.je_storno else None
            self._set_text(i, 0, _format_date(z.datum), color=row_color)
            self._set_text(i, 1, z.cislo_dokladu, color=row_color)
            self._set_text(i, 2, z.md_ucet, color=row_color)
            self._set_text(i, 3, z.dal_ucet, color=row_color)
            self._set_money(i, 4, z.castka, color=row_color)
            znak = "+" if z.znamenko > 0 else "−"
            sign_color = (
                row_color if z.je_storno
                else (QColor("#059669") if z.znamenko > 0 else QColor("#DC2626"))
            )
            self._set_text(i, 5, znak, color=sign_color)
            popis_text = z.popis or ""
            if z.je_storno:
                popis_text = f"[STORNO] {popis_text}"
            self._set_text(i, 6, popis_text, color=row_color)
        h = self._table.horizontalHeader()
        for col in range(6):
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

    def _set_text(
        self, row: int, col: int, text: str,
        color: QColor | None = None,
    ) -> None:
        item = QTableWidgetItem(text)
        if color is not None:
            item.setForeground(color)
        self._table.setItem(row, col, item)

    def _set_money(
        self, row: int, col: int, money: Money,
        color: QColor | None = None,
    ) -> None:
        item = QTableWidgetItem(money.format_cz())
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        if color is not None:
            item.setForeground(color)
        self._table.setItem(row, col, item)
