"""Testy pro DokladDetailDialog (VM-based).

Dialog byl přepsán z read-only labelů na plně interaktivní s edit módem
a akcemi. Testy ověřují základní smoke + edit mode + akce přes mock
``DokladActionsCommand``.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import cast

from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.money import Money
from services.queries.doklady_list import DokladyListItem
from ui.dialogs.doklad_detail_dialog import DokladDetailDialog
from ui.viewmodels.doklad_detail_vm import DokladDetailViewModel


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


class _FakeActions:
    """Minimální stub ``DokladActionsCommand`` — všechny metody vracejí
    „nějaký" refreshnutý DTO (mutovaný ve smyslu odpovídajícím akci)."""

    def __init__(self, item: DokladyListItem) -> None:
        self._item = item
        self.smazat_called: int = 0
        self.storno_called: int = 0
        self.flag_on_called: int = 0
        self.flag_off_called: int = 0
        self.upravit_called: int = 0
        self.raise_on_smazat: Exception | None = None

    def stornovat(self, doklad_id: int) -> DokladyListItem:
        self.storno_called += 1
        self._item = replace(self._item, stav=StavDokladu.STORNOVANY)
        return self._item

    def smazat(self, doklad_id: int) -> None:
        self.smazat_called += 1
        if self.raise_on_smazat is not None:
            raise self.raise_on_smazat

    def oznac_k_doreseni(
        self, doklad_id: int, poznamka: str | None = None,
    ) -> DokladyListItem:
        self.flag_on_called += 1
        self._item = replace(
            self._item, k_doreseni=True, poznamka_doreseni=poznamka,
        )
        return self._item

    def dores(self, doklad_id: int) -> DokladyListItem:
        self.flag_off_called += 1
        self._item = replace(
            self._item, k_doreseni=False, poznamka_doreseni=None,
        )
        return self._item

    def upravit_popis_a_splatnost(
        self,
        doklad_id: int,
        popis: str | None,
        splatnost: date | None,
    ) -> DokladyListItem:
        self.upravit_called += 1
        self._item = replace(
            self._item, popis=popis, datum_splatnosti=splatnost,
        )
        return self._item


def _vm(item: DokladyListItem, actions: _FakeActions | None = None) -> DokladDetailViewModel:
    return DokladDetailViewModel(
        doklad=item,
        actions_command=cast(
            object, actions if actions is not None else _FakeActions(item),
        ),  # type: ignore[arg-type]
    )


