"""OcrUploadDetailDialog — side-by-side PDF preview + editovatelný formulář.

Levá strana: náhled PDF (první strana) nebo obrázku.
Pravá strana: OCR data + editovatelná pole + tlačítka schválit/zamítnout.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from domain.doklady.typy import Mena, TypDokladu
from domain.shared.money import Money

#: Číselné řady pro FAKTURA_PRIJATA — klasická vs reverse charge.
RADA_FP = "FP"
RADA_FPR = "FPR"
from services.queries.ocr_inbox import OcrInboxItem
from services.queries.partneri_list import PartneriListItem
from ui.design_tokens import Colors, Spacing
from ui.widgets.labeled_inputs import (
    LabeledComboBox,
    LabeledDateEdit,
    LabeledLineEdit,
    LabeledMoneyEdit,
    LabeledTextEdit,
)
from ui.widgets.partner_selector import PartnerSelector
from ui.widgets.pdf_viewer import PdfViewerWidget


class OcrUploadDetailDialog(QDialog):
    """Detail uploadu — side-by-side PDF preview + formulář."""

    def __init__(
        self,
        item: OcrInboxItem,
        file_path: str | None = None,
        default_datum_loader: object = None,
        partner_items: list[PartneriListItem] | None = None,
        on_partner_created: object = None,
        next_cislo_loader: Callable[[str, int], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._item = item
        self._file_path = file_path
        self._default_datum_loader = default_datum_loader
        self._partner_items = partner_items or []
        self._on_partner_created = on_partner_created
        self._next_cislo_loader = next_cislo_loader
        self._result_action: str | None = None  # "approve" | "reject" | None

        self.setWindowTitle(f"Detail: {item.file_name}")
        self.setMinimumSize(900, 600)

        self._pdf_viewer: PdfViewerWidget
        self._cislo_input: LabeledLineEdit
        self._typ_combo: LabeledComboBox
        self._rada_combo: LabeledComboBox
        self._partner_selector: PartnerSelector
        self._datum_input: LabeledDateEdit
        self._castka_input: LabeledMoneyEdit
        self._mena_combo: LabeledComboBox
        self._castka_mena_input: LabeledLineEdit
        self._kurz_input: LabeledLineEdit
        self._dodavatel_input: LabeledLineEdit
        self._popis_input: LabeledTextEdit
        self._pytlovani_warning: QLabel
        self._ocr_info: QLabel
        self._mena_error: QLabel

        self._build_ui()
        self._populate()
        self._wire_datum_to_cislo()
        self._wire_mena_signals()

    @property
    def result_action(self) -> str | None:
        return self._result_action

    @property
    def cislo(self) -> str:
        return self._cislo_input.value().strip()

    @property
    def typ(self) -> TypDokladu:
        val = self._typ_combo.value()
        return val if val else TypDokladu.FAKTURA_PRIJATA

    @property
    def datum_vystaveni(self) -> date:
        return self._datum_input.value() or date.today()

    @property
    def castka_celkem(self) -> Money:
        return self._castka_input.value() or Money(0)

    @property
    def popis(self) -> str:
        return self._popis_input.value().strip()

    @property
    def partner_id(self) -> int | None:
        return self._partner_selector.selected_id()

    @property
    def variabilni_symbol(self) -> str | None:
        val = self._vs_input.value().strip()
        return val if val else None

    @property
    def je_vystavena(self) -> bool | None:
        """Pro ZF: True/False; pro non-ZF: None."""
        if self.typ != TypDokladu.ZALOHA_FAKTURA:
            return None
        val = self._zaloha_combo.value()
        return True if val is None else val

    @property
    def mena(self) -> Mena:
        val = self._mena_combo.value()
        return val if val else Mena.CZK

    @property
    def castka_mena(self) -> Money | None:
        """Částka v cizí měně (jen pro EUR/USD), jinak None."""
        if self.mena == Mena.CZK:
            return None
        text = self._castka_mena_input.value().strip()
        if not text:
            return None
        try:
            return Money.from_koruny(text)
        except (ValueError, TypeError):
            return None

    @property
    def kurz(self) -> Decimal | None:
        """Kurz cizí měny (CZK / 1 jednotka). None pro CZK."""
        if self.mena == Mena.CZK:
            return None
        text = self._kurz_input.value().strip()
        if not text:
            return None
        try:
            return Decimal(text.replace(",", "."))
        except (InvalidOperation, ValueError):
            return None

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S4, Spacing.S4, Spacing.S4, Spacing.S4,
        )

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left: preview via PdfViewerWidget
        self._pdf_viewer = PdfViewerWidget(parent=splitter)
        self._pdf_viewer.set_placeholder("Načítám náhled...")
        splitter.addWidget(self._pdf_viewer)

        # Right: form
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(Spacing.S3, 0, 0, 0)

        form_title = QLabel("OCR data", right)
        form_title.setProperty("class", "section-title")
        right_layout.addWidget(form_title)

        # OCR info
        self._ocr_info = QLabel("", right)
        self._ocr_info.setProperty("class", "form-help")
        self._ocr_info.setWordWrap(True)
        right_layout.addWidget(self._ocr_info)

        # Pytlování warning
        self._pytlovani_warning = QLabel("", right)
        self._pytlovani_warning.setProperty("class", "dialog-error")
        self._pytlovani_warning.setWordWrap(True)
        self._pytlovani_warning.setVisible(False)
        right_layout.addWidget(self._pytlovani_warning)

        # Form
        self._typ_combo = LabeledComboBox("Typ dokladu")
        self._typ_combo.add_item("Faktura přijatá", TypDokladu.FAKTURA_PRIJATA)
        self._typ_combo.add_item("Faktura vydaná", TypDokladu.FAKTURA_VYDANA)
        self._typ_combo.add_item(
            "Zálohová faktura", TypDokladu.ZALOHA_FAKTURA,
        )
        self._typ_combo.add_item("Pokladní doklad", TypDokladu.POKLADNI_DOKLAD)
        self._typ_combo.add_item("Interní doklad", TypDokladu.INTERNI_DOKLAD)
        right_layout.addWidget(self._typ_combo)

        # Druh zálohy — visible jen pro ZALOHA_FAKTURA
        self._zaloha_combo = LabeledComboBox("Druh zálohy")
        self._zaloha_combo.add_item("Vystavená (odběrateli)", True)
        self._zaloha_combo.add_item("Přijatá (od dodavatele)", False)
        self._zaloha_combo.set_value(True)
        self._zaloha_combo.setVisible(False)
        right_layout.addWidget(self._zaloha_combo)

        # Číselná řada — visible jen pro FAKTURA_PRIJATA
        self._rada_combo = LabeledComboBox("Číselná řada")
        self._rada_combo.add_item("FP — klasická faktura", RADA_FP)
        self._rada_combo.add_item("FPR — reverse charge (EU)", RADA_FPR)
        self._rada_combo.set_value(RADA_FP)
        right_layout.addWidget(self._rada_combo)

        self._cislo_input = LabeledLineEdit("Číslo dokladu", max_length=50)
        right_layout.addWidget(self._cislo_input)

        self._dodavatel_input = LabeledLineEdit("Dodavatel", max_length=200)
        right_layout.addWidget(self._dodavatel_input)

        self._partner_selector = PartnerSelector(right)
        self._partner_selector.set_items(self._partner_items)
        self._partner_selector.new_partner_requested.connect(
            self._on_new_partner,
        )
        right_layout.addWidget(self._partner_selector)

        self._datum_input = LabeledDateEdit("Datum vystavení")
        right_layout.addWidget(self._datum_input)

        # Měna + kurzové pole — pro EUR/USD se ukáží další 2 inputy
        self._mena_combo = LabeledComboBox("Měna")
        self._mena_combo.add_item("CZK (Kč)", Mena.CZK)
        self._mena_combo.add_item("EUR", Mena.EUR)
        self._mena_combo.add_item("USD", Mena.USD)
        self._mena_combo.set_value(Mena.CZK)
        right_layout.addWidget(self._mena_combo)

        # Castka v cizí měně + kurz — vedle sebe v jedné řadě
        cizi_row = QHBoxLayout()
        cizi_row.setSpacing(Spacing.S2)
        self._castka_mena_input = LabeledLineEdit(
            "Částka v cizí měně", placeholder="123,45",
        )
        self._castka_mena_input.setVisible(False)
        cizi_row.addWidget(self._castka_mena_input)
        self._kurz_input = LabeledLineEdit(
            "Kurz (CZK za 1 jednotku)", placeholder="25,00",
        )
        self._kurz_input.setVisible(False)
        cizi_row.addWidget(self._kurz_input)
        right_layout.addLayout(cizi_row)

        self._castka_input = LabeledMoneyEdit("Částka celkem (Kč)")
        right_layout.addWidget(self._castka_input)

        # Mena error (pro EUR/USD bez kurzu)
        self._mena_error = QLabel("", right)
        self._mena_error.setProperty("class", "dialog-error")
        self._mena_error.setWordWrap(True)
        self._mena_error.setVisible(False)
        right_layout.addWidget(self._mena_error)

        self._vs_input = LabeledLineEdit(
            "Variabilní symbol", max_length=10,
        )
        right_layout.addWidget(self._vs_input)

        self._popis_input = LabeledTextEdit("Poznámka", rows=3)
        right_layout.addWidget(self._popis_input)

        right_layout.addStretch(1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(Spacing.S2)

        btn_approve = QPushButton("Uložit jako NOVÝ", right)
        btn_approve.setProperty("class", "primary")
        btn_approve.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_approve.clicked.connect(self._on_approve)
        btn_row.addWidget(btn_approve)

        btn_reject = QPushButton("Zamítnout", right)
        btn_reject.setProperty("class", "danger-sm")
        btn_reject.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reject.clicked.connect(self._on_reject)
        btn_row.addWidget(btn_reject)

        btn_row.addStretch(1)

        btn_close = QPushButton("Zavřít", right)
        btn_close.setProperty("class", "secondary")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)

        right_layout.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setSizes([450, 450])

        root.addWidget(splitter)

    def _populate(self) -> None:
        """Naplní formulář daty z OcrInboxItem."""
        item = self._item

        # OCR info
        method = item.ocr_method or "?"
        confidence = item.ocr_confidence if item.ocr_confidence is not None else "?"
        self._ocr_info.setText(
            f"OCR metoda: {method} | Spolehlivost: {confidence} %"
        )

        # Pytlování
        if item.is_pytlovani:
            self._pytlovani_warning.setText(
                f"⚠ PYTLOVÁNÍ: Faktura vystavena na společníka "
                f"{item.pytlovani_jmeno}. Zkontrolujte, zda jde o firemní náklad."
            )
            self._pytlovani_warning.setVisible(True)

        # Typ
        if item.parsed_typ:
            try:
                typ = TypDokladu(item.parsed_typ)
                self._typ_combo.set_value(typ)
            except ValueError:
                pass

        # Fallback datum: poslední doklad z DB, nebo date.today()
        fallback_datum = date.today()
        if callable(self._default_datum_loader):
            try:
                fallback_datum = self._default_datum_loader()
            except Exception:  # noqa: BLE001
                pass

        # Cislo — vždy v naší číselné řadě (FP nebo FPR), ne z faktury.
        # Default řada: FPR pokud OCR detekoval RC, jinak FP.
        rok = item.parsed_datum.year if item.parsed_datum else fallback_datum.year
        if item.parsed_is_reverse_charge:
            self._rada_combo.set_value(RADA_FPR)
        else:
            self._rada_combo.set_value(RADA_FP)
        # Visibilita řady — jen pro FAKTURA_PRIJATA
        self._sync_rada_visibility()
        # Naplň cislo přes loader
        self._refresh_cislo()

        # Dodavatel
        if item.parsed_dodavatel:
            self._dodavatel_input.set_value(item.parsed_dodavatel)

        # Datum
        if item.parsed_datum:
            self._datum_input.set_value(item.parsed_datum)
        else:
            self._datum_input.set_value(fallback_datum)

        # Castka
        if item.parsed_castka:
            self._castka_input.set_value(item.parsed_castka)

        # Variabilní symbol
        if item.parsed_vs:
            self._vs_input.set_value(item.parsed_vs)

        # Popis — smart: dodavatel + číslo, fallback na filename
        parts = [p for p in (item.parsed_dodavatel, item.parsed_cislo) if p]
        popis = " \u2013 ".join(parts) if parts else f"OCR: {item.file_name}"
        self._popis_input.set_value(popis)

        # Preview
        self._load_preview()

    def _load_preview(self) -> None:
        """Načte náhled PDF/obrázku přes PdfViewerWidget."""
        if not self._file_path:
            self._pdf_viewer.set_placeholder("Soubor není k dispozici")
            return

        path = Path(self._file_path)
        if not path.exists():
            self._pdf_viewer.set_placeholder("Soubor není k dispozici")
            return

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            self._pdf_viewer.load_pdf(path)
        elif suffix in (".jpg", ".jpeg", ".png"):
            self._pdf_viewer.load_image(path)
        else:
            self._pdf_viewer.set_placeholder(f"Nepodporovaný formát: {suffix}")

    def _wire_datum_to_cislo(self) -> None:
        """Při změně data, typu nebo řady regeneruj číslo dokladu."""
        self._datum_input.date_widget.textChanged.connect(
            lambda _t: self._refresh_cislo()
        )
        self._typ_combo.current_value_changed.connect(self._on_typ_changed)
        self._rada_combo.current_value_changed.connect(
            lambda _v: self._refresh_cislo()
        )

    def _on_typ_changed(self, _value: object) -> None:
        """Změna typu — sync visibility řady + Druhu zálohy + regenerace čísla."""
        self._sync_rada_visibility()
        self._sync_zaloha_visibility()
        self._refresh_cislo()

    def _sync_rada_visibility(self) -> None:
        """Combo Číselná řada se zobrazí jen pro FAKTURA_PRIJATA."""
        is_fp = self._typ_combo.value() == TypDokladu.FAKTURA_PRIJATA
        self._rada_combo.setVisible(is_fp)

    def _sync_zaloha_visibility(self) -> None:
        """Combo Druh zálohy se zobrazí jen pro ZALOHA_FAKTURA."""
        is_zf = self._typ_combo.value() == TypDokladu.ZALOHA_FAKTURA
        self._zaloha_combo.setVisible(is_zf)

    def _refresh_cislo(self) -> None:
        """Vygeneruj nové číslo z aktuální řady + roku přes loader.

        Pokud loader není k dispozici (testy), použije se uchycený fallback.
        """
        d = self._datum_input.value() if self._datum_input is not None else None
        rok = d.year if d else date.today().year
        # Pro non-FP typy (FV, PD, ID) se použije typ.value, jinak řada
        if self._typ_combo.value() == TypDokladu.FAKTURA_PRIJATA:
            prefix = self._rada_combo.value() or RADA_FP
        else:
            t = self._typ_combo.value()
            prefix = t.value if t else "FP"

        if callable(self._next_cislo_loader):
            try:
                new_cislo = self._next_cislo_loader(prefix, rok)
                self._cislo_input.set_value(new_cislo)
                return
            except Exception:  # noqa: BLE001
                pass
        # Fallback: prefix-rok-uploadID (3místný)
        self._cislo_input.set_value(f"{prefix}-{rok}-{self._item.id:04d}")

    def _wire_mena_signals(self) -> None:
        """Měna: toggle viditelnost EUR polí + auto-přepočet CZK = mena*kurz."""
        self._mena_combo.current_value_changed.connect(self._on_mena_changed)
        self._castka_mena_input.text_changed.connect(
            lambda _t: self._recalculate_czk(),
        )
        self._kurz_input.text_changed.connect(
            lambda _t: self._recalculate_czk(),
        )

    def _on_mena_changed(self, _value: object) -> None:
        is_cizi = self.mena != Mena.CZK
        self._castka_mena_input.setVisible(is_cizi)
        self._kurz_input.setVisible(is_cizi)
        self._castka_input.setEnabled(not is_cizi)
        if not is_cizi:
            self._mena_error.setVisible(False)
            self._castka_mena_input.set_value("")
            self._kurz_input.set_value("")
        self._recalculate_czk()

    def _recalculate_czk(self) -> None:
        """Pro EUR/USD: CZK = castka_mena * kurz, naplň do _castka_input."""
        if self.mena == Mena.CZK:
            return
        m = self.castka_mena
        k = self.kurz
        if m is None or k is None or k <= 0:
            self._mena_error.setText(
                "Zadejte částku v cizí měně i kurz (CZK za 1 jednotku)."
            )
            self._mena_error.setVisible(True)
            return
        self._mena_error.setVisible(False)
        czk = Money.from_koruny(m.to_koruny() * k)
        self._castka_input.set_value(czk)

    def _on_new_partner(self) -> None:
        """Inline vytvoření partnera."""
        from ui.dialogs.partner_dialog import PartnerDialog
        dialog = PartnerDialog(parent=self)
        if dialog.exec() and dialog.result is not None:
            if callable(self._on_partner_created):
                new_partner = self._on_partner_created(dialog.result)
                if new_partner is not None:
                    self._partner_items.append(new_partner)
                    self._partner_selector.set_items(self._partner_items)
                    self._partner_selector.set_selected_id(new_partner.id)

    def _on_approve(self) -> None:
        # Validace cizí měny
        if self.mena != Mena.CZK:
            if self.castka_mena is None:
                self._mena_error.setText(
                    "Pro cizí měnu vyplňte částku v cizí měně."
                )
                self._mena_error.setVisible(True)
                return
            if self.kurz is None or self.kurz <= 0:
                self._mena_error.setText(
                    "Pro cizí měnu vyplňte kladný kurz."
                )
                self._mena_error.setVisible(True)
                return
            # Auto-přepočet pro jistotu (možná uživatel manuálně přepsal CZK)
            self._recalculate_czk()
        self._result_action = "approve"
        self.accept()

    def _on_reject(self) -> None:
        self._result_action = "reject"
        self.accept()
