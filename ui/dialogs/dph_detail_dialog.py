"""DphDetailDialog — detail DPH přiznání za měsíc.

Zobrazuje:
- Tabulku 11 řádků EPO formuláře (ř. 7, 9, 10, 11, 43, 44, 47, 48,
  62, 64, 66) s českými popisky a Money formátováním.
- Tabulku RC transakcí dokladů.
- Termín podání (25. den následujícího měsíce).
- Checkbox „Označit jako podané".
- Tlačítka „Kopírovat pro EPO" a „Zavřít".

EPO clipboard formát: jeden řádek na řádek formuláře, celé Kč.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from domain.shared.money import Money
from services.queries.dph_prehled import (
    DphMesicItem,
    DphPriznaniRadky,
    DphTransakceItem,
)
from ui.design_tokens import Spacing
from ui.viewmodels.dph_vm import DphViewModel

_MESICE_CZ_TITLE = [
    "", "Leden", "Únor", "Březen", "Duben", "Květen", "Červen",
    "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec",
]

# (popisek, attribute_name, zda zobrazit i s nulou)
_EPO_ROWS: list[tuple[str, str, bool]] = [
    ("Řádek 7 — Pořízení zboží z JČS (§16)", "radek_7_zbozi_jcs", False),
    ("Řádek 9 — Přijetí služby z JČS (§24)", "radek_9_sluzby_jcs", False),
    ("Řádek 10 — Přijetí služby (21 %)", "radek_10_sluzby_21", False),
    ("Řádek 11 — Přijetí služby (12 %)", "radek_11_sluzby_12", False),
    ("Řádek 43 — DPH základ (21 %)", "radek_43_zaklad_21", False),
    ("Řádek 44 — DPH (21 % z ř. 43)", "radek_44_dph_21", False),
    ("Řádek 47 — DPH základ (12 %)", "radek_47_zaklad_12", False),
    ("Řádek 48 — DPH (12 % z ř. 47)", "radek_48_dph_12", False),
    ("Řádek 62 — Celková daň", "radek_62_celkova_dan", True),
    ("Řádek 64 — Odpočet (identifikovaná osoba = 0)",
     "radek_64_odpocet", True),
    ("Řádek 66 — Vlastní daňová povinnost",
     "radek_66_dan_povinnost", True),
]


def _termin_podani(rok: int, mesic: int) -> str:
    if mesic == 12:
        return f"25. 1. {rok + 1}"
    return f"25. {mesic + 1}. {rok}"


class DphDetailDialog(QDialog):
    """Detail DPH přiznání za měsíc s řádky EPO formuláře."""

    def __init__(
        self,
        view_model: DphViewModel,
        mesic: int,
        mesic_item: DphMesicItem,
        transakce: list[DphTransakceItem],
        priznani: DphPriznaniRadky,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._mesic = mesic
        self._mesic_item = mesic_item
        self._transakce = transakce
        self._priznani = priznani

        self.setWindowTitle(
            f"DPH přiznání — {_MESICE_CZ_TITLE[mesic]} {mesic_item.rok}",
        )
        self.setModal(True)
        self.setProperty("class", "dph-detail-dialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.resize(820, 720)

        self._podano_check: QCheckBox
        self._copy_button: QPushButton
        self._close_button: QPushButton
        self._epo_table: QTableWidget
        self._transakce_table: QTableWidget

        self._build_ui()
        self._wire_signals()

    # ─── UI building ─────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        title = QLabel(
            f"DPH přiznání — {_MESICE_CZ_TITLE[self._mesic]} "
            f"{self._mesic_item.rok}",
            self,
        )
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        termin = _termin_podani(self._mesic_item.rok, self._mesic)
        termin_label = QLabel(f"Termín podání: {termin}", self)
        termin_label.setProperty("class", "dialog-subtitle")
        root.addWidget(termin_label)

        # ── EPO řádky ──
        epo_title = QLabel("Řádky přiznání (formulář EPO):", self)
        epo_title.setProperty("class", "section-title")
        root.addWidget(epo_title)

        self._epo_table = QTableWidget(len(_EPO_ROWS), 2, self)
        self._epo_table.setHorizontalHeaderLabels(["Položka", "Částka"])
        self._epo_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._epo_table.verticalHeader().setVisible(False)
        self._epo_table.setAlternatingRowColors(True)

        eh = self._epo_table.horizontalHeader()
        eh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        eh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        for i, (popisek, attr, _vzdy) in enumerate(_EPO_ROWS):
            label = QTableWidgetItem(popisek)
            self._epo_table.setItem(i, 0, label)
            money = getattr(self._priznani, attr)
            assert isinstance(money, Money)
            cena = QTableWidgetItem(money.format_cz())
            cena.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            # Zvýraznit ř. 66 (vlastní daňová povinnost)
            if attr == "radek_66_dan_povinnost":
                f = cena.font()
                f.setBold(True)
                cena.setFont(f)
                lf = label.font()
                lf.setBold(True)
                label.setFont(lf)
            self._epo_table.setItem(i, 1, cena)
        self._epo_table.setMaximumHeight(
            self._epo_table.verticalHeader().defaultSectionSize()
            * (len(_EPO_ROWS) + 1) + 4,
        )
        root.addWidget(self._epo_table)

        # ── Tabulka transakcí ──
        section_title = QLabel("Reverse charge transakce:", self)
        section_title.setProperty("class", "section-title")
        root.addWidget(section_title)

        n = len(self._transakce)
        self._transakce_table = QTableWidget(n + 1, 5, self)  # +1 CELKEM
        self._transakce_table.setHorizontalHeaderLabels(
            ["Datum", "Doklad", "Partner", "Základ", "DPH"],
        )
        self._transakce_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._transakce_table.verticalHeader().setVisible(False)
        self._transakce_table.setAlternatingRowColors(True)

        h = self._transakce_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        zaklad_total = Money.zero()
        dph_total = Money.zero()
        for i, t in enumerate(self._transakce):
            self._transakce_table.setItem(
                i, 0, QTableWidgetItem(t.doklad_datum.strftime("%d.%m.%Y")),
            )
            self._transakce_table.setItem(
                i, 1, QTableWidgetItem(t.doklad_cislo),
            )
            self._transakce_table.setItem(
                i, 2, QTableWidgetItem(t.partner_nazev or "—"),
            )
            z_item = QTableWidgetItem(t.zaklad.format_cz())
            z_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            self._transakce_table.setItem(i, 3, z_item)
            d_item = QTableWidgetItem(
                f"{t.dph.format_cz()}  ({t.sazba} %)",
            )
            d_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            self._transakce_table.setItem(i, 4, d_item)
            zaklad_total = zaklad_total + t.zaklad
            dph_total = dph_total + t.dph

        # CELKEM řádek
        total_label = QTableWidgetItem("CELKEM")
        f = total_label.font()
        f.setBold(True)
        total_label.setFont(f)
        self._transakce_table.setItem(n, 0, total_label)
        self._transakce_table.setItem(n, 1, QTableWidgetItem(""))
        self._transakce_table.setItem(n, 2, QTableWidgetItem(""))
        zt = QTableWidgetItem(zaklad_total.format_cz())
        zt.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        zt.setFont(f)
        self._transakce_table.setItem(n, 3, zt)
        dt = QTableWidgetItem(dph_total.format_cz())
        dt.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        dt.setFont(f)
        self._transakce_table.setItem(n, 4, dt)

        root.addWidget(self._transakce_table, stretch=1)

        # Označit jako podané
        self._podano_check = QCheckBox("Označit jako podané", self)
        self._podano_check.setProperty("class", "form-check")
        self._podano_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self._podano_check.setChecked(self._mesic_item.je_podane)
        root.addWidget(self._podano_check)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch(1)

        self._close_button = QPushButton("Zavřít", self)
        self._close_button.setProperty("class", "secondary")
        self._close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self._close_button)

        self._copy_button = QPushButton("Kopírovat pro EPO", self)
        self._copy_button.setProperty("class", "primary")
        self._copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self._copy_button)

        root.addLayout(footer)

    # ─── Signals ─────────────────────────────────────────────────

    def _wire_signals(self) -> None:
        self._podano_check.toggled.connect(self._on_podano_toggled)
        self._copy_button.clicked.connect(self._on_copy)
        self._close_button.clicked.connect(self.accept)

    def _on_podano_toggled(self, checked: bool) -> None:
        self._vm.oznac_podane(self._mesic, checked)

    def _on_copy(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self._priznani.to_epo_text())

    # ─── Test-only accessors ─────────────────────────────────────

    @property
    def _epo_table_widget(self) -> QTableWidget:
        return self._epo_table

    @property
    def _transakce_table_widget(self) -> QTableWidget:
        return self._transakce_table

    @property
    def _podano_check_widget(self) -> QCheckBox:
        return self._podano_check

    @property
    def _copy_button_widget(self) -> QPushButton:
        return self._copy_button

    @property
    def _close_button_widget(self) -> QPushButton:
        return self._close_button

    def _epo_clipboard_text(self) -> str:
        """Pro testy — text co se kopíruje při kliknutí na 'Kopírovat'."""
        return self._priznani.to_epo_text()
