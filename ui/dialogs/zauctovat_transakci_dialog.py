"""ZauctovatTransakciDialog — přímé zaúčtování bankovní transakce.

Umožní zaúčtovat transakci bez párování s dokladem (poplatky, úroky, atd.).
MD/Dal účet z dropdownu účtové osnovy, Dal předvyplněný z bankovního účtu.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.queries.banka import TransakceListItem
from services.queries.uctova_osnova import UcetItem
from ui.design_tokens import Colors, Spacing
from ui.widgets.labeled_inputs import (
    LabeledComboBox,
    LabeledLineEdit,
)


class ZauctovatTransakciDialog(QDialog):
    """Dialog pro přímé zaúčtování bankovní transakce."""

    def __init__(
        self,
        transakce: TransakceListItem,
        ucty: list[UcetItem],
        ucet_221: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tx = transakce
        self._ucty = ucty
        self._ucet_221 = ucet_221
        self._is_prijem = transakce.smer == "P"

        self.setWindowTitle("Zaúčtovat transakci")
        self.setMinimumWidth(480)
        self.setModal(True)

        self._md_combo: LabeledComboBox
        self._dal_combo: LabeledComboBox
        self._popis_input: LabeledLineEdit
        self._poznamka_input: LabeledLineEdit

        self._build_ui()
        self._populate()

    @property
    def md_ucet(self) -> str:
        item = self._md_combo.value()
        return item.cislo if item else ""

    @property
    def dal_ucet(self) -> str:
        item = self._dal_combo.value()
        return item.cislo if item else ""

    @property
    def popis_zapisu(self) -> str:
        popis = self._popis_input.value().strip()
        poznamka = self._poznamka_input.value().strip()
        if popis and poznamka:
            return f"{popis} | {poznamka}"
        return popis or poznamka or ""

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S5, Spacing.S5, Spacing.S5, Spacing.S5,
        )
        root.setSpacing(Spacing.S3)

        # Title
        title = QLabel("Zaúčtovat transakci", self)
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        # Info section
        tx = self._tx
        datum_text = tx.datum_zauctovani.strftime("%d.%m.%Y")
        castka_text = tx.castka.format_cz()
        smer_text = "Příjem" if self._is_prijem else "Výdaj"

        info = QLabel(
            f"Datum: {datum_text}\n"
            f"Částka: {castka_text} ({smer_text})\n"
            f"Popis: {tx.popis or '—'}",
            self,
        )
        info.setProperty("class", "dialog-value")
        info.setWordWrap(True)
        root.addWidget(info)

        # Nápověda MD/Dal
        if self._is_prijem:
            hint_text = (
                "Příjem → MD bude bankovní účet, Dal vyberte "
                "(výnosy, pohledávky…)"
            )
        else:
            hint_text = (
                "Výdaj → MD vyberte (náklady, závazky…), "
                "Dal bude bankovní účet"
            )
        hint = QLabel(hint_text, self)
        hint.setProperty("class", "form-help")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # MD účet
        self._md_combo = LabeledComboBox(
            "MD účet" if not self._is_prijem else "MD účet (banka)",
        )
        root.addWidget(self._md_combo)

        # Dal účet
        self._dal_combo = LabeledComboBox(
            "Dal účet (banka)" if not self._is_prijem else "Dal účet",
        )
        root.addWidget(self._dal_combo)

        # Popis zápisu
        self._popis_input = LabeledLineEdit(
            "Popis zápisu", max_length=200,
        )
        root.addWidget(self._popis_input)

        # Poznámka
        self._poznamka_input = LabeledLineEdit(
            "Poznámka (nepovinné)", max_length=200,
            placeholder="karta společník, interní ref…",
        )
        root.addWidget(self._poznamka_input)

        # Error
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        root.addStretch(1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(Spacing.S2)

        btn_cancel = QPushButton("Zrušit", self)
        btn_cancel.setProperty("class", "secondary")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_row.addStretch(1)

        self._btn_ok = QPushButton("Zaúčtovat", self)
        self._btn_ok.setProperty("class", "primary")
        self._btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_ok.clicked.connect(self._on_ok)
        btn_row.addWidget(self._btn_ok)

        root.addLayout(btn_row)

    def _populate(self) -> None:
        """Naplní dropdowny účty a předvyplní hodnoty."""
        # Naplň oba dropdowny všemi účty
        for combo in (self._md_combo, self._dal_combo):
            combo.add_item("— vyberte účet —", None)
            for ucet in self._ucty:
                combo.add_item(ucet.display, ucet)

        # Předvyplnění bankovního účtu
        bank_ucet = next(
            (u for u in self._ucty if u.cislo == self._ucet_221), None,
        )

        if self._is_prijem:
            # Příjem: MD = banka (předvyplněný), Dal = uživatel vybere
            if bank_ucet:
                self._md_combo.set_value(bank_ucet)
        else:
            # Výdaj: MD = uživatel vybere, Dal = banka (předvyplněný)
            if bank_ucet:
                self._dal_combo.set_value(bank_ucet)

        # Popis — z transakce
        self._popis_input.set_value(self._tx.popis or "")

    def _on_ok(self) -> None:
        md = self.md_ucet
        dal = self.dal_ucet
        if not md or not dal:
            self._error_label.setText("Vyberte MD i Dal účet.")
            self._error_label.setVisible(True)
            return
        if md == dal:
            self._error_label.setText("MD a Dal účet nesmí být stejný.")
            self._error_label.setVisible(True)
            return
        self.accept()
