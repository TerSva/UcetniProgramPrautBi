"""ExportZaverkaDialog — vstupní dialog před exportem účetní závěrky.

Uživatelka zadá rozvahový den (defaultně 31.12.rok) a datum sestavení
účetní závěrky (defaultně dnes). Hodnoty se použijí na cover stránce
a v minimální příloze PDF.
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
from ui.widgets.labeled_inputs import LabeledDateEdit


class ExportZaverkaDialog(QDialog):
    """Dialog s rozvahovým dnem a datem sestavení."""

    def __init__(
        self,
        rok: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._rok = rok
        self._rozvahovy_den: date | None = None
        self._datum_sestaveni: date | None = None

        self.setWindowTitle("Export účetní závěrky")
        self.setModal(True)
        self.setProperty("class", "export-zaverka-dialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.resize(440, 220)

        self._rozvahovy_edit: LabeledDateEdit
        self._datum_sestaveni_edit: LabeledDateEdit
        self._ok_button: QPushButton
        self._cancel_button: QPushButton

        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        title = QLabel(f"Export účetní závěrky — {self._rok}", self)
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        info = QLabel(
            "Zadejte rozvahový den a datum sestavení účetní závěrky. "
            "Tyto hodnoty se zobrazí na titulní straně PDF a v minimální "
            "příloze (formulář 25 5404).",
            self,
        )
        info.setWordWrap(True)
        info.setProperty("class", "dialog-subtitle")
        root.addWidget(info)

        self._rozvahovy_edit = LabeledDateEdit(
            "Rozvahový den", parent=self,
        )
        self._rozvahovy_edit.set_value(date(self._rok, 12, 31))
        root.addWidget(self._rozvahovy_edit)

        self._datum_sestaveni_edit = LabeledDateEdit(
            "Datum sestavení účetní závěrky", parent=self,
        )
        self._datum_sestaveni_edit.set_value(date.today())
        root.addWidget(self._datum_sestaveni_edit)

        root.addStretch(1)

        footer = QHBoxLayout()
        footer.addStretch(1)

        self._cancel_button = QPushButton("Zrušit", self)
        self._cancel_button.setProperty("class", "secondary")
        self._cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self._cancel_button)

        self._ok_button = QPushButton("Pokračovat", self)
        self._ok_button.setProperty("class", "primary")
        self._ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self._ok_button)

        root.addLayout(footer)

    def _wire_signals(self) -> None:
        self._ok_button.clicked.connect(self._on_ok)
        self._cancel_button.clicked.connect(self.reject)

    def _on_ok(self) -> None:
        rd = self._rozvahovy_edit.value()
        ds = self._datum_sestaveni_edit.value()
        if rd is None:
            self._rozvahovy_den = date(self._rok, 12, 31)
        else:
            self._rozvahovy_den = rd
        if ds is None:
            self._datum_sestaveni = date.today()
        else:
            self._datum_sestaveni = ds
        self.accept()

    @property
    def rozvahovy_den(self) -> date | None:
        return self._rozvahovy_den

    @property
    def datum_sestaveni(self) -> date | None:
        return self._datum_sestaveni
