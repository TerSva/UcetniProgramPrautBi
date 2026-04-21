"""BankaImportPage — stránka pro import bankovních výpisů (CSV + PDF).

3-krokový workflow:
    1. Výběr účtu + nahrání CSV a PDF souborů
    2. Validace CSV vs PDF — report shod/neshod
    3. Potvrzení importu → výsledek
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import Spacing
from ui.dialogs.novy_bankovni_ucet_dialog import NovyBankovniUcetDialog
from ui.viewmodels.import_vypisu_vm import ImportVypisuViewModel
from ui.widgets.labeled_inputs import LabeledComboBox


class BankaImportPage(QWidget):
    """Stránka importu bankovního výpisu — 3 kroky."""

    def __init__(
        self,
        view_model: ImportVypisuViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._ucet_combo: LabeledComboBox
        self._csv_label: QLabel
        self._pdf_label: QLabel
        self._csv_btn: QPushButton
        self._pdf_btn: QPushButton
        self._validate_btn: QPushButton
        self._import_btn: QPushButton
        self._reset_btn: QPushButton
        self._status_label: QLabel
        self._report_table: QTableWidget

        self._build_ui()
        self._wire_signals()
        self._load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8,
        )
        root.setSpacing(Spacing.S4)

        # Title
        title = QLabel("Import bankovního výpisu", self)
        title.setProperty("class", "page-title")
        root.addWidget(title)

        subtitle = QLabel(
            "Nahrajte CSV a PDF výpis z banky. "
            "Systém porovná data a naimportuje transakce.",
            self,
        )
        subtitle.setProperty("class", "page-subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # Step 1: Account selection + file upload
        step1 = QWidget(self)
        step1.setProperty("class", "card")
        step1.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        step1_layout = QVBoxLayout(step1)
        step1_layout.setContentsMargins(
            Spacing.S4, Spacing.S4, Spacing.S4, Spacing.S4,
        )

        step1_title = QLabel("1. Výběr účtu a souborů", step1)
        step1_title.setProperty("class", "card-title")
        step1_layout.addWidget(step1_title)

        ucet_row = QHBoxLayout()
        self._ucet_combo = LabeledComboBox("Bankovní účet", parent=step1)
        ucet_row.addWidget(self._ucet_combo, stretch=1)

        self._novy_ucet_btn = QPushButton("+ Nový účet", step1)
        self._novy_ucet_btn.setProperty("class", "secondary-sm")
        self._novy_ucet_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ucet_row.addWidget(self._novy_ucet_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        step1_layout.addLayout(ucet_row)

        # CSV file
        csv_row = QHBoxLayout()
        self._csv_label = QLabel("CSV soubor: nevybrán", step1)
        self._csv_btn = QPushButton("Vybrat CSV", step1)
        self._csv_btn.setProperty("class", "secondary-sm")
        self._csv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        csv_row.addWidget(self._csv_label, stretch=1)
        csv_row.addWidget(self._csv_btn)
        step1_layout.addLayout(csv_row)

        # PDF file
        pdf_row = QHBoxLayout()
        self._pdf_label = QLabel("PDF soubor: nevybrán", step1)
        self._pdf_btn = QPushButton("Vybrat PDF", step1)
        self._pdf_btn.setProperty("class", "secondary-sm")
        self._pdf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pdf_row.addWidget(self._pdf_label, stretch=1)
        pdf_row.addWidget(self._pdf_btn)
        step1_layout.addLayout(pdf_row)

        self._validate_btn = QPushButton("Validovat", step1)
        self._validate_btn.setProperty("class", "primary")
        self._validate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        step1_layout.addWidget(self._validate_btn)

        root.addWidget(step1)

        # Step 2: Validation report
        step2 = QWidget(self)
        step2.setProperty("class", "card")
        step2.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        step2_layout = QVBoxLayout(step2)
        step2_layout.setContentsMargins(
            Spacing.S4, Spacing.S4, Spacing.S4, Spacing.S4,
        )

        step2_title = QLabel("2. Výsledek validace", step2)
        step2_title.setProperty("class", "card-title")
        step2_layout.addWidget(step2_title)

        self._status_label = QLabel("Čeká na validaci...", step2)
        self._status_label.setWordWrap(True)
        step2_layout.addWidget(self._status_label)

        self._report_table = QTableWidget(0, 4, step2)
        self._report_table.setHorizontalHeaderLabels([
            "Datum", "Částka", "VS", "Stav",
        ])
        self._report_table.horizontalHeader().setStretchLastSection(True)
        self._report_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )
        self._report_table.setAlternatingRowColors(True)
        step2_layout.addWidget(self._report_table, stretch=1)

        # Import + Reset buttons
        btn_row = QHBoxLayout()
        self._import_btn = QPushButton("Importovat", step2)
        self._import_btn.setProperty("class", "primary")
        self._import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._import_btn.setEnabled(False)

        self._reset_btn = QPushButton("Reset", step2)
        self._reset_btn.setProperty("class", "secondary-sm")
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_row.addWidget(self._import_btn)
        btn_row.addWidget(self._reset_btn)
        btn_row.addStretch()
        step2_layout.addLayout(btn_row)

        self._warning_label = QLabel("", step2)
        self._warning_label.setWordWrap(True)
        self._warning_label.setStyleSheet("color: #cc0000; font-weight: bold;")
        self._warning_label.setVisible(False)
        step2_layout.addWidget(self._warning_label)

        root.addWidget(step2, stretch=1)

    def _wire_signals(self) -> None:
        self._csv_btn.clicked.connect(self._on_select_csv)
        self._pdf_btn.clicked.connect(self._on_select_pdf)
        self._validate_btn.clicked.connect(self._on_validate)
        self._import_btn.clicked.connect(self._on_import)
        self._reset_btn.clicked.connect(self._on_reset)
        self._novy_ucet_btn.clicked.connect(self._on_novy_ucet)

    def _load(self) -> None:
        self._vm.load_ucty()
        self._ucet_combo.clear_items()
        for ucet in self._vm.ucty:
            self._ucet_combo.add_item(
                f"{ucet.nazev} ({ucet.ucet_kod})", ucet.id,
            )

    def _on_select_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Vyberte CSV soubor", "", "CSV soubory (*.csv)",
        )
        if path:
            self._vm.csv_path = Path(path)
            self._csv_label.setText(f"CSV soubor: {Path(path).name}")

    def _on_select_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Vyberte PDF soubor", "", "PDF soubory (*.pdf)",
        )
        if path:
            self._vm.pdf_path = Path(path)
            self._pdf_label.setText(f"PDF soubor: {Path(path).name}")

    def _on_validate(self) -> None:
        ucet_id = self._ucet_combo.value()
        if ucet_id is not None:
            self._vm.selected_ucet_id = ucet_id

        result = self._vm.validate()
        if result is None:
            self._status_label.setText(
                f"Chyba: {self._vm.error or 'Neznámá chyba'}",
            )
            return

        # Display validation report
        self._report_table.setRowCount(0)

        if result.varovani:
            warnings = "\n".join(result.varovani)
            self._status_label.setText(f"Varování:\n{warnings}")
        else:
            self._status_label.setText("Validace úspěšná")

        # Show matched transactions
        for match in result.transakce_shoduji:
            row = self._report_table.rowCount()
            self._report_table.insertRow(row)
            self._report_table.setItem(
                row, 0,
                QTableWidgetItem(
                    match.csv.datum_zauctovani.strftime("%d.%m.%Y"),
                ),
            )
            self._report_table.setItem(
                row, 1,
                QTableWidgetItem(match.csv.castka.format_cz()),
            )
            self._report_table.setItem(
                row, 2,
                QTableWidgetItem(match.csv.variabilni_symbol or ""),
            )
            item = QTableWidgetItem("Shoda")
            item.setForeground(Qt.GlobalColor.darkGreen)
            self._report_table.setItem(row, 3, item)

        # Show CSV-only
        for tx in result.pouze_v_csv:
            row = self._report_table.rowCount()
            self._report_table.insertRow(row)
            self._report_table.setItem(
                row, 0,
                QTableWidgetItem(
                    tx.datum_zauctovani.strftime("%d.%m.%Y"),
                ),
            )
            self._report_table.setItem(
                row, 1, QTableWidgetItem(tx.castka.format_cz()),
            )
            self._report_table.setItem(
                row, 2, QTableWidgetItem(tx.variabilni_symbol or ""),
            )
            item = QTableWidgetItem("Pouze v CSV")
            item.setForeground(Qt.GlobalColor.darkYellow)
            self._report_table.setItem(row, 3, item)

        # Show PDF-only
        for tx in result.pouze_v_pdf:
            row = self._report_table.rowCount()
            self._report_table.insertRow(row)
            self._report_table.setItem(
                row, 0,
                QTableWidgetItem(
                    tx.datum_transakce.strftime("%d.%m.%Y"),
                ),
            )
            self._report_table.setItem(
                row, 1, QTableWidgetItem(tx.castka.format_cz()),
            )
            self._report_table.setItem(
                row, 2, QTableWidgetItem(tx.variabilni_symbol or ""),
            )
            item = QTableWidgetItem("Pouze v PDF")
            item.setForeground(Qt.GlobalColor.red)
            self._report_table.setItem(row, 3, item)

        # PS/KS info
        ps_text = result.ps_pdf.format_cz() if result.ps_pdf else "N/A"
        ks_text = result.ks_pdf.format_cz() if result.ks_pdf else "N/A"
        self._status_label.setText(
            f"PS: {ps_text} | KS: {ks_text} | "
            f"Shoda: {len(result.transakce_shoduji)} | "
            f"Pouze CSV: {len(result.pouze_v_csv)} | "
            f"Pouze PDF: {len(result.pouze_v_pdf)}"
            + (f"\nVarování: {', '.join(result.varovani)}" if result.varovani else ""),
        )

        # Block import when discrepancies exist
        has_discrepancy = (
            len(result.pouze_v_csv) > 0
            or len(result.pouze_v_pdf) > 0
        )
        can_import = result.is_valid and not has_discrepancy

        if has_discrepancy:
            parts: list[str] = []
            if result.pouze_v_csv:
                parts.append(
                    f"{len(result.pouze_v_csv)} transakcí pouze v CSV"
                )
            if result.pouze_v_pdf:
                parts.append(
                    f"{len(result.pouze_v_pdf)} transakcí pouze v PDF"
                )
            self._warning_label.setText(
                "Import blokován — neshoda CSV vs PDF: "
                + ", ".join(parts)
                + ". Zkontrolujte soubory."
            )
            self._warning_label.setVisible(True)
        else:
            self._warning_label.setVisible(False)

        self._import_btn.setEnabled(can_import)

    def _on_import(self) -> None:
        result = self._vm.execute_import()
        if result is None:
            QMessageBox.warning(
                self, "Chyba", self._vm.error or "Neznámá chyba",
            )
            return

        if result.success:
            QMessageBox.information(
                self,
                "Import dokončen",
                f"Importováno {result.pocet_transakci} transakcí.\n"
                f"Doklad: {result.doklad_cislo}",
            )
            self._on_reset()
        else:
            QMessageBox.warning(
                self, "Chyba importu", result.error or "Neznámá chyba",
            )

    def _on_novy_ucet(self) -> None:
        analytiky = self._vm.get_analytiky_221()
        dialog = NovyBankovniUcetDialog(analytiky, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result:
            ok = self._vm.zaloz_ucet(dialog.result)
            if ok:
                self._load()  # refresh dropdown
                QMessageBox.information(
                    self, "Účet založen",
                    f'Bankovní účet "{dialog.result.nazev}" byl úspěšně založen.',
                )
            else:
                QMessageBox.warning(
                    self, "Chyba",
                    self._vm.error or "Nepodařilo se založit účet.",
                )

    def _on_reset(self) -> None:
        self._vm.reset()
        self._csv_label.setText("CSV soubor: nevybrán")
        self._pdf_label.setText("PDF soubor: nevybrán")
        self._status_label.setText("Čeká na validaci...")
        self._report_table.setRowCount(0)
        self._import_btn.setEnabled(False)
        self._warning_label.setVisible(False)
