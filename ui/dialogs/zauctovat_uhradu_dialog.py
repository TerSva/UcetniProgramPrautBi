"""ZauctovatUhraduDialog — dialog pro zaúčtování úhrady z banky.

Zobrazí předvyplněné účty pro úhradu (MD/Dal), částku a popis.
Uživatel zkontroluje a potvrdí, případně upraví. Pokud částka transakce
neodpovídá částce dokladu, zobrazí varování s rozdílem a checkbox
pro přidání řádku 568/663 (rozdíl).

Předvyplnění:
* MD účet (FP) / Dal účet (FV) — reálný účet závazku/pohledávky
  z původního zaúčtování (viz ``_najdi_ucet_zavazku``). Default 321/311.
* Druhá strana — bankovní účet výpisu (221.001 / 221.002 / …).
* Částka — z bankovní transakce (absolutní hodnota).
* Popis — ``Úhrada {cislo_dokladu}``.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from domain.doklady.typy import TypDokladu
from domain.shared.money import Money
from services.queries.banka import TransakceListItem
from services.queries.uctova_osnova import UcetItem
from ui.design_tokens import Spacing
from ui.widgets.labeled_inputs import (
    LabeledComboBox,
    LabeledLineEdit,
    LabeledMoneyEdit,
)


class ZauctovatUhraduDialog(QDialog):
    """Dialog pro potvrzení účetního zápisu úhrady z banky."""

    def __init__(
        self,
        doklad_cislo: str,
        doklad_typ: TypDokladu,
        doklad_castka: Money,
        transakce: TransakceListItem,
        ucty: list[UcetItem],
        ucet_protistrany: str | None,
        ucet_221: str,
        zbyva_uhradit: Money | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._doklad_cislo = doklad_cislo
        self._tx = transakce
        self._ucty = ucty
        self._is_fp = doklad_typ == TypDokladu.FAKTURA_PRIJATA
        self._ucet_protistrany_default = ucet_protistrany or (
            "321" if self._is_fp else "311"
        )
        self._ucet_221 = ucet_221

        # Absolutní částky pro porovnání
        tx_abs = abs(self._tx.castka.to_halire())
        doklad_abs = abs(doklad_castka.to_halire())
        self._tx_castka = Money(tx_abs)
        self._doklad_castka = Money(doklad_abs)
        # Pokud doklad už má dílčí úhrady, zbyva_uhradit < doklad_castka.
        # Pro nový doklad bez úhrad zbyva_uhradit == doklad_castka.
        self._zbyva_uhradit = (
            zbyva_uhradit if zbyva_uhradit is not None else self._doklad_castka
        )
        self._rozdil = Money(tx_abs - doklad_abs)

        self.setWindowTitle("Zaúčtovat úhradu")
        self.setMinimumWidth(520)
        self.setModal(True)

        self._md_combo: LabeledComboBox
        self._dal_combo: LabeledComboBox
        self._castka_input: LabeledMoneyEdit
        self._popis_input: LabeledLineEdit
        self._rozdil_check: QCheckBox

        self._build_ui()
        self._populate()

    # ── Public API (čte volající po accept()) ────────────────────────

    @property
    def md_ucet(self) -> str:
        item = self._md_combo.value()
        return item.cislo if item else ""

    @property
    def dal_ucet(self) -> str:
        item = self._dal_combo.value()
        return item.cislo if item else ""

    @property
    def castka(self) -> Money:
        val = self._castka_input.value()
        return val if val is not None else self._tx_castka

    @property
    def popis(self) -> str:
        return self._popis_input.value().strip()

    @property
    def zauctovat_rozdil(self) -> bool:
        return self._rozdil_check.isChecked()

    # ── UI ───────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S5, Spacing.S5, Spacing.S5, Spacing.S5,
        )
        root.setSpacing(Spacing.S3)

        title = QLabel("Zaúčtovat úhradu", self)
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        # Info o dokladu — pokud má dílčí úhrady, ukázat zbývá vs celkem
        if self._zbyva_uhradit != self._doklad_castka:
            doklad_info = (
                f"Doklad: {self._doklad_cislo} "
                f"(celkem {self._doklad_castka.format_cz()}, "
                f"zbývá uhradit {self._zbyva_uhradit.format_cz()})"
            )
        else:
            doklad_info = (
                f"Doklad: {self._doklad_cislo} "
                f"({self._doklad_castka.format_cz()})"
            )
        info = QLabel(
            f"{doklad_info}\n"
            f"Transakce: "
            f"{self._tx.datum_zauctovani.strftime('%d.%m.%Y')} "
            f"({self._tx.castka.format_cz()})",
            self,
        )
        info.setProperty("class", "form-help")
        info.setWordWrap(True)
        root.addWidget(info)

        # Varování o rozdílu — jen pokud nesedí
        if self._rozdil != Money.zero():
            self._rozdil_label = QLabel(
                f"⚠ Rozdíl: {self._rozdil.format_cz()}",
                self,
            )
            self._rozdil_label.setProperty("class", "dialog-error")
            self._rozdil_label.setWordWrap(True)
            root.addWidget(self._rozdil_label)

        # MD účet
        self._md_combo = LabeledComboBox("MD účet", parent=self)
        root.addWidget(self._md_combo)

        # Dal účet
        self._dal_combo = LabeledComboBox("Dal účet", parent=self)
        root.addWidget(self._dal_combo)

        # Částka — výchozí = celá tx, ale lze upravit pro částečnou úhradu
        self._castka_input = LabeledMoneyEdit(
            "Částka úhrady (Kč)",
            placeholder="0,00",
            parent=self,
        )
        root.addWidget(self._castka_input)
        # Help text pod částkou
        castka_help = QLabel(
            "Tip: pro částečnou úhradu zadejte jen část transakce. "
            "Zbytek dokladu zůstane CASTECNE_UHRAZENY a půjde "
            "spárovat další platbou.",
            self,
        )
        castka_help.setProperty("class", "form-help")
        castka_help.setWordWrap(True)
        root.addWidget(castka_help)

        # Popis
        self._popis_input = LabeledLineEdit(
            "Popis", max_length=200, parent=self,
        )
        root.addWidget(self._popis_input)

        # Checkbox pro rozdíl — viditelný jen když rozdíl > 0
        self._rozdil_check = QCheckBox(
            "Přidat řádek pro rozdíl (účet 568/663)", self,
        )
        self._rozdil_check.setProperty("class", "form-check")
        self._rozdil_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rozdil_check.setVisible(self._rozdil != Money.zero())
        root.addWidget(self._rozdil_check)

        # Error
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        root.addStretch(1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(Spacing.S2)

        btn_cancel = QPushButton("Zrušit", self)
        btn_cancel.setProperty("class", "secondary")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_row.addStretch(1)

        self._btn_ok = QPushButton("Zaúčtovat", self)
        self._btn_ok.setProperty("class", "primary")
        self._btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_ok.clicked.connect(self._on_ok)
        btn_row.addWidget(self._btn_ok)

        root.addLayout(btn_row)

    def _populate(self) -> None:
        """Naplní dropdowny a předvyplní hodnoty."""
        for combo in (self._md_combo, self._dal_combo):
            combo.add_item("— vyberte účet —", None)
            for ucet in self._ucty:
                combo.add_item(ucet.display, ucet)

        # Najdi UcetItem objekty
        protistrany_ucet = next(
            (
                u for u in self._ucty
                if u.cislo == self._ucet_protistrany_default
            ),
            None,
        )
        bank_ucet = next(
            (u for u in self._ucty if u.cislo == self._ucet_221), None,
        )

        if self._is_fp:
            # FP úhrada: MD = závazek, Dal = banka
            if protistrany_ucet:
                self._md_combo.set_value(protistrany_ucet)
            if bank_ucet:
                self._dal_combo.set_value(bank_ucet)
        else:
            # FV úhrada: MD = banka, Dal = pohledávka
            if bank_ucet:
                self._md_combo.set_value(bank_ucet)
            if protistrany_ucet:
                self._dal_combo.set_value(protistrany_ucet)

        self._castka_input.set_value(self._tx_castka)
        self._popis_input.set_value(f"Úhrada {self._doklad_cislo}")

    def _on_ok(self) -> None:
        md = self.md_ucet
        dal = self.dal_ucet
        if not md or not dal:
            self._error_label.setText("Vyberte MD i Dal účet.")
            self._error_label.setVisible(True)
            return
        if md == dal:
            self._error_label.setText("MD a Dal účet nesmí být stejný.")
            self._error_label.setVisible(True)
            return
        castka = self._castka_input.value()
        if castka is None or castka == Money.zero():
            self._error_label.setText("Částka musí být vyplněná a nenulová.")
            self._error_label.setVisible(True)
            return
        self.accept()
