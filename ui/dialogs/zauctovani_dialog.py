"""ZauctovaniDialog — modální okno pro zaúčtování dokladu.

Layout:
    Header: Doklad FV-2026-001, Částka: 12 100 Kč
    ┌────────────────────────────────────────────────────────────┐
    │ Datum účetního případu: [2026-03-01]                       │
    ├────────────────────────────────────────────────────────────┤
    │ Účetní zápisy                                    [+ Řádek] │
    │                                                            │
    │  MD          Dal         Částka         Popis        [×]   │
    │  ▾ 311 …    ▾ 601 …    [12100,00]    [...........]   [×]   │
    │                                                            │
    │ Součet řádků: 12 100 Kč      Rozdíl: 0 Kč ✓ Podvojné      │
    └────────────────────────────────────────────────────────────┘
    [Zrušit]                              [Zaúčtovat]

Tlačítko "Zaúčtovat" je aktivní jen když VM.je_validni == True (účty
vyplněné, podvojné, všechny částky > 0).
"""

from __future__ import annotations

from datetime import date
from typing import cast

from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from domain.shared.money import Money
from services.queries.doklady_list import DokladyListItem
from services.queries.uctova_osnova import UcetItem
from ui.design_tokens import Spacing
from ui.viewmodels.zauctovani_vm import DPH_SAZBY, ZauctovaniViewModel
from ui.widgets.labeled_inputs import (
    LabeledComboBox,
    LabeledDateEdit,
    LabeledLineEdit,
    LabeledMoneyEdit,
)


class _RadekRow(QWidget):
    """Jeden řádek: MD combo, Dal combo, castka, popis, remove button."""

    def __init__(
        self,
        index: int,
        ucty: list[UcetItem],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._index = index

        self._md_combo = LabeledComboBox("MD účet", self)
        self._dal_combo = LabeledComboBox("Dal účet", self)
        for ucet in ucty:
            self._md_combo.add_item(ucet.display, ucet.cislo)
            self._dal_combo.add_item(ucet.display, ucet.cislo)
        self._md_combo.combo_widget.setCurrentIndex(-1)
        self._dal_combo.combo_widget.setCurrentIndex(-1)

        self._castka_input = LabeledMoneyEdit("Částka (Kč)", parent=self)
        self._popis_input = LabeledLineEdit("Popis (nepovinné)", parent=self)

        self._remove_button = QPushButton("×", self)
        self._remove_button.setProperty("class", "row-remove")
        self._remove_button.setFixedSize(32, 32)
        self._remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_button.setToolTip("Odebrat řádek")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.S3)
        layout.addWidget(self._md_combo, stretch=2)
        layout.addWidget(self._dal_combo, stretch=2)
        layout.addWidget(self._castka_input, stretch=1)
        layout.addWidget(self._popis_input, stretch=2)
        # Align the remove button to the bottom (row of inputs has label above)
        layout.addWidget(
            self._remove_button,
            alignment=Qt.AlignmentFlag.AlignBottom,
        )

    @property
    def md_combo(self) -> LabeledComboBox:
        return self._md_combo

    @property
    def dal_combo(self) -> LabeledComboBox:
        return self._dal_combo

    @property
    def castka_input(self) -> LabeledMoneyEdit:
        return self._castka_input

    @property
    def popis_input(self) -> LabeledLineEdit:
        return self._popis_input

    @property
    def remove_button(self) -> QPushButton:
        return self._remove_button


