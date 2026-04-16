"""Testy PartnerSelector widget."""

from decimal import Decimal

import pytest

from domain.partneri.partner import KategoriePartnera
from services.queries.partneri_list import PartneriListItem
from ui.widgets.partner_selector import PartnerSelector


def _make_item(id: int, nazev: str, ico: str | None = None) -> PartneriListItem:
    return PartneriListItem(
        id=id, nazev=nazev, kategorie=KategoriePartnera.DODAVATEL,
        ico=ico, dic=None, adresa=None, je_aktivni=True,
        podil_procent=None,
    )


class TestPartnerSelector:

    def test_initial_state(self, qtbot):
        w = PartnerSelector()
        qtbot.addWidget(w)
        assert w.selected_id() is None

    def test_set_items(self, qtbot):
        w = PartnerSelector()
        qtbot.addWidget(w)
        items = [_make_item(1, "Firma A"), _make_item(2, "Firma B", "12345678")]
        w.set_items(items)
        # First item is "— bez partnera —" + 2 items
        assert w._combo_widget.count() == 3

    def test_select_partner(self, qtbot):
        w = PartnerSelector()
        qtbot.addWidget(w)
        items = [_make_item(1, "Firma A")]
        w.set_items(items)

        w.set_selected_id(1)
        assert w.selected_id() == 1

        w.set_selected_id(None)
        assert w.selected_id() is None

    def test_signal_emitted(self, qtbot):
        w = PartnerSelector()
        qtbot.addWidget(w)
        items = [_make_item(1, "Firma A")]
        w.set_items(items)

        with qtbot.waitSignal(w.partner_selected, timeout=1000):
            w._combo_widget.setCurrentIndex(1)
