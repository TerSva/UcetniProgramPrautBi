"""DphDetailDialog — detail DPH přiznání za měsíc.

Zobrazuje tabulku RC transakcí, řádky pro formulář EPO,
checkbox "Označit jako podané" a tlačítko kopírování.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
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
from services.queries.dph_prehled import DphMesicItem, DphTransakceItem
from ui.design_tokens import Spacing
from ui.viewmodels.dph_vm import DphViewModel

_MESICE_CZ = [
    "", "leden", "únor", "březen", "duben", "květen", "červen",
    "červenec", "srpen", "září", "říjen", "listopad", "prosinec",
]

_MESICE_CZ_TITLE = [
    "", "Leden", "Únor", "Březen", "Duben", "Květen", "Červen",
    "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec",
]


def _termin_podani(rok: int, mesic: int) -> str:
    """Vrátí datum termínu podání (25. dne následujícího měsíce)."""
    if mesic == 12:
        return f"25. 1. {rok + 1}"
    return f"25. {mesic + 1}. {rok}"


class DphDetailDialog(QDialog):
    """Detail DPH přiznání za konkrétní měsíc."""

    def __init__(
        self,
        view_model: DphViewModel,
        mesic: int,
        mesic_item: DphMesicItem,
        transakce: list[DphTransakceItem],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._mesic = mesic
        self._mesic_item = mesic_item
        self._transakce = transakce

        self.setWindowTitle(
            f"DPH přiznání \u2014 {_MESICE_CZ_TITLE[mesic]} {mesic_item.rok}",
        )
        self.setModal(True)
        self.setProperty("class", "dph-detail-dialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.resize(700, 600)

        self._podano_check: QCheckBox
        self._copy_button: QPushButton
        self._close_button: QPushButton
        self._table: QTableWidget
        self._epo_label: QLabel

        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        # Title
        title = QLabel(
            f"DPH přiznání \u2014 {_MESICE_CZ_TITLE[self._mesic]} "
            f"{self._mesic_item.rok}",
            self,
        )
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        # Termín
        termin = _termin_podani(self._mesic_item.rok, self._mesic)
        termin_label = QLabel(f"Termín podání: {termin}", self)
        termin_label.setProperty("class", "dialog-subtitle")
        root.addWidget(termin_label)

        # Transactions table
        section_title = QLabel("Reverse charge transakce:", self)
        section_title.setProperty("class", "section-title")
        root.addWidget(section_title)

        n = len(self._transakce)
        self._table = QTableWidget(n + 1, 4, self)  # +1 for total row
        self._table.setHorizontalHeaderLabels(
            ["Doklad", "Dodavatel", "Základ", "DPH 21\u00a0%"],
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._table.verticalHeader().setVisible(False)

        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        zaklad_total = Money.zero()
        dph_total = Money.zero()
        for i, t in enumerate(self._transakce):
            self._table.setItem(i, 0, QTableWidgetItem(t.doklad_cislo))
            self._table.setItem(
                i, 1, QTableWidgetItem(t.partner_nazev or "\u2014"),
            )
            z_item = QTableWidgetItem(t.zaklad.format_cz())
            z_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            self._table.setItem(i, 2, z_item)
            d_item = QTableWidgetItem(t.dph.format_cz())
            d_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            self._table.setItem(i, 3, d_item)
            zaklad_total = zaklad_total + t.zaklad
            dph_total = dph_total + t.dph

        # Total row
        total_label = QTableWidgetItem("CELKEM")
        total_label.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._table.setItem(n, 0, total_label)
        self._table.setItem(n, 1, QTableWidgetItem(""))
        zt = QTableWidgetItem(zaklad_total.format_cz())
        zt.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self._table.setItem(n, 2, zt)
        dt = QTableWidgetItem(dph_total.format_cz())
        dt.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self._table.setItem(n, 3, dt)

        root.addWidget(self._table, stretch=1)

        # EPO form lines
        epo_text = (
            f"Pro přiznání k DPH (formulář EPO):\n"
            f"Přijaté služby z EU (\u00a7 24a): "
            f"základ {zaklad_total.format_cz()}\n"
            f"DPH 21\u00a0%: {dph_total.format_cz()}\n"
            f"Celková daňová povinnost: {dph_total.format_cz()}"
        )
        self._epo_label = QLabel(epo_text, self)
        self._epo_label.setWordWrap(True)
        self._epo_label.setProperty("class", "epo-section")
        self._epo_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )
        root.addWidget(self._epo_label)

        # Store for clipboard
        self._clipboard_text = (
            f"DPH přiznání \u2014 PRAUT s.r.o. (IČO 22545107)\n"
            f"Období: {_MESICE_CZ_TITLE[self._mesic]} "
            f"{self._mesic_item.rok}\n\n"
            f"Přijaté služby z EU (\u00a7 24a): "
            f"základ {zaklad_total.format_cz()}\n"
            f"DPH 21\u00a0%: {dph_total.format_cz()}\n"
            f"Celková daňová povinnost: {dph_total.format_cz()}"
        )

        # Podáno checkbox
        self._podano_check = QCheckBox("Označit jako podané", self)
        self._podano_check.setProperty("class", "form-check")
        self._podano_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self._podano_check.setChecked(self._mesic_item.je_podane)
        root.addWidget(self._podano_check)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch(1)

        self._close_button = QPushButton("Zavřít", self)
        self._close_button.setProperty("class", "secondary")
        self._close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self._close_button)

        self._copy_button = QPushButton("Kopírovat do schránky", self)
        self._copy_button.setProperty("class", "primary")
        self._copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self._copy_button)

        root.addLayout(footer)

    def _wire_signals(self) -> None:
        self._podano_check.toggled.connect(self._on_podano_toggled)
        self._copy_button.clicked.connect(self._on_copy)
        self._close_button.clicked.connect(self.accept)

    def _on_podano_toggled(self, checked: bool) -> None:
        self._vm.oznac_podane(self._mesic, checked)

    def _on_copy(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self._clipboard_text)

    # ─── Test-only accessors ─────────────────────────────────────

    @property
    def _table_widget(self) -> QTableWidget:
        return self._table

    @property
    def _epo_label_widget(self) -> QLabel:
        return self._epo_label

    @property
    def _podano_check_widget(self) -> QCheckBox:
        return self._podano_check

    @property
    def _copy_button_widget(self) -> QPushButton:
        return self._copy_button

    @property
    def _close_button_widget(self) -> QPushButton:
        return self._close_button
