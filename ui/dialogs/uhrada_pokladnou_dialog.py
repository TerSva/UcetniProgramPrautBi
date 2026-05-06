"""UhradaPokladnouDialog — úhrada FP/FV pokladnou (vytvoří PD doklad)."""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.queries.doklady_list import DokladyListItem
from ui.design_tokens import Spacing
from ui.widgets.labeled_inputs import LabeledDateEdit, LabeledLineEdit


class UhradaPokladnouDialog(QDialog):
    """Dialog pro úhradu dokladu pokladnou — vytvoří PD doklad."""

    def __init__(
        self,
        doklad: DokladyListItem,
        next_pd_cislo: str,
        ucet_pokladny: str = "211",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._doklad = doklad
        self._ucet_pokladny = ucet_pokladny
        self._result_datum: date | None = None
        self._result_cislo: str | None = None
        self._result_popis: str | None = None

        self.setWindowTitle("Úhrada pokladnou")
        self.setMinimumWidth(450)
        self.setModal(True)

        self._datum_input: LabeledDateEdit
        self._cislo_input: LabeledLineEdit
        self._popis_input: LabeledLineEdit
        self._error_label: QLabel

        self._build_ui(next_pd_cislo)

    @property
    def result_datum(self) -> date | None:
        return self._result_datum

    @property
    def result_cislo(self) -> str | None:
        return self._result_cislo

    @property
    def result_popis(self) -> str | None:
        return self._result_popis

    def _build_ui(self, next_pd_cislo: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        title = QLabel("Úhrada pokladnou", self)
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        d = self._doklad
        typ_label = "FP" if d.typ.value == "FP" else "FV"
        info = QLabel(
            f"Doklad: {d.cislo}  {d.partner_nazev or ''}  "
            f"{d.castka_celkem.format_cz()}",
            self,
        )
        info.setProperty("class", "form-help")
        info.setWordWrap(True)
        root.addWidget(info)

        # Účtování preview — pokladna z osnovy (analytika nebo syntetický)
        ucet_p = self._ucet_pokladny
        if d.typ.value == "FP":
            uctovani = (
                f"MD 321 (Dodavatelé)  /  Dal {ucet_p} (Pokladna)  "
                f"{d.castka_celkem.format_cz()}"
            )
        else:
            uctovani = (
                f"MD {ucet_p} (Pokladna)  /  Dal 311 (Odběratelé)  "
                f"{d.castka_celkem.format_cz()}"
            )
        uctovani_label = QLabel(uctovani, self)
        uctovani_label.setProperty("class", "form-help")
        root.addWidget(uctovani_label)

        self._datum_input = LabeledDateEdit("Datum úhrady", parent=self)
        self._datum_input.set_value(date.today())
        root.addWidget(self._datum_input)

        self._cislo_input = LabeledLineEdit(
            "Číslo PD", placeholder=next_pd_cislo, parent=self,
        )
        self._cislo_input.set_value(next_pd_cislo)
        root.addWidget(self._cislo_input)

        self._popis_input = LabeledLineEdit(
            "Popis", parent=self,
        )
        self._popis_input.set_value(f"Úhrada {d.cislo} pokladnou")
        root.addWidget(self._popis_input)

        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel = QPushButton("Zrušit", self)
        cancel.setProperty("class", "secondary")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        submit = QPushButton("Vytvořit PD + Zaúčtovat", self)
        submit.setProperty("class", "primary")
        submit.setCursor(Qt.CursorShape.PointingHandCursor)
        submit.clicked.connect(self._on_submit)
        btn_row.addWidget(submit)

        root.addLayout(btn_row)

    def _on_submit(self) -> None:
        cislo = self._cislo_input.value().strip()
        if not cislo:
            self._error_label.setText("Číslo PD je povinné.")
            self._error_label.setVisible(True)
            return

        self._result_datum = self._datum_input.value() or date.today()
        self._result_cislo = cislo
        popis = self._popis_input.value().strip()
        self._result_popis = popis or None
        self.accept()
