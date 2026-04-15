"""Testy pro DokladFormDialog."""

from __future__ import annotations

from datetime import date
from typing import cast

from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from services.commands.create_doklad import CreateDokladInput
from services.queries.doklady_list import DokladyListItem
from ui.dialogs.doklad_form_dialog import DokladFormDialog
from ui.viewmodels.doklad_form_vm import DokladFormViewModel


class _FakeNextNumber:
    def __init__(self, value: str = "FV-2026-001") -> None:
        self.value = value
        self.calls: list[tuple[TypDokladu, int]] = []

    def execute(self, typ: TypDokladu, rok: int) -> str:
        self.calls.append((typ, rok))
        return self.value


class _FakeCreate:
    def __init__(self, item: DokladyListItem | None = None) -> None:
        self._item = item
        self.calls: list[CreateDokladInput] = []
        self.raise_exc: Exception | None = None

    def execute(self, data: CreateDokladInput) -> DokladyListItem:
        self.calls.append(data)
        if self.raise_exc is not None:
            raise self.raise_exc
        assert self._item is not None
        return self._item


def _item() -> DokladyListItem:
    return DokladyListItem(
        id=1,
        cislo="FV-2026-001",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 4, 1),
        datum_splatnosti=None,
        partner_nazev=None,
        castka_celkem=Money.from_koruny("12100"),
        stav=StavDokladu.NOVY,
        k_doreseni=False,
        poznamka_doreseni=None,
        popis=None,
    )


def _vm(
    next_number: _FakeNextNumber | None = None,
    create: _FakeCreate | None = None,
) -> DokladFormViewModel:
    return DokladFormViewModel(
        next_number_query=cast(object, next_number or _FakeNextNumber()),
        create_command=cast(object, create or _FakeCreate(_item())),
    )  # type: ignore[arg-type]


class TestDokladFormDialog:

    def test_initial_suggest_vyplni_cislo(self, qtbot):
        nn = _FakeNextNumber("FV-2026-099")
        d = DokladFormDialog(_vm(next_number=nn))
        qtbot.addWidget(d)
        assert d._cislo_widget.value() == "FV-2026-099"
        assert len(nn.calls) >= 1

    def test_submit_prazdne_cislo_ukaze_error(self, qtbot):
        d = DokladFormDialog(_vm())
        qtbot.addWidget(d)
        d._cislo_widget.set_value("")
        d._castka_widget.line_widget.setText("100")
        d._submit_widget.click()
        assert d._cislo_widget.error_widget.isHidden() is False

    def test_submit_nevalidni_castka_ukaze_error(self, qtbot):
        d = DokladFormDialog(_vm())
        qtbot.addWidget(d)
        d._castka_widget.line_widget.setText("abc")
        d._submit_widget.click()
        assert d._castka_widget.error_widget.isHidden() is False

    def test_uspesny_submit_accept(self, qtbot):
        create = _FakeCreate(_item())
        d = DokladFormDialog(_vm(create=create))
        qtbot.addWidget(d)
        d.show()
        d._cislo_widget.set_value("FV-2026-001")
        d._castka_widget.line_widget.setText("12100")
        d._submit_widget.click()
        assert len(create.calls) == 1
        assert d.created_item is not None
        assert d.isVisible() is False

    def test_command_fails_zobrazi_error(self, qtbot):
        create = _FakeCreate(_item())
        create.raise_exc = ValueError("duplicate")
        d = DokladFormDialog(_vm(create=create))
        qtbot.addWidget(d)
        d._cislo_widget.set_value("FV-2026-001")
        d._castka_widget.line_widget.setText("100")
        d._submit_widget.click()
        assert d._error_widget.isHidden() is False
        assert "duplicate" in d._error_widget.text()
        assert d.created_item is None

    def test_typ_change_pretahne_cislo(self, qtbot):
        nn = _FakeNextNumber()
        d = DokladFormDialog(_vm(next_number=nn))
        qtbot.addWidget(d)
        initial_calls = len(nn.calls)
        d._typ_combo_widget.set_value(TypDokladu.FAKTURA_PRIJATA)
        assert len(nn.calls) > initial_calls

    def test_cancel_reject(self, qtbot):
        d = DokladFormDialog(_vm())
        qtbot.addWidget(d)
        d.show()
        d._cancel_button.click()
        assert d.isVisible() is False
        assert d.created_item is None
