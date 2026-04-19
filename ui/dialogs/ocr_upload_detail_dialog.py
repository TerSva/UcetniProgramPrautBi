"""OcrUploadDetailDialog — side-by-side PDF preview + editovatelný formulář.

Levá strana: náhled PDF (první strana) nebo obrázku.
Pravá strana: OCR data + editovatelná pole + tlačítka schválit/zamítnout.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from domain.doklady.typy import TypDokladu
from domain.shared.money import Money
from services.queries.ocr_inbox import OcrInboxItem
from ui.design_tokens import Colors, Spacing
from ui.widgets.labeled_inputs import (
    LabeledComboBox,
    LabeledDateEdit,
    LabeledLineEdit,
    LabeledMoneyEdit,
    LabeledTextEdit,
)


class OcrUploadDetailDialog(QDialog):
    """Detail uploadu — side-by-side PDF preview + formulář."""

    def __init__(
        self,
        item: OcrInboxItem,
        file_path: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._item = item
        self._file_path = file_path
        self._result_action: str | None = None  # "approve" | "reject" | None

        self.setWindowTitle(f"Detail: {item.file_name}")
        self.setMinimumSize(900, 600)

        self._preview_label: QLabel
        self._cislo_input: LabeledLineEdit
        self._typ_combo: LabeledComboBox
        self._datum_input: LabeledDateEdit
        self._castka_input: LabeledMoneyEdit
        self._dodavatel_input: LabeledLineEdit
        self._popis_input: LabeledTextEdit
        self._pytlovani_warning: QLabel
        self._ocr_info: QLabel

        self._build_ui()
        self._populate()

    @property
    def result_action(self) -> str | None:
        return self._result_action

    @property
    def cislo(self) -> str:
        return self._cislo_input.value().strip()

    @property
    def typ(self) -> TypDokladu:
        val = self._typ_combo.current_data()
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
    def variabilni_symbol(self) -> str | None:
        val = self._vs_input.value().strip()
        return val if val else None

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S4, Spacing.S4, Spacing.S4, Spacing.S4,
        )

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left: preview
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        preview_title = QLabel("Náhled souboru", left)
        preview_title.setProperty("class", "section-title")
        left_layout.addWidget(preview_title)

        scroll = QScrollArea(left)
        scroll.setWidgetResizable(True)
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumSize(400, 400)
        self._preview_label.setProperty("class", "form-help")
        self._preview_label.setText("Načítám náhled...")
        scroll.setWidget(self._preview_label)
        left_layout.addWidget(scroll, stretch=1)

        splitter.addWidget(left)

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
        self._typ_combo.add_item("Pokladní doklad", TypDokladu.POKLADNI_DOKLAD)
        self._typ_combo.add_item("Interní doklad", TypDokladu.INTERNI_DOKLAD)
        right_layout.addWidget(self._typ_combo)

        self._cislo_input = LabeledLineEdit("Číslo dokladu", max_length=50)
        right_layout.addWidget(self._cislo_input)

        self._dodavatel_input = LabeledLineEdit("Dodavatel", max_length=200)
        right_layout.addWidget(self._dodavatel_input)

        self._datum_input = LabeledDateEdit("Datum vystavení")
        right_layout.addWidget(self._datum_input)

        self._castka_input = LabeledMoneyEdit("Částka celkem (Kč)")
        right_layout.addWidget(self._castka_input)

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
                self._typ_combo.set_current_data(typ)
            except ValueError:
                pass

        # Cislo
        if item.parsed_cislo:
            self._cislo_input.set_value(item.parsed_cislo)
        else:
            self._cislo_input.set_value(
                f"FP-{date.today().year}-{item.id:04d}"
            )

        # Dodavatel
        if item.parsed_dodavatel:
            self._dodavatel_input.set_value(item.parsed_dodavatel)

        # Datum
        if item.parsed_datum:
            self._datum_input.set_value(item.parsed_datum)
        else:
            self._datum_input.set_value(date.today())

        # Castka
        if item.parsed_castka:
            self._castka_input.set_value(item.parsed_castka)

        # Variabilní symbol
        if item.parsed_vs:
            self._vs_input.set_value(item.parsed_vs)

        # Popis
        self._popis_input.set_value(f"OCR: {item.file_name}")

        # Preview
        self._load_preview()

    def _load_preview(self) -> None:
        """Načte náhled PDF/obrázku."""
        if not self._file_path:
            self._preview_label.setText("Soubor není k dispozici")
            return

        path = Path(self._file_path)
        if not path.exists():
            self._preview_label.setText("Soubor není k dispozici")
            return

        suffix = path.suffix.lower()

        if suffix in (".jpg", ".jpeg", ".png"):
            self._show_image(path)
        elif suffix == ".pdf":
            self._show_pdf_preview(path)
        else:
            self._preview_label.setText(f"Nepodporovaný formát: {suffix}")

    def _show_image(self, path: Path) -> None:
        """Zobrazí obrázek."""
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._preview_label.setText("Nelze načíst obrázek")
            return
        scaled = pixmap.scaled(
            400, 600,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)

    def _show_pdf_preview(self, path: Path) -> None:
        """Zobrazí první stranu PDF pomocí pdf2image (poppler)."""
        try:
            from pdf2image import convert_from_path

            images = convert_from_path(
                str(path), first_page=1, last_page=1, dpi=150,
            )
            if not images:
                self._preview_label.setText("PDF je prázdné")
                return

            pil_img = images[0]
            # PIL → QImage → QPixmap
            data = pil_img.tobytes("raw", "RGB")
            qimg = QImage(
                data, pil_img.width, pil_img.height,
                pil_img.width * 3,
                QImage.Format.Format_RGB888,
            )
            pixmap = QPixmap.fromImage(qimg)
            scaled = pixmap.scaled(
                400, 600,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview_label.setPixmap(scaled)

        except ImportError:
            self._preview_label.setText(
                "pdf2image není nainstalován.\n"
                "pip install pdf2image"
            )
        except Exception as exc:  # noqa: BLE001
            self._preview_label.setText(f"Chyba náhledu: {exc}")

    def _on_approve(self) -> None:
        self._result_action = "approve"
        self.accept()

    def _on_reject(self) -> None:
        self._result_action = "reject"
        self.accept()
