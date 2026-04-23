"""SparovatPlatbuDialog — dialog pro ruční párování bankovní transakce s dokladem."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from domain.shared.money import Money
from services.queries.banka import TransakceListItem
from services.queries.neuhrazene_doklady import (
    NeuhrazenyDokladItem,
    NeuhrazeneDokladyQuery,
)
from ui.design_tokens import Colors, Spacing


class SparovatPlatbuDialog(QDialog):
    """Dialog pro spárování bankovní transakce s dokladem."""

    def __init__(
        self,
        transakce: TransakceListItem,
        query: NeuhrazeneDokladyQuery,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tx = transakce
        self._query = query
        self._selected_doklad_id: int | None = None
        self._all_items: list[NeuhrazenyDokladItem] = []

        self.setWindowTitle("Spárovat platbu s dokladem")
        self.setMinimumSize(600, 500)
        self.setModal(True)

        self._radio_group: QButtonGroup
        self._candidates_layout: QVBoxLayout
        self._search_input: QLineEdit
        self._submit_btn: QPushButton

        self._build_ui()
        self._load_candidates(filter_castka=True)

    @property
    def selected_doklad_id(self) -> int | None:
        return self._selected_doklad_id

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S3)

        # Header: info o transakci
        title = QLabel("Spárovat platbu s dokladem", self)
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        info_box = QWidget(self)
        info_box.setProperty("class", "card")
        info_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        info_layout = QVBoxLayout(info_box)
        info_layout.setContentsMargins(
            Spacing.S3, Spacing.S3, Spacing.S3, Spacing.S3,
        )
        info_layout.setSpacing(2)

        tx = self._tx
        info_layout.addWidget(QLabel(
            f"Datum: {tx.datum_zauctovani.strftime('%d.%m.%Y')}",
        ))
        info_layout.addWidget(QLabel(
            f"Castka: {tx.castka.format_cz()}",
        ))
        if tx.variabilni_symbol:
            info_layout.addWidget(QLabel(f"VS: {tx.variabilni_symbol}"))
        if tx.popis:
            popis_label = QLabel(f"Popis: {tx.popis}")
            popis_label.setWordWrap(True)
            info_layout.addWidget(popis_label)

        root.addWidget(info_box)

        # Filtr
        filter_row = QHBoxLayout()
        filter_row.setSpacing(Spacing.S2)

        self._show_all_btn = QPushButton("Zobrazit vse", self)
        self._show_all_btn.setProperty("class", "secondary-sm")
        self._show_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._show_all_btn.setCheckable(True)
        self._show_all_btn.clicked.connect(self._on_toggle_filter)
        filter_row.addWidget(self._show_all_btn)

        filter_row.addStretch()

        self._search_input = QLineEdit(self)
        self._search_input.setPlaceholderText("Hledej cislo dokladu nebo partnera...")
        self._search_input.textChanged.connect(self._on_search)
        filter_row.addWidget(self._search_input, stretch=1)

        root.addLayout(filter_row)

        # Kandidáti label
        self._candidates_label = QLabel("Kandidati (0):", self)
        self._candidates_label.setProperty("class", "section-title")
        root.addWidget(self._candidates_label)

        # Scroll area pro kandidáty
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

        self._candidates_container = QWidget()
        self._candidates_layout = QVBoxLayout(self._candidates_container)
        self._candidates_layout.setContentsMargins(0, 0, 0, 0)
        self._candidates_layout.setSpacing(2)
        scroll.setWidget(self._candidates_container)
        root.addWidget(scroll, stretch=1)

        self._radio_group = QButtonGroup(self)
        self._radio_group.buttonClicked.connect(self._on_radio_clicked)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Zrusit", self)
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._submit_btn = QPushButton("Sparovat a zauctovat", self)
        self._submit_btn.setProperty("class", "primary")
        self._submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit_btn.setEnabled(False)
        self._submit_btn.clicked.connect(self._on_submit)
        btn_row.addWidget(self._submit_btn)

        root.addLayout(btn_row)

    def _load_candidates(self, filter_castka: bool = False) -> None:
        """Načte kandidáty z DB."""
        castka_od: Money | None = None
        castka_do: Money | None = None

        if filter_castka:
            tx_abs = abs(self._tx.castka.to_halire())
            margin = int(tx_abs * 0.01)  # ±1%
            castka_od = Money(tx_abs - margin)
            castka_do = Money(tx_abs + margin)

        search = self._search_input.text().strip() or None
        self._all_items = self._query.execute(
            castka_od=castka_od,
            castka_do=castka_do,
            search=search,
        )
        self._render_candidates()

    def _render_candidates(self) -> None:
        # Clear
        while self._candidates_layout.count():
            child = self._candidates_layout.takeAt(0)
            w = child.widget()
            if w:
                w.setParent(None)

        for btn in self._radio_group.buttons():
            self._radio_group.removeButton(btn)

        self._candidates_label.setText(
            f"Kandidati ({len(self._all_items)}):",
        )

        for item in self._all_items:
            row = QWidget(self._candidates_container)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(
                Spacing.S2, Spacing.S1, Spacing.S2, Spacing.S1,
            )
            row_layout.setSpacing(Spacing.S2)

            radio = QRadioButton(row)
            radio.setProperty("doklad_id", item.id)
            self._radio_group.addButton(radio)
            row_layout.addWidget(radio)

            text = (
                f"{item.cislo}  "
                f"{item.partner_nazev or '—'}  "
                f"{item.castka_celkem.format_cz()}  "
                f"({item.datum.strftime('%d.%m.%Y')})"
            )
            if item.variabilni_symbol:
                text += f"  VS:{item.variabilni_symbol}"

            label = QLabel(text, row)
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            row_layout.addWidget(label, stretch=1)

            self._candidates_layout.addWidget(row)

        self._candidates_layout.addStretch()

    def _on_toggle_filter(self, checked: bool) -> None:
        self._load_candidates(filter_castka=not checked)

    def _on_search(self, _text: str) -> None:
        show_all = self._show_all_btn.isChecked()
        self._load_candidates(filter_castka=not show_all)

    def _on_radio_clicked(self, button: QRadioButton) -> None:
        doklad_id = button.property("doklad_id")
        self._selected_doklad_id = doklad_id
        self._submit_btn.setEnabled(doklad_id is not None)

    def _on_submit(self) -> None:
        if self._selected_doklad_id is not None:
            self.accept()
