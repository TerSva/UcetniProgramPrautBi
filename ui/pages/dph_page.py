"""DphPage — DPH stránka pro identifikovanou osobu.

Tři záložky:
  1) Přiznání k DPH — měsíční tabulka 12 měsíců + filter měsíce.
     Double-click na měsíc s transakcemi otevře detail s řádky EPO.
  2) Souhrnné hlášení (VIES) — poskytnuté služby do EU.
  3) Kontrolní hlášení — info box (identifikovaná osoba KH nepodává).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
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
    """DPH stránka — 3 záložky (Přiznání, Souhrnné hlášení, KH)."""

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
        self._mesic_combo: LabeledComboBox
        self._tabs: QTabWidget
        self._table: QTableWidget
        self._vies_table: QTableWidget
        self._vies_empty_label: QLabel
        self._detail_dialog = None

        self._build_ui()
        self._wire_signals()
        self._load()

    # ─── UI building ─────────────────────────────────────────────

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
            "Přehledy DPH — identifikovaná osoba (§6g ZDPH)",
            self,
        )
        subtitle.setProperty("class", "page-subtitle")
        root.addWidget(subtitle)

        # Period selectors (rok + měsíc) — společné pro všechny záložky
        period_row = QHBoxLayout()
        period_row.setSpacing(Spacing.S3)

        self._rok_combo = LabeledComboBox("Rok", self)
        for r in range(2025, 2031):
            self._rok_combo.add_item(str(r), r)
        self._rok_combo.set_value(self._vm.rok)
        period_row.addWidget(self._rok_combo)

        self._mesic_combo = LabeledComboBox("Měsíc", self)
        self._mesic_combo.add_item("Všechny", 0)
        for i, name in enumerate(_MESICE_CZ, start=1):
            self._mesic_combo.add_item(name, i)
        self._mesic_combo.set_value(0)
        period_row.addWidget(self._mesic_combo)
        period_row.addStretch(1)
        root.addLayout(period_row)

        # Tabs
        self._tabs = QTabWidget(self)
        self._tabs.setProperty("class", "dph-tabs")
        self._tabs.addTab(self._build_priznani_tab(), "Přiznání k DPH")
        self._tabs.addTab(
            self._build_vies_tab(), "Souhrnné hlášení",
        )
        self._tabs.addTab(
            self._build_kh_tab(), "Kontrolní hlášení",
        )
        root.addWidget(self._tabs, stretch=1)

    def _build_priznani_tab(self) -> QWidget:
        wrap = QWidget(self)
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, Spacing.S4, 0, 0)
        layout.setSpacing(Spacing.S3)

        self._info_label = QLabel(
            "DPH přiznání se podává jen za měsíce s reverse charge transakcí. "
            "Termín: 25. den následujícího měsíce. Dvojklikem na měsíc "
            "otevřete detail s řádky EPO formuláře.",
            wrap,
        )
        self._info_label.setWordWrap(True)
        self._info_label.setProperty("class", "info-banner")
        layout.addWidget(self._info_label)

        self._table = QTableWidget(0, 4, wrap)
        self._table.setHorizontalHeaderLabels(
            ["Měsíc", "Základ", "DPH", "Stav přiznání"],
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
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

        layout.addWidget(self._table, stretch=1)
        return wrap

    def _build_vies_tab(self) -> QWidget:
        wrap = QWidget(self)
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, Spacing.S4, 0, 0)
        layout.setSpacing(Spacing.S3)

        info = QLabel(
            "Souhrnné hlášení (VIES) se podává, pokud identifikovaná osoba "
            "POSKYTLA službu do jiného státu EU s přenesenou daňovou "
            "povinností (§102 ZDPH). Termín: 25. den následujícího měsíce.",
            wrap,
        )
        info.setWordWrap(True)
        info.setProperty("class", "info-banner")
        layout.addWidget(info)

        self._vies_empty_label = QLabel(
            "Za zvolený rok nebyly evidovány žádné služby poskytnuté do EU. "
            "Souhrnné hlášení se nepodává.",
            wrap,
        )
        self._vies_empty_label.setWordWrap(True)
        self._vies_empty_label.setProperty("class", "empty-note")
        layout.addWidget(self._vies_empty_label)

        self._vies_table = QTableWidget(0, 5, wrap)
        self._vies_table.setHorizontalHeaderLabels(
            ["Datum", "Doklad", "DIČ odběratele",
             "Partner", "Základ"],
        )
        self._vies_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._vies_table.verticalHeader().setVisible(False)
        self._vies_table.setAlternatingRowColors(True)

        vh = self._vies_table.horizontalHeader()
        vh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        vh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        vh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        vh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        vh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self._vies_table.setVisible(False)
        layout.addWidget(self._vies_table, stretch=1)
        return wrap

    def _build_kh_tab(self) -> QWidget:
        wrap = QWidget(self)
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, Spacing.S4, 0, 0)
        layout.setSpacing(Spacing.S3)

        title = QLabel("Kontrolní hlášení", wrap)
        title.setProperty("class", "section-title")
        layout.addWidget(title)

        body = QLabel(
            "PRAUT s.r.o. je identifikovaná osoba (§6g ZDPH).\n\n"
            "Identifikovaná osoba NEPODÁVÁ kontrolní hlášení. Tato povinnost "
            "se vztahuje pouze na plátce DPH.\n\n"
            "Pokud se PRAUT stane plátcem DPH, tato sekce bude aktivována.",
            wrap,
        )
        body.setWordWrap(True)
        body.setProperty("class", "info-banner")
        layout.addWidget(body)
        layout.addStretch(1)
        return wrap

    # ─── Signals ─────────────────────────────────────────────────

    def _wire_signals(self) -> None:
        self._rok_combo.current_value_changed.connect(self._on_rok_changed)
        self._mesic_combo.current_value_changed.connect(
            self._on_mesic_filter_changed,
        )
        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)
        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _on_rok_changed(self, value: object) -> None:
        if isinstance(value, int):
            self._vm.set_rok(value)
            self._load()

    def _on_mesic_filter_changed(self, value: object) -> None:
        if not isinstance(value, int):
            return
        self._vm.set_mesic_filter(None if value == 0 else value)
        self._fill_priznani_table()

    def _on_tab_changed(self, index: int) -> None:
        # 1 = VIES tab
        if index == 1:
            self._vm.load_vies()
            self._fill_vies()

    def _on_row_double_clicked(self, row: int, _col: int) -> None:
        rows = self._vm.mesice_filtered
        if row < 0 or row >= len(rows):
            return
        item = rows[row]
        if item.pocet_transakci == 0:
            return
        self._show_detail(item.mesic)

    def _show_detail(self, mesic: int) -> None:
        from ui.dialogs.dph_detail_dialog import DphDetailDialog

        self._vm.load_detail(mesic)
        item = next(
            (m for m in self._vm.mesice if m.mesic == mesic), None,
        )
        if item is None or self._vm.priznani is None:
            return
        dialog = DphDetailDialog(
            self._vm, mesic, item, self._vm.detail,
            self._vm.priznani, parent=self,
        )
        dialog.exec()
        self._load()

    # ─── Loading ─────────────────────────────────────────────────

    def _load(self) -> None:
        self._vm.load_prehled()
        self._fill_priznani_table()
        if self._tabs.currentIndex() == 1:
            self._vm.load_vies()
            self._fill_vies()

    def _fill_priznani_table(self) -> None:
        rows = self._vm.mesice_filtered
        self._table.setRowCount(len(rows))
        for i, item in enumerate(rows):
            mesic_item = QTableWidgetItem(_MESICE_CZ[item.mesic - 1])
            mesic_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
            self._table.setItem(i, 0, mesic_item)

            if item.pocet_transakci > 0:
                zaklad_text = item.zaklad_celkem.format_cz()
                dph_text = item.dph_celkem.format_cz()
                if item.je_podane:
                    stav = "✅ Podáno"
                else:
                    stav = "⚠️ K podání"
            else:
                zaklad_text = "—"
                dph_text = "—"
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

    def _fill_vies(self) -> None:
        items = self._vm.vies
        if not items:
            self._vies_empty_label.setVisible(True)
            self._vies_table.setVisible(False)
            self._vies_table.setRowCount(0)
            return
        self._vies_empty_label.setVisible(False)
        self._vies_table.setVisible(True)
        self._vies_table.setRowCount(len(items))
        for i, v in enumerate(items):
            self._vies_table.setItem(
                i, 0, QTableWidgetItem(v.doklad_datum.strftime("%d.%m.%Y")),
            )
            self._vies_table.setItem(i, 1, QTableWidgetItem(v.doklad_cislo))
            self._vies_table.setItem(
                i, 2, QTableWidgetItem(v.partner_dic or "—"),
            )
            self._vies_table.setItem(
                i, 3, QTableWidgetItem(v.partner_nazev or "—"),
            )
            zt = QTableWidgetItem(v.zaklad.format_cz())
            zt.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            self._vies_table.setItem(i, 4, zt)

    # ─── Test-only accessors ─────────────────────────────────────

    @property
    def _table_widget(self) -> QTableWidget:
        return self._table

    @property
    def _rok_combo_widget(self) -> LabeledComboBox:
        return self._rok_combo

    @property
    def _mesic_combo_widget(self) -> LabeledComboBox:
        return self._mesic_combo

    @property
    def _tabs_widget(self) -> QTabWidget:
        return self._tabs

    @property
    def _vies_table_widget(self) -> QTableWidget:
        return self._vies_table

    @property
    def _vies_empty_label_widget(self) -> QLabel:
        return self._vies_empty_label
