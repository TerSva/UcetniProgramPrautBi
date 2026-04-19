"""NastaveniPage — firemní údaje a účetní nastavení.

Zobrazuje editovatelné údaje firmy singleton (PRAUT s.r.o.).
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from domain.firma.firma import Firma
from domain.shared.money import Money
from ui.design_tokens import Spacing
from ui.viewmodels.nastaveni_vm import NastaveniViewModel
from ui.widgets.labeled_inputs import (
    LabeledComboBox,
    LabeledDateEdit,
    LabeledLineEdit,
    LabeledMoneyEdit,
)


class NastaveniPage(QWidget):
    """Nastavení — firma + účetnictví."""

    def __init__(
        self,
        view_model: NastaveniViewModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._nazev_input: LabeledLineEdit
        self._ico_input: LabeledLineEdit
        self._dic_input: LabeledLineEdit
        self._sidlo_input: LabeledLineEdit
        self._pravni_forma_combo: LabeledComboBox
        self._datum_zalozeni: LabeledDateEdit
        self._rok_combo: LabeledComboBox
        self._kategorie_combo: LabeledComboBox
        self._io_dph_check: QCheckBox
        self._platce_dph_check: QCheckBox
        self._save_button: QPushButton
        self._error_label: QLabel

        self._build_ui()
        if self._vm is not None:
            self._vm.load()
            self._fill_from_firma()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8,
        )
        root.setSpacing(Spacing.S4)

        title = QLabel("Nastavení", self)
        title.setProperty("class", "page-title")
        root.addWidget(title)

        subtitle = QLabel(
            "Firemní údaje, účetní období, DPH a uživatelská nastavení.",
            self,
        )
        subtitle.setProperty("class", "page-subtitle")
        root.addWidget(subtitle)

        # ── Firma section ──
        firma_title = QLabel("Firma", self)
        firma_title.setProperty("class", "section-title")
        root.addWidget(firma_title)

        self._nazev_input = LabeledLineEdit(
            "Název", placeholder="PRAUT s.r.o.", parent=self,
        )
        root.addWidget(self._nazev_input)

        row1 = QHBoxLayout()
        row1.setSpacing(Spacing.S3)
        self._ico_input = LabeledLineEdit(
            "IČO", placeholder="22545107", max_length=8, parent=self,
        )
        row1.addWidget(self._ico_input)
        self._dic_input = LabeledLineEdit(
            "DIČ", placeholder="CZ22545107", max_length=12, parent=self,
        )
        row1.addWidget(self._dic_input)
        root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(Spacing.S3)
        self._pravni_forma_combo = LabeledComboBox("Právní forma", self)
        for f in ("s.r.o.", "a.s.", "OSVČ", "v.o.s.", "k.s."):
            self._pravni_forma_combo.add_item(f, f)
        row2.addWidget(self._pravni_forma_combo)
        self._datum_zalozeni = LabeledDateEdit(
            "Datum založení", clearable=True, parent=self,
        )
        row2.addWidget(self._datum_zalozeni)
        root.addLayout(row2)

        self._sidlo_input = LabeledLineEdit(
            "Sídlo", placeholder="Tršnice 36, 35134 Skalná", parent=self,
        )
        root.addWidget(self._sidlo_input)

        # ── Účetnictví section ──
        ucet_title = QLabel("Účetnictví", self)
        ucet_title.setProperty("class", "section-title")
        root.addWidget(ucet_title)

        row3 = QHBoxLayout()
        row3.setSpacing(Spacing.S3)
        self._rok_combo = LabeledComboBox("Účetní období (rok)", self)
        for r in range(2020, 2031):
            self._rok_combo.add_item(str(r), r)
        row3.addWidget(self._rok_combo)

        self._kategorie_combo = LabeledComboBox("Kategorie ÚJ", self)
        for k, label in (
            ("mikro", "Mikro ÚJ"),
            ("mala", "Malá ÚJ"),
            ("stredni", "Střední ÚJ"),
            ("velka", "Velká ÚJ"),
        ):
            self._kategorie_combo.add_item(label, k)
        row3.addWidget(self._kategorie_combo)
        root.addLayout(row3)

        self._io_dph_check = QCheckBox("Identifikovaná osoba DPH", self)
        self._io_dph_check.setProperty("class", "form-check")
        root.addWidget(self._io_dph_check)

        self._platce_dph_check = QCheckBox("Plátce DPH", self)
        self._platce_dph_check.setProperty("class", "form-check")
        root.addWidget(self._platce_dph_check)

        # Error + Save
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self._save_button = QPushButton("Uložit změny", self)
        self._save_button.setProperty("class", "primary")
        self._save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_button.clicked.connect(self._on_save)
        footer.addWidget(self._save_button)
        root.addLayout(footer)

        root.addStretch(1)

    def _fill_from_firma(self) -> None:
        f = self._vm.firma if self._vm else None
        if f is None:
            return
        self._nazev_input.set_value(f.nazev)
        if f.ico:
            self._ico_input.set_value(f.ico)
        if f.dic:
            self._dic_input.set_value(f.dic)
        if f.sidlo:
            self._sidlo_input.set_value(f.sidlo)
        self._pravni_forma_combo.set_value(f.pravni_forma)
        self._datum_zalozeni.set_value(f.datum_zalozeni)
        self._rok_combo.set_value(f.rok_zacatku_uctovani)
        self._kategorie_combo.set_value(f.kategorie_uj)
        self._io_dph_check.setChecked(f.je_identifikovana_osoba_dph)
        self._platce_dph_check.setChecked(f.je_platce_dph)

    def _on_save(self) -> None:
        if self._vm is None:
            return

        # Validate date format if entered
        date_text = ""
        if hasattr(self._datum_zalozeni, '_line_edit') and self._datum_zalozeni._line_edit:
            date_text = self._datum_zalozeni._line_edit.text().strip()
        datum_val = self._datum_zalozeni.value()
        if date_text and datum_val is None:
            QMessageBox.warning(
                self, "Chyba",
                f"Neplatný formát data: '{date_text}'\n"
                "Zadejte datum ve formátu d.M.yyyy (např. 28.5.2025).",
            )
            return

        try:
            firma = Firma(
                nazev=self._nazev_input.value() or "",
                ico=self._ico_input.value() or None,
                dic=self._dic_input.value() or None,
                sidlo=self._sidlo_input.value() or None,
                pravni_forma=self._pravni_forma_combo.value() or "s.r.o.",
                datum_zalozeni=datum_val,
                rok_zacatku_uctovani=self._rok_combo.value() or 2025,
                kategorie_uj=self._kategorie_combo.value() or "mikro",
                je_identifikovana_osoba_dph=self._io_dph_check.isChecked(),
                je_platce_dph=self._platce_dph_check.isChecked(),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Chyba validace", str(exc))
            return

        self._vm.save(firma)
        if self._vm.error:
            QMessageBox.warning(self, "Chyba uložení", self._vm.error)
        else:
            QMessageBox.information(self, "Uloženo", "Nastavení firmy bylo uloženo.")

    # ─── Test-only accessors ─────────────────────────────────────

    @property
    def _nazev_widget(self) -> LabeledLineEdit:
        return self._nazev_input

    @property
    def _ico_widget(self) -> LabeledLineEdit:
        return self._ico_input

    @property
    def _save_widget(self) -> QPushButton:
        return self._save_button
