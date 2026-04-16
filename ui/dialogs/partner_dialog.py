"""PartnerDialog — modální okno pro vytvoření/editaci partnera."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from domain.partneri.partner import KategoriePartnera
from ui.design_tokens import Spacing
from ui.widgets.labeled_inputs import LabeledComboBox, LabeledLineEdit


_KATEGORIE_LABELS: dict[KategoriePartnera, str] = {
    KategoriePartnera.ODBERATEL: "Odběratel",
    KategoriePartnera.DODAVATEL: "Dodavatel",
    KategoriePartnera.SPOLECNIK: "Společník",
    KategoriePartnera.KOMBINOVANY: "Kombinovaný",
}


class PartnerDialogResult:
    """Výsledek dialogu."""

    def __init__(
        self,
        nazev: str,
        kategorie: KategoriePartnera,
        ico: str | None = None,
        dic: str | None = None,
        adresa: str | None = None,
        bankovni_ucet: str | None = None,
        email: str | None = None,
        telefon: str | None = None,
        poznamka: str | None = None,
        podil_procent: Decimal | None = None,
        ucet_pohledavka: str | None = None,
        ucet_zavazek: str | None = None,
    ) -> None:
        self.nazev = nazev
        self.kategorie = kategorie
        self.ico = ico
        self.dic = dic
        self.adresa = adresa
        self.bankovni_ucet = bankovni_ucet
        self.email = email
        self.telefon = telefon
        self.poznamka = poznamka
        self.podil_procent = podil_procent
        self.ucet_pohledavka = ucet_pohledavka
        self.ucet_zavazek = ucet_zavazek


class PartnerDialog(QDialog):
    """Modální dialog pro vytvoření/editaci partnera."""

    def __init__(
        self,
        parent: QWidget | None = None,
        edit_data: PartnerDialogResult | None = None,
    ) -> None:
        super().__init__(parent)
        self._edit_data = edit_data
        self.setWindowTitle(
            "Upravit partnera" if edit_data else "Nový partner",
        )
        self.setModal(True)
        self.setProperty("class", "doklad-form")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.resize(480, 620)

        self.result: PartnerDialogResult | None = None

        self._kategorie_combo: LabeledComboBox
        self._nazev_input: LabeledLineEdit
        self._ico_input: LabeledLineEdit
        self._dic_input: LabeledLineEdit
        self._adresa_input: LabeledLineEdit
        self._email_input: LabeledLineEdit
        self._telefon_input: LabeledLineEdit
        self._bank_ucet_input: LabeledLineEdit
        self._poznamka_input: LabeledLineEdit
        self._spolecnik_section: QWidget
        self._podil_input: LabeledLineEdit
        self._ucet_pohl_input: LabeledLineEdit
        self._ucet_zav_input: LabeledLineEdit
        self._error_label: QLabel

        self._build_ui()
        self._wire_signals()

        if edit_data:
            self._prefill(edit_data)

    # ─── Test accessors ──────────────────────────────────

    @property
    def _nazev_widget(self) -> LabeledLineEdit:
        return self._nazev_input

    @property
    def _kategorie_widget(self) -> LabeledComboBox:
        return self._kategorie_combo

    @property
    def _ico_widget(self) -> LabeledLineEdit:
        return self._ico_input

    @property
    def _submit_widget(self) -> QPushButton:
        return self._submit_button

    @property
    def _error_widget(self) -> QLabel:
        return self._error_label

    @property
    def _spolecnik_section_widget(self) -> QWidget:
        return self._spolecnik_section

    # ─── Build ───────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S3)

        title = QLabel(
            "Upravit partnera" if self._edit_data else "Nový partner",
            self,
        )
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        # Kategorie
        self._kategorie_combo = LabeledComboBox("Kategorie", self)
        for kat, label in _KATEGORIE_LABELS.items():
            self._kategorie_combo.add_item(label, kat)
        self._kategorie_combo.set_value(KategoriePartnera.DODAVATEL)
        root.addWidget(self._kategorie_combo)

        # Název
        self._nazev_input = LabeledLineEdit(
            "Název", placeholder="Název firmy nebo jméno", parent=self,
        )
        root.addWidget(self._nazev_input)

        # IČO + DIČ side by side
        ico_row = QHBoxLayout()
        ico_row.setContentsMargins(0, 0, 0, 0)
        ico_row.setSpacing(Spacing.S3)
        self._ico_input = LabeledLineEdit(
            "IČO", placeholder="12345678", max_length=8, parent=self,
        )
        self._dic_input = LabeledLineEdit(
            "DIČ", placeholder="CZ12345678", parent=self,
        )
        ico_row.addWidget(self._ico_input, stretch=1)
        ico_row.addWidget(self._dic_input, stretch=1)
        root.addLayout(ico_row)

        # Adresa
        self._adresa_input = LabeledLineEdit(
            "Adresa", placeholder="Ulice, Město, PSČ", parent=self,
        )
        root.addWidget(self._adresa_input)

        # Email + Telefon
        contact_row = QHBoxLayout()
        contact_row.setContentsMargins(0, 0, 0, 0)
        contact_row.setSpacing(Spacing.S3)
        self._email_input = LabeledLineEdit(
            "Email", placeholder="firma@example.com", parent=self,
        )
        self._telefon_input = LabeledLineEdit(
            "Telefon", placeholder="+420 ...", parent=self,
        )
        contact_row.addWidget(self._email_input, stretch=1)
        contact_row.addWidget(self._telefon_input, stretch=1)
        root.addLayout(contact_row)

        # Bankovní účet
        self._bank_ucet_input = LabeledLineEdit(
            "Bankovní účet", placeholder="123456789/0800", parent=self,
        )
        root.addWidget(self._bank_ucet_input)

        # Poznámka
        self._poznamka_input = LabeledLineEdit(
            "Poznámka", placeholder="Volitelná poznámka", parent=self,
        )
        root.addWidget(self._poznamka_input)

        # Společník sekce
        self._spolecnik_section = QWidget(self)
        sp_layout = QVBoxLayout(self._spolecnik_section)
        sp_layout.setContentsMargins(0, Spacing.S2, 0, 0)
        sp_layout.setSpacing(Spacing.S2)

        sp_header = QLabel("Společník", self)
        sp_header.setProperty("class", "form-section-header")
        sp_layout.addWidget(sp_header)

        self._podil_input = LabeledLineEdit(
            "Podíl (%)", placeholder="90", parent=self._spolecnik_section,
        )
        sp_layout.addWidget(self._podil_input)

        ucty_row = QHBoxLayout()
        ucty_row.setContentsMargins(0, 0, 0, 0)
        ucty_row.setSpacing(Spacing.S3)
        self._ucet_pohl_input = LabeledLineEdit(
            "Účet pohledávka", placeholder="355.001",
            parent=self._spolecnik_section,
        )
        self._ucet_zav_input = LabeledLineEdit(
            "Účet závazek", placeholder="365.001",
            parent=self._spolecnik_section,
        )
        ucty_row.addWidget(self._ucet_pohl_input, stretch=1)
        ucty_row.addWidget(self._ucet_zav_input, stretch=1)
        sp_layout.addLayout(ucty_row)

        self._spolecnik_section.setVisible(False)
        root.addWidget(self._spolecnik_section)

        # Error
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        root.addStretch(1)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch(1)

        cancel = QPushButton("Zrušit", self)
        cancel.setProperty("class", "secondary")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)

        self._submit_button = QPushButton("Uložit", self)
        self._submit_button.setProperty("class", "primary")
        self._submit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit_button.clicked.connect(self._on_submit)
        footer.addWidget(self._submit_button)

        root.addLayout(footer)

    def _wire_signals(self) -> None:
        self._kategorie_combo.current_value_changed.connect(
            self._on_kategorie_changed,
        )

    def _on_kategorie_changed(self, value: object) -> None:
        is_spolecnik = value == KategoriePartnera.SPOLECNIK
        self._spolecnik_section.setVisible(is_spolecnik)

    def _prefill(self, data: PartnerDialogResult) -> None:
        self._kategorie_combo.set_value(data.kategorie)
        self._nazev_input.set_value(data.nazev)
        if data.ico:
            self._ico_input.set_value(data.ico)
        if data.dic:
            self._dic_input.set_value(data.dic)
        if data.adresa:
            self._adresa_input.set_value(data.adresa)
        if data.email:
            self._email_input.set_value(data.email)
        if data.telefon:
            self._telefon_input.set_value(data.telefon)
        if data.bankovni_ucet:
            self._bank_ucet_input.set_value(data.bankovni_ucet)
        if data.poznamka:
            self._poznamka_input.set_value(data.poznamka)
        if data.podil_procent is not None:
            self._podil_input.set_value(str(data.podil_procent))
        if data.ucet_pohledavka:
            self._ucet_pohl_input.set_value(data.ucet_pohledavka)
        if data.ucet_zavazek:
            self._ucet_zav_input.set_value(data.ucet_zavazek)
        self._on_kategorie_changed(data.kategorie)

    def _on_submit(self) -> None:
        self._nazev_input.set_error(None)
        self._error_label.setVisible(False)

        nazev = self._nazev_input.value().strip()
        if not nazev:
            self._nazev_input.set_error("Název je povinný.")
            return

        kategorie = self._kategorie_combo.value()
        if not isinstance(kategorie, KategoriePartnera):
            return

        ico = self._ico_input.value().strip() or None
        dic = self._dic_input.value().strip() or None
        adresa = self._adresa_input.value().strip() or None
        email = self._email_input.value().strip() or None
        telefon = self._telefon_input.value().strip() or None
        bank = self._bank_ucet_input.value().strip() or None
        poznamka = self._poznamka_input.value().strip() or None

        podil: Decimal | None = None
        ucet_pohl: str | None = None
        ucet_zav: str | None = None

        if kategorie == KategoriePartnera.SPOLECNIK:
            podil_raw = self._podil_input.value().strip()
            if not podil_raw:
                self._error_label.setText("Společník musí mít vyplněný podíl.")
                self._error_label.setVisible(True)
                return
            try:
                podil = Decimal(podil_raw)
            except InvalidOperation:
                self._error_label.setText("Podíl musí být číslo.")
                self._error_label.setVisible(True)
                return
            ucet_pohl = self._ucet_pohl_input.value().strip() or None
            ucet_zav = self._ucet_zav_input.value().strip() or None

        self.result = PartnerDialogResult(
            nazev=nazev,
            kategorie=kategorie,
            ico=ico,
            dic=dic,
            adresa=adresa,
            bankovni_ucet=bank,
            email=email,
            telefon=telefon,
            poznamka=poznamka,
            podil_procent=podil,
            ucet_pohledavka=ucet_pohl,
            ucet_zavazek=ucet_zav,
        )
        self.accept()
