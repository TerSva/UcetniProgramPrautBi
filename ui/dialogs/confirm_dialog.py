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
    QTextEdit,
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
        show_note: bool = False,
        note_placeholder: str = "Volitelná poznámka…",
        initial_note: str | None = None,
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
        self._note_edit: QTextEdit | None = None
        self._destructive = destructive
        self._show_note = show_note

        self._build_ui(
            title, message, confirm_text, cancel_text,
            note_placeholder, initial_note,
        )

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

    @classmethod
    def ask_with_note(
        cls,
        parent: QWidget | None,
        title: str,
        message: str,
        confirm_text: str = "Potvrdit",
        cancel_text: str = "Zrušit",
        destructive: bool = False,
        note_placeholder: str = "Volitelná poznámka…",
        initial_note: str | None = None,
    ) -> tuple[bool, str | None]:
        """Jako ``ask``, navíc s textovým polem pro poznámku.

        Fokus je po otevření na textovém poli, aby uživatelka mohla
        rovnou psát. Prázdná poznámka se vrátí jako ``None``.

        Returns:
            (confirmed, note) — ``confirmed=False`` → ``note=None``.
        """
        dialog = cls(
            title=title,
            message=message,
            confirm_text=confirm_text,
            cancel_text=cancel_text,
            destructive=destructive,
            show_note=True,
            note_placeholder=note_placeholder,
            initial_note=initial_note,
            parent=parent,
        )
        confirmed = dialog.exec() == QDialog.DialogCode.Accepted
        if not confirmed:
            return (False, None)
        raw = dialog.note_text()
        stripped = raw.strip() if raw else ""
        return (True, stripped or None)

    def note_text(self) -> str:
        """Vrátí text z textového pole (prázdný string pokud chybí pole)."""
        if self._note_edit is None:
            return ""
        return self._note_edit.toPlainText()

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

    @property
    def _note_edit_widget(self) -> QTextEdit | None:
        return self._note_edit

    # ─── Build ────────────────────────────────────────────────────

    def _build_ui(
        self,
        title: str,
        message: str,
        confirm_text: str,
        cancel_text: str,
        note_placeholder: str,
        initial_note: str | None,
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

        if self._show_note:
            self._note_edit = QTextEdit(self)
            self._note_edit.setProperty("class", "dialog-note")
            self._note_edit.setPlaceholderText(note_placeholder)
            self._note_edit.setAcceptRichText(False)
            self._note_edit.setMinimumHeight(80)
            if initial_note:
                self._note_edit.setPlainText(initial_note)
            root.addWidget(self._note_edit)

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

        # Fokus na textarea, pokud existuje — uživatelka může rovnou psát.
        if self._note_edit is not None:
            self._note_edit.setFocus()
