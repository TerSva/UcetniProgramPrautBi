"""BankaVypisyPage — stránka přehledu bankovních výpisů a transakcí.

Layout:
    ┌──────────────────────────┬──────────────────┐
    │  Výpisy (kompaktní)      │  Účet ▼          │
    │  max 150px               │  Stav ▼          │
    └──────────────────────────┴──────────────────┘
    │ VS [____]  Protiúčet [____]  Od [__] Do [__] Den [__] │
    ├─────────────────────────────────────────────────────────┤
    │  Transakce (stretch=1, velká)                            │
    └─────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from functools import partial

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from domain.banka.bankovni_transakce import StavTransakce
from ui.design_tokens import Spacing
from ui.viewmodels.bankovni_vypisy_vm import BankovniVypisyViewModel
from ui.widgets.labeled_inputs import LabeledComboBox, LabeledLineEdit, LabeledMoneyEdit

_MESICE_CZ = [
    "Leden", "Únor", "Březen", "Duben", "Květen", "Červen",
    "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec",
]

_STAV_LABELS = {
    StavTransakce.NESPAROVANO: "Nespárováno",
    StavTransakce.SPAROVANO: "Spárováno",
    StavTransakce.AUTO_ZAUCTOVANO: "Auto",
    StavTransakce.IGNOROVANO: "Ignorováno",
}


class BankaVypisyPage(QWidget):
    """Stránka přehledu bankovních výpisů."""

    def __init__(
        self,
        view_model: BankovniVypisyViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._ucet_combo: LabeledComboBox
        self._vypisy_table: QTableWidget
        self._tx_table: QTableWidget
        self._auto_btn: QPushButton
        self._stav_combo: LabeledComboBox
        self._info_label: QLabel
        self._vs_input: LabeledLineEdit
        self._protiucet_input: LabeledLineEdit
        self._castka_od_input: LabeledMoneyEdit
        self._castka_do_input: LabeledMoneyEdit
        self._den_input: LabeledLineEdit

        self._build_ui()
        self._wire_signals()
        self._load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8,
        )
        root.setSpacing(Spacing.S3)

        # Title
        title = QLabel("Bankovní výpisy", self)
        title.setProperty("class", "page-title")
        root.addWidget(title)

        subtitle = QLabel(
            "Přehled importovaných výpisů a transakcí. "
            "Automatické zaúčtování poplatků, úroků a párování s doklady.",
            self,
        )
        subtitle.setProperty("class", "page-subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # ── Top row: výpisy table (left) + account/stav filter (right) ──
        top_row = QHBoxLayout()
        top_row.setSpacing(Spacing.S3)

        # Left card: Výpisy table — compact
        left_card = QWidget(self)
        left_card.setProperty("class", "card")
        left_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left_card.setMaximumHeight(160)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(
            Spacing.S3, Spacing.S3, Spacing.S3, Spacing.S3,
        )
        left_layout.setSpacing(Spacing.S1)

        left_title = QLabel("Výpisy", left_card)
        left_title.setProperty("class", "card-title")
        left_layout.addWidget(left_title)

        self._vypisy_table = QTableWidget(0, 5, left_card)
        self._vypisy_table.setHorizontalHeaderLabels([
            "Období", "Účet", "PS", "KS", "Stav",
        ])
        self._vypisy_table.horizontalHeader().setStretchLastSection(True)
        self._vypisy_table.verticalHeader().setVisible(False)
        self._vypisy_table.verticalHeader().setDefaultSectionSize(22)
        self._vypisy_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._vypisy_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        self._vypisy_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )
        left_layout.addWidget(self._vypisy_table)

        top_row.addWidget(left_card, stretch=2)

        # Right card: Účet + Stav only
        right_card = QWidget(self)
        right_card.setProperty("class", "card")
        right_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        right_card.setMaximumHeight(160)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(
            Spacing.S3, Spacing.S3, Spacing.S3, Spacing.S3,
        )
        right_layout.setSpacing(Spacing.S2)

        self._ucet_combo = LabeledComboBox("Bankovní účet", parent=right_card)
        right_layout.addWidget(self._ucet_combo)

        self._stav_combo = LabeledComboBox("Stav transakcí", parent=right_card)
        self._stav_combo.add_item("Vše", None)
        self._stav_combo.add_item("Nespárováno", StavTransakce.NESPAROVANO)
        self._stav_combo.add_item("Spárováno", StavTransakce.SPAROVANO)
        self._stav_combo.add_item("Auto zaúčtováno", StavTransakce.AUTO_ZAUCTOVANO)
        self._stav_combo.add_item("Ignorováno", StavTransakce.IGNOROVANO)
        right_layout.addWidget(self._stav_combo)

        right_layout.addStretch()

        top_row.addWidget(right_card, stretch=1)

        root.addLayout(top_row)

        # ── Filter bar: VS, Protiúčet, Částka od-do, Den — horizontal ──
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(Spacing.S3)

        self._vs_input = LabeledLineEdit(
            "VS", placeholder="var. symbol", parent=self,
        )
        filter_bar.addWidget(self._vs_input)

        self._protiucet_input = LabeledLineEdit(
            "Protiúčet", placeholder="číslo účtu", parent=self,
        )
        filter_bar.addWidget(self._protiucet_input)

        self._castka_od_input = LabeledMoneyEdit(
            "Částka od", placeholder="0", parent=self,
        )
        filter_bar.addWidget(self._castka_od_input)

        self._castka_do_input = LabeledMoneyEdit(
            "Částka do", placeholder="0", parent=self,
        )
        filter_bar.addWidget(self._castka_do_input)

        self._den_input = LabeledLineEdit(
            "Den", placeholder="1-31", max_length=2, parent=self,
        )
        self._den_input.setMaximumWidth(80)
        filter_bar.addWidget(self._den_input)

        root.addLayout(filter_bar)

        # ── Bottom: Transakce detail (large, stretched) ──
        tx_card = QWidget(self)
        tx_card.setProperty("class", "card")
        tx_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tx_layout = QVBoxLayout(tx_card)
        tx_layout.setContentsMargins(
            Spacing.S3, Spacing.S3, Spacing.S3, Spacing.S3,
        )
        tx_layout.setSpacing(Spacing.S2)

        tx_header = QHBoxLayout()
        tx_title = QLabel("Transakce", tx_card)
        tx_title.setProperty("class", "card-title")
        tx_header.addWidget(tx_title)

        self._auto_btn = QPushButton("Auto zaúčtování", tx_card)
        self._auto_btn.setProperty("class", "primary-sm")
        self._auto_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._auto_btn.setEnabled(False)
        tx_header.addWidget(self._auto_btn)
        tx_header.addStretch()
        tx_layout.addLayout(tx_header)

        self._info_label = QLabel("Vyberte výpis v tabulce nahoře.", tx_card)
        self._info_label.setWordWrap(True)
        tx_layout.addWidget(self._info_label)

        self._tx_table = QTableWidget(0, 8, tx_card)
        self._tx_table.setHorizontalHeaderLabels([
            "Datum", "Částka", "Směr", "VS", "Protiúčet", "Popis", "Stav", "Akce",
        ])
        self._tx_table.horizontalHeader().setStretchLastSection(True)
        self._tx_table.verticalHeader().setVisible(False)
        self._tx_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._tx_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )
        self._tx_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        tx_layout.addWidget(self._tx_table, stretch=1)

        root.addWidget(tx_card, stretch=1)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Refresh data při každém zobrazení stránky."""
        super().showEvent(event)
        self._load()

    def _wire_signals(self) -> None:
        self._ucet_combo.current_value_changed.connect(self._on_ucet_changed)
        self._stav_combo.current_value_changed.connect(self._on_stav_changed)
        self._vypisy_table.currentCellChanged.connect(self._on_vypis_selected)
        self._auto_btn.clicked.connect(self._on_auto_zauctovani)
        self._vs_input.text_changed.connect(self._on_vs_changed)
        self._protiucet_input.text_changed.connect(self._on_protiucet_changed)
        self._castka_od_input.line_widget.editingFinished.connect(
            self._on_castka_changed,
        )
        self._castka_do_input.line_widget.editingFinished.connect(
            self._on_castka_changed,
        )
        self._den_input.text_changed.connect(self._on_den_changed)

    def _load(self) -> None:
        self._vm.load()
        self._ucet_combo.combo_widget.blockSignals(True)
        self._ucet_combo.clear_items()
        self._ucet_combo.add_item("Všechny účty", None)
        for ucet in self._vm.ucty:
            self._ucet_combo.add_item(
                f"{ucet.nazev} ({ucet.ucet_kod})", ucet.id,
            )
        self._ucet_combo.combo_widget.blockSignals(False)
        self._refresh_vypisy()

    def _on_ucet_changed(self, ucet_id: object) -> None:
        self._vm.select_ucet(ucet_id)
        self._refresh_vypisy()

    def _on_stav_changed(self, stav: object) -> None:
        self._vm.set_stav_filter(stav)
        self._refresh_transakce()

    def _on_vs_changed(self, text: str) -> None:
        self._vm.set_vs_filter(text)
        self._refresh_transakce()

    def _on_protiucet_changed(self, text: str) -> None:
        self._vm.set_protiucet_filter(text)
        self._refresh_transakce()

    def _on_castka_changed(self) -> None:
        self._vm.set_castka_od(self._castka_od_input.value())
        self._vm.set_castka_do(self._castka_do_input.value())
        self._refresh_transakce()

    def _on_den_changed(self, text: str) -> None:
        text = text.strip()
        if text.isdigit():
            den = int(text)
            self._vm.set_den_filter(den if 1 <= den <= 31 else None)
        else:
            self._vm.set_den_filter(None)
        self._refresh_transakce()

    def _on_vypis_selected(self, row: int, _col: int, _prev_row: int, _prev_col: int) -> None:
        if row < 0 or row >= len(self._vm.vypisy):
            self._vm.select_vypis(None)
            self._auto_btn.setEnabled(False)
            self._refresh_transakce()
            return

        vypis = self._vm.vypisy[row]
        self._vm.select_vypis(vypis.id)
        self._auto_btn.setEnabled(True)
        self._info_label.setText(
            f"Výpis {_MESICE_CZ[vypis.mesic - 1]} {vypis.rok} — "
            f"{vypis.ucet_nazev} | "
            f"Nespárováno: {vypis.pocet_nesparovanych}/{vypis.pocet_transakci}",
        )
        self._refresh_transakce()

    def _on_auto_zauctovani(self) -> None:
        vypis_id = self._vm.selected_vypis_id
        if vypis_id is None:
            return

        result = self._vm.auto_zauctuj(vypis_id)
        if result is None:
            QMessageBox.warning(
                self, "Chyba", self._vm.error or "Neznámá chyba",
            )
            return

        msg = (
            f"Automaticky zaúčtováno: {result.pocet_zauctovano}\n"
            f"Spárováno s doklady: {result.pocet_sparovano}\n"
            f"Přeskočeno: {result.pocet_preskoceno}"
        )
        if result.chyby:
            msg += f"\nChyby: {', '.join(result.chyby)}"

        QMessageBox.information(self, "Auto zaúčtování", msg)
        self._refresh_transakce()
        self._load()

    def _on_ignorovat(self, tx_id: int) -> None:
        ok = self._vm.ignoruj_transakci(tx_id)
        if not ok:
            QMessageBox.warning(
                self, "Chyba", self._vm.error or "Nepodařilo se ignorovat transakci.",
            )
        self._refresh_transakce()

    def _on_sparovat(self, tx_id: int) -> None:
        QMessageBox.information(
            self, "Spárování",
            f"Spárování transakce {tx_id} — funkce bude doplněna.",
        )

    def _refresh_vypisy(self) -> None:
        vypisy = self._vm.vypisy
        self._vypisy_table.setRowCount(len(vypisy))
        for i, v in enumerate(vypisy):
            mesic_name = _MESICE_CZ[v.mesic - 1] if 1 <= v.mesic <= 12 else str(v.mesic)
            self._vypisy_table.setItem(
                i, 0, QTableWidgetItem(f"{mesic_name} {v.rok}"),
            )
            self._vypisy_table.setItem(
                i, 1, QTableWidgetItem(v.ucet_kod),
            )
            self._vypisy_table.setItem(
                i, 2, QTableWidgetItem(v.pocatecni_stav.format_cz()),
            )
            self._vypisy_table.setItem(
                i, 3, QTableWidgetItem(v.konecny_stav.format_cz()),
            )
            nespar = v.pocet_nesparovanych
            total = v.pocet_transakci
            tx_item = QTableWidgetItem(f"{total} ({nespar} nespár.)")
            if nespar > 0:
                tx_item.setForeground(Qt.GlobalColor.darkRed)
            self._vypisy_table.setItem(i, 4, tx_item)

    def _refresh_transakce(self) -> None:
        txs = self._vm.transakce
        self._tx_table.setRowCount(len(txs))
        for i, tx in enumerate(txs):
            self._tx_table.setItem(
                i, 0,
                QTableWidgetItem(tx.datum_zauctovani.strftime("%d.%m.%Y")),
            )
            self._tx_table.setItem(
                i, 1, QTableWidgetItem(tx.castka.format_cz()),
            )
            smer_label = "Příjem" if tx.smer == "P" else "Výdaj"
            self._tx_table.setItem(i, 2, QTableWidgetItem(smer_label))
            self._tx_table.setItem(
                i, 3, QTableWidgetItem(tx.variabilni_symbol or ""),
            )
            self._tx_table.setItem(
                i, 4, QTableWidgetItem(tx.protiucet or ""),
            )
            self._tx_table.setItem(
                i, 5, QTableWidgetItem(tx.popis or ""),
            )
            stav_text = _STAV_LABELS.get(tx.stav, tx.stav.value)
            stav_item = QTableWidgetItem(stav_text)
            if tx.stav == StavTransakce.NESPAROVANO:
                stav_item.setForeground(Qt.GlobalColor.darkRed)
            elif tx.stav in (StavTransakce.SPAROVANO, StavTransakce.AUTO_ZAUCTOVANO):
                stav_item.setForeground(Qt.GlobalColor.darkGreen)
            self._tx_table.setItem(i, 6, stav_item)

            # Akce column — buttons for NESPAROVANO transactions
            if tx.stav == StavTransakce.NESPAROVANO:
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)
                actions_layout.setSpacing(4)

                sparovat_btn = QPushButton("Spárovat")
                sparovat_btn.setProperty("class", "secondary-sm")
                sparovat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                sparovat_btn.clicked.connect(partial(self._on_sparovat, tx.id))

                ignorovat_btn = QPushButton("Ignorovat")
                ignorovat_btn.setProperty("class", "secondary-sm")
                ignorovat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                ignorovat_btn.clicked.connect(partial(self._on_ignorovat, tx.id))

                actions_layout.addWidget(sparovat_btn)
                actions_layout.addWidget(ignorovat_btn)
                self._tx_table.setCellWidget(i, 7, actions_widget)
            else:
                self._tx_table.setItem(i, 7, QTableWidgetItem(""))
