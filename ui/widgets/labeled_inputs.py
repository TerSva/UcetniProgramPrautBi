"""Labeled input widgets — label + Qt widget + volitelná chybová hláška.

Společný pattern: nahoře label, pod ním samotný input widget, pod ním
schovaný error label (red). ``set_error(msg)`` ho ukáže a přidá třídu
``input-error`` na vnitřní widget — QSS mu dá červený border.

Pět variant:
    * ``LabeledLineEdit`` — QLineEdit (jednořádkový text, max_length).
    * ``LabeledTextEdit`` — QPlainTextEdit (víceřádkový).
    * ``LabeledDateEdit`` — QDateEdit s calendar popupem (+ clearable).
    * ``LabeledMoneyEdit`` — QLineEdit s Money parsingem (vstup v Kč).
    * ``LabeledComboBox`` — QComboBox s typovou safety (itemData).

Žádný widget nevolá ``setStyleSheet()`` — všechno přes ``setProperty``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Generic, TypeVar

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
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
    """QDateEdit s calendar popupem. ``clearable`` povolí None (= prázdno)."""

    def __init__(
        self,
        label_text: str,
        clearable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("d. M. yyyy")
        self._date.setDate(QDate.currentDate())
        self._clearable = clearable
        self._is_empty = False
        if clearable:
            # Qt nemá native "empty" stav; simulujeme placeholderem přes
            # speciální datum + flag. Uživatelka dostane prázdnou lineEdit.
            self._date.setSpecialValueText(" ")
            self._date.setMinimumDate(QDate(1900, 1, 1))
        super().__init__(label_text, self._date, parent)

    def value(self) -> date | None:
        if self._clearable and self._is_empty:
            return None
        qd = self._date.date()
        return date(qd.year(), qd.month(), qd.day())

    def set_value(self, d: date | None) -> None:
        if d is None:
            if self._clearable:
                self._is_empty = True
                self._date.setDate(self._date.minimumDate())
            else:
                self._date.setDate(QDate.currentDate())
            return
        self._is_empty = False
        self._date.setDate(QDate(d.year, d.month, d.day))

    @property
    def date_widget(self) -> QDateEdit:
        return self._date


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
