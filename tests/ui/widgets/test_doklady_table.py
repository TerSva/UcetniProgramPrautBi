"""Testy pro DokladyTable + DokladyTableModel + KDoreseniIconDelegate."""

from datetime import date

from PyQt6.QtCore import Qt

from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from services.queries.doklady_list import DokladyListItem
from ui.widgets.doklady_table import (
    DokladyTable,
    DokladyTableModel,
    KDoreseniIconDelegate,
)


def _item(
    id: int = 1,
    cislo: str = "FV-1",
    typ: TypDokladu = TypDokladu.FAKTURA_VYDANA,
    datum: date = date(2026, 2, 1),
    splatnost: date | None = None,
    partner: str | None = None,
    castka: str = "1234",
    stav: StavDokladu = StavDokladu.NOVY,
    k_doreseni: bool = False,
    poznamka: str | None = None,
) -> DokladyListItem:
    return DokladyListItem(
        id=id,
        cislo=cislo,
        typ=typ,
        datum_vystaveni=datum,
        datum_splatnosti=splatnost,
        partner_id=None,
        partner_nazev=partner,
        castka_celkem=Money.from_koruny(castka),
        stav=stav,
        k_doreseni=k_doreseni,
        poznamka_doreseni=poznamka,
        popis=None,
    )


# ──────────────────────────────────────────────────────────────────────
# DokladyTableModel
# ──────────────────────────────────────────────────────────────────────


class TestModelZaklad:

    def test_pocet_sloupcu_je_9(self, qtbot):
        m = DokladyTableModel()
        assert m.columnCount() == 9

    def test_nazvy_sloupcu_obsahuji_partner(self, qtbot):
        m = DokladyTableModel()
        headers = [
            m.headerData(i, Qt.Orientation.Horizontal,
                         Qt.ItemDataRole.DisplayRole)
            for i in range(m.columnCount())
        ]
        assert "Partner" in headers
        assert "Číslo" in headers
        assert "Částka" in headers
        assert "Uhrazeno" in headers
        assert "Stav" in headers

    def test_set_items_nastavi_pocet_radku(self, qtbot):
        m = DokladyTableModel()
        m.set_items([_item(id=1), _item(id=2), _item(id=3)])
        assert m.rowCount() == 3

    def test_display_cislo(self, qtbot):
        m = DokladyTableModel()
        m.set_items([_item(cislo="FV-2026-001")])
        text = m.data(m.index(0, 0), Qt.ItemDataRole.DisplayRole)
        assert text == "FV-2026-001"

    def test_display_typ_je_zkratka(self, qtbot):
        m = DokladyTableModel()
        m.set_items([_item(typ=TypDokladu.FAKTURA_PRIJATA)])
        text = m.data(m.index(0, 1), Qt.ItemDataRole.DisplayRole)
        assert text == "FP"

    def test_splatnost_none_zobrazi_pomlcku(self, qtbot):
        m = DokladyTableModel()
        m.set_items([_item(splatnost=None)])
        text = m.data(m.index(0, 3), Qt.ItemDataRole.DisplayRole)
        assert text == "—"

    def test_partner_none_zobrazi_pomlcku(self, qtbot):
        m = DokladyTableModel()
        m.set_items([_item(partner=None)])
        text = m.data(m.index(0, 4), Qt.ItemDataRole.DisplayRole)
        assert text == "—"

    def test_castka_je_format_cz(self, qtbot):
        m = DokladyTableModel()
        m.set_items([_item(castka="12345")])
        text = m.data(m.index(0, 5), Qt.ItemDataRole.DisplayRole)
        assert "12" in text and "345,00" in text and "Kč" in text

    def test_item_at(self, qtbot):
        m = DokladyTableModel()
        it = _item(id=42, cislo="FV-42")
        m.set_items([it])
        assert m.item_at(0) is it


# ──────────────────────────────────────────────────────────────────────
# K dořešení sloupec — bool + tooltip
# ──────────────────────────────────────────────────────────────────────


