"""AnalytikaDialog — přidání / úprava analytického účtu.

Dvě varianty:
  * add_analytika() — nová analytika k syntetickému účtu
  * edit_analytika() — úprava názvu a popisu existující analytiky
"""

from __future__ import annotations

import re
from typing import NamedTuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import Spacing
from ui.widgets.labeled_inputs import LabeledLineEdit, LabeledTextEdit

_SUFFIX_RE = re.compile(r"^\w{1,3}$")


class AnalytikaResult(NamedTuple):
    """Výsledek dialogu pro přidání analytiky."""

    suffix: str
    nazev: str
    popis: str | None


class AnalytikaDialog(QDialog):
    """Dialog pro přidání nebo úpravu analytiky."""

    def __init__(
        self,
        syntetic_kod: str,
        syntetic_nazev: str,
        *,
        edit_cislo: str | None = None,
        edit_nazev: str | None = None,
        edit_popis: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._syntetic_kod = syntetic_kod
        self._is_edit = edit_cislo is not None
        self._result: AnalytikaResult | None = None

        if self._is_edit:
            self.setWindowTitle(f"Upravit analytiku {edit_cislo}")
        else:
            self.setWindowTitle(f"Přidat analytiku k účtu {syntetic_kod}")

        self.setMinimumWidth(400)

        self._suffix_input: LabeledLineEdit
        self._nazev_input: LabeledLineEdit
        self._popis_input: LabeledTextEdit
        self._error_label: QLabel
        self._submit_button: QPushButton

        self._build_ui(
            syntetic_kod, syntetic_nazev,
            edit_cislo, edit_nazev, edit_popis,
        )
        self._wire_signals()

    @property
    def result(self) -> AnalytikaResult | None:
        return self._result

    # ─── Test accessors ──────────────────────────────

    @property
    def _suffix_widget(self) -> LabeledLineEdit:
        return self._suffix_input

    @property
    def _nazev_widget(self) -> LabeledLineEdit:
        return self._nazev_input

    @property
    def _popis_widget(self) -> LabeledTextEdit:
        return self._popis_input

    @property
    def _error_widget(self) -> QLabel:
        return self._error_label

    @property
    def _submit_button_widget(self) -> QPushButton:
        return self._submit_button

    # ─── Build ────────────────────────────────────────

    def _build_ui(
        self,
        syntetic_kod: str,
        syntetic_nazev: str,
        edit_cislo: str | None,
        edit_nazev: str | None,
        edit_popis: str | None,
    ) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        # Header
        title_text = (
            f"Upravit analytiku {edit_cislo}"
            if self._is_edit
            else f"Přidat analytiku k účtu {syntetic_kod}"
        )
        title = QLabel(title_text, self)
        title.setProperty("class", "dialog-title")

        subtitle = QLabel(syntetic_nazev, self)
        subtitle.setProperty("class", "page-subtitle")

        root.addWidget(title)
        root.addWidget(subtitle)

        # Suffix input (hidden in edit mode)
        self._suffix_input = LabeledLineEdit(
            f"Kód (za tečkou {syntetic_kod}.)",
            placeholder="např. 100, 200",
            parent=self,
        )
        if self._is_edit:
            # V edit mode je kód immutable — naplníme a skryjeme
            suffix = edit_cislo.split(".")[1] if edit_cislo else ""
            self._suffix_input.set_value(suffix)
            self._suffix_input.setVisible(False)
        root.addWidget(self._suffix_input)

        # Název
        self._nazev_input = LabeledLineEdit(
            "Název", placeholder="Název analytického účtu", parent=self,
        )
        if edit_nazev:
            self._nazev_input.set_value(edit_nazev)
        root.addWidget(self._nazev_input)

        # Popis
        self._popis_input = LabeledTextEdit(
            "Popis (nepovinné)",
            placeholder="Volitelný popis účtu",
            rows=2,
            parent=self,
        )
        if edit_popis:
            self._popis_input.set_value(edit_popis)
        root.addWidget(self._popis_input)

        # Error label
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setVisible(False)
        self._error_label.setWordWrap(True)
        root.addWidget(self._error_label)

        # Buttons
        button_text = "Uložit změny" if self._is_edit else "Přidat"
        self._submit_button = QPushButton(button_text, self)
        self._submit_button.setProperty("class", "primary")
        self._submit_button.setCursor(Qt.CursorShape.PointingHandCursor)

        cancel_button = QPushButton("Zrušit", self)
        cancel_button.setProperty("class", "secondary")
        cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_button.clicked.connect(self.reject)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch(1)
        btn_layout.addWidget(cancel_button)
        btn_layout.addWidget(self._submit_button)
        root.addLayout(btn_layout)

    def _wire_signals(self) -> None:
        self._submit_button.clicked.connect(self._on_submit)

    def _on_submit(self) -> None:
        suffix = (self._suffix_input.value() or "").strip()
        nazev = (self._nazev_input.value() or "").strip()
        popis = (self._popis_input.value() or "").strip() or None

        # Validace
        if not self._is_edit:
            if not suffix:
                self._show_error("Kód analytiky je povinný.")
                return
            if not _SUFFIX_RE.match(suffix):
                self._show_error(
                    "Kód musí být 1-3 alfanumerické znaky."
                )
                return

        if not nazev:
            self._show_error("Název je povinný.")
            return

        self._result = AnalytikaResult(suffix=suffix, nazev=nazev, popis=popis)
        self.accept()

    def _show_error(self, text: str) -> None:
        self._error_label.setText(text)
        self._error_label.setVisible(True)
