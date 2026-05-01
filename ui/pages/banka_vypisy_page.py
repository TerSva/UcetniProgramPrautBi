"""BankaVypisyPage — stránka přehledu bankovních výpisů a transakcí.

Layout:
    ┌──────────────────────────┬──────────────────┐
    │  Výpisy (kompaktní)      │  Účet ▼          │
    │  max 150px               │  Stav ▼          │
    └──────────────────────────┴──────────────────┘
    │ VS [____]  Protiúčet [____]  Od [__] Do [__] Den [__] │
    ├─────────────────────────────────────────────────────────┤
    │  Transakce (stretch=1, velká)                            │
    └─────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from functools import partial
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from domain.banka.bankovni_transakce import StavTransakce
from ui.design_tokens import Spacing
from ui.dialogs.sparovat_platbu_dialog import SparovatPlatbuDialog
from ui.dialogs.zauctovat_transakci_dialog import ZauctovatTransakciDialog
from ui.viewmodels.bankovni_vypisy_vm import BankovniVypisyViewModel
from ui.widgets.labeled_inputs import LabeledComboBox, LabeledLineEdit, LabeledMoneyEdit

_MESICE_CZ = [
    "Leden", "Únor", "Březen", "Duben", "Květen", "Červen",
    "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec",
]

_STAV_LABELS = {
    StavTransakce.NESPAROVANO: "Nespárováno",
    StavTransakce.SPAROVANO: "Spárováno",
    StavTransakce.AUTO_ZAUCTOVANO: "Auto",
    StavTransakce.IGNOROVANO: "Ignorováno",
}


class BankaVypisyPage(QWidget):
    """Stránka přehledu bankovních výpisů."""

    def __init__(
        self,
        view_model: BankovniVypisyViewModel,
        on_open_doklad: Callable[[int], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._on_open_doklad_cb = on_open_doklad
        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._ucet_combo: LabeledComboBox
        self._vypisy_table: QTableWidget
        self._tx_table: QTableWidget
        self._auto_btn: QPushButton
        self._stav_combo: LabeledComboBox
        self._info_label: QLabel
        self._vs_input: LabeledLineEdit
        self._protiucet_input: LabeledLineEdit
        self._castka_od_input: LabeledMoneyEdit
        self._castka_do_input: LabeledMoneyEdit
        self._den_input: LabeledLineEdit

        self._build_ui()
        self._wire_signals()
        self._load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8,
        )
        root.setSpacing(Spacing.S3)

        # Title
        title = QLabel("Bankovní výpisy", self)
        title.setProperty("class", "page-title")
        root.addWidget(title)

        subtitle = QLabel(
            "Přehled importovaných výpisů a transakcí. "
            "Automatické zaúčtování poplatků, úroků a párování s doklady.",
            self,
        )
        subtitle.setProperty("class", "page-subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # ── Top row: výpisy table (left) + account/stav filter (right) ──
        top_row = QHBoxLayout()
        top_row.setSpacing(Spacing.S3)

        # Left card: Výpisy table — compact
        left_card = QWidget(self)
        left_card.setProperty("class", "card")
        left_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left_card.setMaximumHeight(160)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(
            Spacing.S3, Spacing.S3, Spacing.S3, Spacing.S3,
        )
        left_layout.setSpacing(Spacing.S1)

        left_title = QLabel("Výpisy", left_card)
        left_title.setProperty("class", "card-title")
        left_layout.addWidget(left_title)

        self._vypisy_table = QTableWidget(0, 5, left_card)
        self._vypisy_table.setHorizontalHeaderLabels([
            "Období", "Účet", "PS", "KS", "Stav",
        ])
        self._vypisy_table.horizontalHeader().setStretchLastSection(True)
        self._vypisy_table.verticalHeader().setVisible(False)
        self._vypisy_table.verticalHeader().setDefaultSectionSize(22)
        self._vypisy_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._vypisy_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        self._vypisy_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )
        self._vypisy_table.setAlternatingRowColors(True)
        left_layout.addWidget(self._vypisy_table)

        top_row.addWidget(left_card, stretch=2)

        # Right card: Účet + Stav only
        right_card = QWidget(self)
        right_card.setProperty("class", "card")
        right_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        right_card.setMaximumHeight(160)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(
            Spacing.S3, Spacing.S3, Spacing.S3, Spacing.S3,
        )
        right_layout.setSpacing(Spacing.S2)

        self._ucet_combo = LabeledComboBox("Bankovní účet", parent=right_card)
        right_layout.addWidget(self._ucet_combo)

        self._stav_combo = LabeledComboBox("Stav transakcí", parent=right_card)
        self._stav_combo.add_item("Vše", None)
        self._stav_combo.add_item("Nespárováno", StavTransakce.NESPAROVANO)
        self._stav_combo.add_item("Spárováno", StavTransakce.SPAROVANO)
        self._stav_combo.add_item("Auto zaúčtováno", StavTransakce.AUTO_ZAUCTOVANO)
        self._stav_combo.add_item("Ignorováno", StavTransakce.IGNOROVANO)
        right_layout.addWidget(self._stav_combo)

        right_layout.addStretch()

        top_row.addWidget(right_card, stretch=1)

        root.addLayout(top_row)

        # ── Filter bar — primární: datum range + fulltext ──
        from ui.widgets.date_range_filter import DateRangeFilter
        self._date_range = DateRangeFilter(parent=self)
        # Default: "Vše" (zobrazit všechny transakce ve vybraném výpisu)
        self._date_range._apply_preset("Vše", emit=False)  # noqa: SLF001
        root.addWidget(self._date_range)

        search_bar = QHBoxLayout()
        search_bar.setSpacing(Spacing.S3)

        from PyQt6.QtWidgets import QLineEdit as _QLineEdit
        search_label = QLabel("Hledat:", self)
        search_label.setProperty("class", "field-label")
        search_bar.addWidget(search_label)

        self._search_input = _QLineEdit(self)
        self._search_input.setPlaceholderText(
            "Popis, VS, protiúčet, partner",
        )
        self._search_input.setMinimumWidth(280)
        search_bar.addWidget(self._search_input)
        search_bar.addStretch(1)
        root.addLayout(search_bar)

        # ── Sekundární filtry: VS, Protiúčet, Částka od-do, Den ──
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(Spacing.S3)

        sec_label = QLabel("Detailní filtry:", self)
        sec_label.setProperty("class", "field-label")
        filter_bar.addWidget(sec_label)

        self._vs_input = LabeledLineEdit(
            "VS", placeholder="var. symbol", parent=self,
        )
        filter_bar.addWidget(self._vs_input)

        self._protiucet_input = LabeledLineEdit(
            "Protiúčet", placeholder="číslo účtu", parent=self,
        )
        filter_bar.addWidget(self._protiucet_input)

        self._castka_od_input = LabeledMoneyEdit(
            "Částka od", placeholder="0", parent=self,
        )
        filter_bar.addWidget(self._castka_od_input)

        self._castka_do_input = LabeledMoneyEdit(
            "Částka do", placeholder="0", parent=self,
        )
        filter_bar.addWidget(self._castka_do_input)

        self._den_input = LabeledLineEdit(
            "Den", placeholder="1-31", max_length=2, parent=self,
        )
        self._den_input.setMaximumWidth(80)
        filter_bar.addWidget(self._den_input)

        filter_bar.addStretch(1)
        root.addLayout(filter_bar)

        # Search debounce timer
        from PyQt6.QtCore import QTimer
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)

        # ── Bottom: Transakce detail (large, stretched) ──
        tx_card = QWidget(self)
        tx_card.setProperty("class", "card")
        tx_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tx_layout = QVBoxLayout(tx_card)
        tx_layout.setContentsMargins(
            Spacing.S3, Spacing.S3, Spacing.S3, Spacing.S3,
        )
        tx_layout.setSpacing(Spacing.S2)

        tx_header = QHBoxLayout()
        tx_title = QLabel("Transakce", tx_card)
        tx_title.setProperty("class", "card-title")
        tx_header.addWidget(tx_title)

        self._auto_btn = QPushButton("Auto zaúčtování", tx_card)
        self._auto_btn.setProperty("class", "primary-sm")
        self._auto_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._auto_btn.setEnabled(False)
        tx_header.addWidget(self._auto_btn)

        self._delete_btn = QPushButton("Smazat výpis", tx_card)
        self._delete_btn.setProperty("class", "secondary-sm")
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.setEnabled(False)
        tx_header.addWidget(self._delete_btn)

        tx_header.addStretch()
        tx_layout.addLayout(tx_header)

        self._info_label = QLabel("Vyberte výpis v tabulce nahoře.", tx_card)
        self._info_label.setWordWrap(True)
        tx_layout.addWidget(self._info_label)

        self._tx_table = QTableWidget(0, 9, tx_card)
        self._tx_table.setHorizontalHeaderLabels([
            "Datum", "Částka", "Směr", "VS", "Protiúčet", "Popis", "Stav", "Doklad", "Akce",
        ])
        self._tx_table.horizontalHeader().setStretchLastSection(True)
        self._tx_table.verticalHeader().setVisible(False)
        self._tx_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._tx_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )
        self._tx_table.setAlternatingRowColors(True)
        self._tx_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        tx_layout.addWidget(self._tx_table, stretch=1)

        root.addWidget(tx_card, stretch=1)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Refresh data při každém zobrazení stránky."""
        super().showEvent(event)
        self._load()

    def _wire_signals(self) -> None:
        self._ucet_combo.current_value_changed.connect(self._on_ucet_changed)
        self._stav_combo.current_value_changed.connect(self._on_stav_changed)
        self._vypisy_table.currentCellChanged.connect(self._on_vypis_selected)
        self._auto_btn.clicked.connect(self._on_auto_zauctovani)
        self._delete_btn.clicked.connect(self._on_smazat_vypis)
        # Primární filtry — datum range + fulltext (debounced)
        self._date_range.range_changed.connect(self._on_date_range_changed)
        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._search_timer.timeout.connect(self._on_search_apply)
        # Sekundární filtry
        self._vs_input.text_changed.connect(self._on_vs_changed)
        self._protiucet_input.text_changed.connect(self._on_protiucet_changed)
        self._castka_od_input.line_widget.editingFinished.connect(
            self._on_castka_changed,
        )
        self._castka_do_input.line_widget.editingFinished.connect(
            self._on_castka_changed,
        )
        self._den_input.text_changed.connect(self._on_den_changed)

    def _on_date_range_changed(self, od: object, do: object) -> None:
        self._vm.set_datum_range(od, do)
        self._refresh_transakce()

    def _on_search_text_changed(self, _text: str) -> None:
        self._search_timer.start()

    def _on_search_apply(self) -> None:
        self._vm.set_search_text(self._search_input.text())
        self._refresh_transakce()

    def _load(self) -> None:
        self._vm.load()
        self._ucet_combo.combo_widget.blockSignals(True)
        self._ucet_combo.clear_items()
        self._ucet_combo.add_item("Všechny účty", None)
        for ucet in self._vm.ucty:
            self._ucet_combo.add_item(
                f"{ucet.nazev} ({ucet.ucet_kod})", ucet.id,
            )
        self._ucet_combo.combo_widget.blockSignals(False)
        self._refresh_vypisy()

        # Auto-select: obnovit předchozí výběr nebo první výpis
        vypisy = self._vm.vypisy
        if vypisy:
            prev_id = self._vm.selected_vypis_id
            target_row = 0
            if prev_id is not None:
                for i, v in enumerate(vypisy):
                    if v.id == prev_id:
                        target_row = i
                        break
            self._vypisy_table.selectRow(target_row)

    def _on_ucet_changed(self, ucet_id: object) -> None:
        self._vm.select_ucet(ucet_id)
        self._refresh_vypisy()

    def _on_stav_changed(self, stav: object) -> None:
        self._vm.set_stav_filter(stav)
        self._refresh_transakce()

    def _on_vs_changed(self, text: str) -> None:
        self._vm.set_vs_filter(text)
        self._refresh_transakce()

    def _on_protiucet_changed(self, text: str) -> None:
        self._vm.set_protiucet_filter(text)
        self._refresh_transakce()

    def _on_castka_changed(self) -> None:
        self._vm.set_castka_od(self._castka_od_input.value())
        self._vm.set_castka_do(self._castka_do_input.value())
        self._refresh_transakce()

    def _on_den_changed(self, text: str) -> None:
        text = text.strip()
        if text.isdigit():
            den = int(text)
            self._vm.set_den_filter(den if 1 <= den <= 31 else None)
        else:
            self._vm.set_den_filter(None)
        self._refresh_transakce()

    def _on_vypis_selected(self, row: int, _col: int, _prev_row: int, _prev_col: int) -> None:
        if row < 0 or row >= len(self._vm.vypisy):
            self._vm.select_vypis(None)
            self._auto_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            self._refresh_transakce()
            return

        vypis = self._vm.vypisy[row]
        self._vm.select_vypis(vypis.id)
        self._auto_btn.setEnabled(True)
        self._delete_btn.setEnabled(True)
        if vypis.cislo_vypisu:
            label = f"Výpis č. {vypis.cislo_vypisu}"
            if vypis.datum_od and vypis.datum_do:
                label += (
                    f" ({vypis.datum_od.strftime('%d.%m.')}"
                    f"–{vypis.datum_do.strftime('%d.%m.%Y')})"
                )
        else:
            label = f"Výpis {_MESICE_CZ[vypis.mesic - 1]} {vypis.rok}"
        self._info_label.setText(
            f"{label} — {vypis.ucet_nazev} | "
            f"Nespárováno: {vypis.pocet_nesparovanych}/{vypis.pocet_transakci}",
        )
        self._refresh_transakce()

    def _on_auto_zauctovani(self) -> None:
        vypis_id = self._vm.selected_vypis_id
        if vypis_id is None:
            return

        result = self._vm.auto_zauctuj(vypis_id)
        if result is None:
            QMessageBox.warning(
                self, "Chyba", self._vm.error or "Neznámá chyba",
            )
            return

        msg = (
            f"Automaticky zaúčtováno: {result.pocet_zauctovano}\n"
            f"Spárováno s doklady: {result.pocet_sparovano}\n"
            f"Přeskočeno: {result.pocet_preskoceno}"
        )
        if result.chyby:
            msg += f"\nChyby: {', '.join(result.chyby)}"

        QMessageBox.information(self, "Auto zaúčtování", msg)
        self._refresh_transakce()
        self._load()

    def _on_smazat_vypis(self) -> None:
        vypis_id = self._vm.selected_vypis_id
        if vypis_id is None:
            return

        # Find the label for the confirmation dialog
        vypisy = self._vm.vypisy
        label = f"ID {vypis_id}"
        for v in vypisy:
            if v.id == vypis_id:
                if v.cislo_vypisu:
                    label = f"č. {v.cislo_vypisu}"
                else:
                    mesic_name = _MESICE_CZ[v.mesic - 1] if 1 <= v.mesic <= 12 else str(v.mesic)
                    label = f"{mesic_name} {v.rok}"
                break

        reply = QMessageBox.warning(
            self,
            "Smazat výpis",
            f"Opravdu chcete smazat výpis {label}?\n\n"
            "Budou smazány všechny transakce, účetní záznamy,\n"
            "BV doklad a soubory (PDF, CSV).\n\n"
            "Tuto akci nelze vrátit zpět.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        result = self._vm.smazat_vypis(vypis_id)
        if result is None:
            QMessageBox.warning(
                self, "Chyba", self._vm.error or "Neznámá chyba",
            )
            return

        if not result.success:
            QMessageBox.warning(
                self, "Chyba", result.error or "Nepodařilo se smazat výpis.",
            )
            return

        QMessageBox.information(
            self,
            "Výpis smazán",
            f"Výpis {label} byl úspěšně smazán.\n\n"
            f"Smazáno transakcí: {result.smazano_transakci}\n"
            f"Smazáno účetních zápisů: {result.smazano_ucetnich_zapisu}",
        )
        self._info_label.setText("Vyberte výpis v tabulce nahoře.")
        self._auto_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)
        self._refresh_vypisy()
        self._refresh_transakce()

    def _on_ignorovat(self, tx_id: int) -> None:
        ok = self._vm.ignoruj_transakci(tx_id)
        if not ok:
            QMessageBox.warning(
                self, "Chyba", self._vm.error or "Nepodařilo se ignorovat transakci.",
            )
        self._refresh_transakce()

    def _on_obnovit(self, tx_id: int) -> None:
        ok = self._vm.obnov_transakci(tx_id)
        if not ok:
            QMessageBox.warning(
                self, "Chyba",
                self._vm.error or "Nepodařilo se obnovit transakci.",
            )
        self._refresh_transakce()

    def _on_sparovat(self, tx_id: int) -> None:
        """Otevře dialog pro ruční párování transakce s dokladem.

        Po výběru kandidáta otevře dialog zaúčtování úhrady, kde uživatel
        zkontroluje a potvrdí účty (předvyplněné z původního zaúčtování).
        """
        if self._vm.neuhrazene_query is None:
            QMessageBox.warning(
                self, "Chyba", "Párování není nakonfigurováno.",
            )
            return

        # Najdi TransakceListItem
        txs = self._vm.transakce
        tx_item = next((t for t in txs if t.id == tx_id), None)
        if tx_item is None:
            return

        dlg = SparovatPlatbuDialog(
            transakce=tx_item,
            query=self._vm.neuhrazene_query,
            parent=self,
        )
        if not dlg.exec():
            return

        doklad_id = dlg.selected_doklad_id
        if doklad_id is None:
            return

        # Otevři dialog zaúčtování úhrady — předvyplň reálné účty
        if not self._open_zauctovat_uhradu(tx_id, doklad_id, tx_item):
            return

        msg = "Platba úspěšně spárována a zaúčtována."
        self._refresh_transakce()
        self._load()
        QMessageBox.information(self, "Spárováno", msg)

    def _open_zauctovat_uhradu(
        self,
        tx_id: int,
        doklad_id: int,
        tx_item,
    ) -> bool:
        """Načte podklady, otevře ZauctovatUhraduDialog a spáruje.

        Vrací True když všechno proběhlo, False při zrušení/chybě.
        """
        from services.commands.sparovat_platbu_dokladem import (
            _najdi_ucet_zavazku,
        )
        from infrastructure.database.repositories.uctova_osnova_repository import (
            SqliteUctovaOsnovaRepository,
        )
        from infrastructure.database.repositories.doklady_repository import (
            SqliteDokladyRepository,
        )
        from services.queries.uctova_osnova import UcetItem
        from ui.dialogs.zauctovat_uhradu_dialog import ZauctovatUhraduDialog
        from domain.doklady.typy import TypDokladu

        uow_factory = self._vm._uow_factory
        if uow_factory is None:
            QMessageBox.warning(self, "Chyba", "Funkce není dostupná.")
            return False

        uow = uow_factory()
        with uow:
            doklady_repo = SqliteDokladyRepository(uow)
            doklad = doklady_repo.get_by_id(doklad_id)
            sloupec = (
                "dal_ucet" if doklad.typ == TypDokladu.FAKTURA_PRIJATA
                else "md_ucet"
            )
            ucet_protistrany = _najdi_ucet_zavazku(uow, doklad_id, sloupec)

            osnova_repo = SqliteUctovaOsnovaRepository(uow)
            ucty_domain = osnova_repo.list_all(jen_aktivni=True)
        ucty = [UcetItem.from_domain(u) for u in ucty_domain]

        ucet_221 = self._vm.get_ucet_kod_for_vypis() or "221"

        zdlg = ZauctovatUhraduDialog(
            doklad_cislo=doklad.cislo,
            doklad_typ=doklad.typ,
            doklad_castka=doklad.castka_celkem,
            transakce=tx_item,
            ucty=ucty,
            ucet_protistrany=ucet_protistrany,
            ucet_221=ucet_221,
            parent=self,
        )
        if not zdlg.exec():
            return False

        if self._vm._sparovat_cmd is None:
            QMessageBox.warning(
                self, "Chyba", "Příkaz pro párování není nakonfigurován.",
            )
            return False
        try:
            self._vm._sparovat_cmd.execute(
                tx_id, doklad_id,
                md_ucet_override=zdlg.md_ucet,
                dal_ucet_override=zdlg.dal_ucet,
                popis_override=zdlg.popis or None,
                rozdil_zauctovat=zdlg.zauctovat_rozdil,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Chyba", str(exc))
            return False
        return True

    def _on_zauctovat_tx(self, tx_id: int) -> None:
        """Otevře dialog pro přímé zaúčtování transakce."""
        # Najdi TransakceListItem
        txs = self._vm.transakce
        tx_item = next((t for t in txs if t.id == tx_id), None)
        if tx_item is None:
            return

        # Načti účtovou osnovu
        ucet_kod = self._vm.get_ucet_kod_for_vypis()
        if ucet_kod is None:
            QMessageBox.warning(
                self, "Chyba", "Nelze zjistit bankovní účet výpisu.",
            )
            return

        if self._vm._uow_factory is None:
            QMessageBox.warning(self, "Chyba", "Funkce není dostupná.")
            return

        from infrastructure.database.repositories.uctova_osnova_repository import (
            SqliteUctovaOsnovaRepository,
        )
        from services.queries.uctova_osnova import UcetItem

        uow = self._vm._uow_factory()
        with uow:
            repo = SqliteUctovaOsnovaRepository(uow)
            ucty_domain = repo.list_all(jen_aktivni=True)
        ucty = [UcetItem.from_domain(u) for u in ucty_domain]

        dlg = ZauctovatTransakciDialog(
            transakce=tx_item,
            ucty=ucty,
            ucet_221=ucet_kod,
            parent=self,
        )
        if not dlg.exec():
            return

        ok = self._vm.zauctovat_transakci(
            tx_id=tx_id,
            md_ucet=dlg.md_ucet,
            dal_ucet=dlg.dal_ucet,
            popis=dlg.popis_zapisu or None,
        )
        if not ok:
            QMessageBox.warning(
                self, "Chyba",
                self._vm.error or "Zaúčtování selhalo.",
            )
            return

        QMessageBox.information(
            self, "Zaúčtováno",
            "Transakce úspěšně zaúčtována.",
        )
        self._refresh_transakce()
        self._load()

    def _on_open_doklad(self, doklad_id: int) -> None:
        """Otevře detail dokladu přes callback z MainWindow."""
        if self._on_open_doklad_cb is not None:
            self._on_open_doklad_cb(doklad_id)

    def _refresh_vypisy(self) -> None:
        vypisy = self._vm.vypisy
        self._vypisy_table.setRowCount(len(vypisy))
        for i, v in enumerate(vypisy):
            if v.cislo_vypisu:
                obdobi_text = v.cislo_vypisu
            else:
                mesic_name = _MESICE_CZ[v.mesic - 1] if 1 <= v.mesic <= 12 else str(v.mesic)
                obdobi_text = f"{mesic_name} {v.rok}"
            self._vypisy_table.setItem(
                i, 0, QTableWidgetItem(obdobi_text),
            )
            self._vypisy_table.setItem(
                i, 1, QTableWidgetItem(v.ucet_kod),
            )
            self._vypisy_table.setItem(
                i, 2, QTableWidgetItem(v.pocatecni_stav.format_cz()),
            )
            self._vypisy_table.setItem(
                i, 3, QTableWidgetItem(v.konecny_stav.format_cz()),
            )
            nespar = v.pocet_nesparovanych
            total = v.pocet_transakci
            tx_item = QTableWidgetItem(f"{total} ({nespar} nespár.)")
            if nespar > 0:
                tx_item.setForeground(Qt.GlobalColor.darkRed)
            self._vypisy_table.setItem(i, 4, tx_item)

    def _refresh_transakce(self) -> None:
        txs = self._vm.transakce
        # Nejdřív smazat všechny řádky (včetně cell widgetů z předchozího
        # výpisu — setCellWidget se nemaže přes setItem).
        self._tx_table.setRowCount(0)
        self._tx_table.setRowCount(len(txs))
        for i, tx in enumerate(txs):
            self._tx_table.setItem(
                i, 0,
                QTableWidgetItem(tx.datum_zauctovani.strftime("%d.%m.%Y")),
            )
            self._tx_table.setItem(
                i, 1, QTableWidgetItem(tx.castka.format_cz()),
            )
            smer_label = "Příjem" if tx.smer == "P" else "Výdaj"
            self._tx_table.setItem(i, 2, QTableWidgetItem(smer_label))
            self._tx_table.setItem(
                i, 3, QTableWidgetItem(tx.variabilni_symbol or ""),
            )
            self._tx_table.setItem(
                i, 4, QTableWidgetItem(tx.protiucet or ""),
            )
            self._tx_table.setItem(
                i, 5, QTableWidgetItem(tx.popis or ""),
            )
            stav_text = _STAV_LABELS.get(tx.stav, tx.stav.value)
            stav_item = QTableWidgetItem(stav_text)
            if tx.stav == StavTransakce.NESPAROVANO:
                stav_item.setForeground(Qt.GlobalColor.darkRed)
            elif tx.stav in (StavTransakce.SPAROVANO, StavTransakce.AUTO_ZAUCTOVANO):
                stav_item.setForeground(Qt.GlobalColor.darkGreen)
            self._tx_table.setItem(i, 6, stav_item)

            # Doklad column
            if tx.sparovany_doklad_cislo:
                doklad_btn = QPushButton(tx.sparovany_doklad_cislo)
                doklad_btn.setFlat(True)
                doklad_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                doklad_btn.setStyleSheet(
                    "color: #0d9488; text-decoration: underline; "
                    "border: none; text-align: left; padding: 2px;"
                )
                doklad_btn.clicked.connect(
                    partial(self._on_open_doklad, tx.sparovany_doklad_id),
                )
                self._tx_table.setCellWidget(i, 7, doklad_btn)
            else:
                self._tx_table.setItem(i, 7, QTableWidgetItem("—"))

            # Akce column — buttons podle stavu
            if tx.stav == StavTransakce.NESPAROVANO:
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)
                actions_layout.setSpacing(4)

                sparovat_btn = QPushButton("Spárovat")
                sparovat_btn.setProperty("class", "table-action-teal")
                sparovat_btn.setFlat(True)
                sparovat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                sparovat_btn.clicked.connect(partial(self._on_sparovat, tx.id))

                zauctovat_btn = QPushButton("Zaúčtovat")
                zauctovat_btn.setProperty("class", "table-action-teal")
                zauctovat_btn.setFlat(True)
                zauctovat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                zauctovat_btn.clicked.connect(partial(self._on_zauctovat_tx, tx.id))

                ignorovat_btn = QPushButton("Ignorovat")
                ignorovat_btn.setProperty("class", "table-action-gray")
                ignorovat_btn.setFlat(True)
                ignorovat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                ignorovat_btn.clicked.connect(partial(self._on_ignorovat, tx.id))

                actions_layout.addWidget(sparovat_btn)
                actions_layout.addWidget(zauctovat_btn)
                actions_layout.addWidget(ignorovat_btn)
                self._tx_table.setCellWidget(i, 8, actions_widget)
            elif tx.stav == StavTransakce.IGNOROVANO:
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)
                actions_layout.setSpacing(4)

                obnovit_btn = QPushButton("Vrátit zpět")
                obnovit_btn.setProperty("class", "table-action-teal")
                obnovit_btn.setFlat(True)
                obnovit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                obnovit_btn.setToolTip(
                    "Obnovit transakci do stavu Nezpracováno — pak ji můžete "
                    "spárovat nebo zaúčtovat"
                )
                obnovit_btn.clicked.connect(partial(self._on_obnovit, tx.id))

                actions_layout.addWidget(obnovit_btn)
                self._tx_table.setCellWidget(i, 8, actions_widget)
            else:
                self._tx_table.setItem(i, 8, QTableWidgetItem(""))
