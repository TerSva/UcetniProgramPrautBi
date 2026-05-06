"""Testy pro ZauctovaniDialog."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import cast

from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from services.commands.zauctovat_doklad import ZauctovatDokladInput
from services.queries.doklady_list import DokladyListItem
from services.queries.uctova_osnova import UcetItem
from ui.dialogs.zauctovani_dialog import ZauctovaniDialog
from ui.viewmodels.zauctovani_vm import ZauctovaniViewModel


def _item() -> DokladyListItem:
    return DokladyListItem(
        id=42,
        cislo="FV-2026-001",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 3, 1),
        datum_splatnosti=None,
        partner_id=None, partner_nazev=None,
        castka_celkem=Money.from_koruny("12100"),
        stav=StavDokladu.NOVY,
        k_doreseni=False,
        poznamka_doreseni=None,
        popis=None,
    )


class _FakeOsnova:
    def __init__(self) -> None:
        self._ucty = [
            UcetItem(cislo="311", nazev="Odběratelé", typ="A"),
            UcetItem(cislo="601", nazev="Tržby", typ="V"),
            UcetItem(cislo="343", nazev="DPH", typ="P"),
        ]

    def execute(self, jen_aktivni: bool = True) -> list[UcetItem]:
        return self._ucty


class _FakeZauctovat:
    def __init__(self, item: DokladyListItem) -> None:
        self._item = item
        self.calls: list[ZauctovatDokladInput] = []
        self.raise_exc: Exception | None = None

    def execute(self, data: ZauctovatDokladInput) -> DokladyListItem:
        self.calls.append(data)
        if self.raise_exc is not None:
            raise self.raise_exc
        return replace(self._item, stav=StavDokladu.ZAUCTOVANY)


def _vm(
    item: DokladyListItem | None = None,
    zauctovat: _FakeZauctovat | None = None,
) -> ZauctovaniViewModel:
    i = item or _item()
    return ZauctovaniViewModel(
        doklad=i,
        uctova_osnova_query=cast(object, _FakeOsnova()),
        zauctovat_command=cast(object, zauctovat or _FakeZauctovat(i)),
    )  # type: ignore[arg-type]


class TestZauctovaniDialog:

    def test_header_obsahuje_cislo_dokladu(self, qtbot):
        d = ZauctovaniDialog(_vm())
        qtbot.addWidget(d)
        assert "FV-2026-001" in d.windowTitle()

    def test_pri_otevreni_je_jeden_radek_prefilled(self, qtbot):
        d = ZauctovaniDialog(_vm())
        qtbot.addWidget(d)
        assert len(d._rows_list) == 1

    def test_submit_disabled_bez_vybranych_uctu(self, qtbot):
        vm = _vm()
        d = ZauctovaniDialog(vm)
        qtbot.addWidget(d)
        # Smaž default prefill účty — pak je doklad nevalidní
        vm.update_row(0, md_ucet="", dal_ucet="")
        d._sync_ui()
        assert d._submit_widget.isEnabled() is False

    def test_add_row_pridat_radek(self, qtbot):
        d = ZauctovaniDialog(_vm())
        qtbot.addWidget(d)
        before = len(d._rows_list)
        d._add_row_widget.click()
        assert len(d._rows_list) == before + 1

    def test_podvojne_po_nastaveni_uctu(self, qtbot):
        d = ZauctovaniDialog(_vm())
        qtbot.addWidget(d)
        row = d._rows_list[0]
        row.md_combo.set_value("311")
        row.dal_combo.set_value("601")
        # Trigger castka editingFinished přes slot manuálně
        d._on_row_castka_changed(0)
        d._sync_ui()
        assert d._submit_widget.isEnabled() is True

    def test_rozdil_zobrazen_pri_neuplnem_predpisu(self, qtbot):
        d = ZauctovaniDialog(_vm())
        qtbot.addWidget(d)
        row = d._rows_list[0]
        # Upravíme částku na polovinu — bude nenulový rozdíl.
        row.castka_input.set_value(Money.from_koruny("5000"))
        d._on_row_castka_changed(0)
        d._sync_ui()
        assert "7" in d._rozdil_widget.text() or "7 100" in d._rozdil_widget.text()

    def test_uspesny_submit_accept(self, qtbot):
        z = _FakeZauctovat(_item())
        d = ZauctovaniDialog(_vm(zauctovat=z))
        qtbot.addWidget(d)
        d.show()
        row = d._rows_list[0]
        row.md_combo.set_value("311")
        row.dal_combo.set_value("601")
        d._on_row_castka_changed(0)
        d._submit_widget.click()
        assert len(z.calls) == 1
        assert d.posted_item is not None
        assert d.isVisible() is False

    def test_command_fails_zobrazi_error(self, qtbot):
        z = _FakeZauctovat(_item())
        z.raise_exc = ValueError("nebilance")
        d = ZauctovaniDialog(_vm(zauctovat=z))
        qtbot.addWidget(d)
        row = d._rows_list[0]
        row.md_combo.set_value("311")
        row.dal_combo.set_value("601")
        d._on_row_castka_changed(0)
        d._submit_widget.click()
        # Submit se dostane jen k error labelu
        assert d.posted_item is None

    def test_remove_row(self, qtbot):
        d = ZauctovaniDialog(_vm())
        qtbot.addWidget(d)
        d._add_row_widget.click()
        count = len(d._rows_list)
        d._rows_list[0].remove_button.click()
        assert len(d._rows_list) == count - 1
