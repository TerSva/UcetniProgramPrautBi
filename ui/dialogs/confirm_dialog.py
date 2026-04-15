"""ConfirmDialog — jednoduchý OK/Cancel modal.

Použití:
    ok = ConfirmDialog.ask(
        parent,
        title="Stornovat doklad",
        message="Opravdu chcete stornovat FV-2026-001? Tato akce je nevratná.",
        destructive=True,
    )

``destructive=True`` změní potvrzovací tlačítko na červené (třída
``destructive``) — kontrastní k primárnímu teal.
"""

from __future__ import annotations

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


class ConfirmDialog(QDialog):
    """Modální potvrzovací dialog."""

    def __init__(
        self,
        title: str,
        message: str,
        confirm_text: str = "Potvrdit",
        cancel_text: str = "Zrušit",
        destructive: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setProperty("class", "confirm-dialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(400)

        self._title_label: QLabel
        self._message_label: QLabel
        self._confirm_button: QPushButton
        self._cancel_button: QPushButton
        self._destructive = destructive

        self._build_ui(title, message, confirm_text, cancel_text)

    @classmethod
    def ask(
        cls,
        parent: QWidget | None,
        title: str,
        message: str,
        confirm_text: str = "Potvrdit",
        cancel_text: str = "Zrušit",
        destructive: bool = False,
    ) -> bool:
        """Otevře dialog modálně a vrátí ``True`` pokud uživatelka potvrdila."""
        dialog = cls(
            title=title,
            message=message,
            confirm_text=confirm_text,
            cancel_text=cancel_text,
            destructive=destructive,
            parent=parent,
        )
        return dialog.exec() == QDialog.DialogCode.Accepted

    # ─── Test-only accessors ──────────────────────────────────────

    @property
    def _confirm_button_widget(self) -> QPushButton:
        return self._confirm_button

    @property
    def _cancel_button_widget(self) -> QPushButton:
        return self._cancel_button

    @property
    def _message_widget(self) -> QLabel:
        return self._message_label

    # ─── Build ────────────────────────────────────────────────────

    def _build_ui(
        self,
        title: str,
        message: str,
        confirm_text: str,
        cancel_text: str,
    ) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        self._title_label = QLabel(title, self)
        self._title_label.setProperty("class", "dialog-title")
        root.addWidget(self._title_label)

        self._message_label = QLabel(message, self)
        self._message_label.setProperty("class", "dialog-message")
        self._message_label.setWordWrap(True)
        root.addWidget(self._message_label)

        root.addStretch(1)

        footer = QHBoxLayout()
        footer.addStretch(1)

        self._cancel_button = QPushButton(cancel_text, self)
        self._cancel_button.setProperty("class", "secondary")
        self._cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_button.clicked.connect(self.reject)
        footer.addWidget(self._cancel_button)

        self._confirm_button = QPushButton(confirm_text, self)
        variant_class = "destructive" if self._destructive else "primary"
        self._confirm_button.setProperty("class", variant_class)
        self._confirm_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._confirm_button.clicked.connect(self.accept)
        footer.addWidget(self._confirm_button)

        root.addLayout(footer)
