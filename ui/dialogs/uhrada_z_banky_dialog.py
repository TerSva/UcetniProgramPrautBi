"""UhradaZBankyDialog — párování dokladu s bankovní transakcí (z druhé strany)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from domain.shared.money import Money
from services.queries.banka import BankovniTransakceQuery, TransakceListItem
from services.queries.doklady_list import DokladyListItem
from ui.design_tokens import Spacing


class UhradaZBankyDialog(QDialog):
    """Vybere nespárovanou bankovní transakci pro úhradu dokladu."""

    def __init__(
        self,
        doklad: DokladyListItem,
        tx_query: BankovniTransakceQuery,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._doklad = doklad
        self._tx_query = tx_query
        self._selected_tx_id: int | None = None

        self.setWindowTitle("Úhrada z banky")
        self.setMinimumSize(600, 450)
        self.setModal(True)

        self._build_ui()
        self._load_candidates(filter_castka=True)

    @property
    def selected_tx_id(self) -> int | None:
        return self._selected_tx_id

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S3)

        title = QLabel("Úhrada z banky", self)
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        d = self._doklad
        info = QLabel(
            f"Doklad: {d.cislo}\n"
            f"Partner: {d.partner_nazev or '—'}\n"
            f"K úhradě: {d.castka_celkem.format_cz()}",
            self,
        )
        info.setProperty("class", "form-help")
        root.addWidget(info)

        # Filtr
        filter_row = QHBoxLayout()
        self._show_all_btn = QPushButton("Zobrazit vse nesparovane", self)
        self._show_all_btn.setProperty("class", "secondary-sm")
        self._show_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._show_all_btn.setCheckable(True)
        self._show_all_btn.clicked.connect(self._on_toggle)
        filter_row.addWidget(self._show_all_btn)
        filter_row.addStretch()
        root.addLayout(filter_row)

        self._count_label = QLabel("Transakce (0):", self)
        self._count_label.setProperty("class", "section-title")
        root.addWidget(self._count_label)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        scroll.setWidget(self._container)
        root.addWidget(scroll, stretch=1)

        self._radio_group = QButtonGroup(self)
        self._radio_group.buttonClicked.connect(self._on_radio)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel = QPushButton("Zrusit", self)
        cancel.setProperty("class", "secondary")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        self._submit = QPushButton("Sparovat", self)
        self._submit.setProperty("class", "primary")
        self._submit.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit.setEnabled(False)
        self._submit.clicked.connect(self._on_submit)
        btn_row.addWidget(self._submit)

        root.addLayout(btn_row)

    def _load_candidates(self, filter_castka: bool = True) -> None:
        castka_od: Money | None = None
        castka_do: Money | None = None

        if filter_castka:
            abs_castka = abs(self._doklad.castka_celkem.to_halire())
            margin = int(abs_castka * 0.01)
            castka_od = Money(abs_castka - margin)
            castka_do = Money(abs_castka + margin)

        items = self._tx_query.list_nesparovane(
            castka_od=castka_od,
            castka_do=castka_do,
        )
        self._render(items)

    def _render(self, items: list[TransakceListItem]) -> None:
        while self._layout.count():
            child = self._layout.takeAt(0)
            w = child.widget()
            if w:
                w.setParent(None)

        for btn in self._radio_group.buttons():
            self._radio_group.removeButton(btn)

        self._count_label.setText(f"Transakce ({len(items)}):")

        for tx in items:
            row = QWidget(self._container)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(
                Spacing.S2, Spacing.S1, Spacing.S2, Spacing.S1,
            )
            row_layout.setSpacing(Spacing.S2)

            radio = QRadioButton(row)
            radio.setProperty("tx_id", tx.id)
            self._radio_group.addButton(radio)
            row_layout.addWidget(radio)

            text = (
                f"{tx.datum_zauctovani.strftime('%d.%m.%Y')}  "
                f"{tx.castka.format_cz()}"
            )
            if tx.variabilni_symbol:
                text += f"  VS:{tx.variabilni_symbol}"
            if tx.popis:
                text += f"  {tx.popis[:40]}"

            label = QLabel(text, row)
            row_layout.addWidget(label, stretch=1)

            self._layout.addWidget(row)

        self._layout.addStretch()

    def _on_toggle(self, checked: bool) -> None:
        self._load_candidates(filter_castka=not checked)

    def _on_radio(self, button: QRadioButton) -> None:
        self._selected_tx_id = button.property("tx_id")
        self._submit.setEnabled(self._selected_tx_id is not None)

    def _on_submit(self) -> None:
        if self._selected_tx_id is not None:
            self.accept()
