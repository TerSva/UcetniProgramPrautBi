"""DokladFormDialog — modální okno pro vytvoření nového dokladu.

Zobrazuje pole: Typ, Číslo, Datum vystavení, Datum splatnosti (clearable),
Částka celkem, Popis (vícedroádkový). Při otevření se z ViewModelu
vyžádá navrhované číslo pro zvolený typ + aktuální rok.

Submit → ``DokladFormViewModel.submit(CreateDokladInput)`` → při úspěchu
``accept()`` s výsledným DTO dostupným přes ``.created_item``.
"""

from __future__ import annotations

from datetime import date
from typing import cast

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from domain.doklady.typy import TypDokladu
from services.commands.create_doklad import CreateDokladInput
from services.queries.doklady_list import DokladyListItem
from ui.design_tokens import Spacing
from ui.viewmodels.doklad_form_vm import DokladFormViewModel
from ui.widgets.badge import typ_display_text
from ui.widgets.labeled_inputs import (
    LabeledComboBox,
    LabeledDateEdit,
    LabeledLineEdit,
    LabeledMoneyEdit,
    LabeledTextEdit,
)


class DokladFormDialog(QDialog):
    """Modální dialog pro vytvoření nového dokladu."""

    def __init__(
        self,
        view_model: DokladFormViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nový doklad")
        self.setModal(True)
        self.setProperty("class", "doklad-form")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.resize(480, 620)

        self._vm = view_model
        self._created_item: DokladyListItem | None = None

        # Widgety — inicializace v _build_ui
        self._typ_combo: LabeledComboBox
        self._cislo_input: LabeledLineEdit
        self._datum_vystaveni: LabeledDateEdit
        self._datum_splatnosti: LabeledDateEdit
        self._castka_input: LabeledMoneyEdit
        self._popis_input: LabeledTextEdit
        self._error_label: QLabel
        self._submit_button: QPushButton
        self._cancel_button: QPushButton

        self._build_ui()
        self._wire_signals()
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

        # Typ
        self._typ_combo = LabeledComboBox("Typ dokladu", self)
        for t in TypDokladu:
            self._typ_combo.add_item(typ_display_text(t), t)
        self._typ_combo.set_value(TypDokladu.FAKTURA_VYDANA)
        root.addWidget(self._typ_combo)

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

        # Popis
        self._popis_input = LabeledTextEdit(
            "Popis (nepovinné)",
            placeholder="Volitelný komentář k dokladu.",
            rows=3,
            parent=self,
        )
        root.addWidget(self._popis_input)

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
        self._typ_combo.current_value_changed.connect(self._on_typ_changed)
        self._submit_button.clicked.connect(self._on_submit)
        self._cancel_button.clicked.connect(self.reject)

    # ─── Slots ────────────────────────────────────────────────────

    def _initial_suggest_cislo(self) -> None:
        typ = cast(TypDokladu | None, self._typ_combo.value())
        if typ is None:
            return
        cislo = self._vm.suggest_cislo(typ, date.today().year)
        self._cislo_input.set_value(cislo)

    def _on_typ_changed(self, value: object) -> None:
        if not isinstance(value, TypDokladu):
            return
        cislo = self._vm.suggest_cislo(value, date.today().year)
        self._cislo_input.set_value(cislo)

    def _on_submit(self) -> None:
        # Vyresetuj error badges
        self._cislo_input.set_error(None)
        self._castka_input.set_error(None)
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

        data = CreateDokladInput(
            cislo=cislo,
            typ=typ,
            datum_vystaveni=datum_vystaveni,
            datum_splatnosti=datum_splatnosti,
            castka_celkem=castka,
            popis=popis,
        )
        item = self._vm.submit(data)
        if item is None:
            self._show_form_error(
                self._vm.error or "Vytvoření dokladu selhalo.",
            )
            return
        self._created_item = item
        self.accept()

    def _show_form_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)
