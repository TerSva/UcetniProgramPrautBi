"""Dialog pro založení nového bankovního účtu."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from domain.banka.bankovni_ucet import BankovniUcet, FormatCsv
from domain.ucetnictvi.ucet import Ucet
from ui.design_tokens import Spacing
from ui.widgets.labeled_inputs import LabeledComboBox, LabeledLineEdit


_FORMAT_LABELS = {
    FormatCsv.MONEY_BANKA: "Money Banka",
    FormatCsv.CESKA_SPORITELNA: "Česká spořitelna",
    FormatCsv.OBECNY: "Obecný",
}


class NovyBankovniUcetDialog(QDialog):
    """Dialog pro vytvoření nového bankovního účtu."""

    def __init__(
        self,
        analytiky_221: list[Ucet],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nový bankovní účet")
        self.setMinimumWidth(450)
        self._analytiky = analytiky_221
        self._result: BankovniUcet | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Spacing.S5, Spacing.S5, Spacing.S5, Spacing.S5,
        )
        layout.setSpacing(Spacing.S3)

        title = QLabel("Založení bankovního účtu", self)
        title.setProperty("class", "card-title")
        layout.addWidget(title)

        self._nazev_input = LabeledLineEdit(
            "Název", placeholder="např. Money Banka", parent=self,
        )
        layout.addWidget(self._nazev_input)

        self._cislo_input = LabeledLineEdit(
            "Číslo účtu", placeholder="např. 670100-2213456789/6210", parent=self,
        )
        layout.addWidget(self._cislo_input)

        self._ucet_combo = LabeledComboBox("Účet z osnovy (221.xxx)", parent=self)
        for ucet in self._analytiky:
            self._ucet_combo.add_item(
                f"{ucet.cislo} – {ucet.nazev}", ucet.cislo,
            )
        layout.addWidget(self._ucet_combo)

        self._format_combo = LabeledComboBox("Formát CSV", parent=self)
        for fmt, label in _FORMAT_LABELS.items():
            self._format_combo.add_item(label, fmt)
        layout.addWidget(self._format_combo)

        self._poznamka_input = LabeledLineEdit(
            "Poznámka", placeholder="volitelná poznámka", parent=self,
        )
        layout.addWidget(self._poznamka_input)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Zrušit", self)
        cancel_btn.setProperty("class", "secondary-sm")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Založit", self)
        save_btn.setProperty("class", "primary")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _on_save(self) -> None:
        nazev = self._nazev_input.value().strip()
        cislo = self._cislo_input.value().strip()
        ucet_kod = self._ucet_combo.value()
        fmt = self._format_combo.value()
        poznamka = self._poznamka_input.value().strip() or None

        if not nazev:
            QMessageBox.warning(self, "Chyba", "Název je povinný.")
            return
        if not cislo:
            QMessageBox.warning(self, "Chyba", "Číslo účtu je povinné.")
            return
        if not ucet_kod:
            QMessageBox.warning(self, "Chyba", "Vyberte účet z osnovy.")
            return

        self._result = BankovniUcet(
            nazev=nazev,
            cislo_uctu=cislo,
            ucet_kod=ucet_kod,
            format_csv=fmt or FormatCsv.OBECNY,
            poznamka=poznamka,
        )
        self.accept()

    @property
    def result(self) -> BankovniUcet | None:
        return self._result
