"""UcetEditDialog — úprava účtu (syntetického nebo analytického).

Syntetický účet: editovatelný název + popis.
Analytický účet: editovatelný suffix (kód za tečkou), název, popis + tlačítko Smazat.
"""

from __future__ import annotations

import re
from enum import Enum, auto
from typing import NamedTuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import Spacing
from ui.widgets.labeled_inputs import LabeledLineEdit, LabeledTextEdit

_SUFFIX_RE = re.compile(r"^\w{1,3}$")


class UcetEditAction(Enum):
    SAVE = auto()
    DELETE = auto()


class UcetEditResult(NamedTuple):
    """Výsledek dialogu pro úpravu účtu."""

    action: UcetEditAction
    nazev: str
    popis: str | None
    new_suffix: str | None  # jen pro analytiky, None = nezměněno
    je_danovy: bool | None = None  # None = nezměněno, jinak nová hodnota


class UcetEditDialog(QDialog):
    """Dialog pro úpravu syntetického nebo analytického účtu."""

    def __init__(
        self,
        cislo: str,
        nazev: str,
        popis: str | None = None,
        *,
        je_danovy: bool | None = None,
        typ: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cislo = cislo
        self._is_analytic = "." in cislo
        self._typ = typ  # 'N', 'V', 'A', 'P', 'Z' — pro zobrazení checkboxu
        self._result: UcetEditResult | None = None

        self.setWindowTitle(f"Upravit účet {cislo}")
        self.setMinimumWidth(400)

        self._suffix_input: LabeledLineEdit | None = None
        self._nazev_input: LabeledLineEdit
        self._popis_input: LabeledTextEdit
        self._danovy_check: QCheckBox | None = None
        self._error_label: QLabel
        self._submit_button: QPushButton

        self._build_ui(cislo, nazev, popis, je_danovy)
        self._wire_signals()

    @property
    def result(self) -> UcetEditResult | None:
        return self._result

    def _build_ui(
        self,
        cislo: str,
        nazev: str,
        popis: str | None,
        je_danovy: bool | None = None,
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

        # Suffix (jen pro analytiky)
        if self._is_analytic:
            parent_kod, current_suffix = cislo.split(".", 1)
            self._suffix_input = LabeledLineEdit(
                f"Kód (za tečkou {parent_kod}.)",
                placeholder="100",
                parent=self,
            )
            self._suffix_input.set_value(current_suffix)
            root.addWidget(self._suffix_input)
        else:
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

        # Daňová uznatelnost — jen pro nákladové (N) a výnosové (V) účty
        if self._typ in ("N", "V"):
            self._danovy_check = QCheckBox(
                "Daňově uznatelný (zahrnout do základu daně)", self,
            )
            self._danovy_check.setProperty("class", "form-check")
            self._danovy_check.setCursor(Qt.CursorShape.PointingHandCursor)
            # je_danovy: None → True (default), False → odškrtnuté
            self._danovy_check.setChecked(je_danovy is None or je_danovy)
            root.addWidget(self._danovy_check)

        # Error label
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setVisible(False)
        self._error_label.setWordWrap(True)
        root.addWidget(self._error_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)

        # Smazat (jen pro analytiky)
        if self._is_analytic:
            delete_button = QPushButton("Smazat", self)
            delete_button.setProperty("class", "danger-sm")
            delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_button.clicked.connect(self._on_delete)
            btn_layout.addWidget(delete_button)

        btn_layout.addStretch(1)

        cancel_button = QPushButton("Zrušit", self)
        cancel_button.setProperty("class", "secondary")
        cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_button.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_button)

        self._submit_button = QPushButton("Uložit změny", self)
        self._submit_button.setProperty("class", "primary")
        self._submit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(self._submit_button)

        root.addLayout(btn_layout)

    def _wire_signals(self) -> None:
        self._submit_button.clicked.connect(self._on_submit)

    def _on_submit(self) -> None:
        nazev = (self._nazev_input.value() or "").strip()
        if not nazev:
            self._show_error("Název je povinný.")
            return

        popis = (self._popis_input.value() or "").strip() or None
        new_suffix: str | None = None

        if self._is_analytic and self._suffix_input is not None:
            suffix = (self._suffix_input.value() or "").strip().lstrip(".")
            if not suffix:
                self._show_error("Kód analytiky je povinný.")
                return
            if not _SUFFIX_RE.match(suffix):
                self._show_error(
                    "Kód za tečkou: max 3 znaky (např. '100', '01')."
                )
                return
            new_suffix = suffix

        je_danovy: bool | None = None
        if self._danovy_check is not None:
            je_danovy = self._danovy_check.isChecked()

        self._result = UcetEditResult(
            action=UcetEditAction.SAVE,
            nazev=nazev,
            popis=popis,
            new_suffix=new_suffix,
            je_danovy=je_danovy,
        )
        self.accept()

    def _on_delete(self) -> None:
        reply = QMessageBox.question(
            self,
            "Smazat analytiku",
            f"Opravdu smazat účet {self._cislo}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._result = UcetEditResult(
                action=UcetEditAction.DELETE,
                nazev="",
                popis=None,
                new_suffix=None,
                je_danovy=None,
            )
            self.accept()

    def _show_error(self, text: str) -> None:
        self._error_label.setText(text)
        self._error_label.setVisible(True)
