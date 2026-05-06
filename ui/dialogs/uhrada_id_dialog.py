"""UhradaIntDoklademDialog — úhrada FP/FV interním dokladem (pytlování přes 365)."""

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

from domain.partneri.partner import KategoriePartnera, Partner
from services.queries.doklady_list import DokladyListItem
from ui.design_tokens import Spacing
from ui.widgets.labeled_inputs import (
    LabeledComboBox,
    LabeledDateEdit,
    LabeledLineEdit,
)


class UhradaIntDoklademDialog(QDialog):
    """Dialog pro úhradu interním dokladem — pytlování přes 365.xxx."""

    def __init__(
        self,
        doklad: DokladyListItem,
        spolecnici: list[Partner],
        next_id_cislo: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._doklad = doklad
        self._spolecnici = spolecnici
        self._result_datum: date | None = None
        self._result_cislo: str | None = None
        self._result_popis: str | None = None
        self._result_ucet: str | None = None

        self.setWindowTitle("Úhrada interním dokladem")
        self.setMinimumWidth(480)
        self.setModal(True)

        self._datum_input: LabeledDateEdit
        self._cislo_input: LabeledLineEdit
        self._popis_input: LabeledLineEdit
        self._spolecnik_combo: LabeledComboBox
        self._error_label: QLabel

        self._build_ui(next_id_cislo)

    @property
    def result_datum(self) -> date | None:
        return self._result_datum

    @property
    def result_cislo(self) -> str | None:
        return self._result_cislo

    @property
    def result_popis(self) -> str | None:
        return self._result_popis

    @property
    def result_ucet_spolecnika(self) -> str | None:
        return self._result_ucet

    def _build_ui(self, next_id_cislo: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        title = QLabel("Úhrada interním dokladem (pytlování)", self)
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        d = self._doklad
        info = QLabel(
            f"Doklad: {d.cislo}  {d.partner_nazev or ''}  "
            f"{d.castka_celkem.format_cz()}",
            self,
        )
        info.setProperty("class", "form-help")
        info.setWordWrap(True)
        root.addWidget(info)

        self._spolecnik_combo = LabeledComboBox(
            "Společník", parent=self,
        )
        for sp in self._spolecnici:
            ucet = sp.ucet_zavazek or "365"
            label = f"{sp.nazev} ({ucet})"
            self._spolecnik_combo.add_item(label, ucet)
        root.addWidget(self._spolecnik_combo)

        # Default: splatnost > vystavení > dnes (viz UhradaPokladnouDialog)
        default_datum = (
            d.datum_splatnosti or d.datum_vystaveni or date.today()
        )
        self._datum_input = LabeledDateEdit("Datum úhrady", parent=self)
        self._datum_input.set_value(default_datum)
        root.addWidget(self._datum_input)

        self._cislo_input = LabeledLineEdit(
            "Číslo ID", placeholder=next_id_cislo, parent=self,
        )
        self._cislo_input.set_value(next_id_cislo)
        root.addWidget(self._cislo_input)

        self._popis_input = LabeledLineEdit("Popis", parent=self)
        self._popis_input.set_value(
            f"Úhrada {d.cislo} ze soukromé karty",
        )
        root.addWidget(self._popis_input)

        # Preview účtování
        if d.typ.value == "FP":
            uctovani = "MD 321 (Dodavatelé)  /  Dal 365.xxx"
        else:
            uctovani = "MD 365.xxx  /  Dal 311 (Odběratelé)"
        uctovani_lbl = QLabel(
            f"Účtování: {uctovani}  {d.castka_celkem.format_cz()}", self,
        )
        uctovani_lbl.setProperty("class", "form-help")
        root.addWidget(uctovani_lbl)

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

        submit = QPushButton("Vytvořit ID + Zaúčtovat", self)
        submit.setProperty("class", "primary")
        submit.setCursor(Qt.CursorShape.PointingHandCursor)
        submit.clicked.connect(self._on_submit)
        btn_row.addWidget(submit)

        root.addLayout(btn_row)

    def _on_submit(self) -> None:
        cislo = self._cislo_input.value().strip()
        if not cislo:
            self._error_label.setText("Číslo ID je povinné.")
            self._error_label.setVisible(True)
            return

        ucet = self._spolecnik_combo.current_data()
        if not ucet:
            self._error_label.setText("Vyberte společníka.")
            self._error_label.setVisible(True)
            return

        self._result_datum = self._datum_input.value() or date.today()
        self._result_cislo = cislo
        self._result_ucet = ucet
        popis = self._popis_input.value().strip()
        self._result_popis = popis or None
        self.accept()
