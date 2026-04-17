"""VkladZKDialog — 3-krokový wizard pro vklad základního kapitálu.

Krok 1: Částka ZK + datum
Krok 2: Výběr bankovního účtu pro splacení
Krok 3: Potvrzení — vytvoří 2 ID doklady (upsání + splacení)
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from domain.shared.money import Money
from ui.design_tokens import Spacing
from ui.viewmodels.pocatecni_stavy_vm import PocatecniStavyViewModel
from ui.widgets.labeled_inputs import (
    LabeledComboBox,
    LabeledDateEdit,
    LabeledLineEdit,
    LabeledMoneyEdit,
)


class VkladZKDialog(QDialog):
    """Wizard: Vklad základního kapitálu — 3 kroky."""

    def __init__(
        self,
        view_model: PocatecniStavyViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setWindowTitle("Vklad základního kapitálu")
        self.setMinimumWidth(500)
        self.setMinimumHeight(350)

        self._stack: QStackedWidget
        self._castka_input: LabeledMoneyEdit
        self._datum_input: LabeledDateEdit
        self._bank_ucet_input: LabeledLineEdit
        self._summary_label: QLabel
        self._error_label: QLabel
        self._back_button: QPushButton
        self._next_button: QPushButton
        self._result_ids: list[int] = []

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S6, Spacing.S6, Spacing.S6, Spacing.S6,
        )
        root.setSpacing(Spacing.S4)

        title = QLabel("Vklad základního kapitálu", self)
        title.setProperty("class", "dialog-title")
        root.addWidget(title)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._build_step1())
        self._stack.addWidget(self._build_step2())
        self._stack.addWidget(self._build_step3())
        root.addWidget(self._stack, stretch=1)

        # Error
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        # Footer
        footer = QHBoxLayout()
        self._back_button = QPushButton("Zpět", self)
        self._back_button.setProperty("class", "secondary")
        self._back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_button.clicked.connect(self._on_back)
        self._back_button.setEnabled(False)
        footer.addWidget(self._back_button)

        footer.addStretch(1)

        self._next_button = QPushButton("Další", self)
        self._next_button.setProperty("class", "primary")
        self._next_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_button.clicked.connect(self._on_next)
        footer.addWidget(self._next_button)

        root.addLayout(footer)

    def _build_step1(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.S3)

        step_label = QLabel("Krok 1/3: Základní údaje", page)
        step_label.setProperty("class", "section-title")
        layout.addWidget(step_label)

        desc = QLabel(
            "Zadejte výši základního kapitálu a datum zápisu do OR.",
            page,
        )
        desc.setProperty("class", "form-help")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._castka_input = LabeledMoneyEdit(
            "Základní kapitál (Kč)", placeholder="200 000", parent=page,
        )
        layout.addWidget(self._castka_input)

        self._datum_input = LabeledDateEdit(
            "Datum zápisu do OR", parent=page,
        )
        layout.addWidget(self._datum_input)

        layout.addStretch(1)
        return page

    def _build_step2(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.S3)

        step_label = QLabel("Krok 2/3: Bankovní účet", page)
        step_label.setProperty("class", "section-title")
        layout.addWidget(step_label)

        desc = QLabel(
            "Zadejte analytický účet banky, na který byl ZK splacen.\n"
            "Např. 221.001 (Money Banka) nebo 221 (syntetický).",
            page,
        )
        desc.setProperty("class", "form-help")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._bank_ucet_input = LabeledLineEdit(
            "Bankovní účet", placeholder="221.001", max_length=10, parent=page,
        )
        layout.addWidget(self._bank_ucet_input)

        layout.addStretch(1)
        return page

    def _build_step3(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.S3)

        step_label = QLabel("Krok 3/3: Potvrzení", page)
        step_label.setProperty("class", "section-title")
        layout.addWidget(step_label)

        desc = QLabel(
            "Budou vytvořeny 2 interní doklady:",
            page,
        )
        desc.setProperty("class", "form-help")
        layout.addWidget(desc)

        self._summary_label = QLabel("", page)
        self._summary_label.setWordWrap(True)
        self._summary_label.setProperty("class", "form-help")
        layout.addWidget(self._summary_label)

        layout.addStretch(1)
        return page

    def _on_next(self) -> None:
        idx = self._stack.currentIndex()
        if idx == 0:
            castka = self._castka_input.value()
            if castka is None or not castka.is_positive:
                self._show_error("Zadejte kladnou částku ZK.")
                return
            self._hide_error()
            self._stack.setCurrentIndex(1)
            self._back_button.setEnabled(True)

        elif idx == 1:
            bank = self._bank_ucet_input.value()
            if not bank or not bank.strip():
                self._show_error("Vyplňte bankovní účet.")
                return
            self._hide_error()
            # Prepare summary
            castka = self._castka_input.value()
            datum = self._datum_input.value()
            self._summary_label.setText(
                f"1. Upsání ZK: MD 353 / Dal 411 — {castka.format_cz()}\n"
                f"2. Splacení ZK: MD {bank.strip()} / Dal 353 — {castka.format_cz()}\n"
                f"Datum: {datum.strftime('%d. %m. %Y') if datum else '—'}"
            )
            self._next_button.setText("Vytvořit doklady")
            self._stack.setCurrentIndex(2)

        elif idx == 2:
            self._execute_vklad()

    def _on_back(self) -> None:
        idx = self._stack.currentIndex()
        if idx > 0:
            self._stack.setCurrentIndex(idx - 1)
            self._next_button.setText("Další")
            self._hide_error()
        if self._stack.currentIndex() == 0:
            self._back_button.setEnabled(False)

    def _execute_vklad(self) -> None:
        castka = self._castka_input.value()
        datum = self._datum_input.value()
        bank = self._bank_ucet_input.value()
        if castka is None or datum is None or not bank:
            return

        rok = self._vm.rok
        try:
            from services.commands.vklad_zk import VkladZKCommand
            # Access uow_factory through the vm's command
            cmd = self._vm._vklad_cmd
            ids = cmd.execute(
                castka_zk=castka,
                datum=datum,
                bankovni_ucet=bank.strip(),
                rok=rok,
            )
            self._result_ids = ids
            self.accept()
        except Exception as exc:  # noqa: BLE001
            self._show_error(str(exc) or exc.__class__.__name__)

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.setVisible(True)

    def _hide_error(self) -> None:
        self._error_label.setVisible(False)

    # ─── Test-only accessors ─────────────────────────────────────

    @property
    def _castka_widget(self) -> LabeledMoneyEdit:
        return self._castka_input

    @property
    def _datum_widget(self) -> LabeledDateEdit:
        return self._datum_input

    @property
    def _bank_ucet_widget(self) -> LabeledLineEdit:
        return self._bank_ucet_input

    @property
    def _next_widget(self) -> QPushButton:
        return self._next_button

    @property
    def _back_widget(self) -> QPushButton:
        return self._back_button

    @property
    def _stack_widget(self) -> QStackedWidget:
        return self._stack

    @property
    def result_ids(self) -> list[int]:
        return self._result_ids
