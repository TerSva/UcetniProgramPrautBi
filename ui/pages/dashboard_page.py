"""Dashboard — placeholder stránka pro Fázi 6 Krok 1.

Reálný obsah (KPI karty, grafy, recent activity) přijde v dalších krocích.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.design_tokens import Spacing


class DashboardPage(QWidget):
    """Placeholder Dashboard — titul + podtitulek."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8
        )
        layout.setSpacing(Spacing.S3)

        title = QLabel("Dashboard", self)
        title.setProperty("class", "page-title")

        subtitle = QLabel("Přehled klíčových ukazatelů firmy.", self)
        subtitle.setProperty("class", "page-subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch(1)