class TestDetailDialog:

    def test_titulek_obsahuje_cislo(self, qtbot):
        d = DokladDetailDialog(_vm(_item()))
        qtbot.addWidget(d)
        assert "FV-TEST" in d.windowTitle()

    def test_typ_badge_je_fv(self, qtbot):
        d = DokladDetailDialog(_vm(_item()))
        qtbot.addWidget(d)
        assert d._typ_badge_widget.text() == "FV"

    def test_stav_badge_ma_text(self, qtbot):
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.ZAUCTOVANY)))
        qtbot.addWidget(d)
        assert "Zaúčtovaný" in d._stav_badge_widget.text()

    def test_doreseni_box_skryty_kdyz_nefragovano(self, qtbot):
        d = DokladDetailDialog(_vm(_item(k_doreseni=False)))
        qtbot.addWidget(d)
        assert d._doreseni_box_widget.isVisible() is False

    def test_doreseni_box_viditelny_kdyz_flagnuto(self, qtbot):
        d = DokladDetailDialog(_vm(_item(k_doreseni=True, poznamka="pz")))
        qtbot.addWidget(d)
        d.show()
        assert d._doreseni_box_widget.isVisibleTo(d) is True

    def test_close_button_zavre_dialog(self, qtbot):
        d = DokladDetailDialog(_vm(_item()))
        qtbot.addWidget(d)
        d.show()
        d._close_button_widget.click()
        assert d.isVisible() is False

    # ── Edit mode ────────────────────────────────────────────────

    def test_edit_button_prepne_do_edit_modu(self, qtbot):
        d = DokladDetailDialog(_vm(_item(popis="původní")))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        assert d._save_edit_widget.isVisibleTo(d) is True
        assert d._cancel_edit_widget.isVisibleTo(d) is True

    def test_cancel_edit_se_vrati_do_read_only(self, qtbot):
        d = DokladDetailDialog(_vm(_item()))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        d._cancel_edit_widget.click()
        assert d._close_button_widget.isVisibleTo(d) is True

    def test_save_edit_zavola_actions(self, qtbot):
        actions = _FakeActions(_item(popis="A"))
        d = DokladDetailDialog(_vm(_item(popis="A"), actions))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        d._save_edit_widget.click()
        assert actions.upravit_called == 1

    # ── Akce ──────────────────────────────────────────────────────

    def test_flag_button_prepne_flag(self, qtbot):
        actions = _FakeActions(_item())
        d = DokladDetailDialog(_vm(_item(), actions))
        qtbot.addWidget(d)
        d._flag_button_widget.click()
        assert actions.flag_on_called == 1

    def test_smazat_uspech_zavre_dialog(self, qtbot, monkeypatch):
        actions = _FakeActions(_item())
        d = DokladDetailDialog(_vm(_item(), actions))
        qtbot.addWidget(d)
        d.show()
        # Obejít confirm dialog — vrať rovnou True
        monkeypatch.setattr(
            "ui.dialogs.doklad_detail_dialog.ConfirmDialog.ask",
            classmethod(lambda cls, *a, **kw: True),
        )
        d._smazat_button_widget.click()
        assert actions.smazat_called == 1
        assert d.isVisible() is False

    def test_zauctovat_button_emitne_signal(self, qtbot):
        d = DokladDetailDialog(_vm(_item()))
        qtbot.addWidget(d)
        received: list[object] = []
        d.zauctovat_requested.connect(lambda item: received.append(item))
        d._zauctovat_button_widget.click()
        assert len(received) == 1

    # ── Storno (Fáze 6.5 — aktivní) ───────────────────────────────

    def test_storno_button_enabled_pro_zauctovany(self, qtbot):
        """ZAUCTOVANY doklad má storno aktivní — vytvoří protizápis."""
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.ZAUCTOVANY)))
        qtbot.addWidget(d)
        assert d._storno_button_widget.isEnabled() is True

    def test_storno_button_disabled_pro_novy(self, qtbot):
        """NOVY doklad — storno zakázané, uživatelka má použít Smazat."""
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.NOVY)))
        qtbot.addWidget(d)
        assert d._storno_button_widget.isEnabled() is False

    def test_storno_button_disabled_pro_stornovany(self, qtbot):
        """Už stornovaný doklad nelze stornovat znovu."""
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.STORNOVANY)))
        qtbot.addWidget(d)
        assert d._storno_button_widget.isEnabled() is False

    def test_storno_tooltip_vysvetluje_protizapis(self, qtbot):
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.ZAUCTOVANY)))
        qtbot.addWidget(d)
        tooltip = d._storno_button_widget.toolTip()
        assert "opravný účetní předpis" in tooltip or "protizápis" in tooltip

    def test_datum_storna_viditelne_pro_stornovany(self, qtbot):
        item = DokladyListItem(
            id=7, cislo="FV-S", typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2026, 4, 1),
            datum_splatnosti=None, partner_nazev=None,
            castka_celkem=Money.from_koruny("1000"),
            stav=StavDokladu.STORNOVANY,
            k_doreseni=False, poznamka_doreseni=None, popis=None,
            datum_storna=date(2026, 4, 20),
        )
        d = DokladDetailDialog(_vm(item))
        qtbot.addWidget(d)
        d.show()
        assert d._storno_value.isVisibleTo(d) is True
        assert "20" in d._storno_value.text()
        assert "2026" in d._storno_value.text()

    def test_datum_storna_skryte_pro_ne_stornovany(self, qtbot):
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.ZAUCTOVANY)))
        qtbot.addWidget(d)
        d.show()
        assert d._storno_value.isVisible() is False
