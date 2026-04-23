"""UcetEditDialog — úprava názvu a popisu syntetického účtu.

Jednoduchý dialog: zobrazí číslo (read-only), editovatelný název a popis.
"""

from __future__ import annotations

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


class UcetEditResult(NamedTuple):
    """Výsledek dialogu pro úpravu účtu."""

    nazev: str
    popis: str | None


class UcetEditDialog(QDialog):
    """Dialog pro úpravu syntetického nebo analytického účtu."""

    def __init__(
        self,
        cislo: str,
        nazev: str,
        popis: str | None = None,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cislo = cislo
        self._result: UcetEditResult | None = None

        self.setWindowTitle(f"Upravit účet {cislo}")
        self.setMinimumWidth(400)

        self._nazev_input: LabeledLineEdit
        self._popis_input: LabeledTextEdit
        self._error_label: QLabel
        self._submit_button: QPushButton

        self._build_ui(cislo, nazev, popis)
        self._wire_signals()

    @property
    def result(self) -> UcetEditResult | None:
        return self._result

    def _build_ui(
        self, cislo: str, nazev: str, popis: str | None,
    ) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        # Header
        title = QLabel(f"Upravit účet {cislo}", self)
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        # Číslo (read-only)
        cislo_label = QLabel(f"Číslo účtu: {cislo}", self)
        cislo_label.setProperty("class", "page-subtitle")
        root.addWidget(cislo_label)

        # Název
        self._nazev_input = LabeledLineEdit(
            "Název", placeholder="Název účtu", parent=self,
        )
        self._nazev_input.set_value(nazev)
        root.addWidget(self._nazev_input)

        # Popis
        self._popis_input = LabeledTextEdit(
            "Popis (nepovinné)",
            placeholder="Volitelný popis účtu",
            rows=2,
            parent=self,
        )
        if popis:
            self._popis_input.set_value(popis)
        root.addWidget(self._popis_input)

        # Error label
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setVisible(False)
        self._error_label.setWordWrap(True)
        root.addWidget(self._error_label)

        # Buttons
        self._submit_button = QPushButton("Uložit změny", self)
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
        nazev = (self._nazev_input.value() or "").strip()

        if not nazev:
            self._error_label.setText("Název je povinný.")
            self._error_label.setVisible(True)
            return

        popis = (self._popis_input.value() or "").strip() or None
        self._result = UcetEditResult(nazev=nazev, popis=popis)
        self.accept()
