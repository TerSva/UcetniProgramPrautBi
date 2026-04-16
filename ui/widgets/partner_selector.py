"""PartnerSelector — typeahead dropdown pro výběr partnera.

QComboBox s editable=True a filtrováním při psaní. Obsahuje i tlačítko
"+ Nový partner" pro inline vytvoření.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.queries.partneri_list import PartneriListItem
from ui.design_tokens import Spacing


class PartnerSelector(QWidget):
    """Widget pro výběr partnera s typeahead a '+ Nový' tlačítkem.

    Signals:
        partner_selected(int | None): emitováno při výběru/zrušení partnera.
        new_partner_requested(): emitováno při kliknutí na '+ Nový'.
    """

    partner_selected = pyqtSignal(object)  # int | None
    new_partner_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._items: list[PartneriListItem] = []
        self._selected_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.S1)

        lbl = QLabel("Partner", self)
        lbl.setProperty("class", "form-label")
        layout.addWidget(lbl)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Spacing.S2)

        self._combo = QComboBox(self)
        self._combo.setEditable(True)
        self._combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._combo.lineEdit().setPlaceholderText("Hledej partnera...")
        self._combo.setProperty("class", "form-input")

        self._new_btn = QPushButton("+ Nový", self)
        self._new_btn.setProperty("class", "secondary")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.setFixedWidth(80)

        row.addWidget(self._combo, stretch=1)
        row.addWidget(self._new_btn)
        layout.addLayout(row)

        self._new_btn.clicked.connect(self.new_partner_requested.emit)
        self._combo.currentIndexChanged.connect(self._on_index_changed)

    def set_items(self, items: list[PartneriListItem]) -> None:
        """Nastav seznam partnerů pro dropdown."""
        self._items = items
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItem("— bez partnera —", None)
        for item in items:
            display = item.nazev
            if item.ico:
                display += f" ({item.ico})"
            self._combo.addItem(display, item.id)
        self._combo.setCurrentIndex(0)
        self._combo.blockSignals(False)

        # Setup completer for typeahead
        completer = self._combo.completer()
        if completer:
            completer.setFilterMode(
                Qt.MatchFlag.MatchContains,
            )
            completer.setCaseSensitivity(
                Qt.CaseSensitivity.CaseInsensitive,
            )

    def set_selected_id(self, partner_id: int | None) -> None:
        """Nastav vybraného partnera podle ID."""
        self._combo.blockSignals(True)
        if partner_id is None:
            self._combo.setCurrentIndex(0)
        else:
            for i in range(self._combo.count()):
                if self._combo.itemData(i) == partner_id:
                    self._combo.setCurrentIndex(i)
                    break
        self._selected_id = partner_id
        self._combo.blockSignals(False)

    def selected_id(self) -> int | None:
        return self._selected_id

    def _on_index_changed(self, index: int) -> None:
        if index < 0:
            self._selected_id = None
        else:
            data = self._combo.itemData(index)
            self._selected_id = data if isinstance(data, int) else None
        self.partner_selected.emit(self._selected_id)

    # Test accessors
    @property
    def _combo_widget(self) -> QComboBox:
        return self._combo

    @property
    def _new_btn_widget(self) -> QPushButton:
        return self._new_btn
