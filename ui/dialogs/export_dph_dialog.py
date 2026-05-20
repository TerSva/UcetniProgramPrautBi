"""ExportDphDialog — výběr období pro export DPH přehledu do PDF.

Tři předvolby: jeden měsíc, rozsah od–do, celý rok. Po potvrzení
volající otevře save dialog a spustí export.
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from services.export.dph_export import DphExportRozsah
from ui.design_tokens import Spacing


_MESICE_CZ = [
    "Leden", "Únor", "Březen", "Duben", "Květen", "Červen",
    "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec",
]


def _mesic_combo(default_mesic: int) -> QComboBox:
    c = QComboBox()
    for i, nazev in enumerate(_MESICE_CZ, start=1):
        c.addItem(f"{i:02d} — {nazev}", i)
    c.setCurrentIndex(default_mesic - 1)
    return c


def _rok_combo(default_rok: int) -> QComboBox:
    c = QComboBox()
    for r in range(2020, 2031):
        c.addItem(str(r), r)
    idx = c.findData(default_rok)
    if idx >= 0:
        c.setCurrentIndex(idx)
    return c


class ExportDphDialog(QDialog):
    """Dialog pro výběr období DPH exportu."""

    MODE_MESIC = 0
    MODE_ROZSAH = 1
    MODE_ROK = 2

    def __init__(
        self,
        default_rok: int,
        default_mesic: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._default_rok = default_rok
        self._default_mesic = default_mesic or date.today().month
        self._rozsah: DphExportRozsah | None = None

        self.setWindowTitle("Export DPH přehledu (PDF)")
        self.setModal(True)
        self.setProperty("class", "export-dph-dialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.resize(520, 360)

        self._radio_mesic: QRadioButton
        self._radio_rozsah: QRadioButton
        self._radio_rok: QRadioButton
        self._stack: QStackedWidget
        self._mesic_rok: QComboBox
        self._mesic_mesic: QComboBox
        self._od_rok: QComboBox
        self._od_mesic: QComboBox
        self._do_rok: QComboBox
        self._do_mesic: QComboBox
        self._rok_rok: QComboBox
        self._ok_button: QPushButton
        self._cancel_button: QPushButton

        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        title = QLabel("Export DPH přehledu do PDF", self)
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        info = QLabel(
            "Vyber rozsah měsíců. PDF obsahuje za každý měsíc řádky "
            "EPO přiznání a tabulku reverse charge transakcí. Měsíce bez "
            "RC plnění se vynechají.",
            self,
        )
        info.setWordWrap(True)
        info.setProperty("class", "dialog-subtitle")
        root.addWidget(info)

        # Radio
        group = QButtonGroup(self)
        self._radio_mesic = QRadioButton("Jeden měsíc", self)
        self._radio_rozsah = QRadioButton("Rozsah od – do", self)
        self._radio_rok = QRadioButton("Celý rok", self)
        for i, rb in enumerate(
            (self._radio_mesic, self._radio_rozsah, self._radio_rok),
        ):
            group.addButton(rb, i)
            root.addWidget(rb)
        self._radio_mesic.setChecked(True)

        # Stack s parametry pro každý mode
        self._stack = QStackedWidget(self)

        # 0 – jeden měsíc
        w_mesic = QWidget()
        l_mesic = QHBoxLayout(w_mesic)
        l_mesic.setContentsMargins(20, 6, 0, 6)
        self._mesic_rok = _rok_combo(self._default_rok)
        self._mesic_mesic = _mesic_combo(self._default_mesic)
        l_mesic.addWidget(QLabel("Rok:"))
        l_mesic.addWidget(self._mesic_rok)
        l_mesic.addSpacing(12)
        l_mesic.addWidget(QLabel("Měsíc:"))
        l_mesic.addWidget(self._mesic_mesic)
        l_mesic.addStretch(1)
        self._stack.addWidget(w_mesic)

        # 1 – rozsah od-do
        w_rozsah = QWidget()
        l_rozsah = QVBoxLayout(w_rozsah)
        l_rozsah.setContentsMargins(20, 6, 0, 6)
        l_rozsah.setSpacing(6)
        from_row = QHBoxLayout()
        self._od_rok = _rok_combo(self._default_rok)
        self._od_mesic = _mesic_combo(1)
        from_row.addWidget(QLabel("Od:"))
        from_row.addWidget(self._od_rok)
        from_row.addWidget(self._od_mesic)
        from_row.addStretch(1)
        l_rozsah.addLayout(from_row)
        to_row = QHBoxLayout()
        self._do_rok = _rok_combo(self._default_rok)
        self._do_mesic = _mesic_combo(self._default_mesic)
        to_row.addWidget(QLabel("Do:"))
        to_row.addWidget(self._do_rok)
        to_row.addWidget(self._do_mesic)
        to_row.addStretch(1)
        l_rozsah.addLayout(to_row)
        self._stack.addWidget(w_rozsah)

        # 2 – celý rok
        w_rok = QWidget()
        l_rok = QHBoxLayout(w_rok)
        l_rok.setContentsMargins(20, 6, 0, 6)
        self._rok_rok = _rok_combo(self._default_rok)
        l_rok.addWidget(QLabel("Rok:"))
        l_rok.addWidget(self._rok_rok)
        l_rok.addStretch(1)
        self._stack.addWidget(w_rok)

        root.addWidget(self._stack)
        root.addStretch(1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self._cancel_button = QPushButton("Zrušit", self)
        self._cancel_button.setProperty("class", "secondary")
        self._cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self._cancel_button)
        self._ok_button = QPushButton("Exportovat", self)
        self._ok_button.setProperty("class", "primary")
        self._ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self._ok_button)
        root.addLayout(footer)

    def _wire_signals(self) -> None:
        self._radio_mesic.toggled.connect(
            lambda checked: checked and self._stack.setCurrentIndex(self.MODE_MESIC)
        )
        self._radio_rozsah.toggled.connect(
            lambda checked: checked and self._stack.setCurrentIndex(self.MODE_ROZSAH)
        )
        self._radio_rok.toggled.connect(
            lambda checked: checked and self._stack.setCurrentIndex(self.MODE_ROK)
        )
        self._ok_button.clicked.connect(self._on_ok)
        self._cancel_button.clicked.connect(self.reject)

    def _on_ok(self) -> None:
        if self._radio_mesic.isChecked():
            r = self._mesic_rok.currentData()
            m = self._mesic_mesic.currentData()
            self._rozsah = DphExportRozsah(
                od_rok=r, od_mesic=m, do_rok=r, do_mesic=m,
            )
        elif self._radio_rok.isChecked():
            r = self._rok_rok.currentData()
            self._rozsah = DphExportRozsah(
                od_rok=r, od_mesic=1, do_rok=r, do_mesic=12,
            )
        else:
            od_r = self._od_rok.currentData()
            od_m = self._od_mesic.currentData()
            do_r = self._do_rok.currentData()
            do_m = self._do_mesic.currentData()
            if (od_r, od_m) > (do_r, do_m):
                od_r, od_m, do_r, do_m = do_r, do_m, od_r, od_m
            self._rozsah = DphExportRozsah(
                od_rok=od_r, od_mesic=od_m, do_rok=do_r, do_mesic=do_m,
            )
        self.accept()

    @property
    def rozsah(self) -> DphExportRozsah | None:
        return self._rozsah
