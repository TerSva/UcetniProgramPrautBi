"""PlaceholderPage — čistá stránka pro budoucí funkce.

Zobrazuje název, popis a badge s číslem fáze. Používá se pro sekce,
které budou implementovány v dalších fázích sprintu.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.design_tokens import Spacing


class PlaceholderPage(QWidget):
    """Placeholder pro funkce, které ještě nejsou implementované."""

    def __init__(
        self,
        title: str,
        subtitle: str,
        phase_number: int | None = None,
        phase_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title_text = title
        self._phase_number = phase_number
        self._phase_name = phase_name

        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._title_label: QLabel
        self._phase_badge: QLabel
        self._build_ui(title, subtitle, phase_number, phase_name)

    @property
    def title_label(self) -> QLabel:
        return self._title_label

    @property
    def phase_badge(self) -> QLabel:
        return self._phase_badge

    def _build_ui(
        self,
        title: str,
        subtitle: str,
        phase_number: int | None,
        phase_name: str,
    ) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8,
        )
        root.setSpacing(Spacing.S4)

        # Title + subtitle (top-left, consistent with other pages)
        self._title_label = QLabel(title, self)
        self._title_label.setProperty("class", "page-title")

        subtitle_label = QLabel(subtitle, self)
        subtitle_label.setProperty("class", "page-subtitle")

        root.addWidget(self._title_label)
        root.addWidget(subtitle_label)
        root.addSpacing(Spacing.S8)

        # Centered phase badge
        center_box = QVBoxLayout()
        center_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if phase_number is not None:
            badge_text = (
                f"Fáze {phase_number}: {phase_name}\n\n"
                f"Tato sekce bude přidána v této fázi.\n"
                f"Spadá do sprintu pro daňové přiznání do 4. 5. 2026."
            )
        else:
            badge_text = (
                f"{phase_name}\n\n"
                f"Tato sekce bude doplněna postupně."
            )

        self._phase_badge = QLabel(badge_text, self)
        self._phase_badge.setProperty("class", "placeholder-badge")
        self._phase_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._phase_badge.setWordWrap(True)
        self._phase_badge.setFixedWidth(450)

        center_box.addWidget(
            self._phase_badge, alignment=Qt.AlignmentFlag.AlignCenter,
        )

        root.addLayout(center_box)
        root.addStretch(1)
