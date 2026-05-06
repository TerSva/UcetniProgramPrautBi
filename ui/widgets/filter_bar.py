"""FilterBar — kompletní filtrace seznamu dokladů.

Filtry:
  Řádek 1: Rok | Typ | Stav | K dořešení
  Řádek 2: Datum od/do (preset) | DPH režim | Partner | Hledat | Vymazat

Auto-apply: jakákoli změna emituje `filters_changed` signál (4-arg, kvůli
zpětné kompatibilitě testů). Hledání má debounce 300 ms; ostatní okamžitě.
Pages volají `current_filter()` pro získání DokladyFilter snapshotu.

Partner combo se naplní callbackem `partner_loader` (nepovinně).
"""

from __future__ import annotations

from datetime import date
from typing import Callable

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from domain.doklady.typy import DphRezim, StavDokladu, TypDokladu
from domain.shared.money import Money
from services.queries.doklady_list import DokladyFilter, KDoreseniFilter
from ui.design_tokens import Spacing
from ui.widgets.badge import stav_display_text, typ_display_text
from ui.widgets.date_range_filter import DateRangeFilter
from ui.widgets.labeled_inputs import LabeledMoneyEdit


#: Kolik posledních let zobrazit v dropdownu Rok (vedle aktuálního).
_ROK_HISTORY_YEARS = 5


