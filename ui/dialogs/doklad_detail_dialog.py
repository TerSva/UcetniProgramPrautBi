"""DokladDetailDialog — detail dokladu s edit módem + akcemi.

Layout:
    Header  : Číslo dokladu  [Typ badge] [Stav badge]
    (editable) Popis + Datum splatnosti inputs
    (read-only) Ostatní metadata
    K dořešení box (pokud flag nebo v edit módu tlačítko „Označit / Dořešit")
    Akční řádek:
        [Upravit] [Zaúčtovat] [Označit k dořešení / Dořešit]
        [Stornovat] [Smazat]                           [Zavřít]
    V edit módu:
        [Zrušit úpravy]                             [Uložit změny]

Všechny akce procházejí přes ``DokladDetailViewModel``. Dialog po
úspěšné mutaci neukončuje se — refreshne obsah z VM. ``accept()`` se
zavolá jen pokud byl doklad smazaný.

``result_item`` — aktuální DTO v okamžiku zavření (pro refresh listu).
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from domain.doklady.typy import StavDokladu
from services.queries.doklady_list import DokladyListItem
from ui.design_tokens import Colors, Spacing
from ui.dialogs.confirm_dialog import ConfirmDialog
from ui.viewmodels.doklad_detail_vm import DokladDetailViewModel
from ui.widgets.badge import (
    Badge,
    badge_variant_for_stav,
    badge_variant_for_typ,
    stav_display_text,
    typ_display_text,
)
from ui.widgets.icon import load_icon
from ui.widgets.labeled_inputs import LabeledDateEdit, LabeledTextEdit


def _format_date_long(d: date) -> str:
    return f"{d.day}. {d.month}. {d.year}"


class DokladDetailDialog(QDialog):
    """Modální dialog s detailem + edit módem + akcemi."""

    #: Emitováno, když uživatelka kliknutím na „Zaúčtovat" chce otevřít
    #: zaúčtovací dialog. Page to zpracuje (má k dispozici VM factories).
    zauctovat_requested = pyqtSignal(object)   # DokladyListItem

    def __init__(
        self,
        view_model: DokladDetailViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setWindowTitle(f"Doklad {view_model.doklad.cislo}")
        self.setProperty("class", "doklad-detail")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setModal(True)
        self.resize(580, 620)

        # Widgety
        self._typ_badge: Badge
        self._stav_badge: Badge
        self._doreseni_box: QWidget
        self._popis_display: QLabel
        self._splatnost_display: QLabel
        self._popis_edit: LabeledTextEdit
        self._splatnost_edit: LabeledDateEdit
        self._error_label: QLabel

        self._edit_button: QPushButton
        self._zauctovat_button: QPushButton
        self._flag_button: QPushButton
        self._storno_button: QPushButton
        self._smazat_button: QPushButton
        self._close_button: QPushButton
        self._cancel_edit_button: QPushButton
        self._save_edit_button: QPushButton

        self._build_ui()
        self._wire_signals()
        self._sync_ui()

    # ─── Public API ──────────────────────────────────────────────

    @property
    def result_item(self) -> DokladyListItem | None:
        """Aktuální DTO v okamžiku uzavření. None pokud smazán."""
        if self._vm.is_deleted:
            return None
        return self._vm.doklad

    # ─── Test-only accessors ─────────────────────────────────────

    @property
    def _typ_badge_widget(self) -> Badge:
        return self._typ_badge

    @property
    def _stav_badge_widget(self) -> Badge:
        return self._stav_badge

    @property
    def _doreseni_box_widget(self) -> QWidget:
        return self._doreseni_box

    @property
    def _edit_button_widget(self) -> QPushButton:
        return self._edit_button

    @property
    def _zauctovat_button_widget(self) -> QPushButton:
        return self._zauctovat_button

    @property
    def _flag_button_widget(self) -> QPushButton:
        return self._flag_button

    @property
    def _storno_button_widget(self) -> QPushButton:
        return self._storno_button

    @property
    def _smazat_button_widget(self) -> QPushButton:
        return self._smazat_button

    @property
    def _close_button_widget(self) -> QPushButton:
        return self._close_button

    @property
    def _save_edit_widget(self) -> QPushButton:
        return self._save_edit_button

    @property
    def _cancel_edit_widget(self) -> QPushButton:
        return self._cancel_edit_button

    # ─── Build ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        item = self._vm.doklad

        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        # Header
        header = QHBoxLayout()
        header.setSpacing(Spacing.S3)
        title = QLabel(item.cislo, self)
        title.setProperty("class", "dialog-title")
        header.addWidget(title)
        header.addStretch(1)

        self._typ_badge = Badge(
            typ_display_text(item.typ),
            variant=badge_variant_for_typ(item.typ),
            parent=self,
        )
        header.addWidget(self._typ_badge)

        self._stav_badge = Badge(
            stav_display_text(item.stav),
            variant=badge_variant_for_stav(item.stav),
            parent=self,
        )
        header.addWidget(self._stav_badge)
        root.addLayout(header)

        # K dořešení box (jen když flagnuto)
        self._doreseni_box = self._build_doreseni_box()
        root.addWidget(self._doreseni_box)

        # Form: read-only + editable
        form = QFormLayout()
        form.setHorizontalSpacing(Spacing.S5)
        form.setVerticalSpacing(Spacing.S2)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        form.addRow(
            self._form_label("Datum vystavení:"),
            self._form_value(_format_date_long(item.datum_vystaveni)),
        )

        # Splatnost — read-only label + editable widget (prepínaný)
        self._splatnost_display = self._form_value("—")
        form.addRow(
            self._form_label("Datum splatnosti:"),
            self._splatnost_display,
        )

        form.addRow(
            self._form_label("Partner:"),
            self._form_value(item.partner_nazev or "—"),
        )
        castka = self._form_value(item.castka_celkem.format_cz())
        castka.setProperty("class", "dialog-value-strong")
        form.addRow(self._form_label("Částka celkem:"), castka)

        self._popis_display = QLabel("", self)
        self._popis_display.setProperty("class", "dialog-value")
        self._popis_display.setWordWrap(True)
        form.addRow(self._form_label("Popis:"), self._popis_display)

        # Fáze 6.5: datum storna — viditelné jen pro STORNOVANY doklad
        self._storno_label = self._form_label("Stornováno:")
        self._storno_value = self._form_value("—")
        form.addRow(self._storno_label, self._storno_value)

        root.addLayout(form)

        # Edit widgets (shown only in edit mode)
        self._popis_edit = LabeledTextEdit(
            "Popis", rows=3, parent=self,
        )
        self._popis_edit.setVisible(False)
        root.addWidget(self._popis_edit)

        self._splatnost_edit = LabeledDateEdit(
            "Datum splatnosti", clearable=True, parent=self,
        )
        self._splatnost_edit.setVisible(False)
        root.addWidget(self._splatnost_edit)

        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        root.addStretch(1)

        # Actions row (read-only mode)
        self._actions_row = self._build_actions_row()
        root.addWidget(self._actions_row)

        # Edit actions row
        self._edit_actions_row = self._build_edit_actions_row()
        self._edit_actions_row.setVisible(False)
        root.addWidget(self._edit_actions_row)

    def _build_doreseni_box(self) -> QWidget:
        box = QWidget(self)
        box.setProperty("class", "doreseni-box")
        box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(box)
        layout.setContentsMargins(
            Spacing.S4, Spacing.S3, Spacing.S4, Spacing.S3,
        )
        layout.setSpacing(Spacing.S1)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(Spacing.S2)

        icon_label = QLabel(box)
        icon = load_icon("bell", color=Colors.WARNING_600, size=16)
        icon_label.setPixmap(icon.pixmap(16, 16))
        icon_label.setFixedSize(16, 16)
        header_row.addWidget(icon_label)

        header = QLabel("K dořešení", box)
        header.setProperty("class", "doreseni-header")
        header_row.addWidget(header)
        header_row.addStretch(1)
        layout.addLayout(header_row)

        self._doreseni_note = QLabel("", box)
        self._doreseni_note.setProperty("class", "doreseni-note")
        self._doreseni_note.setWordWrap(True)
        layout.addWidget(self._doreseni_note)

        return box

    def _build_actions_row(self) -> QWidget:
        container = QWidget(self)
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Spacing.S2)

        self._edit_button = QPushButton("Upravit", container)
        self._edit_button.setProperty("class", "secondary")
        self._edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self._edit_button)

        self._zauctovat_button = QPushButton("Zaúčtovat", container)
        self._zauctovat_button.setProperty("class", "primary")
        self._zauctovat_button.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self._zauctovat_button)

        self._flag_button = QPushButton("Označit k dořešení", container)
        self._flag_button.setProperty("class", "secondary")
        self._flag_button.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self._flag_button)

        self._storno_button = QPushButton("Stornovat", container)
        self._storno_button.setProperty("class", "destructive")
        self._storno_button.setCursor(Qt.CursorShape.PointingHandCursor)
        # Fáze 6.5: Storno přes opravný účetní předpis je aktivní.
        # Tlačítko ovládá ``_vm.can_storno`` — viz ``_sync_ui``.
        self._storno_button.setToolTip(
            "Stornovat vytvoří opravný účetní předpis (protizápis), "
            "který anuluje dopad původního zaúčtování ve výkazech."
        )
        row.addWidget(self._storno_button)

        self._smazat_button = QPushButton("Smazat", container)
        self._smazat_button.setProperty("class", "destructive")
        self._smazat_button.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self._smazat_button)

        row.addStretch(1)

        self._close_button = QPushButton("Zavřít", container)
        self._close_button.setProperty("class", "secondary")
        self._close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self._close_button)

        return container

    def _build_edit_actions_row(self) -> QWidget:
        container = QWidget(self)
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Spacing.S2)

        self._cancel_edit_button = QPushButton(
            "Zrušit úpravy", container,
        )
        self._cancel_edit_button.setProperty("class", "secondary")
        self._cancel_edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self._cancel_edit_button)

        row.addStretch(1)

        self._save_edit_button = QPushButton("Uložit změny", container)
        self._save_edit_button.setProperty("class", "primary")
        self._save_edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self._save_edit_button)

        return container

    def _wire_signals(self) -> None:
        self._edit_button.clicked.connect(self._on_edit)
        self._zauctovat_button.clicked.connect(self._on_zauctovat)
        self._flag_button.clicked.connect(self._on_toggle_flag)
        self._storno_button.clicked.connect(self._on_storno)
        self._smazat_button.clicked.connect(self._on_smazat)
        self._close_button.clicked.connect(self.accept)

        self._cancel_edit_button.clicked.connect(self._on_cancel_edit)
        self._save_edit_button.clicked.connect(self._on_save_edit)

    # ─── Slots ───────────────────────────────────────────────────

    def _on_edit(self) -> None:
        self._vm.enter_edit()
        # Předvyplň edit widgety z aktuálního DTO
        self._popis_edit.set_value(self._vm.draft_popis or "")
        self._splatnost_edit.set_value(self._vm.draft_splatnost)
        self._splatnost_edit.inner_widget.setEnabled(
            self._vm.can_edit_splatnost
        )
        self._sync_ui()

    def _on_cancel_edit(self) -> None:
        self._vm.cancel_edit()
        self._sync_ui()

    def _on_save_edit(self) -> None:
        popis_text = self._popis_edit.value().strip()
        popis = popis_text or None
        splatnost = (
            self._splatnost_edit.value()
            if self._vm.can_edit_splatnost
            else self._vm.doklad.datum_splatnosti
        )
        self._vm.set_draft_popis(popis)
        self._vm.set_draft_splatnost(splatnost)
        result = self._vm.save_edit()
        if result is None:
            self._show_error(self._vm.error or "Uložení selhalo.")
            return
        self._sync_ui()

    def _on_zauctovat(self) -> None:
        # Dialog neotevírá zauctovací dialog sám — signál obsluhuje page.
        self.zauctovat_requested.emit(self._vm.doklad)

    def _on_toggle_flag(self) -> None:
        if self._vm.doklad.k_doreseni:
            self._vm.dores()
        else:
            self._vm.oznac_k_doreseni()
        if self._vm.error:
            self._show_error(self._vm.error)
        else:
            self._sync_ui()

    def _on_storno(self) -> None:
        ok = ConfirmDialog.ask(
            self,
            title="Stornovat doklad",
            message=(
                f"Opravdu chcete stornovat doklad "
                f"{self._vm.doklad.cislo}?\n"
                "Vytvoří se opravný účetní předpis (protizápis), "
                "který anuluje dopad původního zaúčtování "
                "ve Předvaze, Hlavní knize a v KPI na Dashboardu. "
                "Akce je nevratná."
            ),
            confirm_text="Ano, stornovat",
            destructive=True,
        )
        if not ok:
            return
        self._vm.stornovat()
        if self._vm.error:
            self._show_error(self._vm.error)
        else:
            self._sync_ui()

    def _on_smazat(self) -> None:
        ok = ConfirmDialog.ask(
            self,
            title="Smazat doklad",
            message=(
                f"Opravdu chcete smazat doklad {self._vm.doklad.cislo}?\n"
                "Smazat lze jen doklad ve stavu NOVY bez účetních zápisů."
            ),
            confirm_text="Ano, smazat",
            destructive=True,
        )
        if not ok:
            return
        if self._vm.smazat():
            self.accept()
            return
        self._show_error(self._vm.error or "Smazání selhalo.")

    # ─── External: zauctovani_dialog succeeded ───────────────────

    def refresh_after_zauctovani(self, item: DokladyListItem) -> None:
        """Volá page po úspěšném zaúčtování — zrefreshuje detail."""
        self._vm.refresh_from(item)
        self._sync_ui()

    # ─── UI sync ─────────────────────────────────────────────────

    def _sync_ui(self) -> None:
        item = self._vm.doklad

        # Badges
        self._stav_badge.setText(stav_display_text(item.stav))
        self._stav_badge.set_variant(badge_variant_for_stav(item.stav))

        # Splatnost + popis
        splatnost_text = (
            _format_date_long(item.datum_splatnosti)
            if item.datum_splatnosti is not None
            else "—"
        )
        self._splatnost_display.setText(splatnost_text)
        self._popis_display.setText(item.popis or "—")

        # Datum storna — jen pro STORNOVANY
        je_stornovany = item.stav == StavDokladu.STORNOVANY
        self._storno_label.setVisible(je_stornovany)
        self._storno_value.setVisible(je_stornovany)
        if je_stornovany and item.datum_storna is not None:
            self._storno_value.setText(_format_date_long(item.datum_storna))
        else:
            self._storno_value.setText("—")

        # K dořešení box
        self._doreseni_box.setVisible(item.k_doreseni)
        if item.k_doreseni:
            self._doreseni_note.setText(item.poznamka_doreseni or "")

        # Edit mode: toggle sets
        edit = self._vm.edit_mode
        self._popis_edit.setVisible(edit)
        self._splatnost_edit.setVisible(edit)
        self._popis_display.setVisible(not edit)
        self._splatnost_display.setVisible(not edit)
        self._actions_row.setVisible(not edit)
        self._edit_actions_row.setVisible(edit)

        # Button enabled
        self._edit_button.setEnabled(self._vm.can_edit)
        self._zauctovat_button.setEnabled(self._vm.can_zauctovat)
        self._zauctovat_button.setVisible(
            item.stav == StavDokladu.NOVY
        )
        # Fáze 6.5: storno řeší can_storno. Pro NOVY je True v domain VM,
        # ale service vyhodí ValidationError — aby UI nelákalo uživatelku,
        # disabled zůstává pro NOVY (ať použije Smazat).
        self._storno_button.setEnabled(
            self._vm.can_storno
            and item.stav != StavDokladu.NOVY
        )
        self._smazat_button.setEnabled(self._vm.can_smazat)
        self._flag_button.setEnabled(self._vm.can_toggle_flag)
        self._flag_button.setText(
            "Dořešit" if item.k_doreseni else "Označit k dořešení"
        )

        # Reset error pokud nejsme v edit mode
        if not edit and not self._vm.error:
            self._error_label.setVisible(False)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    @staticmethod
    def _form_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("class", "dialog-label")
        return label

    @staticmethod
    def _form_value(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("class", "dialog-value")
        return label