class ZauctovaniDialog(QDialog):
    """Modální dialog pro zaúčtování dokladu."""

    def __init__(
        self,
        view_model: ZauctovaniViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Zaúčtovat {view_model.doklad.cislo}")
        self.setModal(True)
        self.setProperty("class", "zauctovani-dialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.resize(860, 600)

        self._vm = view_model
        self._posted_item: DokladyListItem | None = None
        self._rows: list[_RadekRow] = []

        self._title_label: QLabel
        self._summary_label: QLabel
        self._rc_section: QWidget
        self._rc_check: QCheckBox
        self._dph_sazba_combo: LabeledComboBox
        self._datum_edit: LabeledDateEdit
        self._rows_container: QWidget
        self._rows_layout: QVBoxLayout
        self._sum_label: QLabel
        self._rozdil_label: QLabel
        self._status_label: QLabel
        self._error_label: QLabel
        self._add_row_button: QPushButton
        self._submit_button: QPushButton
        self._cancel_button: QPushButton

        self._vm.load()
        self._build_ui()
        self._wire_signals()
        self._rebuild_rows()
        self._sync_ui()

    # ─── Public API ──────────────────────────────────────────────

    @property
    def posted_item(self) -> DokladyListItem | None:
        return self._posted_item

    # ─── Test-only accessors ─────────────────────────────────────

    @property
    def _submit_widget(self) -> QPushButton:
        return self._submit_button

    @property
    def _add_row_widget(self) -> QPushButton:
        return self._add_row_button

    @property
    def _rozdil_widget(self) -> QLabel:
        return self._rozdil_label

    @property
    def _rows_list(self) -> list[_RadekRow]:
        return self._rows

    @property
    def _rc_check_widget(self) -> QCheckBox:
        return self._rc_check

    @property
    def _rc_section_widget(self) -> QWidget:
        return self._rc_section

    @property
    def _dph_sazba_combo_widget(self) -> LabeledComboBox:
        return self._dph_sazba_combo

    # ─── Build ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        # Header
        self._title_label = QLabel(
            f"Zaúčtovat {self._vm.doklad.cislo}", self,
        )
        self._title_label.setProperty("class", "dialog-title")
        root.addWidget(self._title_label)

        self._summary_label = QLabel(
            f"Celková částka dokladu: "
            f"{self._vm.doklad.castka_celkem.format_cz()}",
            self,
        )
        self._summary_label.setProperty("class", "dialog-subtitle")
        root.addWidget(self._summary_label)

        # ── Reverse charge section ──
        self._rc_section = QWidget(self)
        rc_layout = QVBoxLayout(self._rc_section)
        rc_layout.setContentsMargins(0, 0, 0, 0)
        rc_layout.setSpacing(Spacing.S2)

        self._rc_check = QCheckBox(
            "Reverse charge \u2014 služba z EU "
            "(přenesení daňové povinnosti dle čl. 196 směrnice 2006/112/EC)",
            self._rc_section,
        )
        self._rc_check.setProperty("class", "form-check")
        self._rc_check.setCursor(Qt.CursorShape.PointingHandCursor)
        rc_layout.addWidget(self._rc_check)

        self._dph_sazba_combo = LabeledComboBox(
            "Sazba DPH", self._rc_section,
        )
        for s in DPH_SAZBY:
            self._dph_sazba_combo.add_item(f"{s} %", s)
        self._dph_sazba_combo.set_value(self._vm.dph_sazba)
        self._dph_sazba_combo.setVisible(False)
        rc_layout.addWidget(self._dph_sazba_combo)

        self._rc_section.setVisible(self._vm.show_reverse_charge)
        root.addWidget(self._rc_section)

        # Datum
        self._datum_edit = LabeledDateEdit(
            "Datum účetního případu", parent=self,
        )
        self._datum_edit.set_value(self._vm.datum)
        root.addWidget(self._datum_edit)

        # Rows header
        rows_header = QHBoxLayout()
        rows_title = QLabel("Účetní zápisy", self)
        rows_title.setProperty("class", "section-title")
        rows_header.addWidget(rows_title)
        rows_header.addStretch(1)
        self._add_row_button = QPushButton("+ Řádek", self)
        self._add_row_button.setProperty("class", "secondary")
        self._add_row_button.setCursor(Qt.CursorShape.PointingHandCursor)
        rows_header.addWidget(self._add_row_button)
        root.addLayout(rows_header)

        # Rows container (scrollable)
        self._rows_container = QWidget(self)
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(Spacing.S3)
        self._rows_layout.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._rows_container)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        root.addWidget(scroll, stretch=1)

        # Summary row (součet + rozdíl)
        summary_row = QHBoxLayout()
        summary_row.setSpacing(Spacing.S6)
        self._sum_label = QLabel("Součet řádků: 0 Kč", self)
        self._sum_label.setProperty("class", "sum-label")
        summary_row.addWidget(self._sum_label)

        self._rozdil_label = QLabel("Rozdíl: 0 Kč", self)
        self._rozdil_label.setProperty("class", "rozdil-label")
        summary_row.addWidget(self._rozdil_label)

        summary_row.addStretch(1)

        self._status_label = QLabel("", self)
        self._status_label.setProperty("class", "status-label")
        summary_row.addWidget(self._status_label)
        root.addLayout(summary_row)

        # Error
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch(1)
        self._cancel_button = QPushButton("Zrušit", self)
        self._cancel_button.setProperty("class", "secondary")
        self._cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self._cancel_button)

        self._submit_button = QPushButton("Zaúčtovat", self)
        self._submit_button.setProperty("class", "primary")
        self._submit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self._submit_button)
        root.addLayout(footer)

    def _wire_signals(self) -> None:
        self._rc_check.toggled.connect(self._on_rc_toggled)
        self._dph_sazba_combo.current_value_changed.connect(
            self._on_dph_sazba_changed,
        )
        self._add_row_button.clicked.connect(self._on_add_row)
        self._submit_button.clicked.connect(self._on_submit)
        self._cancel_button.clicked.connect(self.reject)

    # ─── Row management ──────────────────────────────────────────

    def _rebuild_rows(self) -> None:
        # Odstraň všechny existující row widgety (kromě stretchu na konci).
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()

        # Nový seznam na základě VM.
        for i, radek in enumerate(self._vm.radky):
            row = _RadekRow(index=i, ucty=self._vm.ucty, parent=self)
            # Pre-fill z VM
            if radek.md_ucet:
                row.md_combo.set_value(radek.md_ucet)
            if radek.dal_ucet:
                row.dal_combo.set_value(radek.dal_ucet)
            if radek.castka != Money.zero():
                row.castka_input.set_value(radek.castka)
            if radek.popis:
                row.popis_input.set_value(radek.popis)

            # Connect signals → push to VM
            row.md_combo.current_value_changed.connect(
                lambda v, idx=i: self._on_row_md_changed(idx, v)
            )
            row.dal_combo.current_value_changed.connect(
                lambda v, idx=i: self._on_row_dal_changed(idx, v)
            )
            row.castka_input.line_widget.editingFinished.connect(
                lambda idx=i: self._on_row_castka_changed(idx)
            )
            row.popis_input.text_changed.connect(
                lambda text, idx=i: self._on_row_popis_changed(idx, text)
            )
            row.remove_button.clicked.connect(
                lambda _checked=False, idx=i: self._on_remove_row(idx)
            )

            # Insert before final stretch
            count = self._rows_layout.count()
            self._rows_layout.insertWidget(count - 1, row)
            self._rows.append(row)

    def _on_add_row(self) -> None:
        self._vm.add_row()
        self._rebuild_rows()
        self._sync_ui()

    def _on_remove_row(self, index: int) -> None:
        self._vm.remove_row(index)
        self._rebuild_rows()
        self._sync_ui()

    def _on_row_md_changed(self, index: int, value: object) -> None:
        md = value if isinstance(value, str) else ""
        self._vm.update_row(index, md_ucet=md)
        self._sync_ui()

    def _on_row_dal_changed(self, index: int, value: object) -> None:
        dal = value if isinstance(value, str) else ""
        self._vm.update_row(index, dal_ucet=dal)
        self._sync_ui()

    def _on_row_castka_changed(self, index: int) -> None:
        row = self._rows[index]
        castka = row.castka_input.value() or Money.zero()
        self._vm.update_row(index, castka=castka)
        self._sync_ui()

    def _on_row_popis_changed(self, index: int, text: str) -> None:
        self._vm.update_row(index, popis=text)

    # ─── Reverse charge ─────────────────────────────────────────

    def _on_rc_toggled(self, checked: bool) -> None:
        self._dph_sazba_combo.setVisible(checked)
        self._vm.set_reverse_charge(checked)
        self._rebuild_rows()
        self._sync_ui()

    def _on_dph_sazba_changed(self, value: object) -> None:
        if isinstance(value, Decimal):
            self._vm.set_dph_sazba(value)
            self._rebuild_rows()
            self._sync_ui()

    # ─── Submit ──────────────────────────────────────────────────

    def _on_submit(self) -> None:
        # Flush VM state s aktuálními castka hodnotami (v případě, že
        # editingFinished se nespustilo).
        for i, row in enumerate(self._rows):
            castka = row.castka_input.value() or Money.zero()
            self._vm.update_row(i, castka=castka)

        datum = self._datum_edit.value()
        if datum is not None:
            self._vm.set_datum(datum)

        item = self._vm.submit()
        if item is None:
            self._error_label.setText(
                self._vm.error or "Zaúčtování selhalo."
            )
            self._error_label.setVisible(True)
            return
        self._posted_item = item
        self.accept()

    # ─── UI sync ─────────────────────────────────────────────────

    def _sync_ui(self) -> None:
        soucet = self._vm.soucet_radku
        rozdil = self._vm.rozdil
        self._sum_label.setText(f"Součet: {soucet.format_cz()}")
        self._rozdil_label.setText(f"Rozdíl: {rozdil.format_cz()}")

        if self._vm.je_podvojne:
            self._status_label.setText("✓ Podvojné")
            self._status_label.setProperty("class", "status-ok")
        else:
            self._status_label.setText("⚠ Nepodvojné")
            self._status_label.setProperty("class", "status-error")
        # Refresh property-based styling
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)

        self._submit_button.setEnabled(self._vm.je_validni)