class TestKDoreseniSloupec:

    def test_user_role_vraci_bool(self, qtbot):
        m = DokladyTableModel()
        m.set_items([
            _item(id=1, k_doreseni=False),
            _item(id=2, k_doreseni=True, poznamka="x"),
        ])
        assert m.data(m.index(0, 8), Qt.ItemDataRole.UserRole) is False
        assert m.data(m.index(1, 8), Qt.ItemDataRole.UserRole) is True

    def test_display_je_prazdny(self, qtbot):
        m = DokladyTableModel()
        m.set_items([_item(k_doreseni=True, poznamka="p")])
        # Delegate kreslí ikonu, DisplayRole musí být prázdný
        assert m.data(m.index(0, 8), Qt.ItemDataRole.DisplayRole) == ""

    def test_tooltip_obsahuje_poznamku(self, qtbot):
        m = DokladyTableModel()
        m.set_items([_item(k_doreseni=True, poznamka="vyřešit fakturu")])
        tooltip = m.data(m.index(0, 8), Qt.ItemDataRole.ToolTipRole)
        assert tooltip == "vyřešit fakturu"

    def test_tooltip_none_bez_flagnutí(self, qtbot):
        m = DokladyTableModel()
        m.set_items([_item(k_doreseni=False)])
        assert m.data(m.index(0, 8), Qt.ItemDataRole.ToolTipRole) is None


# ──────────────────────────────────────────────────────────────────────
# DokladyTable (view)
# ──────────────────────────────────────────────────────────────────────


class TestDokladyTable:

    def test_delegate_je_na_sloupci_8(self, qtbot):
        table = DokladyTable()
        qtbot.addWidget(table)
        delegate = table.itemDelegateForColumn(8)
        assert isinstance(delegate, KDoreseniIconDelegate)

    def test_set_items_propise_do_modelu(self, qtbot):
        table = DokladyTable()
        qtbot.addWidget(table)
        table.set_items([_item(id=1), _item(id=2)])
        assert table._model_adapter.rowCount() == 2

    def test_row_activated_emituje_id_pri_double_click(self, qtbot):
        table = DokladyTable()
        qtbot.addWidget(table)
        table.set_items([_item(id=99, cislo="X-99")])

        received: list[int] = []
        table.row_activated.connect(lambda i: received.append(i))

        # Simulace: emituj doubleClicked na validní index
        model = table.model()
        table.doubleClicked.emit(model.index(0, 0))
        assert received == [99]


