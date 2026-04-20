"""DokladFormDialog — modální okno pro vytvoření nového dokladu.

Zobrazuje pole: Typ, Číslo, Datum vystavení, Datum splatnosti (clearable),
Částka celkem, Popis (vícedroádkový). Při otevření se z ViewModelu
vyžádá navrhované číslo pro zvolený typ + aktuální rok.

Submit → ``DokladFormViewModel.submit(CreateDokladInput)`` → při úspěchu
``accept()`` s výsledným DTO dostupným přes ``.created_item``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import cast

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from typing import Protocol, runtime_checkable

from domain.doklady.typy import DphRezim, Mena, TypDokladu
from domain.partneri.partner import KategoriePartnera
from domain.shared.money import Money
from infrastructure.ocr.invoice_parser import ParsedInvoice
from services.commands.create_doklad import CreateDokladInput
from services.queries.doklady_list import DokladyListItem
from services.queries.partneri_list import PartneriListItem
from ui.design_tokens import Spacing
from ui.dialogs.partner_dialog import PartnerDialog
from ui.viewmodels.doklad_form_vm import DokladFormViewModel
from ui.widgets.badge import typ_display_text
from ui.widgets.labeled_inputs import (
    LabeledComboBox,
    LabeledDateEdit,
    LabeledLineEdit,
    LabeledMoneyEdit,
    LabeledTextEdit,
)
from ui.widgets.partner_selector import PartnerSelector
from ui.widgets.pdf_upload_zone import PdfUploadZone


@runtime_checkable
class PdfParserCallback(Protocol):
    """Callback: cesta k PDF → ParsedInvoice | None."""
    def __call__(self, path: str) -> ParsedInvoice | None: ...


@runtime_checkable
class PrilohaUploaderCallback(Protocol):
    """Callback: (doklad_id, cesta) → None — přiloží PDF k dokladu."""
    def __call__(self, doklad_id: int, path: str) -> None: ...


class DuplikatPrefill:
    """Data pro předvyplnění formuláře při duplikování dokladu."""

    __slots__ = (
        "zdrojove_cislo", "typ", "datum_vystaveni", "partner_id",
        "castka_celkem", "mena", "castka_mena", "kurz", "dph_rezim",
        "popis", "nove_cislo",
    )

    def __init__(
        self,
        zdrojove_cislo: str,
        typ: TypDokladu,
        nove_cislo: str,
        datum_vystaveni: "date | None" = None,
        partner_id: int | None = None,
        castka_celkem: Money | None = None,
        mena: Mena = Mena.CZK,
        castka_mena: Money | None = None,
        kurz: "Decimal | None" = None,
        dph_rezim: "DphRezim" = DphRezim.TUZEMSKO,
        popis: str | None = None,
    ) -> None:
        self.zdrojove_cislo = zdrojove_cislo
        self.typ = typ
        self.nove_cislo = nove_cislo
        self.datum_vystaveni = datum_vystaveni
        self.partner_id = partner_id
        self.castka_celkem = castka_celkem
        self.mena = mena
        self.castka_mena = castka_mena
        self.kurz = kurz
        self.dph_rezim = dph_rezim
        self.popis = popis


class DokladFormDialog(QDialog):
    """Modální dialog pro vytvoření nového dokladu."""

    def __init__(
        self,
        view_model: DokladFormViewModel,
        partner_items: list[PartneriListItem] | None = None,
        on_partner_created: object = None,
        preset_typ: TypDokladu | None = None,
        pdf_parser: PdfParserCallback | None = None,
        priloha_uploader: PrilohaUploaderCallback | None = None,
        duplikat_prefill: DuplikatPrefill | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nový doklad")
        self.setModal(True)
        self.setProperty("class", "doklad-form")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.resize(520, 700)

        self._vm = view_model
        self._partner_items = partner_items or []
        self._on_partner_created = on_partner_created
        self._preset_typ = preset_typ
        self._pdf_parser = pdf_parser
        self._priloha_uploader = priloha_uploader
        self._duplikat_prefill = duplikat_prefill
        self._created_item: DokladyListItem | None = None
        self._selected_pdf_path: str | None = None

        self._spolecnici_items = [
            p for p in self._partner_items
            if p.kategorie == KategoriePartnera.SPOLECNIK
        ]

        # Widgety — inicializace v _build_ui
        self._partner_selector: PartnerSelector
        self._typ_combo: LabeledComboBox
        self._cislo_input: LabeledLineEdit
        self._datum_vystaveni: LabeledDateEdit
        self._datum_splatnosti: LabeledDateEdit
        self._castka_input: LabeledMoneyEdit
        self._mena_combo: LabeledComboBox
        self._castka_mena_input: LabeledMoneyEdit
        self._kurz_input: LabeledLineEdit
        self._prepocet_label: QLabel
        self._mena_section: QWidget
        self._spolecnik_check: QCheckBox
        self._spolecnik_combo: LabeledComboBox
        self._spolecnik_section: QWidget
        self._popis_input: LabeledTextEdit
        self._k_doreseni_check: QCheckBox
        self._poznamka_doreseni_input: LabeledTextEdit
        self._error_label: QLabel
        self._submit_button: QPushButton
        self._cancel_button: QPushButton

        self._build_ui()
        self._wire_signals()
        if self._duplikat_prefill is not None:
            self._apply_duplikat_prefill()
        else:
            self._initial_suggest_cislo()

    # ─── Public API ──────────────────────────────────────────────

    @property
    def created_item(self) -> DokladyListItem | None:
        """DTO vytvořeného dokladu po accept() — jinak None."""
        return self._created_item

    # ─── Test-only accessors ─────────────────────────────────────

    @property
    def _typ_combo_widget(self) -> LabeledComboBox:
        return self._typ_combo

    @property
    def _cislo_widget(self) -> LabeledLineEdit:
        return self._cislo_input

    @property
    def _castka_widget(self) -> LabeledMoneyEdit:
        return self._castka_input

    @property
    def _submit_widget(self) -> QPushButton:
        return self._submit_button

    @property
    def _error_widget(self) -> QLabel:
        return self._error_label

    @property
    def _k_doreseni_check_widget(self) -> QCheckBox:
        return self._k_doreseni_check

    @property
    def _poznamka_doreseni_widget(self) -> LabeledTextEdit:
        return self._poznamka_doreseni_input

    @property
    def _mena_combo_widget(self) -> LabeledComboBox:
        return self._mena_combo

    @property
    def _castka_mena_widget(self) -> LabeledMoneyEdit:
        return self._castka_mena_input

    @property
    def _kurz_widget(self) -> LabeledLineEdit:
        return self._kurz_input

    @property
    def _prepocet_widget(self) -> QLabel:
        return self._prepocet_label

    @property
    def _mena_section_widget(self) -> QWidget:
        return self._mena_section

    @property
    def _spolecnik_check_widget(self) -> QCheckBox:
        return self._spolecnik_check

    @property
    def _spolecnik_combo_widget(self) -> LabeledComboBox:
        return self._spolecnik_combo

    @property
    def _spolecnik_section_widget(self) -> QWidget:
        return self._spolecnik_section

    # ─── Build ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        title = QLabel("Nový doklad", self)
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        # Duplikát banner (viditelný jen při duplikování)
        self._duplikat_banner = QLabel("", self)
        self._duplikat_banner.setProperty("class", "doreseni-box")
        self._duplikat_banner.setWordWrap(True)
        self._duplikat_banner.setContentsMargins(
            Spacing.S3, Spacing.S2, Spacing.S3, Spacing.S2,
        )
        self._duplikat_banner.setVisible(False)
        root.addWidget(self._duplikat_banner)

        # PDF upload zona
        self._pdf_upload = PdfUploadZone(
            message="Přetáhni PDF faktury pro auto-vyplnění",
            parent=self,
        )
        self._pdf_status = QLabel("", self)
        self._pdf_status.setProperty("class", "form-help")
        self._pdf_status.setVisible(False)
        root.addWidget(self._pdf_upload)
        root.addWidget(self._pdf_status)

        # Typ
        self._typ_combo = LabeledComboBox("Typ dokladu", self)
        # BV se vytváří importem, ne ručně
        for t in TypDokladu:
            if t == TypDokladu.BANKOVNI_VYPIS:
                continue
            self._typ_combo.add_item(typ_display_text(t), t)
        if self._preset_typ is not None:
            self._typ_combo.set_value(self._preset_typ)
            self._typ_combo.setVisible(False)
        else:
            self._typ_combo.set_value(TypDokladu.FAKTURA_VYDANA)
        root.addWidget(self._typ_combo)

        # Partner selector
        self._partner_selector = PartnerSelector(self)
        self._partner_selector.set_items(self._partner_items)
        root.addWidget(self._partner_selector)

        # Variabilní symbol
        self._vs_input = LabeledLineEdit(
            "Variabilní symbol (nepovinné)",
            placeholder="např. 20250044",
            max_length=10,
            parent=self,
        )
        root.addWidget(self._vs_input)

        # Číslo — prefilled, editovatelné
        self._cislo_input = LabeledLineEdit(
            "Číslo dokladu",
            placeholder="FV-2026-001",
            max_length=50,
            parent=self,
        )
        root.addWidget(self._cislo_input)

        # Datum vystavení + splatnosti (side by side)
        date_row = QHBoxLayout()
        date_row.setContentsMargins(0, 0, 0, 0)
        date_row.setSpacing(Spacing.S3)

        self._datum_vystaveni = LabeledDateEdit("Datum vystavení", parent=self)
        self._datum_vystaveni.set_value(date.today())
        date_row.addWidget(self._datum_vystaveni, stretch=1)

        self._datum_splatnosti = LabeledDateEdit(
            "Datum splatnosti (nepovinné)", clearable=True, parent=self,
        )
        self._datum_splatnosti.set_value(None)
        date_row.addWidget(self._datum_splatnosti, stretch=1)

        root.addLayout(date_row)

        # Částka
        self._castka_input = LabeledMoneyEdit(
            "Částka celkem (Kč)", placeholder="0,00", parent=self,
        )
        root.addWidget(self._castka_input)

        # ── Sekce Měna ──
        self._mena_combo = LabeledComboBox("Měna", self)
        for m in Mena:
            self._mena_combo.add_item(m.value, m)
        self._mena_combo.set_value(Mena.CZK)
        root.addWidget(self._mena_combo)

        self._mena_section = QWidget(self)
        mena_layout = QVBoxLayout(self._mena_section)
        mena_layout.setContentsMargins(0, 0, 0, 0)
        mena_layout.setSpacing(Spacing.S2)

        mena_row = QHBoxLayout()
        mena_row.setContentsMargins(0, 0, 0, 0)
        mena_row.setSpacing(Spacing.S3)

        self._castka_mena_input = LabeledMoneyEdit(
            "Částka v cizí měně", placeholder="0,00", parent=self._mena_section,
        )
        mena_row.addWidget(self._castka_mena_input, stretch=1)

        self._kurz_input = LabeledLineEdit(
            "Kurz ČNB (Kč/1 j.)", placeholder="25,100",
            parent=self._mena_section,
        )
        mena_row.addWidget(self._kurz_input, stretch=1)
        mena_layout.addLayout(mena_row)

        self._prepocet_label = QLabel("= 0,00 Kč", self._mena_section)
        self._prepocet_label.setProperty("class", "dialog-value")
        mena_layout.addWidget(self._prepocet_label)

        self._mena_section.setVisible(False)
        root.addWidget(self._mena_section)

        # ── Placeno společníkem ──
        self._spolecnik_section = QWidget(self)
        spol_layout = QVBoxLayout(self._spolecnik_section)
        spol_layout.setContentsMargins(0, 0, 0, 0)
        spol_layout.setSpacing(Spacing.S2)

        self._spolecnik_check = QCheckBox(
            "Placeno ze soukromé karty/účtu společníka", self._spolecnik_section,
        )
        self._spolecnik_check.setProperty("class", "form-check")
        self._spolecnik_check.setCursor(Qt.CursorShape.PointingHandCursor)
        spol_layout.addWidget(self._spolecnik_check)

        self._spolecnik_combo = LabeledComboBox(
            "Společník", self._spolecnik_section,
        )
        for sp in self._spolecnici_items:
            label = f"{sp.nazev} ({sp.podil_procent}%)" if sp.podil_procent else sp.nazev
            self._spolecnik_combo.add_item(label, sp.id)
        self._spolecnik_combo.setVisible(False)
        spol_layout.addWidget(self._spolecnik_combo)

        # Visible only for FP and PD
        typ_val = cast(TypDokladu | None, self._typ_combo.value())
        self._spolecnik_section.setVisible(
            typ_val in (TypDokladu.FAKTURA_PRIJATA, TypDokladu.POKLADNI_DOKLAD)
        )
        root.addWidget(self._spolecnik_section)

        # Popis
        self._popis_input = LabeledTextEdit(
            "Popis (nepovinné)",
            placeholder="Volitelný komentář k dokladu.",
            rows=3,
            parent=self,
        )
        root.addWidget(self._popis_input)

        # K dořešení — checkbox + poznámka (viditelná jen když zaškrtnuto)
        self._k_doreseni_check = QCheckBox(
            "Označit jako k dořešení", self,
        )
        self._k_doreseni_check.setProperty("class", "form-check")
        self._k_doreseni_check.setCursor(Qt.CursorShape.PointingHandCursor)
        root.addWidget(self._k_doreseni_check)

        self._poznamka_doreseni_input = LabeledTextEdit(
            "Poznámka k dořešení",
            placeholder="Proč vyžaduje pozornost? (nepovinné)",
            rows=2,
            parent=self,
        )
        self._poznamka_doreseni_input.setVisible(False)
        root.addWidget(self._poznamka_doreseni_input)

        # Error label — shown above buttons when submit fails
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        root.addStretch(1)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch(1)

        self._cancel_button = QPushButton("Zrušit", self)
        self._cancel_button.setProperty("class", "secondary")
        self._cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self._cancel_button)

        self._submit_button = QPushButton("Vytvořit doklad", self)
        self._submit_button.setProperty("class", "primary")
        self._submit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self._submit_button)

        root.addLayout(footer)

    def _wire_signals(self) -> None:
        self._pdf_upload.file_selected.connect(self._on_pdf_selected)
        self._typ_combo.current_value_changed.connect(self._on_typ_changed)
        self._partner_selector.new_partner_requested.connect(
            self._on_new_partner,
        )
        self._mena_combo.current_value_changed.connect(self._on_mena_changed)
        self._castka_mena_input.line_widget.editingFinished.connect(
            self._on_foreign_amount_changed,
        )
        self._kurz_input.text_changed.connect(
            lambda _: self._on_foreign_amount_changed(),
        )
        self._spolecnik_check.toggled.connect(self._on_spolecnik_toggled)
        self._submit_button.clicked.connect(self._on_submit)
        self._cancel_button.clicked.connect(self.reject)
        self._k_doreseni_check.toggled.connect(self._on_k_doreseni_toggled)

    def _on_k_doreseni_toggled(self, checked: bool) -> None:
        """Zobraz/skryj pole poznámky podle checkboxu."""
        self._poznamka_doreseni_input.setVisible(checked)

    def _on_pdf_selected(self, path: str) -> None:
        """PDF vybráno — uloží cestu a pokusí se o OCR auto-fill."""
        from pathlib import Path as _P
        self._selected_pdf_path = path
        name = _P(path).name
        self._pdf_status.setText(f"📎 {name}")
        self._pdf_status.setVisible(True)

        if self._pdf_parser is None:
            return
        parsed = self._pdf_parser(path)
        if parsed is None:
            return
        self._autofill_from_parsed(parsed)

    def _autofill_from_parsed(self, parsed: ParsedInvoice) -> None:
        """Vyplní formulářová pole z ParsedInvoice (přepíše jen prázdná)."""
        if parsed.typ_dokladu is not None and self._preset_typ is None:
            self._typ_combo.set_value(parsed.typ_dokladu)
            # Suggest číslo pro nový typ
            cislo = self._vm.suggest_cislo(
                parsed.typ_dokladu, self._vm.ucetni_rok,
            )
            self._cislo_input.set_value(cislo)

        if parsed.datum_vystaveni is not None:
            self._datum_vystaveni.set_value(parsed.datum_vystaveni)

        if parsed.datum_splatnosti is not None:
            self._datum_splatnosti.set_value(parsed.datum_splatnosti)

        if parsed.castka_celkem is not None:
            self._castka_input.set_value(parsed.castka_celkem)

        if parsed.variabilni_symbol:
            self._vs_input.set_value(parsed.variabilni_symbol)

        if parsed.mena != Mena.CZK:
            self._mena_combo.set_value(parsed.mena)
            if parsed.castka_mena is not None:
                self._castka_mena_input.set_value(parsed.castka_mena)
            if parsed.kurz is not None:
                self._kurz_input.set_value(str(parsed.kurz).replace(".", ","))

        # Popis z dodavatele + čísla dokladu
        parts = []
        if parsed.dodavatel_nazev:
            parts.append(parsed.dodavatel_nazev)
        if parsed.cislo_dokladu:
            parts.append(parsed.cislo_dokladu)
        if parts and not self._popis_input.value().strip():
            self._popis_input.set_value(" – ".join(parts))

        self._pdf_status.setText(
            f"📎 {self._pdf_status.text().lstrip('📎 ').strip()} — auto-vyplněno"
        )

    # ─── Slots ────────────────────────────────────────────────────

    def _apply_duplikat_prefill(self) -> None:
        """Předvyplní formulář daty z duplikovaného dokladu."""
        pf = self._duplikat_prefill
        if pf is None:
            return

        # Banner
        self._duplikat_banner.setText(
            f"\u26A0 Duplikát dokladu {pf.zdrojove_cislo} — "
            "zkontroluj datum, VS, částku a PDF před uložením"
        )
        self._duplikat_banner.setVisible(True)

        # Typ
        self._typ_combo.set_value(pf.typ)
        if self._preset_typ is not None:
            self._typ_combo.setVisible(False)

        # Číslo
        self._cislo_input.set_value(pf.nove_cislo)

        # Partner
        if pf.partner_id is not None:
            self._partner_selector.set_selected_id(pf.partner_id)

        # Částka
        if pf.castka_celkem is not None:
            self._castka_input.set_value(pf.castka_celkem)

        # Měna
        if pf.mena != Mena.CZK:
            self._mena_combo.set_value(pf.mena)
            if pf.castka_mena is not None:
                self._castka_mena_input.set_value(pf.castka_mena)
            if pf.kurz is not None:
                self._kurz_input.set_value(str(pf.kurz).replace(".", ","))

        # Popis
        if pf.popis:
            self._popis_input.set_value(pf.popis)

        # K dořešení — zaškrtnuto s poznámkou
        self._k_doreseni_check.setChecked(True)
        self._poznamka_doreseni_input.set_value(
            f"Duplikát dokladu {pf.zdrojove_cislo}. "
            "Zkontroluj: datum, VS, částku, PDF."
        )

        # VS: prázdné s placeholder "Doplň VS!"
        self._vs_input.set_value("")
        self._vs_input.line_widget.setPlaceholderText("Doplň VS!")

        # Datum vystavení: z zdrojového dokladu (editovatelné), žlutý border
        if pf.datum_vystaveni is not None:
            self._datum_vystaveni.set_value(pf.datum_vystaveni)
        self._datum_vystaveni.inner_widget.setStyleSheet(
            "border: 2px solid #D97706;"  # warning-600
        )

    def _initial_suggest_cislo(self) -> None:
        typ = cast(TypDokladu | None, self._typ_combo.value())
        if typ is None:
            return
        cislo = self._vm.suggest_cislo(typ, self._vm.ucetni_rok)
        self._cislo_input.set_value(cislo)

    def _on_new_partner(self) -> None:
        """Inline vytvoření partnera z dropdown."""
        dialog = PartnerDialog(parent=self)
        if dialog.exec() and dialog.result is not None:
            if callable(self._on_partner_created):
                new_partner = self._on_partner_created(dialog.result)
                if new_partner is not None:
                    # Refresh items and select the new one
                    self._partner_items.append(new_partner)
                    self._partner_selector.set_items(self._partner_items)
                    self._partner_selector.set_selected_id(new_partner.id)

    def _on_mena_changed(self, value: object) -> None:
        if not isinstance(value, Mena):
            return
        is_foreign = value != Mena.CZK
        self._mena_section.setVisible(is_foreign)
        # When switching to CZK, make castka editable again
        self._castka_input.line_widget.setReadOnly(is_foreign)
        if not is_foreign:
            self._prepocet_label.setText("= 0,00 Kč")
        else:
            self._on_foreign_amount_changed()

    def _on_foreign_amount_changed(self) -> None:
        castka_mena = self._castka_mena_input.value()
        kurz_text = self._kurz_input.value().strip().replace(",", ".")
        try:
            kurz = Decimal(kurz_text) if kurz_text else None
        except InvalidOperation:
            kurz = None

        if castka_mena is not None and kurz is not None and kurz > 0:
            czk = castka_mena * kurz
            self._prepocet_label.setText(f"= {czk.format_cz()}")
            self._castka_input.set_value(czk)
        else:
            self._prepocet_label.setText("= ? Kč")

    def _on_spolecnik_toggled(self, checked: bool) -> None:
        self._spolecnik_combo.setVisible(checked)

    def _on_typ_changed(self, value: object) -> None:
        if not isinstance(value, TypDokladu):
            return
        cislo = self._vm.suggest_cislo(value, self._vm.ucetni_rok)
        self._cislo_input.set_value(cislo)
        # Show společník section only for FP and PD
        self._spolecnik_section.setVisible(
            value in (TypDokladu.FAKTURA_PRIJATA, TypDokladu.POKLADNI_DOKLAD)
        )

    def _on_submit(self) -> None:
        # Vyresetuj error badges
        self._cislo_input.set_error(None)
        self._castka_input.set_error(None)
        self._castka_mena_input.set_error(None)
        self._kurz_input.set_error(None)
        self._error_label.setVisible(False)

        typ = cast(TypDokladu | None, self._typ_combo.value())
        cislo = self._cislo_input.value().strip()
        datum_vystaveni = self._datum_vystaveni.value()
        datum_splatnosti = self._datum_splatnosti.value()
        castka = self._castka_input.value()
        popis = self._popis_input.value().strip() or None

        # Client-side validace
        has_error = False
        if not cislo:
            self._cislo_input.set_error("Číslo dokladu je povinné.")
            has_error = True
        if castka is None:
            self._castka_input.set_error("Zadej částku (např. 12100 nebo 12100,50).")
            has_error = True
        if typ is None or datum_vystaveni is None:
            self._show_form_error("Vyplň typ a datum vystavení.")
            has_error = True
        if has_error:
            return

        # Type narrowing — po guardu výše víme, že nejsou None
        assert typ is not None
        assert datum_vystaveni is not None
        assert castka is not None

        # Měna
        mena = cast(Mena | None, self._mena_combo.value()) or Mena.CZK
        castka_mena_val: "Money | None" = None
        kurz_val: Decimal | None = None
        if mena != Mena.CZK:
            castka_mena_val = self._castka_mena_input.value()
            kurz_text = self._kurz_input.value().strip().replace(",", ".")
            try:
                kurz_val = Decimal(kurz_text) if kurz_text else None
            except InvalidOperation:
                kurz_val = None
            if castka_mena_val is None:
                self._castka_mena_input.set_error("Částka v cizí měně je povinná.")
                has_error = True
            if kurz_val is None or kurz_val <= 0:
                self._kurz_input.set_error("Kurz je povinný a musí být kladný.")
                has_error = True
            if has_error:
                return

        vs_raw = self._vs_input.value().strip() or None
        data = CreateDokladInput(
            cislo=cislo,
            typ=typ,
            datum_vystaveni=datum_vystaveni,
            datum_splatnosti=datum_splatnosti,
            castka_celkem=castka,
            popis=popis,
            partner_id=self._partner_selector.selected_id(),
            mena=mena,
            castka_mena=castka_mena_val,
            kurz=kurz_val,
            variabilni_symbol=vs_raw,
        )

        k_doreseni = self._k_doreseni_check.isChecked()
        poznamka = None
        if k_doreseni:
            raw = self._poznamka_doreseni_input.value().strip()
            poznamka = raw or None

        item = self._vm.submit(
            data,
            k_doreseni=k_doreseni,
            poznamka_doreseni=poznamka,
        )
        if item is None:
            self._show_form_error(
                self._vm.error or "Vytvoření dokladu selhalo.",
            )
            return
        self._created_item = item

        # Přiloží PDF k nově vytvořenému dokladu
        if (
            self._selected_pdf_path is not None
            and self._priloha_uploader is not None
            and item.id is not None
        ):
            try:
                self._priloha_uploader(item.id, self._selected_pdf_path)
            except Exception:
                pass  # PDF se nepodařilo přiložit — doklad je stále platný

        self.accept()

    def _show_form_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)