class FilterBar(QWidget):
    """Horizontální panel s rozšířenými filtry + reset tlačítkem."""

    #: Emitováno při změně kteréhokoli filtru (4-arg, kvůli back-compat).
    filters_changed = pyqtSignal(object, object, object, object)
    # (rok: int|None, typ: TypDokladu|None, stav: StavDokladu|None,
    #  k_doreseni: KDoreseniFilter)

    #: Emitováno při kliknutí na „Vymazat filtry".
    clear_requested = pyqtSignal()

    SEARCH_DEBOUNCE_MS = 300

    def __init__(
        self,
        partner_loader: Callable[[], list[tuple[int, str]]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("FilterBar")
        self.setProperty("class", "filter-bar")
        self.setProperty("active", "false")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._suppress_signals = False
        self._typ_hidden = False  # True when typ combo is hidden by preset
        self._partner_loader = partner_loader
        self._search_timer: QTimer

        self._build_ui()
        self._wire_signals()
        self._refresh_active_indicator()
        self._load_partner_options()

    # ────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────

    def current_filter(self) -> DokladyFilter:
        """Přečti aktuální stav všech filtrů jako DokladyFilter."""
        od, do = self._date_range.current_range()
        return DokladyFilter(
            rok=self._combo_rok.currentData(),
            typ=self._combo_typ.currentData(),
            stav=self._combo_stav.currentData(),
            k_doreseni=self._combo_doreseni.currentData(),
            datum_od=od,
            datum_do=do,
            partner_id=self._combo_partner.currentData(),
            castka_od=self._castka_od.value(),
            castka_do=self._castka_do.value(),
            dph_rezim=self._combo_dph.currentData(),
            search_text=self._search_input.text().strip(),
            je_vystavena=self._combo_zaloha.currentData(),
        )

    def set_filter(self, f: DokladyFilter) -> None:
        """Naplň všechny widgety z DokladyFilter bez emitu signálů."""
        self._suppress_signals = True
        try:
            self._set_combo_data(self._combo_rok, f.rok)
            self._set_combo_data(self._combo_typ, f.typ)
            self._set_combo_data(self._combo_stav, f.stav)
            self._set_combo_data(self._combo_doreseni, f.k_doreseni)
            self._set_combo_data(self._combo_partner, f.partner_id)
            self._set_combo_data(self._combo_dph, f.dph_rezim)
            self._set_combo_data(self._combo_zaloha, f.je_vystavena)
            self._castka_od.set_value(f.castka_od)
            self._castka_do.set_value(f.castka_do)
            self._search_input.setText(f.search_text or "")
            # DateRange — set hodnoty programaticky
            if f.datum_od is None and f.datum_do is None:
                self._date_range._apply_preset("Vše", emit=False)  # noqa: SLF001
            else:
                self._date_range._od_input.set_value(f.datum_od)  # noqa: SLF001
                self._date_range._do_input.set_value(f.datum_do)  # noqa: SLF001
        finally:
            self._suppress_signals = False
        self._refresh_active_indicator()

    def set_typ(self, typ: TypDokladu | None) -> None:
        """Nastav jen Typ filter programaticky a emitni filters_changed."""
        self._suppress_signals = True
        try:
            self._set_combo_data(self._combo_typ, typ)
        finally:
            self._suppress_signals = False
        self._refresh_active_indicator()
        self._emit_filters()

    def hide_typ_combo(self) -> None:
        """Skryj Typ combo (preset stránka)."""
        self._typ_hidden = True
        self._combo_typ.setVisible(False)
        self._typ_label.setVisible(False)

    def reset(self) -> None:
        """Vrať všechny widgety do default stavu."""
        preserved_typ = self._combo_typ.currentData() if self._typ_hidden else None
        self.set_filter(DokladyFilter(typ=preserved_typ))
        self.clear_requested.emit()

    def has_active_filters(self) -> bool:
        return self.active_filters_count() > 0

    def active_filters_count(self) -> int:
        """Počet filtrů s non-default hodnotou."""
        f = self.current_filter()
        count = 0
        if f.rok is not None:
            count += 1
        if f.typ is not None and not self._typ_hidden:
            count += 1
        if f.stav is not None:
            count += 1
        if f.k_doreseni != KDoreseniFilter.VSE:
            count += 1
        if f.datum_od is not None or f.datum_do is not None:
            count += 1
        if f.partner_id is not None:
            count += 1
        if f.castka_od is not None or f.castka_do is not None:
            count += 1
        if f.dph_rezim is not None:
            count += 1
        if f.search_text.strip():
            count += 1
        if f.je_vystavena is not None:
            count += 1
        return count

    # ────────────────────────────────────────────────
    # Test-only accessors
    # ────────────────────────────────────────────────

    @property
    def _combo_rok_widget(self) -> QComboBox:
        return self._combo_rok

    @property
    def _combo_typ_widget(self) -> QComboBox:
        return self._combo_typ

    @property
    def _combo_stav_widget(self) -> QComboBox:
        return self._combo_stav

    @property
    def _combo_doreseni_widget(self) -> QComboBox:
        return self._combo_doreseni

    @property
    def _clear_button_widget(self) -> QPushButton:
        return self._clear_button

    @property
    def _search_input_widget(self) -> QLineEdit:
        return self._search_input

    @property
    def _combo_partner_widget(self) -> QComboBox:
        return self._combo_partner

    @property
    def _combo_dph_widget(self) -> QComboBox:
        return self._combo_dph

    @property
    def _date_range_widget(self) -> DateRangeFilter:
        return self._date_range

    # ────────────────────────────────────────────────
    # Build
    # ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S4, Spacing.S3, Spacing.S4, Spacing.S3,
        )
        root.setSpacing(Spacing.S2)

        # ── Řádek 1: Rok / Typ / Stav / K dořešení ──
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(Spacing.S3)

        self._combo_rok = QComboBox(self)
        self._combo_rok.addItem("Všechny roky", None)
        current_year = date.today().year
        for rok in range(current_year, current_year - _ROK_HISTORY_YEARS, -1):
            self._combo_rok.addItem(str(rok), rok)
        row1.addLayout(_labeled("Rok", self._combo_rok))

        self._combo_typ = QComboBox(self)
        self._combo_typ.addItem("Všechny typy", None)
        for typ in TypDokladu:
            if typ == TypDokladu.BANKOVNI_VYPIS:
                continue
            self._combo_typ.addItem(typ_display_text(typ), typ)
        # Pamatovat label widget pro hide_typ_combo
        typ_layout = _labeled("Typ", self._combo_typ)
        self._typ_label = typ_layout.itemAt(0).widget()
        row1.addLayout(typ_layout)

        self._combo_stav = QComboBox(self)
        self._combo_stav.addItem("Všechny stavy", None)
        for stav in StavDokladu:
            self._combo_stav.addItem(stav_display_text(stav), stav)
        row1.addLayout(_labeled("Stav", self._combo_stav))

        self._combo_doreseni = QComboBox(self)
        self._combo_doreseni.addItem("Zobrazit vše", KDoreseniFilter.VSE)
        self._combo_doreseni.addItem("Skrýt k dořešení", KDoreseniFilter.SKRYT)
        self._combo_doreseni.addItem("Pouze k dořešení", KDoreseniFilter.POUZE)
        row1.addLayout(_labeled("K dořešení", self._combo_doreseni))

        row1.addStretch(1)

        self._active_indicator = QLabel("● Filtr aktivní", self)
        self._active_indicator.setProperty("class", "filter-active-indicator")
        self._active_indicator.setVisible(False)
        row1.addWidget(self._active_indicator)

        self._clear_button = QPushButton("Vymazat filtry", self)
        self._clear_button.setProperty("class", "secondary")
        self._clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        row1.addWidget(self._clear_button)

        root.addLayout(row1)

        # ── Řádek 2: Datum range | DPH režim | Partner | Částka | Hledat ──
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(Spacing.S3)

        self._date_range = DateRangeFilter(year=current_year, parent=self)
        # Default = "Vše" — ne "Tento rok" — protože už je dropdown Rok
        self._date_range._apply_preset("Vše", emit=False)  # noqa: SLF001
        row2.addWidget(self._date_range)

        self._combo_dph = QComboBox(self)
        self._combo_dph.addItem("Všechny", None)
        self._combo_dph.addItem("Tuzemsko", DphRezim.TUZEMSKO)
        self._combo_dph.addItem("Reverse charge", DphRezim.REVERSE_CHARGE)
        row2.addLayout(_labeled("DPH režim", self._combo_dph))

        # Druh zálohy — pro typ ZF: Vystavená / Přijatá
        self._combo_zaloha = QComboBox(self)
        self._combo_zaloha.addItem("Všechny zálohy", None)
        self._combo_zaloha.addItem("Vystavené (odběratel)", True)
        self._combo_zaloha.addItem("Přijaté (dodavatel)", False)
        row2.addLayout(_labeled("Druh zálohy", self._combo_zaloha))

        self._combo_partner = QComboBox(self)
        self._combo_partner.addItem("Všichni partneři", None)
        self._combo_partner.setMinimumWidth(180)
        row2.addLayout(_labeled("Partner", self._combo_partner))

        self._castka_od = LabeledMoneyEdit(
            "Částka od", placeholder="0", parent=self,
        )
        row2.addWidget(self._castka_od)
        self._castka_do = LabeledMoneyEdit(
            "Částka do", placeholder="∞", parent=self,
        )
        row2.addWidget(self._castka_do)

        # Search input
        self._search_input = QLineEdit(self)
        self._search_input.setPlaceholderText(
            "Hledat (číslo, partner, popis)",
        )
        self._search_input.setMinimumWidth(240)
        row2.addLayout(_labeled("Hledat", self._search_input))

        row2.addStretch(1)
        root.addLayout(row2)

        # Search debounce
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(self.SEARCH_DEBOUNCE_MS)

    def _wire_signals(self) -> None:
        for combo in (
            self._combo_rok,
            self._combo_typ,
            self._combo_stav,
            self._combo_doreseni,
            self._combo_partner,
            self._combo_dph,
            self._combo_zaloha,
        ):
            combo.currentIndexChanged.connect(self._on_any_changed)
        self._date_range.range_changed.connect(self._on_date_range_changed)
        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._search_timer.timeout.connect(self._emit_filters_with_indicator)
        for money_edit in (self._castka_od, self._castka_do):
            money_edit._line.editingFinished.connect(  # noqa: SLF001
                self._emit_filters_with_indicator,
            )
        self._clear_button.clicked.connect(self._on_clear_clicked)

    def _load_partner_options(self) -> None:
        if self._partner_loader is None:
            return
        try:
            partners = self._partner_loader()
        except Exception:  # noqa: BLE001
            return
        self._suppress_signals = True
        try:
            for pid, name in partners:
                self._combo_partner.addItem(name, pid)
        finally:
            self._suppress_signals = False

    # ────────────────────────────────────────────────
    # Slots
    # ────────────────────────────────────────────────

    def _on_any_changed(self, _index: int) -> None:
        if self._suppress_signals:
            return
        self._emit_filters_with_indicator()

    def _on_date_range_changed(
        self, _od: object, _do: object,
    ) -> None:
        if self._suppress_signals:
            return
        self._emit_filters_with_indicator()

    def _on_search_text_changed(self, _text: str) -> None:
        if self._suppress_signals:
            return
        self._search_timer.start()  # debounce

    def _emit_filters_with_indicator(self) -> None:
        self._refresh_active_indicator()
        self._emit_filters()

    def _emit_filters(self) -> None:
        self.filters_changed.emit(
            self._combo_rok.currentData(),
            self._combo_typ.currentData(),
            self._combo_stav.currentData(),
            self._combo_doreseni.currentData(),
        )

    def _on_clear_clicked(self) -> None:
        self.reset()

    def _refresh_active_indicator(self) -> None:
        active = self.has_active_filters()
        count = self.active_filters_count()
        if active:
            self._active_indicator.setText(
                f"● {count} {'filtr' if count == 1 else 'filtry' if count < 5 else 'filtrů'} aktivní"
            )
        self._active_indicator.setVisible(active)
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    # ────────────────────────────────────────────────
    # Internals
    # ────────────────────────────────────────────────

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: object) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
        combo.setCurrentIndex(0)


def _labeled(label_text: str, widget: QWidget) -> QVBoxLayout:
    box = QVBoxLayout()
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(2)
    label = QLabel(label_text)
    label.setProperty("class", "filter-label")
    box.addWidget(label)
    box.addWidget(widget)
    return box
