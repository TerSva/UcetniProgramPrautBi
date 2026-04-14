"""DokladDetailDialog — read-only modální okno s detailem jednoho dokladu.

V Kroku 3 čistě read-only: titulek, typ/stav badge, datumy, částka,
případný panel „K dořešení" (warning amber) a popis. Tlačítko „Zavřít".

Editace a Zaúčtování přijdou v dalších krocích — v tomto dialogu je
nevystavujeme, aby nebyl scope creep.
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.queries.doklady_list import DokladyListItem
from ui.design_tokens import Colors, Spacing
from ui.widgets.badge import (
    Badge,
    badge_variant_for_stav,
    badge_variant_for_typ,
    stav_display_text,
    typ_display_text,
)
from ui.widgets.icon import load_icon


def _format_date_long(d: date) -> str:
    return f"{d.day}. {d.month}. {d.year}"


class DokladDetailDialog(QDialog):
    """Modální dialog s detailem jednoho DokladyListItem."""

    def __init__(
        self,
        item: DokladyListItem,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Doklad {item.cislo}")
        self.setProperty("class", "doklad-detail")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setModal(True)
        self.resize(520, 480)

        self._item = item
        self._typ_badge: Badge
        self._stav_badge: Badge
        self._doreseni_box: QWidget
        self._close_button: QPushButton
        self._build_ui()

    # ────────────────────────────────────────────────
    # Test-only accessors (underscore = interní)
    # ────────────────────────────────────────────────

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
    def _close_button_widget(self) -> QPushButton:
        return self._close_button

    # ────────────────────────────────────────────────
    # Build
    # ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        item = self._item

        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        # Hlavička — číslo + badges
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
        self._doreseni_box.setVisible(item.k_doreseni)
        root.addWidget(self._doreseni_box)

        # Základní údaje — form
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(Spacing.S5)
        form.setVerticalSpacing(Spacing.S2)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        form.addRow(
            self._form_label("Datum vystavení:"),
            self._form_value(_format_date_long(item.datum_vystaveni)),
        )
        splatnost = (
            _format_date_long(item.datum_splatnosti)
            if item.datum_splatnosti is not None
            else "—"
        )
        form.addRow(
            self._form_label("Datum splatnosti:"),
            self._form_value(splatnost),
        )
        form.addRow(
            self._form_label("Partner:"),
            self._form_value(item.partner_nazev or "—"),
        )
        castka = self._form_value(item.castka_celkem.format_cz())
        castka.setProperty("class", "dialog-value-strong")
        form.addRow(self._form_label("Částka celkem:"), castka)

        if item.popis:
            popis_label = QLabel(item.popis, self)
            popis_label.setProperty("class", "dialog-value")
            popis_label.setWordWrap(True)
            form.addRow(self._form_label("Popis:"), popis_label)

        root.addLayout(form)
        root.addStretch(1)

        # Tlačítko „Zavřít"
        footer = QHBoxLayout()
        footer.addStretch(1)
        self._close_button = QPushButton("Zavřít", self)
        self._close_button.setProperty("class", "primary")
        self._close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_button.clicked.connect(self.accept)
        footer.addWidget(self._close_button)
        root.addLayout(footer)

    def _build_doreseni_box(self) -> QWidget:
        item = self._item
        box = QWidget(self)
        box.setProperty("class", "doreseni-box")
        box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(box)
        layout.setContentsMargins(
            Spacing.S4, Spacing.S3, Spacing.S4, Spacing.S3,
        )
        layout.setSpacing(Spacing.S1)

        # Header: Lucide bell ikona + text „K dořešení"
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

        if item.poznamka_doreseni:
            note = QLabel(item.poznamka_doreseni, box)
            note.setProperty("class", "doreseni-note")
            note.setWordWrap(True)
            layout.addWidget(note)

        return box

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
