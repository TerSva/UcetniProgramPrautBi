"""DokladDetailDialog — dvousloupcovy detail dokladu s PDF nahledem.

Layout:
    QSplitter(Horizontal) 1100x700
    ┌──────────────────────────┬───────────────────────────────────┐
    │ PDF nahled               │ Header: Cislo [Typ] [Stav]       │
    │ (PdfViewerWidget)        │ K doreseni box                   │
    │                          │ Form: metadata                   │
    │ nebo                     │ Castka celkem                    │
    │                          │ Zbyva uhradit: XX Kc             │
    │ PdfUploadZone            │ Popis                            │
    │ "Pretahni sem PDF"       │                                  │
    │                          │ [Upravit] [Zauctovat] ... [Zavrit]│
    └──────────────────────────┴───────────────────────────────────┘

Vsechny akce prochazi pres ``DokladDetailViewModel``. Dialog po
uspesne mutaci neukoncuje se — refreshne obsah z VM. ``accept()`` se
zavola jen pokud byl doklad smazany.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable, Protocol

from PyQt6.QtCore import Qt, QSettings, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from domain.doklady.priloha import PrilohaDokladu
from domain.doklady.typy import DphRezim, Mena, StavDokladu, TypDokladu
from domain.shared.money import Money
from services.queries.doklady_list import DokladyListItem
from ui.design_tokens import Colors, Spacing
from ui.dialogs.confirm_dialog import ConfirmDialog
from ui.dialogs.storno_dialog import StornoDialog
from ui.viewmodels.doklad_detail_vm import DokladDetailViewModel
from ui.widgets.badge import (
    Badge,
    BadgeVariant,
    badge_variant_for_stav,
    badge_variant_for_typ,
    stav_display_text,
    typ_display_text,
)
from ui.widgets.icon import load_icon
from services.queries.partneri_list import PartneriListItem
from ui.widgets.labeled_inputs import (
    LabeledComboBox,
    LabeledDateEdit,
    LabeledLineEdit,
    LabeledMoneyEdit,
    LabeledTextEdit,
)
from ui.widgets.partner_selector import PartnerSelector
from ui.widgets.pdf_upload_zone import PdfUploadZone
from ui.widgets.pdf_viewer import PdfViewerWidget


def _format_date_long(d: date) -> str:
    return f"{d.day}. {d.month}. {d.year}"


class _PrilohaLoader(Protocol):
    """Callback pro nacteni priloh dokladu."""
    def __call__(self, doklad_id: int) -> list[PrilohaDokladu]: ...


class _PrilohaUploader(Protocol):
    """Callback pro upload PDF k dokladu."""
    def __call__(
        self, doklad_id: int, source_path: Path, original_name: str,
    ) -> PrilohaDokladu: ...


class _UhrazenoQuery(Protocol):
    """Callback pro zjisteni uhrazene castky z ucetniho deniku."""
    def __call__(self, doklad_id: int) -> Money: ...


class _UcetniZapisyQuery(Protocol):
    """Callback pro načtení účetních zápisů dokladu."""
    def __call__(self, doklad_id: int) -> list: ...


class DokladDetailDialog(QDialog):
    """Modalni dialog s detailem + edit modem + akcemi."""

    #: Emitovano kdyz uzivatelka klikne na Zauctovat.
    zauctovat_requested = pyqtSignal(object)   # DokladyListItem
    #: Emitováno když uživatelka klikne na Duplikovat.
    duplikat_requested = pyqtSignal(object)    # DokladyListItem
    #: Emitováno po úspěšné úhradě — doklady page by měl refreshnout.
    uhrada_completed = pyqtSignal()

    def __init__(
        self,
        view_model: DokladDetailViewModel,
        priloha_loader: _PrilohaLoader | None = None,
        priloha_uploader: _PrilohaUploader | None = None,
        priloha_full_path: Callable[[str], Path] | None = None,
        uhrazeno_query: _UhrazenoQuery | None = None,
        ucetni_zapisy_query: _UcetniZapisyQuery | None = None,
        uow_factory: Callable | None = None,
        partner_items: list[PartneriListItem] | None = None,
        on_partner_created: object = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._priloha_loader = priloha_loader
        self._priloha_uploader = priloha_uploader
        self._priloha_full_path = priloha_full_path
        self._uhrazeno_query = uhrazeno_query
        self._ucetni_zapisy_query = ucetni_zapisy_query
        self._uow_factory = uow_factory
        self._partner_items = partner_items or []
        self._on_partner_created = on_partner_created

        self.setWindowTitle(f"Doklad {view_model.doklad.cislo}")
        self.setProperty("class", "doklad-detail")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setModal(True)
        self.resize(1100, 700)

        # Widgety
        self._typ_badge: Badge
        self._stav_badge: Badge
        self._doreseni_box: QWidget
        self._popis_display: QLabel
        self._splatnost_display: QLabel
        self._popis_edit: LabeledTextEdit
        self._datum_vystaveni_edit: LabeledDateEdit
        self._splatnost_edit: LabeledDateEdit
        self._k_doreseni_check: QCheckBox
        self._poznamka_doreseni_edit: LabeledTextEdit
        self._error_label: QLabel
        self._zbyva_label: QLabel

        self._edit_button: QPushButton
        self._duplikat_button: QPushButton
        self._zauctovat_button: QPushButton
        self._flag_button: QPushButton
        self._storno_button: QPushButton
        self._uhrada_button: QPushButton
        self._smazat_button: QPushButton
        self._close_button: QPushButton
        self._cancel_edit_button: QPushButton
        self._save_edit_button: QPushButton

        self._pdf_viewer: PdfViewerWidget
        self._upload_zone: PdfUploadZone

        self._build_ui()
        self._wire_signals()
        self._load_pdf()
        self._sync_ui()

    # ─── Public API ──────────────────────────────────────────────

    @property
    def result_item(self) -> DokladyListItem | None:
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

    @property
    def _k_doreseni_check_widget(self) -> QCheckBox:
        return self._k_doreseni_check

    @property
    def _poznamka_doreseni_edit_widget(self) -> LabeledTextEdit:
        return self._poznamka_doreseni_edit

    @property
    def _doreseni_note_widget(self) -> QLabel:
        return self._doreseni_note

    @property
    def _castka_edit_widget(self) -> LabeledMoneyEdit:
        return self._castka_edit

    @property
    def _mena_edit_widget(self) -> LabeledComboBox:
        return self._mena_edit

    @property
    def _castka_mena_edit_widget(self) -> LabeledLineEdit:
        return self._castka_mena_edit

    @property
    def _kurz_edit_widget(self) -> LabeledLineEdit:
        return self._kurz_edit

    # ─── Build ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        item = self._vm.doklad

        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S4, Spacing.S4, Spacing.S4, Spacing.S4,
        )
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # ── LEFT: PDF viewer / upload zone ──
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, Spacing.S3, 0)
        left_layout.setSpacing(Spacing.S2)

        left_title = QLabel("Příloha", left)
        left_title.setProperty("class", "section-title")
        left_layout.addWidget(left_title)

        self._pdf_viewer = PdfViewerWidget(left)
        left_layout.addWidget(self._pdf_viewer, stretch=1)

        self._upload_zone = PdfUploadZone(
            message="Doklad nemá přiloženo PDF.\nPřetáhni sem soubor.",
            parent=left,
        )
        self._upload_zone.file_selected.connect(self._on_pdf_uploaded)
        self._upload_zone.setVisible(False)
        left_layout.addWidget(self._upload_zone, stretch=1)

        splitter.addWidget(left)

        # ── RIGHT: metadata ──
        right = QWidget()
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(Spacing.S3, 0, 0, 0)
        right_layout.setSpacing(Spacing.S4)

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
        right_layout.addLayout(header)

        # K doreseni box
        self._doreseni_box = self._build_doreseni_box()
        right_layout.addWidget(self._doreseni_box)

        # Form: read-only + editable
        form = QFormLayout()
        form.setHorizontalSpacing(Spacing.S5)
        form.setVerticalSpacing(Spacing.S2)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._datum_vystaveni_label = self._form_label("Datum vystavení:")
        self._datum_vystaveni_display = self._form_value(
            _format_date_long(item.datum_vystaveni)
        )
        form.addRow(
            self._datum_vystaveni_label,
            self._datum_vystaveni_display,
        )

        self._splatnost_display = self._form_value("—")
        form.addRow(
            self._form_label("Datum splatnosti:"),
            self._splatnost_display,
        )

        self._partner_display = self._form_value(item.partner_nazev or "—")
        form.addRow(
            self._form_label("Partner:"),
            self._partner_display,
        )
        self._vs_display = self._form_value(item.variabilni_symbol or "—")
        form.addRow(
            self._form_label("Variabilní symbol:"),
            self._vs_display,
        )

        # DPH rezim
        _DPH_REZIM_LABELS = {
            DphRezim.REVERSE_CHARGE: "Reverse Charge",
            DphRezim.OSVOBOZENO: "Osvobozeno",
            DphRezim.MIMO_DPH: "Mimo predmet DPH",
        }
        dph_label_text = _DPH_REZIM_LABELS.get(item.dph_rezim)
        self._dph_rezim_label = self._form_label("DPH režim:")
        if dph_label_text:
            self._dph_rezim_value = Badge(
                dph_label_text, variant=BadgeVariant.WARNING, parent=self,
            )
        else:
            self._dph_rezim_value = self._form_value("Tuzemsko")
        self._dph_rezim_label.setVisible(
            item.dph_rezim != DphRezim.TUZEMSKO,
        )
        self._dph_rezim_value.setVisible(
            item.dph_rezim != DphRezim.TUZEMSKO,
        )
        form.addRow(self._dph_rezim_label, self._dph_rezim_value)

        # Hlavní zobrazení castka_celkem (read-only). Aktualizuje se ve
        # _sync_ui po edit-save, aby uživatelka viděla novou hodnotu.
        self._castka_value_label = self._form_value(
            item.castka_celkem.format_cz()
        )
        self._castka_value_label.setProperty("class", "dialog-value-strong")
        form.addRow(
            self._form_label("Částka celkem:"), self._castka_value_label,
        )

        # Zbyva uhradit
        self._zbyva_label = QLabel("", self)
        self._zbyva_label.setProperty("class", "dialog-value-strong")
        self._zbyva_uhradit_label = self._form_label("Zbývá uhradit:")
        form.addRow(self._zbyva_uhradit_label, self._zbyva_label)

        # Cizomenovy radek
        self._foreign_label = self._form_label("Puvodne:")
        if (
            item.mena != Mena.CZK
            and item.castka_mena is not None
            and item.kurz is not None
        ):
            foreign_koruny = item.castka_mena.to_koruny()
            foreign_text = (
                f"{foreign_koruny:,.2f} {item.mena.value} "
                f"(kurz {item.kurz})"
            ).replace(",", "\u00a0").replace(".", ",")
            self._foreign_value = self._form_value(foreign_text)
        else:
            self._foreign_value = self._form_value("—")
        self._foreign_label.setVisible(item.mena != Mena.CZK)
        self._foreign_value.setVisible(item.mena != Mena.CZK)
        form.addRow(self._foreign_label, self._foreign_value)

        self._popis_display = QLabel("", self)
        self._popis_display.setProperty("class", "dialog-value")
        self._popis_display.setWordWrap(True)
        form.addRow(self._form_label("Popis:"), self._popis_display)

        # Datum storna
        self._storno_label = self._form_label("Stornovano:")
        self._storno_value = self._form_value("—")
        form.addRow(self._storno_label, self._storno_value)

        right_layout.addLayout(form)

        # Účetní zápisy section
        self._zapisy_section = QWidget(self)
        zapisy_layout = QVBoxLayout(self._zapisy_section)
        zapisy_layout.setContentsMargins(0, Spacing.S2, 0, 0)
        zapisy_layout.setSpacing(Spacing.S1)

        zapisy_title = QLabel("Účetní zápisy:", self._zapisy_section)
        zapisy_title.setProperty("class", "dialog-label")
        zapisy_layout.addWidget(zapisy_title)

        self._zapisy_table = QTableWidget(0, 6, self._zapisy_section)
        self._zapisy_table.setHorizontalHeaderLabels([
            "Datum", "Doklad", "MD účet", "Dal účet", "Částka", "Popis",
        ])
        self._zapisy_table.horizontalHeader().setStretchLastSection(True)
        for col in range(5):  # all except last (Popis) stretch
            self._zapisy_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents,
            )
        self._zapisy_table.verticalHeader().setVisible(False)
        self._zapisy_table.verticalHeader().setDefaultSectionSize(22)
        self._zapisy_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )
        self._zapisy_table.setAlternatingRowColors(True)
        self._zapisy_table.setMaximumHeight(130)
        zapisy_layout.addWidget(self._zapisy_table)

        self._zapisy_section.setVisible(False)
        right_layout.addWidget(self._zapisy_section)

        # Edit widgets
        self._popis_edit = LabeledTextEdit(
            "Popis", rows=3, parent=self,
        )
        self._popis_edit.setVisible(False)
        right_layout.addWidget(self._popis_edit)

        self._datum_vystaveni_edit = LabeledDateEdit(
            "Datum vystavení", parent=self,
        )
        self._datum_vystaveni_edit.setVisible(False)
        right_layout.addWidget(self._datum_vystaveni_edit)

        self._splatnost_edit = LabeledDateEdit(
            "Datum splatnosti", clearable=True, parent=self,
        )
        self._splatnost_edit.setVisible(False)
        right_layout.addWidget(self._splatnost_edit)

        # Měna edit (NOVY doklad). Při přepnutí na EUR/USD se ukáží i
        # vstupy pro originál hodnotu a kurz; CZK pole je auto-přepočet.
        self._mena_edit = LabeledComboBox("Měna", parent=self)
        self._mena_edit.add_item("CZK (Kč)", Mena.CZK)
        self._mena_edit.add_item("EUR", Mena.EUR)
        self._mena_edit.add_item("USD", Mena.USD)
        self._mena_edit.setVisible(False)
        right_layout.addWidget(self._mena_edit)

        # Castka v cizí měně + kurz — visible jen pro EUR/USD měnu.
        # Visibility řídíme přes wrapper widget (NEsetVisible(False) na
        # vnitřních inputech, jinak by zůstaly hidden i když je wrapper visible).
        self._cizi_wrap = QWidget(self)
        cizi_row = QHBoxLayout(self._cizi_wrap)
        cizi_row.setContentsMargins(0, 0, 0, 0)
        cizi_row.setSpacing(Spacing.S2)
        self._castka_mena_edit = LabeledLineEdit(
            "Částka v cizí měně", placeholder="123,45",
        )
        cizi_row.addWidget(self._castka_mena_edit)
        self._kurz_edit = LabeledLineEdit(
            "Kurz (CZK / 1 jednotka)", placeholder="25,00",
        )
        cizi_row.addWidget(self._kurz_edit)
        self._cizi_wrap.setVisible(False)
        right_layout.addWidget(self._cizi_wrap)

        # Castka v CZK — pro NOVY je vždy editovatelná. Pro EUR/USD měnu se
        # auto-přepočítá z (cizí měna × kurz), ale Tereza ji může taky ručně
        # přepsat (pro neobvyklé případy, např. když chce zaokrouhlit).
        self._castka_edit = LabeledMoneyEdit(
            "Částka celkem (Kč)", parent=self,
        )
        self._castka_edit.setVisible(False)
        right_layout.addWidget(self._castka_edit)

        # Partner edit
        self._partner_edit = PartnerSelector(self)
        self._partner_edit.set_items(self._partner_items)
        self._partner_edit.new_partner_requested.connect(
            self._on_new_partner_edit,
        )
        self._partner_edit.setVisible(False)
        right_layout.addWidget(self._partner_edit)

        # K doreseni edit widgety
        self._k_doreseni_check = QCheckBox(
            "Označit k dořešení", self,
        )
        self._k_doreseni_check.setProperty("class", "form-check")
        self._k_doreseni_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self._k_doreseni_check.setVisible(False)
        right_layout.addWidget(self._k_doreseni_check)

        self._poznamka_doreseni_edit = LabeledTextEdit(
            "Poznámka k dořešení",
            placeholder="Proc vyzaduje pozornost? (nepovinne)",
            rows=2,
            parent=self,
        )
        self._poznamka_doreseni_edit.setVisible(False)
        right_layout.addWidget(self._poznamka_doreseni_edit)

        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        right_layout.addWidget(self._error_label)

        right_layout.addStretch(1)

        # Actions row (read-only mode)
        self._actions_row = self._build_actions_row()
        right_layout.addWidget(self._actions_row)

        # Edit actions row
        self._edit_actions_row = self._build_edit_actions_row()
        self._edit_actions_row.setVisible(False)
        right_layout.addWidget(self._edit_actions_row)

        right_scroll.setWidget(right)
        splitter.addWidget(right_scroll)

        # Splitter sizes — restore or default 45:55
        settings = QSettings("PrautBi", "UcetniProgram")
        saved = settings.value("doklad_detail_splitter")
        if saved:
            splitter.restoreState(saved)
        else:
            splitter.setSizes([450, 550])
        self._splitter = splitter
        splitter.splitterMoved.connect(self._on_splitter_moved)

        root.addWidget(splitter)

    def _on_splitter_moved(self) -> None:
        settings = QSettings("PrautBi", "UcetniProgram")
        settings.setValue(
            "doklad_detail_splitter", self._splitter.saveState()
        )

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

        self._duplikat_button = QPushButton("Duplikovat", container)
        self._duplikat_button.setProperty("class", "secondary")
        self._duplikat_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._duplikat_button.setToolTip(
            "Vytvoří kopii dokladu s dnešním datem, "
            "bez VS a PDF. Ideální pro opakující se faktury."
        )
        row.addWidget(self._duplikat_button)

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
        self._storno_button.setToolTip(
            "Stornovat vytvoří opravný účetní předpis (protizápis), "
            "který anuluje dopad původního zaúčtování ve výkazech."
        )
        row.addWidget(self._storno_button)

        self._uhrada_button = QPushButton("Úhrada", container)
        self._uhrada_button.setProperty("class", "primary")
        self._uhrada_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._uhrada_button.setToolTip("Zaznamenat úhradu faktury")
        uhrada_menu = QMenu(self._uhrada_button)
        uhrada_menu.addAction("Z banky...", self._on_uhrada_z_banky)
        uhrada_menu.addAction("Pokladnou...", self._on_uhrada_pokladnou)
        uhrada_menu.addAction(
            "Interním dokladem (pytlování)...",
            self._on_uhrada_int_dokladem,
        )
        self._uhrada_button.setMenu(uhrada_menu)
        row.addWidget(self._uhrada_button)

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
        self._duplikat_button.clicked.connect(self._on_duplikat)
        self._zauctovat_button.clicked.connect(self._on_zauctovat)
        self._flag_button.clicked.connect(self._on_toggle_flag)
        self._storno_button.clicked.connect(self._on_storno)
        self._smazat_button.clicked.connect(self._on_smazat)
        self._close_button.clicked.connect(self.accept)

        self._cancel_edit_button.clicked.connect(self._on_cancel_edit)
        self._save_edit_button.clicked.connect(self._on_save_edit)

        self._k_doreseni_check.toggled.connect(
            self._on_k_doreseni_toggled_edit
        )

        # Měna: change → toggle visibility EUR fields + auto recalc CZK
        self._mena_edit.current_value_changed.connect(self._on_mena_changed)
        self._castka_mena_edit.text_changed.connect(
            lambda _t: self._recalc_czk_from_eur(),
        )
        self._kurz_edit.text_changed.connect(
            lambda _t: self._recalc_czk_from_eur(),
        )

    def _on_k_doreseni_toggled_edit(self, checked: bool) -> None:
        if self._vm.edit_mode and self._is_novy():
            self._poznamka_doreseni_edit.setVisible(checked)

    # ─── PDF loading ─────────────────────────────────────────────

    def _load_pdf(self) -> None:
        """Nacte PDF nebo obrazkovou prilohu pro doklad."""
        if self._priloha_loader is None or self._priloha_full_path is None:
            self._pdf_viewer.setVisible(False)
            self._upload_zone.setVisible(True)
            return

        prilohy = self._priloha_loader(self._vm.doklad.id)

        _IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg"}

        # Preferuj PDF, fallback na obrázek
        priloha = next(
            (p for p in prilohy if p.mime_type == "application/pdf"), None,
        )
        is_image = False
        if priloha is None:
            priloha = next(
                (p for p in prilohy if p.mime_type in _IMAGE_MIMES), None,
            )
            is_image = priloha is not None

        if priloha is None:
            self._pdf_viewer.setVisible(False)
            self._upload_zone.setVisible(True)
            return

        full = self._priloha_full_path(priloha.relativni_cesta)
        self._pdf_viewer.setVisible(True)
        self._upload_zone.setVisible(False)
        if is_image:
            self._pdf_viewer.load_image(full)
        else:
            self._pdf_viewer.load_pdf(full)

    def _on_pdf_uploaded(self, path_str: str) -> None:
        """Upload PDF k dokladu."""
        if self._priloha_uploader is None:
            return
        path = Path(path_str)
        try:
            self._priloha_uploader(
                self._vm.doklad.id, path, path.name,
            )
            # Refresh — zobraz PDF
            self._load_pdf()
        except Exception as exc:  # noqa: BLE001
            self._show_error(f"Chyba uploadu: {exc}")

    # ─── Slots ───────────────────────────────────────────────────

    def _is_novy(self) -> bool:
        return self._vm.doklad.stav == StavDokladu.NOVY

    def _on_edit(self) -> None:
        self._vm.enter_edit()
        self._popis_edit.set_value(self._vm.draft_popis or "")
        self._datum_vystaveni_edit.set_value(self._vm.draft_datum_vystaveni)
        self._datum_vystaveni_edit.inner_widget.setEnabled(
            self._vm.can_edit_datum_vystaveni
        )
        self._splatnost_edit.set_value(self._vm.draft_splatnost)
        self._splatnost_edit.inner_widget.setEnabled(
            self._vm.can_edit_splatnost
        )
        # Měna + cizoměnová pole + CZK — editace povolena pro NOVY.
        # CZK input je VŽDY editovatelný (i pro EUR/USD — auto-přepočet
        # z EUR×kurz se aplikuje při změně EUR/kurz, ale uživatel může
        # CZK i ručně přepsat).
        self._mena_edit.set_value(self._vm.draft_mena)
        if self._vm.draft_castka_mena is not None:
            cm_str = f"{self._vm.draft_castka_mena.to_koruny():.2f}".replace(
                ".", ",",
            )
            self._castka_mena_edit.set_value(cm_str)
        else:
            self._castka_mena_edit.set_value("")
        if self._vm.draft_kurz is not None:
            self._kurz_edit.set_value(
                str(self._vm.draft_kurz).replace(".", ",")
            )
        else:
            self._kurz_edit.set_value("")
        self._castka_edit.set_value(self._vm.draft_castka_celkem)
        # Enabled = stav umožňuje editaci (NOVY). Měna nehraje roli — všechny
        # inputy editovatelné, protože pro EUR jdou upravit CZK i EUR i kurz.
        can_edit_castka = self._vm.can_edit_castka
        self._mena_edit.setEnabled(can_edit_castka)
        self._castka_mena_edit.setEnabled(can_edit_castka)
        self._kurz_edit.setEnabled(can_edit_castka)
        self._castka_edit.line_widget.setEnabled(can_edit_castka)
        self._sync_mena_visibility()

        self._partner_edit.set_selected_id(self._vm.draft_partner_id)
        self._k_doreseni_check.setChecked(self._vm.draft_k_doreseni)
        self._poznamka_doreseni_edit.set_value(
            self._vm.draft_poznamka_doreseni or ""
        )
        self._sync_ui()

    def _sync_mena_visibility(self) -> None:
        """Visibilita EUR/kurz polí podle aktuální draft_mena.

        CZK input je vždy editovatelný (nezávisle na měně) — pro EUR/USD
        slouží auto-přepočet, ale Tereza může CZK i ručně přepsat.
        """
        is_cizi = self._mena_edit.value() != Mena.CZK
        self._cizi_wrap.setVisible(self._vm.edit_mode and is_cizi)

    def _on_mena_changed(self, _value: object) -> None:
        """Změna měny — přepni viditelnost EUR pole + spočítej CZK."""
        self._sync_mena_visibility()
        self._recalc_czk_from_eur()

    def _recalc_czk_from_eur(self) -> None:
        """Auto-přepočet CZK = EUR × kurz pro cizí měnu."""
        from decimal import Decimal as _D, InvalidOperation
        if self._mena_edit.value() == Mena.CZK:
            return
        cm_text = self._castka_mena_edit.value().strip().replace(",", ".")
        kurz_text = self._kurz_edit.value().strip().replace(",", ".")
        if not cm_text or not kurz_text:
            return
        try:
            cm = _D(cm_text)
            k = _D(kurz_text)
            if k <= 0:
                return
            from domain.shared.money import Money as _Money
            czk = _Money.from_koruny((cm * k).quantize(_D("0.01")))
            self._castka_edit.set_value(czk)
        except (InvalidOperation, ValueError):
            pass

    def _on_new_partner_edit(self) -> None:
        """Inline vytvoření partnera z edit módu."""
        from ui.dialogs.partner_dialog import PartnerDialog
        dialog = PartnerDialog(parent=self)
        if dialog.exec() and dialog.result is not None:
            if callable(self._on_partner_created):
                new_partner = self._on_partner_created(dialog.result)
                if new_partner is not None:
                    self._partner_items.append(new_partner)
                    self._partner_edit.set_items(self._partner_items)
                    self._partner_edit.set_selected_id(new_partner.id)

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
        # Datum vystavení — pokud uživatel mazal, fallback na původní
        novy_datum = self._datum_vystaveni_edit.value()
        if novy_datum is None or not self._vm.can_edit_datum_vystaveni:
            novy_datum = self._vm.doklad.datum_vystaveni
        self._vm.set_draft_popis(popis)
        self._vm.set_draft_datum_vystaveni(novy_datum)
        self._vm.set_draft_splatnost(splatnost)
        self._vm.set_draft_partner_id(self._partner_edit.selected_id())
        # Měna + castka + EUR/kurz — pouze pokud je editovatelná (NOVY)
        if self._vm.can_edit_castka:
            nova_mena = self._mena_edit.value() or Mena.CZK
            self._vm.set_draft_mena(nova_mena)
            if nova_mena == Mena.CZK:
                nova_castka = self._castka_edit.value()
                if nova_castka is not None:
                    self._vm.set_draft_castka_celkem(nova_castka)
            else:
                # EUR/USD — parse castka_mena + kurz, draft_castka_celkem
                # už bylo aktualizováno auto-přepočtem
                from decimal import Decimal as _D, InvalidOperation
                from domain.shared.money import Money as _Money
                cm_text = self._castka_mena_edit.value().strip().replace(",", ".")
                kurz_text = self._kurz_edit.value().strip().replace(",", ".")
                try:
                    cm = _Money.from_koruny(_D(cm_text)) if cm_text else None
                    k = _D(kurz_text) if kurz_text else None
                    self._vm.set_draft_castka_mena(cm)
                    self._vm.set_draft_kurz(k)
                except (InvalidOperation, ValueError):
                    pass
                # CZK přepočet z UI inputu (auto-přepočet ho už nastavil)
                czk = self._castka_edit.value()
                if czk is not None:
                    self._vm.set_draft_castka_celkem(czk)

        if self._is_novy():
            flag = self._k_doreseni_check.isChecked()
            self._vm.set_draft_k_doreseni(flag)
            if flag:
                raw = self._poznamka_doreseni_edit.value().strip()
                self._vm.set_draft_poznamka_doreseni(raw or None)
            else:
                self._vm.set_draft_poznamka_doreseni(None)

        result = self._vm.save_edit()
        if result is None:
            self._show_error(self._vm.error or "Ulozeni selhalo.")
            return
        self._sync_ui()

    def _on_duplikat(self) -> None:
        self.duplikat_requested.emit(self._vm.doklad)
        self.accept()

    def _on_zauctovat(self) -> None:
        item = self._vm.doklad
        if item.k_doreseni and "Duplikát" in (item.poznamka_doreseni or ""):
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "Zaúčtovat duplikát?",
                "Doklad je duplikát. Zkontroloval/a jsi datum, VS, "
                "částku a PDF?\n\nPokračovat?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.zauctovat_requested.emit(item)

    def _on_toggle_flag(self) -> None:
        if self._vm.doklad.k_doreseni:
            self._vm.dores()
        else:
            confirmed, poznamka = ConfirmDialog.ask_with_note(
                self,
                title="Označit k dořešení",
                message=(
                    f"Označit doklad {self._vm.doklad.cislo} jako "
                    f"k dořešení?\n"
                    "Můžeš volitelně přidat poznámku, proč vyžaduje "
                    "pozornost."
                ),
                confirm_text="Označit",
                note_placeholder="Proč vyžaduje pozornost? (nepovinné)",
            )
            if not confirmed:
                return
            self._vm.oznac_k_doreseni(poznamka)
        if self._vm.error:
            self._show_error(self._vm.error)
        else:
            self._sync_ui()

    def _on_storno(self) -> None:
        result = StornoDialog.ask(
            self,
            cislo_dokladu=self._vm.doklad.cislo,
            default_datum=self._vm.doklad.datum_vystaveni,
        )
        if result is None:
            return
        datum, poznamka = result
        self._vm.stornovat(datum=datum, poznamka=poznamka)
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
                "Smazat lze jen doklad ve stavu NOVÝ bez účetních zápisů."
            ),
            confirm_text="Ano, smazat",
            destructive=True,
        )
        if not ok:
            return
        if self._vm.smazat():
            self.accept()
            return
        self._show_error(self._vm.error or "Smazani selhalo.")

    # ─── Úhrada handlers ──────────────────────────────────────────

    def _on_uhrada_z_banky(self) -> None:
        from services.queries.banka import BankovniTransakceQuery
        from services.commands.sparovat_platbu_dokladem import (
            SparovatPlatbuDoklademCommand,
            _najdi_ucet_zavazku,
        )
        from ui.dialogs.uhrada_z_banky_dialog import UhradaZBankyDialog
        from ui.dialogs.zauctovat_uhradu_dialog import ZauctovatUhraduDialog
        from PyQt6.QtWidgets import QMessageBox

        if self._uow_factory is None:
            self._show_error("Funkce úhrady z banky není dostupná.")
            return

        item = self._vm.doklad
        tx_query = BankovniTransakceQuery(uow_factory=self._uow_factory)
        dlg = UhradaZBankyDialog(item, tx_query, parent=self)
        if not dlg.exec():
            return

        tx_id = dlg.selected_tx_id
        if tx_id is None:
            return

        # Otevři dialog zaúčtování úhrady — předvyplň reálné účty
        # z původního zaúčtování dokladu a bankovní účet z výpisu
        from datetime import date as _date
        from domain.banka.bankovni_transakce import StavTransakce
        from domain.doklady.typy import TypDokladu
        from domain.shared.money import Money
        from infrastructure.database.repositories.uctova_osnova_repository import (
            SqliteUctovaOsnovaRepository,
        )
        from services.queries.banka import TransakceListItem
        from services.queries.uctova_osnova import UcetItem

        uow = self._uow_factory()
        with uow:
            sloupec = (
                "dal_ucet" if item.typ == TypDokladu.FAKTURA_PRIJATA
                else "md_ucet"
            )
            ucet_protistrany = _najdi_ucet_zavazku(uow, item.id, sloupec)

            # Bankovní účet z výpisu (přes transakci) + data transakce
            row = uow.connection.execute(
                """
                SELECT bu.ucet_kod, bt.*
                FROM bankovni_transakce bt
                JOIN bankovni_vypisy bv ON bv.id = bt.bankovni_vypis_id
                JOIN bankovni_ucty bu ON bu.id = bv.bankovni_ucet_id
                WHERE bt.id = ?
                """,
                (tx_id,),
            ).fetchone()
            if row is None:
                self._show_error("Transakce nebyla nalezena.")
                return
            ucet_221 = row["ucet_kod"]
            tx_item = TransakceListItem(
                id=row["id"],
                datum_transakce=_date.fromisoformat(row["datum_transakce"]),
                datum_zauctovani=_date.fromisoformat(row["datum_zauctovani"]),
                castka=Money(row["castka"]),
                smer=row["smer"],
                variabilni_symbol=row["variabilni_symbol"],
                protiucet=row["protiucet"],
                popis=row["popis"],
                stav=StavTransakce(row["stav"]),
            )

            # Účtová osnova
            osnova_repo = SqliteUctovaOsnovaRepository(uow)
            ucty_domain = osnova_repo.list_all(jen_aktivni=True)
        ucty = [UcetItem.from_domain(u) for u in ucty_domain]

        zdlg = ZauctovatUhraduDialog(
            doklad_cislo=item.cislo,
            doklad_typ=item.typ,
            doklad_castka=item.castka_celkem,
            transakce=tx_item,
            ucty=ucty,
            ucet_protistrany=ucet_protistrany,
            ucet_221=ucet_221,
            parent=self,
        )
        if not zdlg.exec():
            return

        cmd = SparovatPlatbuDoklademCommand(uow_factory=self._uow_factory)
        try:
            result = cmd.execute(
                tx_id, item.id,
                md_ucet_override=zdlg.md_ucet,
                dal_ucet_override=zdlg.dal_ucet,
                popis_override=zdlg.popis or None,
                rozdil_zauctovat=zdlg.zauctovat_rozdil,
            )
            msg = f"Doklad {item.cislo} úspěšně uhrazen z banky."
            if result.kurzovy_rozdil:
                msg += f"\nKurzový rozdíl: {result.kurzovy_rozdil.format_cz()}"
            QMessageBox.information(self, "Uhrazeno", msg)
            self._refresh_doklad_from_db(item.id)
            self._sync_ui()
            self.uhrada_completed.emit()
        except Exception as exc:  # noqa: BLE001
            self._show_error(str(exc))

    def _on_uhrada_pokladnou(self) -> None:
        from services.commands.uhrada_dokladu import UhradaPokladnouCommand
        from ui.dialogs.uhrada_pokladnou_dialog import UhradaPokladnouDialog
        from PyQt6.QtWidgets import QMessageBox

        if self._uow_factory is None:
            self._show_error("Funkce úhrady pokladnou není dostupná.")
            return

        item = self._vm.doklad
        rok = item.datum_vystaveni.year
        next_cislo = f"PD-{rok}-{item.id:03d}"

        dlg = UhradaPokladnouDialog(item, next_cislo, parent=self)
        if not dlg.exec():
            return

        cmd = UhradaPokladnouCommand(uow_factory=self._uow_factory)
        try:
            result = cmd.execute(
                doklad_id=item.id,
                datum_uhrady=dlg.result_datum,
                cislo_pd=dlg.result_cislo,
                popis=dlg.result_popis,
            )
            QMessageBox.information(
                self, "Uhrazeno",
                f"Vytvořen PD doklad {result.novy_doklad_cislo}.\n"
                f"Doklad {item.cislo} uhrazen.",
            )
            self._refresh_doklad_from_db(item.id)
            self._sync_ui()
            self.uhrada_completed.emit()
        except Exception as exc:  # noqa: BLE001
            self._show_error(str(exc))

    def _on_uhrada_int_dokladem(self) -> None:
        from domain.partneri.partner import KategoriePartnera
        from services.commands.uhrada_dokladu import UhradaIntDoklademCommand
        from ui.dialogs.uhrada_id_dialog import UhradaIntDoklademDialog
        from PyQt6.QtWidgets import QMessageBox

        if self._uow_factory is None:
            self._show_error("Funkce úhrady int. dokladem není dostupná.")
            return

        item = self._vm.doklad

        # Načti společníky
        from infrastructure.database.repositories.partneri_repository import (
            SqlitePartneriRepository,
        )
        uow = self._uow_factory()
        with uow:
            repo = SqlitePartneriRepository(uow)
            all_partners = repo.list_all()
        spolecnici = [
            p for p in all_partners
            if p.kategorie == KategoriePartnera.SPOLECNIK
        ]

        if not spolecnici:
            self._show_error("Žádní společníci v systému.")
            return

        rok = item.datum_vystaveni.year
        next_cislo = f"ID-{rok}-{item.id:03d}"

        dlg = UhradaIntDoklademDialog(
            item, spolecnici, next_cislo, parent=self,
        )
        if not dlg.exec():
            return

        cmd = UhradaIntDoklademCommand(uow_factory=self._uow_factory)
        try:
            result = cmd.execute(
                doklad_id=item.id,
                datum_uhrady=dlg.result_datum,
                cislo_id=dlg.result_cislo,
                ucet_spolecnika=dlg.result_ucet_spolecnika,
                popis=dlg.result_popis,
            )
            QMessageBox.information(
                self, "Uhrazeno",
                f"Vytvořen ID doklad {result.novy_doklad_cislo}.\n"
                f"Doklad {item.cislo} uhrazen (pytlování).",
            )
            self._refresh_doklad_from_db(item.id)
            self._sync_ui()
            self.uhrada_completed.emit()
        except Exception as exc:  # noqa: BLE001
            self._show_error(str(exc))

    def _refresh_doklad_from_db(self, doklad_id: int) -> None:
        """Re-načte doklad z DB po úhradě a aktualizuje VM."""
        if self._uow_factory is None:
            return
        from infrastructure.database.repositories.doklady_repository import (
            SqliteDokladyRepository,
        )
        from services.queries.doklady_list import DokladyListItem
        uow = self._uow_factory()
        with uow:
            repo = SqliteDokladyRepository(uow)
            doklad = repo.get_by_id(doklad_id)
        item = DokladyListItem.from_domain(doklad)
        self._vm.refresh_from(item)

    # ─── External: zauctovani_dialog succeeded ───────────────────

    def refresh_after_zauctovani(self, item: DokladyListItem) -> None:
        self._vm.refresh_from(item)
        self._sync_ui()

    # ─── UI sync ─────────────────────────────────────────────────

    def _sync_ui(self) -> None:
        item = self._vm.doklad

        # Badges
        self._stav_badge.setText(stav_display_text(item.stav))
        self._stav_badge.set_variant(badge_variant_for_stav(item.stav))

        # Castka celkem — aktualizuj po edit-save (jinak by zůstala
        # původní hodnota uvnitř formu).
        self._castka_value_label.setText(item.castka_celkem.format_cz())

        # Cizoměnový řádek "Puvodne: X EUR (kurz Y)"
        if (
            item.mena != Mena.CZK
            and item.castka_mena is not None
            and item.kurz is not None
        ):
            foreign_koruny = item.castka_mena.to_koruny()
            foreign_text = (
                f"{foreign_koruny:,.2f} {item.mena.value} "
                f"(kurz {item.kurz})"
            ).replace(",", " ").replace(".", ",")
            self._foreign_value.setText(foreign_text)
            self._foreign_label.setVisible(True)
            self._foreign_value.setVisible(True)
        else:
            self._foreign_label.setVisible(False)
            self._foreign_value.setVisible(False)

        # Splatnost + popis + partner
        splatnost_text = (
            _format_date_long(item.datum_splatnosti)
            if item.datum_splatnosti is not None
            else "—"
        )
        self._datum_vystaveni_display.setText(
            _format_date_long(item.datum_vystaveni)
        )
        self._splatnost_display.setText(splatnost_text)
        self._popis_display.setText(item.popis or "—")
        self._partner_display.setText(item.partner_nazev or "—")
        self._vs_display.setText(item.variabilni_symbol or "—")

        # Zbyva uhradit
        self._update_zbyva_uhradit()

        # Účetní zápisy
        self._update_zapisy()

        # Datum storna
        je_stornovany = item.stav == StavDokladu.STORNOVANY
        self._storno_label.setVisible(je_stornovany)
        self._storno_value.setVisible(je_stornovany)
        if je_stornovany and item.datum_storna is not None:
            self._storno_value.setText(_format_date_long(item.datum_storna))
        else:
            self._storno_value.setText("—")

        # K doreseni box — show only for NOVY documents
        self._doreseni_box.setVisible(
            item.k_doreseni and item.stav == StavDokladu.NOVY
        )
        if item.k_doreseni:
            if item.poznamka_doreseni:
                self._doreseni_note.setText(item.poznamka_doreseni)
                self._doreseni_note.setProperty("empty", "false")
            else:
                self._doreseni_note.setText("(bez poznámky)")
                self._doreseni_note.setProperty("empty", "true")
            self._doreseni_note.style().unpolish(self._doreseni_note)
            self._doreseni_note.style().polish(self._doreseni_note)

        # Edit mode: toggle sets
        edit = self._vm.edit_mode
        self._popis_edit.setVisible(edit)
        self._datum_vystaveni_edit.setVisible(edit)
        self._splatnost_edit.setVisible(edit)
        # Měna + castka editor — visible v edit mode pro NOVY.
        self._mena_edit.setVisible(edit and self._vm.can_edit_castka)
        self._castka_edit.setVisible(edit and self._vm.can_edit_castka)
        # EUR/kurz fields — visible jen pro EUR/USD měnu (řeší _sync_mena_visibility)
        if edit and self._vm.can_edit_castka:
            self._sync_mena_visibility()
        else:
            self._cizi_wrap.setVisible(False)
        self._partner_edit.setVisible(edit)
        self._popis_display.setVisible(not edit)
        self._datum_vystaveni_display.setVisible(not edit)
        self._splatnost_display.setVisible(not edit)
        self._actions_row.setVisible(not edit)
        self._edit_actions_row.setVisible(edit)

        is_novy = item.stav == StavDokladu.NOVY
        self._k_doreseni_check.setVisible(edit and is_novy)
        self._poznamka_doreseni_edit.setVisible(
            edit and is_novy and self._k_doreseni_check.isChecked()
        )

        # Button enabled
        self._edit_button.setEnabled(self._vm.can_edit)
        self._zauctovat_button.setEnabled(self._vm.can_zauctovat)
        self._zauctovat_button.setVisible(
            item.stav == StavDokladu.NOVY
        )
        self._storno_button.setEnabled(
            self._vm.can_storno
            and item.stav != StavDokladu.NOVY
        )
        self._smazat_button.setEnabled(self._vm.can_smazat)
        self._flag_button.setVisible(not is_novy)
        self._flag_button.setEnabled(self._vm.can_toggle_flag)
        self._flag_button.setText(
            "Dořešit" if item.k_doreseni else "Označit k dořešení"
        )

        # Úhrada — jen pro zaúčtované FP/FV, které nejsou uhrazeny/stornovány
        is_invoice = item.typ in (
            TypDokladu.FAKTURA_PRIJATA, TypDokladu.FAKTURA_VYDANA,
        )
        can_uhrada = (
            is_invoice
            and item.stav in (
                StavDokladu.ZAUCTOVANY, StavDokladu.CASTECNE_UHRAZENY,
            )
        )
        self._uhrada_button.setVisible(can_uhrada)

        # Reset error
        if not edit and not self._vm.error:
            self._error_label.setVisible(False)

    def _update_zbyva_uhradit(self) -> None:
        """Vypocte a zobrazi 'Zbyva uhradit'."""
        item = self._vm.doklad

        # Úhrada se sleduje jen u faktur
        is_invoice = item.typ in (TypDokladu.FAKTURA_PRIJATA, TypDokladu.FAKTURA_VYDANA)
        self._zbyva_uhradit_label.setVisible(is_invoice)
        self._zbyva_label.setVisible(is_invoice)
        if not is_invoice:
            return

        if item.stav in (StavDokladu.UHRAZENY,):
            self._zbyva_label.setText("Uhrazeno \u2713")
            self._zbyva_label.setStyleSheet(f"color: {Colors.SUCCESS_700};")
            return

        if item.stav == StavDokladu.STORNOVANY:
            self._zbyva_label.setText("Storno")
            self._zbyva_label.setStyleSheet(f"color: {Colors.GRAY_500};")
            return

        if item.stav == StavDokladu.NOVY:
            self._zbyva_label.setText(item.castka_celkem.format_cz())
            self._zbyva_label.setStyleSheet(f"color: {Colors.GRAY_500};")
            return

        # ZAUCTOVANY nebo CASTECNE_UHRAZENY — zkus zjistit ze deniku
        uhrazeno = Money.zero()
        if self._uhrazeno_query is not None:
            try:
                uhrazeno = self._uhrazeno_query(item.id)
            except Exception:  # noqa: BLE001
                pass

        zbyva = item.castka_celkem - uhrazeno
        if zbyva <= Money.zero():
            self._zbyva_label.setText("Uhrazeno \u2713")
            self._zbyva_label.setStyleSheet(f"color: {Colors.SUCCESS_700};")
        elif uhrazeno > Money.zero():
            self._zbyva_label.setText(f"{zbyva.format_cz()}")
            self._zbyva_label.setStyleSheet(f"color: {Colors.WARNING_700};")
        else:
            self._zbyva_label.setText(item.castka_celkem.format_cz())
            self._zbyva_label.setStyleSheet(f"color: {Colors.ERROR_600};")

    def _update_zapisy(self) -> None:
        """Načte a zobrazí účetní záznamy pro doklad."""
        item = self._vm.doklad

        # Zobrazit jen pro zaúčtované+ stavy
        show = (
            self._ucetni_zapisy_query is not None
            and item.stav in (
                StavDokladu.ZAUCTOVANY,
                StavDokladu.UHRAZENY,
                StavDokladu.CASTECNE_UHRAZENY,
                StavDokladu.STORNOVANY,
            )
        )
        if not show:
            self._zapisy_section.setVisible(False)
            return

        zapisy = self._ucetni_zapisy_query(item.id)
        if not zapisy:
            self._zapisy_section.setVisible(False)
            return

        self._zapisy_table.setRowCount(len(zapisy))
        for i, z in enumerate(zapisy):
            self._zapisy_table.setItem(
                i, 0,
                QTableWidgetItem(f"{z.datum.day:02d}.{z.datum.month:02d}.{z.datum.year % 100:02d}"),
            )
            self._zapisy_table.setItem(i, 1, QTableWidgetItem(z.zdroj_doklad))
            self._zapisy_table.setItem(i, 2, QTableWidgetItem(z.md_ucet))
            self._zapisy_table.setItem(i, 3, QTableWidgetItem(z.dal_ucet))
            self._zapisy_table.setItem(
                i, 4, QTableWidgetItem(z.castka.format_cz()),
            )
            popis_text = z.popis or ""
            if z.je_storno:
                popis_text = f"[STORNO] {popis_text}"
            self._zapisy_table.setItem(i, 5, QTableWidgetItem(popis_text))

        self._zapisy_section.setVisible(True)

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
