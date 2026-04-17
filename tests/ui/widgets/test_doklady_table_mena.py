"""Testy zobrazení měny v DokladyTable."""

from datetime import date
from decimal import Decimal

import pytest

from domain.doklady.typy import Mena, StavDokladu, TypDokladu
from domain.shared.money import Money
from services.queries.doklady_list import DokladyListItem
from ui.widgets.doklady_table import DokladyTable


def _make_item(mena=Mena.CZK, castka_mena=None, kurz=None):
    return DokladyListItem(
        id=1, cislo="FP-001", typ=TypDokladu.FAKTURA_PRIJATA,
        datum_vystaveni=date(2026, 4, 10), datum_splatnosti=None,
        partner_id=None, partner_nazev=None,
        castka_celkem=Money(25100), stav=StavDokladu.NOVY,
        k_doreseni=False, poznamka_doreseni=None, popis=None,
        mena=mena, castka_mena=castka_mena, kurz=kurz,
    )


class TestDokladyTableMena:

    def test_czk_format(self, qtbot):
        table = DokladyTable()
        qtbot.addWidget(table)
        item = _make_item()
        table.set_items([item])
        # Column 5 = Částka
        idx = table._model_adapter.index(0, 5)
        text = table._model_adapter.data(idx)
        assert "Kč" in text
        assert "EUR" not in text

    def test_eur_format_shows_both(self, qtbot):
        table = DokladyTable()
        qtbot.addWidget(table)
        item = _make_item(
            mena=Mena.EUR,
            castka_mena=Money(1000),
            kurz=Decimal("25.10"),
        )
        table.set_items([item])
        idx = table._model_adapter.index(0, 5)
        text = table._model_adapter.data(idx)
        assert "EUR" in text
        assert "Kč" in text
