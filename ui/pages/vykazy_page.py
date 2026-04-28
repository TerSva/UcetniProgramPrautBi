"""VykazyPage — Účetní závěrka a sestavy (Fáze 15).

Stránka se 7 záložkami:
  1. Rozvaha (zkrácený rozsah pro mikro ÚJ)
  2. VZZ (druhové členění)
  3. Předvaha
  4. Hlavní kniha (výběr účtu)
  5. Saldokonto (neuhrazené závazky/pohledávky)
  6. DPH přehled
  7. Pokladní kniha (účet 211)

+ Tlačítko Export PDF (všechny výkazy do jednoho souboru).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from domain.shared.money import Money
from services.queries.vykazy_query import (
    DphPrehled,
    HlavniKnihaUctu,
    PokladniKniha,
    PredvahaRadek,
    RozvahaRadek,
    SaldokontoRadek,
    VykazyQuery,
    VzzRadek,
)
from ui.design_tokens import Colors, Spacing


# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────

def _format_money(m: Money) -> str:
    """Vrátí '1 234,56 Kč' s NBSP. Pro nulu vrátí '0,00 Kč'."""
    return m.format_cz()


def _format_date(d: date) -> str:
    return f"{d.day:02d}. {d.month:02d}. {d.year}"


def _set_money_cell(
    table: QTableWidget, row: int, col: int, m: Money,
    bold: bool = False,
) -> None:
    """Nastaví money buňku — zarovnaná doprava, záporné červeně."""
    item = QTableWidgetItem(_format_money(m))
    item.setTextAlignment(int(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    ))
    if m.is_negative:
        item.setForeground(QBrush(QColor(Colors.ERROR_700)))
    if bold:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    table.setItem(row, col, item)


def _set_text_cell(
    table: QTableWidget, row: int, col: int, text: str,
    bold: bool = False, indent: int = 0,
) -> None:
    item = QTableWidgetItem(("  " * indent) + text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if bold:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    table.setItem(row, col, item)


def _make_table(headers: tuple[str, ...]) -> QTableWidget:
    table = QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setShowGrid(False)
    table.setAlternatingRowColors(True)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setProperty("class", "doklady-table")
    h = table.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    h.setHighlightSections(False)
    return table


# ────────────────────────────────────────────────────────────
# Page
# ────────────────────────────────────────────────────────────

class VykazyPage(QWidget):
    """Stránka Výkazy — 7 záložek + Export PDF."""

    TABS = (
        ("rozvaha",   "Rozvaha"),
        ("vzz",       "VZZ"),
        ("predvaha",  "Předvaha"),
        ("kniha",     "Hlavní kniha"),
        ("saldo",     "Saldokonto"),
        ("dph",       "DPH přehled"),
        ("pokladna",  "Pokladní kniha"),
    )

    def __init__(
        self,
        vykazy_query: VykazyQuery,
        rok_default: int = 2025,
        firma_nazev: str = "PRAUT s.r.o.",
        firma_ico: str = "22545107",
        export_pdf_fn: Callable[[int, Path], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._query = vykazy_query
        self._rok = rok_default
        self._firma_nazev = firma_nazev
        self._firma_ico = firma_ico
        self._export_pdf_fn = export_pdf_fn

        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._build_ui()
        self._reload_active_tab()

    # ──────────────────────────────────────────────
    # UI build
    # ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6)
        root.setSpacing(Spacing.S4)

        # Header
        title = QLabel("Výkazy", self)
        title.setProperty("class", "page-title")
        root.addWidget(title)

        subtitle = QLabel(
            f"Účetní závěrka a sestavy {self._firma_nazev}", self,
        )
        subtitle.setProperty("class", "page-subtitle")
        root.addWidget(subtitle)

        # Rok selector + Export PDF
        controls = QHBoxLayout()
        controls.setSpacing(Spacing.S3)

        rok_label = QLabel("Účetní rok:", self)
        controls.addWidget(rok_label)

        self._rok_combo = QComboBox(self)
        for r in (2025, 2026, 2027):
            self._rok_combo.addItem(str(r), r)
        idx = self._rok_combo.findData(self._rok)
        if idx >= 0:
            self._rok_combo.setCurrentIndex(idx)
        self._rok_combo.currentIndexChanged.connect(self._on_rok_changed)
        controls.addWidget(self._rok_combo)

        controls.addStretch(1)

        self._export_btn = QPushButton("Exportovat vše do PDF", self)
        self._export_btn.setProperty("class", "primary")
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.clicked.connect(self._on_export_pdf)
        controls.addWidget(self._export_btn)

        root.addLayout(controls)

        # Bilanční warning banner
        self._warning_label = QLabel("", self)
        self._warning_label.setProperty("class", "dialog-error")
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        root.addWidget(self._warning_label)

        # Tab buttons
        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(Spacing.S2)
        self._tab_buttons: dict[str, QPushButton] = {}
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        for key, label in self.TABS:
            btn = QPushButton(label, self)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("class", "tab")
            btn.clicked.connect(
                lambda _checked=False, k=key: self._on_tab_clicked(k)
            )
            tabs_row.addWidget(btn)
            self._tab_buttons[key] = btn
            self._tab_group.addButton(btn)
        tabs_row.addStretch(1)
        root.addLayout(tabs_row)

        # Stack pro obsah jednotlivých tabů
        self._stack = QStackedWidget(self)
        self._tab_index: dict[str, int] = {}

        self._stack.addWidget(self._build_rozvaha_tab())
        self._tab_index["rozvaha"] = 0

        self._stack.addWidget(self._build_vzz_tab())
        self._tab_index["vzz"] = 1

        self._stack.addWidget(self._build_predvaha_tab())
        self._tab_index["predvaha"] = 2

        self._stack.addWidget(self._build_kniha_tab())
        self._tab_index["kniha"] = 3

        self._stack.addWidget(self._build_saldo_tab())
        self._tab_index["saldo"] = 4

        self._stack.addWidget(self._build_dph_tab())
        self._tab_index["dph"] = 5

        self._stack.addWidget(self._build_pokladna_tab())
        self._tab_index["pokladna"] = 6

        root.addWidget(self._stack, stretch=1)

        # Aktivní tab default
        self._active_tab = "rozvaha"
        self._tab_buttons[self._active_tab].setChecked(True)

    # ──────────────────────────────────────────────
    # Tab 1: Rozvaha
    # ──────────────────────────────────────────────

    def _build_rozvaha_tab(self) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, Spacing.S2, 0, 0)
        layout.setSpacing(Spacing.S2)

        cols = ("Označení", "Název", "Běžné období", "Minulé období")
        self._rozvaha_aktiva_table = _make_table(cols)
        self._rozvaha_pasiva_table = _make_table(cols)

        h_a = QLabel("AKTIVA", w)
        h_a.setProperty("class", "page-subtitle")
        layout.addWidget(h_a)
        layout.addWidget(self._rozvaha_aktiva_table)

        h_p = QLabel("PASIVA", w)
        h_p.setProperty("class", "page-subtitle")
        layout.addWidget(h_p)
        layout.addWidget(self._rozvaha_pasiva_table)

        return w

    def _load_rozvaha(self) -> None:
        try:
            aktiva, pasiva = self._query.get_rozvaha(self._rok)
        except Exception as e:
            self._show_warning(f"Chyba při načítání rozvahy: {e}")
            return
        self._fill_rozvaha_table(self._rozvaha_aktiva_table, aktiva)
        self._fill_rozvaha_table(self._rozvaha_pasiva_table, pasiva)

        # Bilanční kontrola
        a_total = next((r.hodnota for r in aktiva if r.kind == "sum_top"), Money.zero())
        p_total = next((r.hodnota for r in pasiva if r.kind == "sum_top"), Money.zero())
        if a_total != p_total:
            zaverkove = self._query.get_zaverkove_saldo(self._rok)
            zaverkove_hint = ""
            if not zaverkove.is_zero:
                zaverkove_hint = (
                    f"   Tip: závěrkové účty (701/702/710) mají saldo "
                    f"{_format_money(zaverkove)} — pravděpodobně tam je rozdíl."
                )
            self._show_warning(
                f"⚠ Rozvaha NEBILANCUJE: Aktiva {_format_money(a_total)} "
                f"≠ Pasiva {_format_money(p_total)}." + zaverkove_hint
            )
        else:
            self._hide_warning()

    def _fill_rozvaha_table(
        self, table: QTableWidget, radky: tuple[RozvahaRadek, ...],
    ) -> None:
        table.setRowCount(len(radky))
        for i, r in enumerate(radky):
            bold = r.kind in ("sum_top", "sum_group")
            indent = max(0, r.level - 1)
            _set_text_cell(table, i, 0, r.oznaceni, bold=bold)
            _set_text_cell(table, i, 1, r.nazev, bold=bold, indent=indent)
            _set_money_cell(table, i, 2, r.hodnota, bold=bold)
            _set_money_cell(table, i, 3, r.minule, bold=bold)
        table.resizeColumnsToContents()
        h = table.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    # ──────────────────────────────────────────────
    # Tab 2: VZZ
    # ──────────────────────────────────────────────

    def _build_vzz_tab(self) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, Spacing.S2, 0, 0)
        cols = ("Označení", "Název", "Běžné období", "Minulé období")
        self._vzz_table = _make_table(cols)
        layout.addWidget(self._vzz_table)
        return w

    def _load_vzz(self) -> None:
        try:
            radky = self._query.get_vzz(self._rok)
        except Exception as e:
            self._show_warning(f"Chyba při načítání VZZ: {e}")
            return

        # Vyčistit oznaceni labels (interní '*', '**fin', '***pred', '****', '**pod')
        # Přejmenovat na čisté symboly pro výkaz.
        oznaceni_map = {
            "*":       "*",
            "**fin":   "*",
            "***pred": "**",
            "**pod":   "**",
            "****":    "***",
        }

        self._vzz_table.setRowCount(len(radky))
        for i, r in enumerate(radky):
            bold = r.druh.startswith("sum") or r.druh == "N_group"
            display_oznaceni = oznaceni_map.get(r.oznaceni, r.oznaceni)
            _set_text_cell(self._vzz_table, i, 0, display_oznaceni, bold=bold)
            indent = max(0, r.level - 1)
            _set_text_cell(self._vzz_table, i, 1, r.nazev, bold=bold, indent=indent)
            _set_money_cell(self._vzz_table, i, 2, r.hodnota, bold=bold)
            _set_money_cell(self._vzz_table, i, 3, r.minule, bold=bold)
        self._vzz_table.resizeColumnsToContents()
        h = self._vzz_table.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    # ──────────────────────────────────────────────
    # Tab 3: Předvaha
    # ──────────────────────────────────────────────

    def _build_predvaha_tab(self) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, Spacing.S2, 0, 0)
        layout.setSpacing(Spacing.S2)

        ctrl_row = QHBoxLayout()
        self._predvaha_show_zero = QCheckBox("Zobrazit i nulové účty", w)
        self._predvaha_show_zero.toggled.connect(lambda _b: self._load_predvaha())
        ctrl_row.addWidget(self._predvaha_show_zero)
        ctrl_row.addStretch(1)

        self._predvaha_balance_label = QLabel("", w)
        ctrl_row.addWidget(self._predvaha_balance_label)
        layout.addLayout(ctrl_row)

        cols = ("Účet", "Název", "PS MD", "PS Dal", "Obrat MD", "Obrat Dal", "KZ MD", "KZ Dal")
        self._predvaha_table = _make_table(cols)
        layout.addWidget(self._predvaha_table)
        return w

    def _load_predvaha(self) -> None:
        try:
            jen_pohyb = not self._predvaha_show_zero.isChecked()
            radky = self._query.get_predvaha(self._rok, jen_s_pohybem=jen_pohyb)
        except Exception as e:
            self._show_warning(f"Chyba při načítání předvahy: {e}")
            return

        self._predvaha_table.setRowCount(len(radky) + 1)  # +1 pro CELKEM
        celkem_md = 0
        celkem_dal = 0
        for i, r in enumerate(radky):
            _set_text_cell(self._predvaha_table, i, 0, r.ucet)
            _set_text_cell(self._predvaha_table, i, 1, r.nazev)
            _set_money_cell(self._predvaha_table, i, 2, r.ps_md)
            _set_money_cell(self._predvaha_table, i, 3, r.ps_dal)
            _set_money_cell(self._predvaha_table, i, 4, r.obrat_md)
            _set_money_cell(self._predvaha_table, i, 5, r.obrat_dal)
            _set_money_cell(self._predvaha_table, i, 6, r.kz_md)
            _set_money_cell(self._predvaha_table, i, 7, r.kz_dal)
            celkem_md += r.obrat_md.to_halire()
            celkem_dal += r.obrat_dal.to_halire()

        # CELKEM řádek
        last = len(radky)
        _set_text_cell(self._predvaha_table, last, 1, "CELKEM", bold=True)
        _set_money_cell(self._predvaha_table, last, 4, Money(celkem_md), bold=True)
        _set_money_cell(self._predvaha_table, last, 5, Money(celkem_dal), bold=True)

        if celkem_md != celkem_dal:
            self._predvaha_balance_label.setText(
                f"⚠ MD ({Money(celkem_md).format_cz()}) ≠ Dal ({Money(celkem_dal).format_cz()})"
            )
            self._predvaha_balance_label.setStyleSheet(f"color: {Colors.ERROR_700};")
        else:
            self._predvaha_balance_label.setText(
                f"✓ Předvaha vyvážená: {Money(celkem_md).format_cz()}"
            )
            self._predvaha_balance_label.setStyleSheet(f"color: {Colors.SUCCESS_700};")

        self._predvaha_table.resizeColumnsToContents()
        h = self._predvaha_table.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    # ──────────────────────────────────────────────
    # Tab 4: Hlavní kniha
    # ──────────────────────────────────────────────

    def _build_kniha_tab(self) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, Spacing.S2, 0, 0)
        layout.setSpacing(Spacing.S2)

        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Účet:", w))
        self._kniha_combo = QComboBox(w)
        self._kniha_combo.setMinimumWidth(360)
        self._kniha_combo.currentIndexChanged.connect(
            lambda _i: self._load_kniha_detail()
        )
        ctrl_row.addWidget(self._kniha_combo)
        ctrl_row.addStretch(1)

        self._kniha_summary = QLabel("", w)
        ctrl_row.addWidget(self._kniha_summary)
        layout.addLayout(ctrl_row)

        cols = ("Datum", "Doklad", "Popis", "MD", "Dal", "Zůstatek")
        self._kniha_table = _make_table(cols)
        layout.addWidget(self._kniha_table)
        return w

    def _load_kniha(self) -> None:
        """Naplní dropdown účty s pohybem."""
        try:
            ucty = self._query.get_ucty_s_pohybem(self._rok)
        except Exception as e:
            self._show_warning(f"Chyba při načítání seznamu účtů: {e}")
            return

        self._kniha_combo.blockSignals(True)
        self._kniha_combo.clear()
        for cislo, nazev in ucty:
            self._kniha_combo.addItem(f"{cislo} – {nazev}", cislo)
        self._kniha_combo.blockSignals(False)
        if ucty:
            self._load_kniha_detail()
        else:
            self._kniha_table.setRowCount(0)
            self._kniha_summary.setText("Žádné účty s pohybem v roce.")

    def _load_kniha_detail(self) -> None:
        ucet = self._kniha_combo.currentData()
        if not ucet:
            return
        try:
            kniha = self._query.get_hlavni_kniha(ucet, self._rok)
        except Exception as e:
            self._show_warning(f"Chyba: {e}")
            return
        self._fill_kniha_table(kniha)

    def _fill_kniha_table(self, kniha: HlavniKnihaUctu) -> None:
        self._kniha_summary.setText(
            f"PS: {kniha.pocatecni_stav.format_cz()}   "
            f"Obrat MD: {kniha.obrat_md.format_cz()}   "
            f"Obrat Dal: {kniha.obrat_dal.format_cz()}   "
            f"KZ: {kniha.koncovy_zustatek.format_cz()}"
        )
        self._kniha_table.setRowCount(len(kniha.radky))
        for i, r in enumerate(kniha.radky):
            _set_text_cell(self._kniha_table, i, 0, _format_date(r.datum))
            _set_text_cell(self._kniha_table, i, 1, r.cislo_dokladu)
            _set_text_cell(self._kniha_table, i, 2, r.popis or "")
            if r.md.is_positive:
                _set_money_cell(self._kniha_table, i, 3, r.md)
            if r.dal.is_positive:
                _set_money_cell(self._kniha_table, i, 4, r.dal)
            _set_money_cell(self._kniha_table, i, 5, r.zustatek)
        self._kniha_table.resizeColumnsToContents()
        h = self._kniha_table.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

    # ──────────────────────────────────────────────
    # Tab 5: Saldokonto
    # ──────────────────────────────────────────────

    def _build_saldo_tab(self) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, Spacing.S2, 0, 0)
        layout.setSpacing(Spacing.S2)

        layout.addWidget(QLabel("Závazky (neuhrazené FP):", w))
        cols = ("Doklad", "Partner", "Datum", "Částka", "Uhrazeno", "Zbývá")
        self._saldo_zavazky = _make_table(cols)
        layout.addWidget(self._saldo_zavazky)

        layout.addWidget(QLabel("Pohledávky (neuhrazené FV):", w))
        self._saldo_pohledavky = _make_table(cols)
        layout.addWidget(self._saldo_pohledavky)
        return w

    def _load_saldo(self) -> None:
        try:
            zavazky, pohledavky = self._query.get_saldokonto(self._rok)
        except Exception as e:
            self._show_warning(f"Chyba: {e}")
            return
        self._fill_saldo_table(self._saldo_zavazky, zavazky)
        self._fill_saldo_table(self._saldo_pohledavky, pohledavky)

    def _fill_saldo_table(
        self, table: QTableWidget, radky: tuple[SaldokontoRadek, ...],
    ) -> None:
        table.setRowCount(len(radky) + 1)
        celkem_zbyva = 0
        for i, r in enumerate(radky):
            _set_text_cell(table, i, 0, r.cislo_dokladu)
            _set_text_cell(table, i, 1, r.partner_nazev or "—")
            _set_text_cell(table, i, 2, _format_date(r.datum))
            _set_money_cell(table, i, 3, r.castka)
            _set_money_cell(table, i, 4, r.uhrazeno)
            _set_money_cell(table, i, 5, r.zbyva)
            celkem_zbyva += r.zbyva.to_halire()
        last = len(radky)
        _set_text_cell(table, last, 0, "CELKEM", bold=True)
        _set_money_cell(table, last, 5, Money(celkem_zbyva), bold=True)
        table.resizeColumnsToContents()
        h = table.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    # ──────────────────────────────────────────────
    # Tab 6: DPH přehled
    # ──────────────────────────────────────────────

    def _build_dph_tab(self) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, Spacing.S2, 0, 0)
        layout.setSpacing(Spacing.S2)

        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Období:", w))
        self._dph_obdobi = QComboBox(w)
        self._dph_obdobi.addItem("Celý rok", ("rok", None))
        for q in (1, 2, 3, 4):
            self._dph_obdobi.addItem(f"Q{q}", ("ctvrtleti", q))
        for m in range(1, 13):
            self._dph_obdobi.addItem(f"Měsíc {m}", ("mesic", m))
        self._dph_obdobi.currentIndexChanged.connect(lambda _i: self._load_dph())
        ctrl_row.addWidget(self._dph_obdobi)
        ctrl_row.addStretch(1)
        layout.addLayout(ctrl_row)

        # Souhrnná tabulka
        self._dph_summary_table = _make_table(("Položka", "Částka"))
        self._dph_summary_table.setMaximumHeight(200)
        layout.addWidget(self._dph_summary_table)

        layout.addWidget(QLabel("Detail dokladů s DPH:", w))
        cols = ("Datum", "Doklad", "Partner", "Základ", "DPH", "Režim")
        self._dph_doklady_table = _make_table(cols)
        layout.addWidget(self._dph_doklady_table, stretch=1)
        return w

    def _load_dph(self) -> None:
        data = self._dph_obdobi.currentData()
        if not data:
            return
        kind, val = data
        try:
            if kind == "rok":
                prehled = self._query.get_dph_prehled(self._rok)
            elif kind == "ctvrtleti":
                prehled = self._query.get_dph_prehled(self._rok, ctvrtleti=val)
            else:
                prehled = self._query.get_dph_prehled(self._rok, mesic=val)
        except Exception as e:
            self._show_warning(f"Chyba: {e}")
            return
        self._fill_dph(prehled)

    def _fill_dph(self, prehled: DphPrehled) -> None:
        self._dph_summary_table.setRowCount(5)
        rows = (
            ("DPH na vstupu (343.100)", prehled.vstup_celkem, False),
            ("  z toho reverse charge", prehled.vstup_rc, False),
            ("DPH na výstupu (343.200)", prehled.vystup_celkem, False),
            ("  z toho reverse charge", prehled.vystup_rc, False),
            ("DPH k úhradě (výstup − vstup)", prehled.k_uhrade, True),
        )
        for i, (label, money, bold) in enumerate(rows):
            _set_text_cell(self._dph_summary_table, i, 0, label, bold=bold)
            _set_money_cell(self._dph_summary_table, i, 1, money, bold=bold)
        self._dph_summary_table.resizeColumnsToContents()
        h = self._dph_summary_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self._dph_doklady_table.setRowCount(len(prehled.doklady))
        for i, d in enumerate(prehled.doklady):
            _set_text_cell(self._dph_doklady_table, i, 0, _format_date(d.datum))
            _set_text_cell(self._dph_doklady_table, i, 1, d.cislo_dokladu)
            _set_text_cell(self._dph_doklady_table, i, 2, d.partner_nazev or "—")
            _set_money_cell(self._dph_doklady_table, i, 3, d.zaklad)
            _set_money_cell(self._dph_doklady_table, i, 4, d.dph)
            rezim_label = "RC" if d.rezim == "REVERSE_CHARGE" else "Tuzemsko"
            _set_text_cell(self._dph_doklady_table, i, 5, rezim_label)
        self._dph_doklady_table.resizeColumnsToContents()
        h2 = self._dph_doklady_table.horizontalHeader()
        h2.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

    # ──────────────────────────────────────────────
    # Tab 7: Pokladní kniha
    # ──────────────────────────────────────────────

    def _build_pokladna_tab(self) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, Spacing.S2, 0, 0)
        layout.setSpacing(Spacing.S2)

        self._pokladna_summary = QLabel("", w)
        layout.addWidget(self._pokladna_summary)

        self._pokladna_empty = QLabel("", w)
        self._pokladna_empty.setProperty("class", "form-help")
        self._pokladna_empty.setVisible(False)
        layout.addWidget(self._pokladna_empty)

        cols = ("Datum", "Doklad", "Popis", "Příjem", "Výdaj", "Zůstatek")
        self._pokladna_table = _make_table(cols)
        layout.addWidget(self._pokladna_table)
        return w

    def _load_pokladna(self) -> None:
        try:
            kniha = self._query.get_pokladni_kniha(self._rok)
        except Exception as e:
            self._show_warning(f"Chyba: {e}")
            return

        if not kniha.pouzita:
            self._pokladna_empty.setText(
                f"Pokladna nebyla v roce {self._rok} používána."
            )
            self._pokladna_empty.setVisible(True)
            self._pokladna_table.setRowCount(0)
            self._pokladna_summary.setText("")
            return

        self._pokladna_empty.setVisible(False)
        self._pokladna_summary.setText(
            f"Počáteční stav: {kniha.pocatecni_stav.format_cz()}    "
            f"Konečný stav: {kniha.koncovy_stav.format_cz()}"
        )

        self._pokladna_table.setRowCount(len(kniha.radky))
        for i, r in enumerate(kniha.radky):
            _set_text_cell(self._pokladna_table, i, 0, _format_date(r.datum))
            _set_text_cell(self._pokladna_table, i, 1, r.cislo_dokladu)
            _set_text_cell(self._pokladna_table, i, 2, r.popis or "")
            if r.md.is_positive:
                _set_money_cell(self._pokladna_table, i, 3, r.md)
            if r.dal.is_positive:
                _set_money_cell(self._pokladna_table, i, 4, r.dal)
            _set_money_cell(self._pokladna_table, i, 5, r.zustatek)
        self._pokladna_table.resizeColumnsToContents()
        h = self._pokladna_table.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

    # ──────────────────────────────────────────────
    # Routing + helpers
    # ──────────────────────────────────────────────

    def _on_tab_clicked(self, key: str) -> None:
        self._active_tab = key
        self._stack.setCurrentIndex(self._tab_index[key])
        self._reload_active_tab()

    def _on_rok_changed(self) -> None:
        self._rok = self._rok_combo.currentData() or self._rok
        self._reload_active_tab()

    def _reload_active_tab(self) -> None:
        loaders = {
            "rozvaha":  self._load_rozvaha,
            "vzz":      self._load_vzz,
            "predvaha": self._load_predvaha,
            "kniha":    self._load_kniha,
            "saldo":    self._load_saldo,
            "dph":      self._load_dph,
            "pokladna": self._load_pokladna,
        }
        loader = loaders.get(self._active_tab)
        if loader:
            loader()

    def _show_warning(self, msg: str) -> None:
        self._warning_label.setText(msg)
        self._warning_label.setVisible(True)

    def _hide_warning(self) -> None:
        self._warning_label.setVisible(False)

    # ──────────────────────────────────────────────
    # PDF Export
    # ──────────────────────────────────────────────

    def _on_export_pdf(self) -> None:
        if self._export_pdf_fn is None:
            QMessageBox.warning(
                self, "Export PDF",
                "Export PDF není nakonfigurován.",
            )
            return

        default_name = f"PRAUT_vykazy_{self._rok}.pdf"
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Uložit PDF", default_name, "PDF (*.pdf)",
        )
        if not path_str:
            return
        path = Path(path_str)
        if path.suffix.lower() != ".pdf":
            path = path.with_suffix(".pdf")

        try:
            self._export_pdf_fn(self._rok, path)
        except Exception as e:
            QMessageBox.critical(
                self, "Export PDF",
                f"Chyba při exportu:\n{e}",
            )
            return

        QMessageBox.information(
            self, "Export PDF",
            f"Výkazy uloženy do:\n{path}",
        )
