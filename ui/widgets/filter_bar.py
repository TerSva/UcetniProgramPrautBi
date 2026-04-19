"""FilterBar — řádek s dropdowny pro filtrování seznamu dokladů.

4 filtry:
    * Rok (All / 2022..aktuální)
    * Typ dokladu
    * Stav dokladu
    * K dořešení (Skrýt / Vše / Pouze)

+ tlačítko „Vymazat filtry"

Emituje jeden `filters_changed(rok, typ, stav, k_doreseni)` signál pokaždé,
když se kterákoli hodnota změní. Page VOLÁ vm.apply_filters() s kompletem.

Žádné date pickery, žádný search input — scope Kroku 3.
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from domain.doklady.typy import StavDokladu, TypDokladu
from services.queries.doklady_list import DokladyFilter, KDoreseniFilter
from ui.design_tokens import Spacing
from ui.widgets.badge import stav_display_text, typ_display_text


#: Kolik posledních let zobrazit v dropdownu Rok (vedle aktuálního).
_ROK_HISTORY_YEARS = 5


class FilterBar(QWidget):
    """Horizontální panel s 4 dropdowny + tlačítkem pro reset."""

    #: Emitováno při změně kteréhokoli filtru — posílá kompletní stav.
    filters_changed = pyqtSignal(object, object, object, object)
    # (rok: int|None, typ: TypDokladu|None, stav: StavDokladu|None,
    #  k_doreseni: KDoreseniFilter)

    #: Emitováno při kliknutí na „Vymazat filtry".
    clear_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FilterBar")
        self.setProperty("class", "filter-bar")
        self.setProperty("active", "false")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._suppress_signals = False
        self._typ_hidden = False  # True when typ combo is hidden by preset
        self._build_ui()
        self._wire_signals()
        self._refresh_active_indicator()

    # ────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────

    def current_filter(self) -> DokladyFilter:
        """Přečti aktuální stav všech dropdownů jako DokladyFilter."""
        return DokladyFilter(
            rok=self._combo_rok.currentData(),
            typ=self._combo_typ.currentData(),
            stav=self._combo_stav.currentData(),
            k_doreseni=self._combo_doreseni.currentData(),
        )

    def set_filter(self, f: DokladyFilter) -> None:
        """Naplň dropdowny z DokladyFilter bez emitu signálů."""
        self._suppress_signals = True
        try:
            self._set_combo_data(self._combo_rok, f.rok)
            self._set_combo_data(self._combo_typ, f.typ)
            self._set_combo_data(self._combo_stav, f.stav)
            self._set_combo_data(self._combo_doreseni, f.k_doreseni)
        finally:
            self._suppress_signals = False
        self._refresh_active_indicator()

    def set_typ(self, typ: TypDokladu | None) -> None:
        """Nastav jen Typ filter programaticky a emitni filters_changed.

        Slouží pro drill-down z Dashboardu — klik na Pohledávky vyvolá
        ``filter_bar.set_typ(TypDokladu.FAKTURA_VYDANA)``, ostatní filtry
        zůstanou beze změny.
        """
        self._suppress_signals = True
        try:
            self._set_combo_data(self._combo_typ, typ)
        finally:
            self._suppress_signals = False
        self._refresh_active_indicator()
        self.filters_changed.emit(
            self._combo_rok.currentData(),
            self._combo_typ.currentData(),
            self._combo_stav.currentData(),
            self._combo_doreseni.currentData(),
        )

    def hide_typ_combo(self) -> None:
        """Skryj Typ combo (preset stránka). Typ se nepočítá do aktivních filtrů."""
        self._typ_hidden = True
        self._combo_typ.setVisible(False)

    def reset(self) -> None:
        """Vrať všechny dropdowny do default stavu a emitni clear_requested.

        Hidden combo (preset typ) zůstává beze změny.
        """
        # Preserve hidden typ combo value
        preserved_typ = self._combo_typ.currentData() if self._typ_hidden else None
        self.set_filter(DokladyFilter(typ=preserved_typ))
        self.clear_requested.emit()

    def has_active_filters(self) -> bool:
        """True pokud je nějaký uživatelský filtr na jiné než výchozí hodnotě."""
        return self.active_filters_count() > 0

    def active_filters_count(self) -> int:
        """Počet filtrů s non-default hodnotou (0–3).

        Používá se pro status bar „N filtrů aktivní".
        Hidden typ combo (preset stránky) se nepočítá.
        """
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
        return count

    # ────────────────────────────────────────────────
    # Test-only accessors (underscore prefix = interní API)
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

    # ────────────────────────────────────────────────
    # Build
    # ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S4, Spacing.S3, Spacing.S4, Spacing.S3,
        )
        root.setSpacing(Spacing.S1)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Spacing.S3)

        # Rok
        self._combo_rok = QComboBox(self)
        self._combo_rok.addItem("Všechny roky", None)
        current_year = date.today().year
        for rok in range(current_year, current_year - _ROK_HISTORY_YEARS, -1):
            self._combo_rok.addItem(str(rok), rok)
        row.addLayout(_labeled("Rok", self._combo_rok))

        # Typ
        self._combo_typ = QComboBox(self)
        self._combo_typ.addItem("Všechny typy", None)
        for typ in TypDokladu:
            if typ == TypDokladu.BANKOVNI_VYPIS:
                continue  # BV managed in Banka section
            self._combo_typ.addItem(typ_display_text(typ), typ)
        row.addLayout(_labeled("Typ", self._combo_typ))

        # Stav
        self._combo_stav = QComboBox(self)
        self._combo_stav.addItem("Všechny stavy", None)
        for stav in StavDokladu:
            self._combo_stav.addItem(stav_display_text(stav), stav)
        row.addLayout(_labeled("Stav", self._combo_stav))

        # K dořešení
        self._combo_doreseni = QComboBox(self)
        self._combo_doreseni.addItem("Zobrazit vše", KDoreseniFilter.VSE)
        self._combo_doreseni.addItem("Skrýt k dořešení", KDoreseniFilter.SKRYT)
        self._combo_doreseni.addItem("Pouze k dořešení", KDoreseniFilter.POUZE)
        row.addLayout(_labeled("K dořešení", self._combo_doreseni))

        row.addStretch(1)

        # Aktivní-filtr indikátor — barevná tečka s textem. Skrytý v default stavu.
        self._active_indicator = QLabel("● Filtr aktivní", self)
        self._active_indicator.setProperty("class", "filter-active-indicator")
        self._active_indicator.setVisible(False)
        row.addWidget(self._active_indicator)

        # Clear button
        self._clear_button = QPushButton("Vymazat filtry", self)
        self._clear_button.setProperty("class", "secondary")
        self._clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self._clear_button)

        root.addLayout(row)

    def _wire_signals(self) -> None:
        for combo in (
            self._combo_rok,
            self._combo_typ,
            self._combo_stav,
            self._combo_doreseni,
        ):
            combo.currentIndexChanged.connect(self._on_any_changed)
        self._clear_button.clicked.connect(self._on_clear_clicked)

    # ────────────────────────────────────────────────
    # Slots
    # ────────────────────────────────────────────────

    def _on_any_changed(self, _index: int) -> None:
        if self._suppress_signals:
            return
        self._refresh_active_indicator()
        self.filters_changed.emit(
            self._combo_rok.currentData(),
            self._combo_typ.currentData(),
            self._combo_stav.currentData(),
            self._combo_doreseni.currentData(),
        )

    def _on_clear_clicked(self) -> None:
        self.reset()

    def _refresh_active_indicator(self) -> None:
        """Přepni indikátor podle aktuálního stavu filtrů."""
        active = self.has_active_filters()
        self._active_indicator.setVisible(active)
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    # ────────────────────────────────────────────────
    # Internals
    # ────────────────────────────────────────────────

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: object) -> None:
        """Najdi index s daným .currentData() a přepni combo na něj.

        Pokud hodnota není v dropdownu, nechá combo na indexu 0.
        """
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
        combo.setCurrentIndex(0)


def _labeled(label_text: str, widget: QWidget) -> QVBoxLayout:
    """Helper: malý label nad widgetem."""
    box = QVBoxLayout()
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(2)
    label = QLabel(label_text)
    label.setProperty("class", "filter-label")
    box.addWidget(label)
    box.addWidget(widget)
    return box
