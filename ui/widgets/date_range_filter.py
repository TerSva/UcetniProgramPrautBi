"""DateRangeFilter — sdílený widget pro filtrování datumového rozsahu.

Inputy „Datum od" / „Datum do" + dropdown s předvolbami (Tento rok,
Minulý rok, Q1–Q4, Tento měsíc, Vše). Emituje `range_changed(od, do)`
signál s debounce 300 ms při ručním psaní data; předvolby aplikují
okamžitě.

Použití:
    bar = DateRangeFilter()
    bar.range_changed.connect(self._on_range_changed)
    bar.set_default_year(2025)  # nastaví "Tento rok" jako výchozí
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from ui.design_tokens import Spacing
from ui.widgets.labeled_inputs import LabeledDateEdit


# Předvolby: (label, fn(today, year_default) -> (od, do) | None)
# None znamená "Vše" (žádný rozsah, query nedává WHERE)
_PRESET_VSE = "Vše"
_PRESET_TENTO_ROK = "Tento rok"
_PRESET_MINULY_ROK = "Minulý rok"
_PRESET_TENTO_MESIC = "Tento měsíc"
_PRESET_MINULY_MESIC = "Minulý měsíc"
_PRESET_Q1 = "Q1"
_PRESET_Q2 = "Q2"
_PRESET_Q3 = "Q3"
_PRESET_Q4 = "Q4"
_PRESET_VLASTNI = "— vlastní —"


def _quarter_range(year: int, quarter: int) -> tuple[date, date]:
    """Vrátí (od, do) pro daný kvartál."""
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2
    od = date(year, start_month, 1)
    if end_month == 12:
        do = date(year, 12, 31)
    else:
        from datetime import timedelta
        first_next = date(year, end_month + 1, 1)
        do = first_next - timedelta(days=1)
    return od, do


def _month_range(today: date) -> tuple[date, date]:
    """Vrátí (1.den, poslední den) aktuálního měsíce."""
    od = today.replace(day=1)
    if today.month == 12:
        do = date(today.year, 12, 31)
    else:
        from datetime import timedelta
        first_next = date(today.year, today.month + 1, 1)
        do = first_next - timedelta(days=1)
    return od, do


def _previous_month_range(today: date) -> tuple[date, date]:
    if today.month == 1:
        return date(today.year - 1, 12, 1), date(today.year - 1, 12, 31)
    od = date(today.year, today.month - 1, 1)
    do = today.replace(day=1).fromordinal(today.replace(day=1).toordinal() - 1)
    return od, do


def _preset_range(
    preset: str, today: date, year: int,
) -> tuple[date | None, date | None]:
    """Vrátí (od, do) pro předvolbu. (None, None) = bez filtru."""
    if preset == _PRESET_VSE:
        return None, None
    if preset == _PRESET_TENTO_ROK:
        return date(year, 1, 1), date(year, 12, 31)
    if preset == _PRESET_MINULY_ROK:
        return date(year - 1, 1, 1), date(year - 1, 12, 31)
    if preset == _PRESET_TENTO_MESIC:
        return _month_range(today)
    if preset == _PRESET_MINULY_MESIC:
        return _previous_month_range(today)
    if preset == _PRESET_Q1:
        return _quarter_range(year, 1)
    if preset == _PRESET_Q2:
        return _quarter_range(year, 2)
    if preset == _PRESET_Q3:
        return _quarter_range(year, 3)
    if preset == _PRESET_Q4:
        return _quarter_range(year, 4)
    # _PRESET_VLASTNI nebo neznámé → vrať None znamenající „nic neměnit"
    return None, None


class DateRangeFilter(QWidget):
    """Datum od + Datum do + dropdown s předvolbami.

    Emituje `range_changed(od, do)` po debounce 300 ms při ručním
    zadání nebo okamžitě po výběru předvolby. (od, do) jsou
    `date | None` (None = bez ohraničení).
    """

    range_changed = pyqtSignal(object, object)
    # (od: date | None, do: date | None)

    DEFAULT_DEBOUNCE_MS = 300

    def __init__(
        self,
        year: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("class", "date-range-filter")
        self._year = year if year is not None else date.today().year
        self._suppress_signals = False

        self._od_input: LabeledDateEdit
        self._do_input: LabeledDateEdit
        self._preset_combo: QComboBox
        self._error_label: QLabel
        self._debounce_timer: QTimer

        self._build_ui()
        self._wire_signals()

        # Default = "Tento rok"
        self._apply_preset(_PRESET_TENTO_ROK, emit=False)

    # ─── UI ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.S3)

        self._od_input = LabeledDateEdit("Datum od", clearable=True, parent=self)
        layout.addWidget(self._od_input)

        self._do_input = LabeledDateEdit("Datum do", clearable=True, parent=self)
        layout.addWidget(self._do_input)

        # Předvolby — kompaktní combo
        preset_label = QLabel("Předvolba:", self)
        preset_label.setProperty("class", "field-label")
        # Vertikálně srovnat s inputy
        preset_wrap = QWidget(self)
        from PyQt6.QtWidgets import QVBoxLayout
        pwl = QVBoxLayout(preset_wrap)
        pwl.setContentsMargins(0, 0, 0, 0)
        pwl.setSpacing(2)
        pwl.addWidget(preset_label)
        self._preset_combo = QComboBox(preset_wrap)
        for p in (
            _PRESET_VLASTNI,
            _PRESET_VSE,
            _PRESET_TENTO_ROK,
            _PRESET_MINULY_ROK,
            _PRESET_TENTO_MESIC,
            _PRESET_MINULY_MESIC,
            _PRESET_Q1, _PRESET_Q2, _PRESET_Q3, _PRESET_Q4,
        ):
            self._preset_combo.addItem(p, p)
        self._preset_combo.setMinimumWidth(140)
        pwl.addWidget(self._preset_combo)
        layout.addWidget(preset_wrap)

        # Chybový label vpravo (pokud parsuju neplatné datum)
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "form-help-error")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        layout.addStretch(1)

        # Debounce timer pro auto-apply při ručním psaní
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(self.DEFAULT_DEBOUNCE_MS)

    def _wire_signals(self) -> None:
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        # Manual edit = textChanged → reset preset to vlastni + debounce emit
        for line_edit in (
            self._od_input.date_widget,
            self._do_input.date_widget,
        ):
            line_edit.textChanged.connect(self._on_text_changed)
        self._debounce_timer.timeout.connect(self._emit_range)

    # ─── Public API ──────────────────────────────────────────────

    def set_year(self, year: int) -> None:
        """Změna roku přepíná default ('Tento rok' = ten zadaný)."""
        self._year = year

    def current_range(self) -> tuple[date | None, date | None]:
        return self._od_input.value(), self._do_input.value()

    # ─── Internals ───────────────────────────────────────────────

    def _on_preset_changed(self, _idx: int) -> None:
        if self._suppress_signals:
            return
        preset = self._preset_combo.currentData()
        if preset == _PRESET_VLASTNI:
            return  # vlastní rozsah už je v inputech
        self._apply_preset(preset, emit=True)

    def _apply_preset(self, preset: str, emit: bool) -> None:
        od, do = _preset_range(preset, date.today(), self._year)
        self._suppress_signals = True
        self._od_input.set_value(od)
        self._do_input.set_value(do)
        # Sync combo na zvolený preset
        idx = self._preset_combo.findData(preset)
        if idx >= 0:
            self._preset_combo.setCurrentIndex(idx)
        self._suppress_signals = False
        self._update_error_state()
        if emit:
            self.range_changed.emit(od, do)

    def _on_text_changed(self) -> None:
        if self._suppress_signals:
            return
        # Přepni combo na "vlastní" — uživatel ručně edituje
        self._suppress_signals = True
        idx = self._preset_combo.findData(_PRESET_VLASTNI)
        if idx >= 0:
            self._preset_combo.setCurrentIndex(idx)
        self._suppress_signals = False
        # Debounce emit
        self._debounce_timer.start()

    def _emit_range(self) -> None:
        od_text = self._od_input.date_widget.text().strip()
        do_text = self._do_input.date_widget.text().strip()
        od = self._od_input.value() if od_text else None
        do = self._do_input.value() if do_text else None

        # Validace: pokud user napsal neplatný formát, ukázat error
        invalid: list[str] = []
        if od_text and od is None:
            invalid.append("Datum od")
        if do_text and do is None:
            invalid.append("Datum do")

        if invalid:
            self._error_label.setText(
                f"Neplatný formát: {', '.join(invalid)}"
            )
            self._error_label.setVisible(True)
            return

        # Validace rozsahu
        if od and do and od > do:
            self._error_label.setText("Datum od je pozdější než Datum do")
            self._error_label.setVisible(True)
            return

        self._error_label.setVisible(False)
        self.range_changed.emit(od, do)

    def _update_error_state(self) -> None:
        self._error_label.setVisible(False)
