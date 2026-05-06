"""VyberZalohDialog — výběr nezúčtovaných záloh partnera pro odečet.

Spouští se z zauctovani dialogu (FV/FP) tlačítkem "Načíst zálohy partnera".
Uživatelka zaškrtne, které ZF chce odečíst od finální faktury — VM
následně sníží hlavní řádek o sumu vybraných záloh a přidá řádky odečtu.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.queries.zalohy_partnera import ZalohaItem
from ui.design_tokens import Spacing


class VyberZalohDialog(QDialog):
    """Dialog s tabulkou nezúčtovaných ZF + checkbox pro výběr."""

    def __init__(
        self,
        zalohy: list[ZalohaItem],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._zalohy = zalohy
        self._selected_zalohy: list[ZalohaItem] = []
        self._checkboxes: list[QCheckBox] = []

        self.setWindowTitle("Vybrat zálohy k odečtu")
        self.setModal(True)
        self.resize(640, 420)

        self._build_ui()

    @property
    def selected_zalohy(self) -> list[ZalohaItem]:
        return self._selected_zalohy

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S5, Spacing.S5, Spacing.S5, Spacing.S5,
        )
        root.setSpacing(Spacing.S3)

        title = QLabel("Vyberte zálohy k odečtu", self)
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        info = QLabel(
            "Označte zálohy, které chcete zúčtovat s touto finální fakturou. "
            "Hlavní řádek předpisu se sníží o jejich součet a přidají se "
            "řádky odečtu (MD 324/Dal 601 pro FV, MD 518/Dal 314 pro FP).",
            self,
        )
        info.setWordWrap(True)
        info.setProperty("class", "form-help")
        root.addWidget(info)

        # Tabulka záloh
        self._table = QTableWidget(len(self._zalohy), 4, self)
        self._table.setHorizontalHeaderLabels(
            ["", "Číslo", "Datum", "Částka"],
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._table.verticalHeader().setVisible(False)
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(0, 36)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        for i, z in enumerate(self._zalohy):
            check = QCheckBox()
            check.setCursor(Qt.CursorShape.PointingHandCursor)
            self._checkboxes.append(check)
            self._table.setCellWidget(i, 0, check)
            self._table.setItem(i, 1, QTableWidgetItem(z.cislo))
            self._table.setItem(
                i, 2, QTableWidgetItem(z.datum.strftime("%d.%m.%Y")),
            )
            castka_item = QTableWidgetItem(z.castka_celkem.format_cz())
            castka_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            self._table.setItem(i, 3, castka_item)
        root.addWidget(self._table, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Zrušit", self)
        btn_cancel.setProperty("class", "secondary")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch(1)
        btn_ok = QPushButton("Načíst vybrané", self)
        btn_ok.setProperty("class", "primary")
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.clicked.connect(self._on_ok)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

    def _on_ok(self) -> None:
        self._selected_zalohy = [
            z for z, ck in zip(self._zalohy, self._checkboxes)
            if ck.isChecked()
        ]
        self.accept()
