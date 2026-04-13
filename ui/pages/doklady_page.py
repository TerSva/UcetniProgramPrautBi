"""Doklady — placeholder stránka pro Fázi 6 Krok 1.

Reálný obsah (tabulka faktur, filtry, detail) přijde v dalších krocích.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.design_tokens import Spacing


class DokladyPage(QWidget):
    """Placeholder Doklady — titul + podtitulek."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8
        )
        layout.setSpacing(Spacing.S3)

        title = QLabel("Doklady", self)
        title.setProperty("class", "page-title")

        subtitle = QLabel(
            "Přijaté a vydané faktury, příjmové a výdajové doklady.", self
        )
        subtitle.setProperty("class", "page-subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch(1)
