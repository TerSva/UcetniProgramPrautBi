"""DphPage — stránka s přehledem DPH za rok.

Zobrazuje měsíční tabulku se základem, DPH a stavem podání.
Klik na měsíc s transakcemi otevře detail dialog.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import Spacing
from ui.viewmodels.dph_vm import DphViewModel
from ui.widgets.labeled_inputs import LabeledComboBox

_MESICE_CZ = [
    "Leden", "Únor", "Březen", "Duben", "Květen", "Červen",
    "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec",
]


class DphPage(QWidget):
    """Stránka DPH — měsíční přehled pro identifikovanou osobu."""

    def __init__(
        self,
        view_model: DphViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._title_label: QLabel
        self._info_label: QLabel
        self._rok_combo: LabeledComboBox
        self._table: QTableWidget
        self._detail_dialog = None

        self._build_ui()
        self._wire_signals()
        self._load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8,
        )
        root.setSpacing(Spacing.S4)

        self._title_label = QLabel("DPH", self)
        self._title_label.setProperty("class", "page-title")
        root.addWidget(self._title_label)

        subtitle = QLabel(
            "Přehled daně z přidané hodnoty \u2014 identifikovaná osoba",
            self,
        )
        subtitle.setProperty("class", "page-subtitle")
        root.addWidget(subtitle)

        self._info_label = QLabel(
            "PRAUT s.r.o. je identifikovaná osoba k DPH. "
            "Nepodává kontrolní hlášení. DPH přiznání se podává "
            "jen za měsíce s reverse charge transakcí.",
            self,
        )
        self._info_label.setWordWrap(True)
        self._info_label.setProperty("class", "info-banner")
        root.addWidget(self._info_label)

        # Rok selector
        rok_row = QHBoxLayout()
        rok_row.setSpacing(Spacing.S3)
        self._rok_combo = LabeledComboBox("Období", self)
        for r in range(2025, 2031):
            self._rok_combo.add_item(str(r), r)
        self._rok_combo.set_value(self._vm.rok)
        rok_row.addWidget(self._rok_combo)
        rok_row.addStretch(1)
        root.addLayout(rok_row)

        # Table
        self._table = QTableWidget(12, 4, self)
        self._table.setHorizontalHeaderLabels(
            ["Měsíc", "Základ", "DPH 21\u00a0%", "Stav přiznání"],
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)

        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        root.addWidget(self._table, stretch=1)

    def _wire_signals(self) -> None:
        self._rok_combo.current_value_changed.connect(self._on_rok_changed)
        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)

    def _on_rok_changed(self, value: object) -> None:
        if isinstance(value, int):
            self._vm.set_rok(value)
            self._load()

    def _on_row_double_clicked(self, row: int, _col: int) -> None:
        if row < 0 or row >= len(self._vm.mesice):
            return
        item = self._vm.mesice[row]
        if item.pocet_transakci == 0:
            return
        self._show_detail(item.mesic)

    def _show_detail(self, mesic: int) -> None:
        from ui.dialogs.dph_detail_dialog import DphDetailDialog

        self._vm.load_detail(mesic)
        item = next(
            (m for m in self._vm.mesice if m.mesic == mesic), None,
        )
        if item is None:
            return
        dialog = DphDetailDialog(
            self._vm, mesic, item, self._vm.detail, parent=self,
        )
        dialog.exec()
        # Refresh after potential "podáno" change
        self._load()

    def _load(self) -> None:
        self._vm.load_prehled()
        self._fill_table()

    def _fill_table(self) -> None:
        for i, item in enumerate(self._vm.mesice):
            # Měsíc
            mesic_item = QTableWidgetItem(_MESICE_CZ[i])
            mesic_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
            self._table.setItem(i, 0, mesic_item)

            if item.pocet_transakci > 0:
                zaklad_text = item.zaklad_celkem.format_cz()
                dph_text = item.dph_celkem.format_cz()
                if item.je_podane:
                    stav = "\u2705 Podáno"
                else:
                    stav = "\u26a0\ufe0f K podání"
            else:
                zaklad_text = "\u2014"
                dph_text = "\u2014"
                stav = "Bez transakcí"

            for col, text in enumerate(
                [zaklad_text, dph_text, stav], start=1,
            ):
                cell = QTableWidgetItem(text)
                cell.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    if col < 3
                    else Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                )
                self._table.setItem(i, col, cell)

    # ─── Test-only accessors ─────────────────────────────────────

    @property
    def _table_widget(self) -> QTableWidget:
        return self._table

    @property
    def _rok_combo_widget(self) -> LabeledComboBox:
        return self._rok_combo
