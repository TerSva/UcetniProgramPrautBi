"""Labeled input widgets — label + Qt widget + volitelná chybová hláška.

Společný pattern: nahoře label, pod ním samotný input widget, pod ním
schovaný error label (red). ``set_error(msg)`` ho ukáže a přidá třídu
``input-error`` na vnitřní widget — QSS mu dá červený border.

Pět variant:
    * ``LabeledLineEdit`` — QLineEdit (jednořádkový text, max_length).
    * ``LabeledTextEdit`` — QPlainTextEdit (víceřádkový).
    * ``LabeledDateEdit`` — QLineEdit pro datum (d.M.yyyy), volitelně clearable.
    * ``LabeledMoneyEdit`` — QLineEdit s Money parsingem (vstup v Kč).
    * ``LabeledComboBox`` — QComboBox s typovou safety (itemData).

Žádný widget nevolá ``setStyleSheet()`` — všechno přes ``setProperty``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Generic, TypeVar

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from domain.shared.money import Money
from ui.design_tokens import Spacing


T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════════
# Společná kostra
# ═══════════════════════════════════════════════════════════════════


class _LabeledBase(QWidget):
    """Kostra: label nahoře, widget uprostřed, error dole."""

    def __init__(
        self,
        label_text: str,
        inner: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._inner = inner
        self._label = QLabel(label_text, self)
        self._label.setProperty("class", "input-label")

        self._error = QLabel("", self)
        self._error.setProperty("class", "input-error-text")
        self._error.setWordWrap(True)
        self._error.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.S1)
        layout.addWidget(self._label)
        layout.addWidget(self._inner)
        layout.addWidget(self._error)

    # ── Error state ──────────────────────────────────────────────

    def set_error(self, message: str | None) -> None:
        """Ukaž/skryj chybovou hlášku a přepni vzhled vnitřního widgetu."""
        if message:
            self._error.setText(message)
            self._error.setVisible(True)
            self._inner.setProperty("class", "input-error")
        else:
            self._error.clear()
            self._error.setVisible(False)
            self._inner.setProperty("class", "")
        # Refresh style po změně property
        self._inner.style().unpolish(self._inner)
        self._inner.style().polish(self._inner)

    @property
    def label_widget(self) -> QLabel:
        return self._label

    @property
    def error_widget(self) -> QLabel:
        return self._error

    @property
    def inner_widget(self) -> QWidget:
        return self._inner


# ═══════════════════════════════════════════════════════════════════
# Varianty
# ═══════════════════════════════════════════════════════════════════


class LabeledLineEdit(_LabeledBase):
    """Jednořádkové textové pole."""

    text_changed = pyqtSignal(str)

    def __init__(
        self,
        label_text: str,
        placeholder: str = "",
        max_length: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self._line = QLineEdit()
        if placeholder:
            self._line.setPlaceholderText(placeholder)
        if max_length is not None:
            self._line.setMaxLength(max_length)
        super().__init__(label_text, self._line, parent)
        self._line.textChanged.connect(self.text_changed)

    def value(self) -> str:
        return self._line.text()

    def set_value(self, text: str) -> None:
        self._line.setText(text)

    @property
    def line_widget(self) -> QLineEdit:
        return self._line


class LabeledTextEdit(_LabeledBase):
    """Víceřádkové textové pole."""

    def __init__(
        self,
        label_text: str,
        placeholder: str = "",
        rows: int = 4,
        parent: QWidget | None = None,
    ) -> None:
        self._edit = QPlainTextEdit()
        if placeholder:
            self._edit.setPlaceholderText(placeholder)
        line_height = 20
        self._edit.setFixedHeight(line_height * rows + 12)
        super().__init__(label_text, self._edit, parent)

    def value(self) -> str:
        return self._edit.toPlainText()

    def set_value(self, text: str) -> None:
        self._edit.setPlainText(text)

    @property
    def edit_widget(self) -> QPlainTextEdit:
        return self._edit


class LabeledDateEdit(_LabeledBase):
    """Datum input — QLineEdit pro volné psaní data (d.M.yyyy).

    clearable=False: předvyplněno dnešním datem, vždy má hodnotu.
    clearable=True: prázdný placeholder — pole může být prázdné (→ None).
    """

    def __init__(
        self,
        label_text: str,
        clearable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        self._clearable = clearable
        self._line_edit: QLineEdit | None = None

        # Obě varianty používají QLineEdit pro volné psaní data.
        # clearable=True: pole může být prázdné (→ None).
        # clearable=False: předvyplněno dnešním datem.
        self._line_edit = QLineEdit()
        self._line_edit.setPlaceholderText("d.M.yyyy")
        if not clearable:
            today = date.today()
            self._line_edit.setText(f"{today.day}.{today.month}.{today.year}")
        widget = self._line_edit

        super().__init__(label_text, widget, parent)

    def value(self) -> date | None:
        assert self._line_edit is not None
        text = self._line_edit.text().strip()
        if not text:
            return None
        return self._parse_date(text)

    def set_value(self, d: date | None) -> None:
        assert self._line_edit is not None
        if d is None:
            if self._clearable:
                self._line_edit.clear()
            else:
                today = date.today()
                self._line_edit.setText(f"{today.day}.{today.month}.{today.year}")
        else:
            self._line_edit.setText(f"{d.day}.{d.month}.{d.year}")

    @property
    def date_widget(self) -> QLineEdit:
        assert self._line_edit is not None
        return self._line_edit

    @staticmethod
    def _parse_date(text: str) -> date | None:
        """Tolerantní datum parser.

        Podporované formáty:
          * d.M.yyyy / d.M.yy        — český s tečkami
          * d/M/yyyy / d/M/yy        — lomítky
          * d-M-yyyy / d-M-yy        — pomlčky (ne ISO!)
          * yyyy-MM-dd / yyyy/MM/dd  — ISO
          * d M yyyy / d M yy        — mezery
          * "dnes" / "vcera"         — klíčová slova
        """
        from datetime import timedelta

        text = text.strip().lower()
        if not text:
            return None

        # Klíčová slova
        if text in ("dnes", "today"):
            return date.today()
        if text in ("vcera", "včera", "yesterday"):
            return date.today() - timedelta(days=1)

        # ISO formát: yyyy-MM-dd nebo yyyy/MM/dd (rok první, 4 číslice)
        iso_text = text.replace("/", "-")
        if len(iso_text) == 10 and iso_text[4] == "-" and iso_text[7] == "-":
            try:
                return date.fromisoformat(iso_text)
            except ValueError:
                pass

        # Český formát: rozdělit po tečkách / lomítkách / pomlčkách / mezerách
        normalized = text
        for sep in ("/", "-"):
            normalized = normalized.replace(sep, ".")
        # Mezera jako separátor (jen pokud nejsou tečky)
        if "." not in normalized and " " in normalized:
            normalized = ".".join(normalized.split())
        parts = [p for p in normalized.split(".") if p]
        if len(parts) != 3:
            return None
        try:
            day = int(parts[0])
            month = int(parts[1])
            year = int(parts[2])
            if year < 100:
                year += 2000
            return date(year, month, day)
        except (ValueError, OverflowError):
            return None


class LabeledMoneyEdit(_LabeledBase):
    """QLineEdit pro korunové částky.

    Parse tolerantní k českému formátu (mezery jako oddělovače tisíců,
    čárka jako desetinný oddělovač). ``value()`` vrátí ``Money`` nebo
    ``None`` pokud text neodpovídá validnímu číslu.
    """

    def __init__(
        self,
        label_text: str,
        placeholder: str = "0,00",
        parent: QWidget | None = None,
    ) -> None:
        self._line = QLineEdit()
        self._line.setPlaceholderText(placeholder)
        super().__init__(label_text, self._line, parent)

    def value(self) -> Money | None:
        text = self._line.text().strip()
        if not text:
            return None
        # Normalizace — podporuj "12 100,50", "12100.50", "12100".
        normalized = text.replace(" ", "").replace("\u00A0", "")
        normalized = normalized.replace(",", ".")
        try:
            dec = Decimal(normalized)
        except (InvalidOperation, ValueError):
            return None
        return Money.from_koruny(str(dec))

    def set_value(self, money: Money | None) -> None:
        if money is None:
            self._line.clear()
            return
        # Formátuj jako "12100,50" (bez měny, bez tisícových oddělovačů —
        # uživatelka si je pak může doplnit sama, ale primárně píše číslo).
        halire = money.to_halire()
        koruny = halire // 100
        cent = abs(halire) % 100
        sign = "-" if halire < 0 else ""
        self._line.setText(f"{sign}{abs(koruny)},{cent:02d}")

    @property
    def line_widget(self) -> QLineEdit:
        return self._line


class LabeledComboBox(_LabeledBase, Generic[T]):
    """QComboBox se stabilním ``value()`` přes ``currentData()``."""

    current_value_changed = pyqtSignal(object)

    def __init__(
        self,
        label_text: str,
        parent: QWidget | None = None,
    ) -> None:
        self._combo = QComboBox()
        super().__init__(label_text, self._combo, parent)
        self._combo.currentIndexChanged.connect(self._on_changed)

    def add_item(self, display: str, value: T) -> None:
        self._combo.addItem(display, value)

    def clear_items(self) -> None:
        self._combo.clear()

    def value(self) -> T | None:
        data = self._combo.currentData()
        return data  # type: ignore[return-value]

    def set_value(self, value: T | None) -> None:
        for i in range(self._combo.count()):
            if self._combo.itemData(i) == value:
                self._combo.setCurrentIndex(i)
                return
        self._combo.setCurrentIndex(-1)

    def _on_changed(self, _index: int) -> None:
        self.current_value_changed.emit(self.value())

    @property
    def combo_widget(self) -> QComboBox:
        return self._combo