class TestSortableTable:
    """sortable=True: klikatelné Číslo / Datum / Částka, ostatní noop."""

    def test_default_sortable_je_false(self, qtbot):
        table = DokladyTable()
        qtbot.addWidget(table)
        # setSortingEnabled odráží sortable
        assert table.isSortingEnabled() is False

    def test_sortable_true_zapne_sorting(self, qtbot):
        table = DokladyTable(sortable=True)
        qtbot.addWidget(table)
        assert table.isSortingEnabled() is True

    def test_sortable_radi_castku_descending(self, qtbot):
        from PyQt6.QtCore import Qt
        table = DokladyTable(sortable=True)
        qtbot.addWidget(table)
        table.set_items([
            _item(id=1, cislo="FV-2025-001", datum=date(2025, 1, 1), castka="100"),
            _item(id=2, cislo="FV-2025-002", datum=date(2025, 2, 1), castka="500"),
            _item(id=3, cislo="FV-2025-003", datum=date(2025, 3, 1), castka="200"),
        ])
        # Sort podle Částky (col 5) DESC
        table.sortByColumn(5, Qt.SortOrder.DescendingOrder)
        # Pořadí v UI: id=2 (500), id=3 (200), id=1 (100)
        # Klikni na první řádek → emit id=2
        received: list[int] = []
        table.row_activated.connect(lambda i: received.append(i))
        model = table.model()
        table.doubleClicked.emit(model.index(0, 0))
        assert received == [2]

    def test_sortable_radi_datum_ascending(self, qtbot):
        from PyQt6.QtCore import Qt
        table = DokladyTable(sortable=True)
        qtbot.addWidget(table)
        table.set_items([
            _item(id=1, datum=date(2025, 3, 1)),
            _item(id=2, datum=date(2025, 1, 1)),
            _item(id=3, datum=date(2025, 2, 1)),
        ])
        # Sort podle Data (col 2) ASC — nejstarší nahoře
        table.sortByColumn(2, Qt.SortOrder.AscendingOrder)
        received: list[int] = []
        table.row_activated.connect(lambda i: received.append(i))
        model = table.model()
        table.doubleClicked.emit(model.index(0, 0))
        # První řádek = id=2 (1.1.2025)
        assert received == [2]

    def test_sortable_default_je_datum_desc(self, qtbot):
        from PyQt6.QtCore import Qt
        table = DokladyTable(sortable=True)
        qtbot.addWidget(table)
        table.set_items([
            _item(id=1, datum=date(2025, 1, 1)),
            _item(id=2, datum=date(2025, 5, 1)),
            _item(id=3, datum=date(2025, 3, 1)),
        ])
        # Default sort proběhne v __init__ (Datum DESC)
        # První řádek by měl být nejnovější (id=2, 1.5.)
        received: list[int] = []
        table.row_activated.connect(lambda i: received.append(i))
        model = table.model()
        table.doubleClicked.emit(model.index(0, 0))
        assert received == [2]

    def test_sortable_radi_stav_asc_novy_nahore(self, qtbot):
        """Klik na sloupec Stav ASC → Nový doklady jsou nahoře."""
        from PyQt6.QtCore import Qt
        table = DokladyTable(sortable=True)
        qtbot.addWidget(table)
        table.set_items([
            _item(id=1, stav=StavDokladu.UHRAZENY),
            _item(id=2, stav=StavDokladu.NOVY),
            _item(id=3, stav=StavDokladu.ZAUCTOVANY),
            _item(id=4, stav=StavDokladu.NOVY),
            _item(id=5, stav=StavDokladu.STORNOVANY),
        ])
        # Sort podle Stavu (col 7) ASC — Nový nahoře, Stornovaný dole
        table.sortByColumn(7, Qt.SortOrder.AscendingOrder)
        # První dva řádky musí být oba NOVY (id=2, id=4)
        received: list[int] = []
        table.row_activated.connect(lambda i: received.append(i))
        model = table.model()
        table.doubleClicked.emit(model.index(0, 0))
        table.doubleClicked.emit(model.index(1, 0))
        # Pořadí mezi stejnými stavy zachová insertion order (stable sort)
        assert set(received[:2]) == {2, 4}

    def test_sortable_radi_stav_desc_stornovane_nahore(self, qtbot):
        """Klik na sloupec Stav DESC → Stornované doklady jsou nahoře."""
        from PyQt6.QtCore import Qt
        table = DokladyTable(sortable=True)
        qtbot.addWidget(table)
        table.set_items([
            _item(id=1, stav=StavDokladu.NOVY),
            _item(id=2, stav=StavDokladu.STORNOVANY),
            _item(id=3, stav=StavDokladu.UHRAZENY),
        ])
        table.sortByColumn(7, Qt.SortOrder.DescendingOrder)
        received: list[int] = []
        table.row_activated.connect(lambda i: received.append(i))
        model = table.model()
        table.doubleClicked.emit(model.index(0, 0))
        # První řádek = id=2 (STORNOVANY)
        assert received == [2]

    def test_sortable_klik_na_neactive_sloupec_je_noop(self, qtbot):
        """Klik na sloupec Typ (col 1) nesortuje — pořadí zůstane jak default."""
        from PyQt6.QtCore import Qt
        table = DokladyTable(sortable=True)
        qtbot.addWidget(table)
        table.set_items([
            _item(id=1, datum=date(2025, 1, 1)),
            _item(id=2, datum=date(2025, 5, 1)),
        ])
        # Default DESC: id=2 první. Klik na Typ (col 1) by měl být noop.
        table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        received: list[int] = []
        table.row_activated.connect(lambda i: received.append(i))
        model = table.model()
        table.doubleClicked.emit(model.index(0, 0))
        # Pořadí stejné jako default sort (id=2 nahoře)
        assert received == [2]
