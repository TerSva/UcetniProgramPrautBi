"""PocatecniStavyPage — správa počátečních stavů účtů.

Zobrazuje tabulku počátečních zůstatků s kontrolou MD == DAL,
tlačítko pro wizard Vklad ZK a generování dokladu 701.
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

from domain.shared.money import Money
from ui.design_tokens import Colors, Spacing
from ui.viewmodels.pocatecni_stavy_vm import PocatecniStavyViewModel
from ui.widgets.labeled_inputs import (
    LabeledComboBox,
    LabeledLineEdit,
    LabeledMoneyEdit,
)


class PocatecniStavyPage(QWidget):
    """Počáteční stavy účtů — evidence + akce."""

    def __init__(
        self,
        view_model: PocatecniStavyViewModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._rok_combo: LabeledComboBox
        self._table: QTableWidget
        self._ucet_input: LabeledLineEdit
        self._castka_input: LabeledMoneyEdit
        self._strana_combo: LabeledComboBox
        self._poznamka_input: LabeledLineEdit
        self._pridat_button: QPushButton
        self._vklad_zk_button: QPushButton
        self._generovat_button: QPushButton
        self._bilance_label: QLabel
        self._error_label: QLabel

        self._build_ui()
        if self._vm is not None:
            self._vm.load()
            self._refresh_table()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8,
        )
        root.setSpacing(Spacing.S4)

        title = QLabel("Počáteční stavy", self)
        title.setProperty("class", "page-title")
        root.addWidget(title)

        subtitle = QLabel(
            "Počáteční zůstatky účtů na začátku účetního období.",
            self,
        )
        subtitle.setProperty("class", "page-subtitle")
        root.addWidget(subtitle)

        # ── Rok selector ──
        row_rok = QHBoxLayout()
        row_rok.setSpacing(Spacing.S3)
        self._rok_combo = LabeledComboBox("Rok", self)
        for r in range(2020, 2031):
            self._rok_combo.add_item(str(r), r)
        self._rok_combo.set_value(2025)
        self._rok_combo.current_value_changed.connect(self._on_rok_changed)
        row_rok.addWidget(self._rok_combo)
        row_rok.addStretch(1)

        self._vklad_zk_button = QPushButton("Wizard: Vklad ZK", self)
        self._vklad_zk_button.setProperty("class", "secondary")
        self._vklad_zk_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._vklad_zk_button.clicked.connect(self._on_vklad_zk)
        row_rok.addWidget(self._vklad_zk_button)

        self._generovat_button = QPushButton("Generovat doklad 701", self)
        self._generovat_button.setProperty("class", "primary")
        self._generovat_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._generovat_button.clicked.connect(self._on_generovat)
        row_rok.addWidget(self._generovat_button)

        root.addLayout(row_rok)

        # ── Table ──
        self._table = QTableWidget(self)
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Účet", "Strana", "Částka", "Poznámka", ""],
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        h = self._table.horizontalHeader()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(0, 120)
        h.resizeSection(1, 80)
        h.resizeSection(2, 160)
        h.resizeSection(4, 60)
        root.addWidget(self._table, stretch=1)

        # ── Bilance bar ──
        self._bilance_label = QLabel("", self)
        self._bilance_label.setProperty("class", "form-help")
        root.addWidget(self._bilance_label)

        # ── Add row form ──
        form_title = QLabel("Přidat počáteční stav", self)
        form_title.setProperty("class", "section-title")
        root.addWidget(form_title)

        row_form = QHBoxLayout()
        row_form.setSpacing(Spacing.S3)

        self._ucet_input = LabeledLineEdit(
            "Účet", placeholder="221", max_length=10, parent=self,
        )
        row_form.addWidget(self._ucet_input)

        self._strana_combo = LabeledComboBox("Strana", self)
        self._strana_combo.add_item("MD (Má dáti)", "MD")
        self._strana_combo.add_item("DAL (Dal)", "DAL")
        row_form.addWidget(self._strana_combo)

        self._castka_input = LabeledMoneyEdit(
            "Částka (Kč)", placeholder="0,00", parent=self,
        )
        row_form.addWidget(self._castka_input)

        self._poznamka_input = LabeledLineEdit(
            "Poznámka", placeholder="", parent=self,
        )
        row_form.addWidget(self._poznamka_input)

        self._pridat_button = QPushButton("Přidat", self)
        self._pridat_button.setProperty("class", "primary")
        self._pridat_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pridat_button.clicked.connect(self._on_pridat)
        row_form.addWidget(self._pridat_button)

        root.addLayout(row_form)

        # ── Error ──
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

    def _on_rok_changed(self, value: object) -> None:
        if self._vm is None or value is None:
            return
        self._vm.set_rok(int(value))
        self._vm.load()
        self._refresh_table()

    def _on_pridat(self) -> None:
        if self._vm is None:
            return
        ucet = self._ucet_input.value()
        castka = self._castka_input.value()
        strana = self._strana_combo.value()
        poznamka = self._poznamka_input.value() or None

        if not ucet:
            self._show_error("Vyplňte kód účtu.")
            return
        if castka is None or not castka.is_positive:
            self._show_error("Zadejte kladnou částku.")
            return
        if strana not in ("MD", "DAL"):
            self._show_error("Zvolte stranu MD nebo DAL.")
            return

        self._vm.pridat_stav(ucet, castka, strana, poznamka)
        if self._vm.error:
            self._show_error(self._vm.error)
        else:
            self._hide_error()
            self._ucet_input.set_value("")
            self._castka_input.set_value(None)
            self._poznamka_input.set_value("")
            self._refresh_table()

    def _on_smazat(self, stav_id: int) -> None:
        if self._vm is None:
            return
        self._vm.smazat_stav(stav_id)
        if self._vm.error:
            self._show_error(self._vm.error)
        else:
            self._hide_error()
            self._refresh_table()

    def _on_vklad_zk(self) -> None:
        from ui.dialogs.vklad_zk_dialog import VkladZKDialog
        if self._vm is None:
            return
        dlg = VkladZKDialog(self._vm, parent=self)
        if dlg.exec():
            self._vm.load()
            self._refresh_table()

    def _on_generovat(self) -> None:
        if self._vm is None:
            return
        result = self._vm.generovat_doklad()
        if self._vm.error:
            self._show_error(self._vm.error)
        elif result is not None:
            self._hide_error()
            self._show_error(f"Doklad 701 vytvořen (ID: {result}).")
        else:
            self._show_error("Žádné počáteční stavy nebo doklad již existuje.")

    def _refresh_table(self) -> None:
        if self._vm is None:
            return
        stavy = self._vm.stavy
        self._table.setRowCount(len(stavy))
        for i, s in enumerate(stavy):
            self._table.setItem(i, 0, QTableWidgetItem(s.ucet_kod))
            self._table.setItem(i, 1, QTableWidgetItem(s.strana))
            castka_item = QTableWidgetItem(s.castka.format_cz())
            castka_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            self._table.setItem(i, 2, castka_item)
            self._table.setItem(i, 3, QTableWidgetItem(s.poznamka or ""))

            btn = QPushButton("Smazat", self._table)
            btn.setProperty("class", "table-action-danger")
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            sid = s.id
            btn.clicked.connect(lambda _checked, sid=sid: self._on_smazat(sid))
            self._table.setCellWidget(i, 4, btn)

        # Bilance
        md = self._vm.soucet_md
        dal = self._vm.soucet_dal
        ok = self._vm.bilance_souhlasi
        color = Colors.SUCCESS_600 if ok else Colors.ERROR_600
        symbol = "\u2713" if ok else "\u2717"
        self._bilance_label.setText(
            f"MD: {md.format_cz()}  |  DAL: {dal.format_cz()}  |  "
            f"Bilance: {symbol} {'souhlasí' if ok else 'nesouhlasí'}"
        )
        self._bilance_label.setStyleSheet(f"color: {color};")

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.setVisible(True)

    def _hide_error(self) -> None:
        self._error_label.setVisible(False)

    # ─── Test-only accessors ─────────────────────────────────────

    @property
    def _table_widget(self) -> QTableWidget:
        return self._table

    @property
    def _ucet_widget(self) -> LabeledLineEdit:
        return self._ucet_input

    @property
    def _castka_widget(self) -> LabeledMoneyEdit:
        return self._castka_input

    @property
    def _strana_widget(self) -> LabeledComboBox:
        return self._strana_combo

    @property
    def _pridat_widget(self) -> QPushButton:
        return self._pridat_button

    @property
    def _generovat_widget(self) -> QPushButton:
        return self._generovat_button

    @property
    def _vklad_zk_widget(self) -> QPushButton:
        return self._vklad_zk_button

    @property
    def _bilance_widget(self) -> QLabel:
        return self._bilance_label
