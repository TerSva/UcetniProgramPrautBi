"""StornoDialog — datum + poznámka pro storno dokladu.

Vyvolá se z detail dialogu před vlastním stornováním. Default datum
storna = ``datum_vystaveni`` původního dokladu, aby protizápis zůstal
ve stejném účetním období jako originál (jinak by storno faktury
z 02/2025 v dubnu 2026 spadlo mimo uzavřený rok).

Použití:
    result = StornoDialog.ask(
        parent,
        cislo_dokladu="ID-2025-003",
        default_datum=date(2025, 2, 3),
    )
    if result is not None:
        datum, poznamka = result
        vm.stornovat(datum=datum, poznamka=poznamka)
"""

from __future__ import annotations

from datetime import date

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
from ui.widgets.labeled_inputs import LabeledDateEdit, LabeledTextEdit


class StornoDialog(QDialog):
    """Modální dialog: datum storna + nepovinná poznámka."""

    def __init__(
        self,
        cislo_dokladu: str,
        default_datum: date,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Stornovat doklad {cislo_dokladu}")
        self.setModal(True)
        self.setProperty("class", "confirm-dialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(440)

        self._cislo = cislo_dokladu
        self._default_datum = default_datum
        self._datum_input: LabeledDateEdit
        self._poznamka_input: LabeledTextEdit
        self._error_label: QLabel
        self._confirm_button: QPushButton
        self._cancel_button: QPushButton

        self._build_ui()

    # ─── Public API ───────────────────────────────────────────────

    @classmethod
    def ask(
        cls,
        parent: QWidget | None,
        cislo_dokladu: str,
        default_datum: date,
    ) -> tuple[date, str | None] | None:
        """Otevře dialog modálně a vrátí (datum, poznamka) nebo None.

        Returns:
            (datum, poznamka) — poznámka může být None pokud byla prázdná.
            None — uživatel zrušil dialog.
        """
        dialog = cls(
            cislo_dokladu=cislo_dokladu,
            default_datum=default_datum,
            parent=parent,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        datum = dialog._datum_input.value()
        if datum is None:
            return None
        raw = dialog._poznamka_input.value().strip()
        return (datum, raw or None)

    # ─── Test-only accessors ──────────────────────────────────────

    @property
    def datum_input(self) -> LabeledDateEdit:
        return self._datum_input

    @property
    def poznamka_input(self) -> LabeledTextEdit:
        return self._poznamka_input

    @property
    def confirm_button(self) -> QPushButton:
        return self._confirm_button

    @property
    def cancel_button(self) -> QPushButton:
        return self._cancel_button

    # ─── Build ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        title = QLabel(f"Stornovat doklad {self._cislo}", self)
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        message = QLabel(
            "Vytvoří se opravný účetní předpis (protizápis). Datum storna "
            "určuje, do kterého účetního období protizápis spadne — default "
            "je datum původního dokladu.",
            self,
        )
        message.setProperty("class", "dialog-message")
        message.setWordWrap(True)
        root.addWidget(message)

        self._datum_input = LabeledDateEdit("Datum storna", parent=self)
        self._datum_input.set_value(self._default_datum)
        root.addWidget(self._datum_input)

        self._poznamka_input = LabeledTextEdit(
            "Poznámka (nepovinné)",
            placeholder="Např. Duplicitní zaúčtování ZK",
            rows=3,
            parent=self,
        )
        root.addWidget(self._poznamka_input)

        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        root.addStretch(1)

        footer = QHBoxLayout()
        footer.addStretch(1)

        self._cancel_button = QPushButton("Zrušit", self)
        self._cancel_button.setProperty("class", "secondary")
        self._cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_button.clicked.connect(self.reject)
        footer.addWidget(self._cancel_button)

        self._confirm_button = QPushButton("Stornovat", self)
        self._confirm_button.setProperty("class", "destructive")
        self._confirm_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._confirm_button.clicked.connect(self._on_confirm)
        footer.addWidget(self._confirm_button)

        root.addLayout(footer)

        self._poznamka_input.edit_widget.setFocus()

    def _on_confirm(self) -> None:
        """Validate datum, then accept."""
        datum = self._datum_input.value()
        if datum is None:
            self._error_label.setText(
                "Datum storna musí být ve formátu d.M.rrrr (např. 3.2.2025)."
            )
            self._error_label.setVisible(True)
            return
        self._error_label.setVisible(False)
        self.accept()
