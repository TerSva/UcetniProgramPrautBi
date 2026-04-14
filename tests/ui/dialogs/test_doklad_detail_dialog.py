"""Testy pro DokladDetailDialog."""

from datetime import date

from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from services.queries.doklady_list import DokladyListItem
from ui.dialogs.doklad_detail_dialog import DokladDetailDialog


def _item(
    k_doreseni: bool = False,
    poznamka: str | None = None,
    popis: str | None = None,
    stav: StavDokladu = StavDokladu.NOVY,
    splatnost: date | None = None,
) -> DokladyListItem:
    return DokladyListItem(
        id=7,
        cislo="FV-TEST",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 2, 15),
        datum_splatnosti=splatnost,
        partner_nazev=None,
        castka_celkem=Money.from_koruny("25000"),
        stav=stav,
        k_doreseni=k_doreseni,
        poznamka_doreseni=poznamka,
        popis=popis,
    )


class TestDetailDialog:

    def test_titulek_obsahuje_cislo(self, qtbot):
        d = DokladDetailDialog(_item())
        qtbot.addWidget(d)
        assert "FV-TEST" in d.windowTitle()

    def test_typ_badge_je_fv(self, qtbot):
        d = DokladDetailDialog(_item())
        qtbot.addWidget(d)
        assert d._typ_badge_widget.text() == "FV"

    def test_stav_badge_ma_text(self, qtbot):
        d = DokladDetailDialog(_item(stav=StavDokladu.ZAUCTOVANY))
        qtbot.addWidget(d)
        assert "Zaúčtovaný" in d._stav_badge_widget.text()

    def test_doreseni_box_skryty_kdyz_nefragovano(self, qtbot):
        d = DokladDetailDialog(_item(k_doreseni=False))
        qtbot.addWidget(d)
        assert d._doreseni_box_widget.isVisible() is False

    def test_doreseni_box_viditelny_kdyz_flagnuto(self, qtbot):
        d = DokladDetailDialog(_item(k_doreseni=True, poznamka="pz"))
        qtbot.addWidget(d)
        d.show()
        assert d._doreseni_box_widget.isVisibleTo(d) is True

    def test_close_button_zavre_dialog(self, qtbot):
        d = DokladDetailDialog(_item())
        qtbot.addWidget(d)
        d.show()
        d._close_button_widget.click()
        assert d.isVisible() is False
