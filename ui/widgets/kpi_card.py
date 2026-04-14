"""KpiCard — kartička pro jednu KPI hodnotu na Dashboardu.

Layout:
    ┌─────────────────────────┐
    │ LABEL (uppercase, gray) │
    │                         │
    │ VALUE                   │
    │ (large, brand)          │
    │                         │
    │ subtitle (muted)        │
    └─────────────────────────┘

Subtitle widget je vytvořen vždy a viditelnost se řídí přes `setVisible()`,
aby se vyhnulo destrukci/rekonstrukci widgetu mezi stavy s a bez subtitle.

Subtitle lze volitelně udělat „clickable" — emituje signal `subtitle_clicked`
a získá QSS property `clickable="true"` (underline + brand barva + cursor).

Žádné `setStyleSheet()` — všechny barvy a typografie přicházejí z globálního
QSS přes property-based selektory (class + variant).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ui.design_tokens import Spacing


class _SubtitleLabel(QLabel):
    """QLabel, který emituje `clicked` pouze když je `clickable=True`.

    Interní třída KpiCard — nesmí se používat zvenku.
    """

    clicked = pyqtSignal()

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._clickable = False

    def set_clickable(self, clickable: bool) -> None:
        self._clickable = clickable
        self.setProperty("clickable", "true" if clickable else "false")
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.unsetCursor()
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, ev: QMouseEvent) -> None:  # noqa: N802 (Qt API)
        if self._clickable and ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            ev.accept()
            return
        super().mousePressEvent(ev)


class KpiCard(QFrame):
    """KPI kartička s labelem, hlavní hodnotou a volitelným podtitulkem."""

    #: Emituje se při kliku na subtitle, pokud je `subtitle_clickable=True`.
    subtitle_clicked = pyqtSignal()

    def __init__(
        self,
        label: str,
        value: str,
        subtitle: str | None = None,
        positive: bool = False,
        subtitle_clickable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("class", "kpi-card")
        self.setProperty("positive", "true" if positive else "false")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Spacing.S5, Spacing.S5, Spacing.S5, Spacing.S5
        )
        layout.setSpacing(Spacing.S2)

        self._label = QLabel(label, self)
        self._label.setProperty("class", "kpi-label")

        self._value = QLabel(value, self)
        self._value.setProperty("class", "kpi-value")
        self._value.setProperty("positive", "true" if positive else "false")
        self._value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self._subtitle = _SubtitleLabel(subtitle or "", self)
        self._subtitle.setProperty("class", "kpi-subtitle")
        self._subtitle.setProperty("clickable", "false")
        self._subtitle.setVisible(subtitle is not None)
        self._subtitle.clicked.connect(self.subtitle_clicked)
        if subtitle_clickable:
            self._subtitle.set_clickable(True)

        layout.addWidget(self._label)
        layout.addWidget(self._value)
        layout.addStretch(1)
        layout.addWidget(self._subtitle)

    # ────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────

    def set_value(self, value: str) -> None:
        self._value.setText(value)

    def set_subtitle(self, subtitle: str | None) -> None:
        self._subtitle.setText(subtitle or "")
        self._subtitle.setVisible(subtitle is not None)

    def set_positive(self, positive: bool) -> None:
        flag = "true" if positive else "false"
        self.setProperty("positive", flag)
        self._value.setProperty("positive", flag)
        # Refresh QSS — Qt nereaguje na změnu property bez unpolish/polish
        for w in (self, self._value):
            w.style().unpolish(w)
            w.style().polish(w)

    def set_subtitle_clickable(self, clickable: bool) -> None:
        """Zapne/vypne klikatelnost subtitle. Žádný signál se neemituje."""
        self._subtitle.set_clickable(clickable)

    # ────────────────────────────────────────────────
    # Test-friendly accessors
    # ────────────────────────────────────────────────

    @property
    def label_widget(self) -> QLabel:
        return self._label

    @property
    def value_widget(self) -> QLabel:
        return self._value

    @property
    def subtitle_widget(self) -> QLabel:
        return self._subtitle
