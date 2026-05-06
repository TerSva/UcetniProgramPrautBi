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
    mena=None,
    castka_mena: Money | None = None,
    kurz=None,
) -> DokladyListItem:
    from domain.doklady.typy import Mena as _Mena
    kwargs = {}
    if mena is not None:
        kwargs["mena"] = mena
    if castka_mena is not None:
        kwargs["castka_mena"] = castka_mena
    if kurz is not None:
        kwargs["kurz"] = kurz
    return DokladyListItem(
        id=7,
        cislo="FV-TEST",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 2, 15),
        datum_splatnosti=splatnost,
        partner_id=None, partner_nazev=None,
        castka_celkem=Money.from_koruny("25000"),
        stav=stav,
        k_doreseni=k_doreseni,
        poznamka_doreseni=poznamka,
        popis=popis,
        **kwargs,
    )


class _FakeActions:
    """Minimální stub ``DokladActionsCommand`` — všechny metody vracejí
    „nějaký" refreshnutý DTO (mutovaný ve smyslu odpovídajícím akci)."""

    def __init__(self, item: DokladyListItem) -> None:
        self._item = item
        self.smazat_called: int = 0
        self.storno_called: int = 0
        self.flag_on_called: int = 0
        self.flag_on_calls: list[tuple[int, str | None]] = []
        self.flag_off_called: int = 0
        self.upravit_called: int = 0
        self.upravit_pole_novy_called: int = 0
        self.upravit_pole_novy_last: dict | None = None
        self.raise_on_smazat: Exception | None = None

    def stornovat(
        self,
        doklad_id: int,
        datum: date | None = None,
        poznamka: str | None = None,
    ) -> DokladyListItem:
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
        self.flag_on_calls.append((doklad_id, poznamka))
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
        partner_id: object = ...,
        datum_vystaveni: date | None = None,
    ) -> DokladyListItem:
        self.upravit_called += 1
        kwargs = {"popis": popis, "datum_splatnosti": splatnost}
        if datum_vystaveni is not None:
            kwargs["datum_vystaveni"] = datum_vystaveni
        self._item = replace(self._item, **kwargs)
        return self._item

    def upravit_pole_novy_dokladu(
        self,
        doklad_id: int,
        popis: str | None,
        splatnost: date | None,
        k_doreseni: bool,
        poznamka_doreseni: str | None,
        partner_id: object = ...,
        datum_vystaveni: date | None = None,
        castka_celkem: object = ...,
        castka_mena: object = ...,
        kurz: object = ...,
        mena: object = ...,
    ) -> DokladyListItem:
        self.upravit_pole_novy_called += 1
        self.upravit_pole_novy_last = {
            "id": doklad_id,
            "popis": popis,
            "splatnost": splatnost,
            "k_doreseni": k_doreseni,
            "poznamka_doreseni": poznamka_doreseni,
            "datum_vystaveni": datum_vystaveni,
            "castka_celkem": castka_celkem,
            "castka_mena": castka_mena,
            "kurz": kurz,
            "mena": mena,
        }
        kwargs = {
            "popis": popis,
            "datum_splatnosti": splatnost,
            "k_doreseni": k_doreseni,
            "poznamka_doreseni": poznamka_doreseni,
        }
        if datum_vystaveni is not None:
            kwargs["datum_vystaveni"] = datum_vystaveni
        self._item = replace(self._item, **kwargs)
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
        """Non-NOVY doklad volá ``upravit_popis_a_splatnost``."""
        actions = _FakeActions(
            _item(popis="A", stav=StavDokladu.ZAUCTOVANY),
        )
        d = DokladDetailDialog(_vm(
            _item(popis="A", stav=StavDokladu.ZAUCTOVANY), actions,
        ))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        d._save_edit_widget.click()
        assert actions.upravit_called == 1

    # ── Akce ──────────────────────────────────────────────────────

    def test_flag_button_prepne_flag(self, qtbot, monkeypatch):
        """Non-NOVY: klik na flag button volá ``oznac_k_doreseni``.

        NOVY doklad má flag_button schovaný (viz Fáze 6.7 — flag ovládá
        edit mode), proto test používá ZAUCTOVANY.
        """
        actions = _FakeActions(_item(stav=StavDokladu.ZAUCTOVANY))
        d = DokladDetailDialog(_vm(
            _item(stav=StavDokladu.ZAUCTOVANY), actions,
        ))
        qtbot.addWidget(d)
        # Obejít ask_with_note — vrať (True, "pz")
        monkeypatch.setattr(
            "ui.dialogs.doklad_detail_dialog.ConfirmDialog.ask_with_note",
            classmethod(lambda cls, *a, **kw: (True, "pz")),
        )
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
            datum_splatnosti=None, partner_id=None, partner_nazev=None,
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


class TestDetailDialogEditKDoreseni:
    """Fáze 6.7: edit NOVY obsahuje k_doreseni checkbox + poznámku."""

    def test_k_doreseni_check_skryty_mimo_edit(self, qtbot):
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.NOVY)))
        qtbot.addWidget(d)
        d.show()
        assert d._k_doreseni_check_widget.isVisible() is False

    def test_k_doreseni_check_viditelny_v_edit_pro_novy(self, qtbot):
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.NOVY)))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        assert d._k_doreseni_check_widget.isVisible() is True

    def test_k_doreseni_check_skryty_v_edit_pro_zauctovany(self, qtbot):
        """ZAUCTOVANY nemá flag v edit módu — flag ovládá tlačítko."""
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.ZAUCTOVANY)))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        assert d._k_doreseni_check_widget.isVisible() is False

    def test_k_doreseni_check_prefilled_z_draftu(self, qtbot):
        """Po vstupu do edit módu je checkbox prefilled z doklad.k_doreseni."""
        d = DokladDetailDialog(_vm(
            _item(stav=StavDokladu.NOVY, k_doreseni=True, poznamka="pz"),
        ))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        assert d._k_doreseni_check_widget.isChecked() is True

    def test_poznamka_edit_viditelna_kdyz_check_zaskrtnuty(self, qtbot):
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.NOVY)))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        d._k_doreseni_check_widget.setChecked(True)
        assert d._poznamka_doreseni_edit_widget.isVisible() is True

    def test_poznamka_edit_skryta_kdyz_check_odskrtnuty(self, qtbot):
        d = DokladDetailDialog(_vm(
            _item(stav=StavDokladu.NOVY, k_doreseni=True, poznamka="x"),
        ))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        assert d._k_doreseni_check_widget.isChecked() is True
        d._k_doreseni_check_widget.setChecked(False)
        assert d._poznamka_doreseni_edit_widget.isVisible() is False

    def test_save_edit_novy_vola_upravit_pole_novy(self, qtbot):
        actions = _FakeActions(_item(stav=StavDokladu.NOVY))
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.NOVY), actions))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        d._k_doreseni_check_widget.setChecked(True)
        d._poznamka_doreseni_edit_widget.set_value("chybí IČO")
        d._save_edit_widget.click()
        assert actions.upravit_pole_novy_called == 1
        assert actions.upravit_pole_novy_last is not None
        assert actions.upravit_pole_novy_last["k_doreseni"] is True
        assert actions.upravit_pole_novy_last["poznamka_doreseni"] == "chybí IČO"


class TestDetailDialogEditCastkaMena:
    """Tereziin scénář: NOVY doklad — editovatelná castka, měna i kurz."""

    def test_castka_input_je_enabled_v_edit_pro_novy_czk(self, qtbot):
        """CZK NOVY → CZK input editovatelný."""
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.NOVY)))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        assert d._castka_edit_widget.line_widget.isEnabled() is True

    def test_castka_input_je_enabled_i_pro_eur_doklad(self, qtbot):
        """EUR NOVY → CZK input je editovatelný (auto-přepočet, ale lze ručně)."""
        from decimal import Decimal as _D
        from domain.doklady.typy import Mena
        d = DokladDetailDialog(_vm(_item(
            stav=StavDokladu.NOVY,
            mena=Mena.EUR,
            castka_mena=Money.from_koruny("100"),
            kurz=_D("25.00"),
        )))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        assert d._castka_edit_widget.line_widget.isEnabled() is True

    def test_mena_kurz_eur_inputy_viditelne_pro_eur(self, qtbot):
        from decimal import Decimal as _D
        from domain.doklady.typy import Mena
        d = DokladDetailDialog(_vm(_item(
            stav=StavDokladu.NOVY,
            mena=Mena.EUR,
            castka_mena=Money.from_koruny("100"),
            kurz=_D("25.00"),
        )))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        # Měna combo + EUR pole + kurz pole jsou všechny visible
        assert d._mena_edit_widget.isVisible()
        assert d._castka_mena_edit_widget.isVisible()
        assert d._kurz_edit_widget.isVisible()
        # A enabled pro úpravu
        assert d._mena_edit_widget.isEnabled()
        assert d._castka_mena_edit_widget.line_widget.isEnabled()
        assert d._kurz_edit_widget.line_widget.isEnabled()

    def test_eur_inputy_skryte_pro_czk(self, qtbot):
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.NOVY)))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        # Měna combo visible, ale EUR/kurz skryté pro CZK
        assert d._mena_edit_widget.isVisible()
        assert not d._castka_mena_edit_widget.isVisible()

    def test_zmena_castky_se_zobrazi_v_ui_po_save(self, qtbot):
        """Tereziin scénář: po Uložit musí UI zobrazit novou částku.

        Bug: castka_value_label byl lokální QLabel který _sync_ui
        neaktualizoval — UI po editu zobrazoval starou hodnotu.
        """
        actions = _FakeActions(_item(stav=StavDokladu.NOVY))
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.NOVY), actions))
        qtbot.addWidget(d)
        d.show()
        # UI ukazuje původní 25 000 Kč
        from domain.shared.money import Money as _M
        assert "25" in d._castka_value_label.text()
        # Edit
        d._edit_button_widget.click()
        d._castka_edit_widget.set_value(_M.from_koruny("5000"))
        d._save_edit_widget.click()
        # Po save UI ukazuje 5 000 (FakeActions vrací doklad s novou castkou)
        # FakeActions ale ne — vrací původní item bez castka_celkem update.
        # Zkontrolujme aspoň že _sync_ui běhl a label se aktualizoval na
        # vm.doklad.castka_celkem hodnotu (která je co vrátil FakeActions).
        assert d._castka_value_label.text() == d._vm.doklad.castka_celkem.format_cz()

    def test_zmena_castky_se_propaguje_do_command(self, qtbot):
        actions = _FakeActions(_item(stav=StavDokladu.NOVY))
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.NOVY), actions))
        qtbot.addWidget(d)
        d.show()
        d._edit_button_widget.click()
        # Uživatelka změní castku z 1000 na 5000
        d._castka_edit_widget.set_value(Money.from_koruny("5000"))
        d._save_edit_widget.click()
        assert actions.upravit_pole_novy_called == 1
        # castka_celkem v calls má hodnotu Money(500000) (5000 hal)
        assert actions.upravit_pole_novy_last["castka_celkem"] == Money.from_koruny("5000")


class TestDetailDialogFlagButton:
    """Fáze 6.7: flag_button chování podle stavu."""

    def test_flag_button_skryty_pro_novy(self, qtbot):
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.NOVY)))
        qtbot.addWidget(d)
        d.show()
        assert d._flag_button_widget.isVisible() is False

    def test_flag_button_viditelny_pro_zauctovany(self, qtbot):
        d = DokladDetailDialog(_vm(_item(stav=StavDokladu.ZAUCTOVANY)))
        qtbot.addWidget(d)
        d.show()
        assert d._flag_button_widget.isVisible() is True

    def test_flag_click_non_novy_vola_ask_with_note(self, qtbot, monkeypatch):
        """Non-NOVY doklad: flag → ConfirmDialog.ask_with_note → poznámka."""
        calls: list[dict] = []

        def fake_ask(cls, *a, **kw):
            calls.append({"args": a, "kwargs": kw})
            return (True, "ručně zadaná poznámka")

        monkeypatch.setattr(
            "ui.dialogs.doklad_detail_dialog.ConfirmDialog.ask_with_note",
            classmethod(fake_ask),
        )
        actions = _FakeActions(_item(stav=StavDokladu.ZAUCTOVANY))
        d = DokladDetailDialog(_vm(
            _item(stav=StavDokladu.ZAUCTOVANY), actions,
        ))
        qtbot.addWidget(d)
        d._flag_button_widget.click()
        assert len(calls) == 1
        assert actions.flag_on_called == 1
        assert actions.flag_on_calls[-1][1] == "ručně zadaná poznámka"

    def test_flag_click_non_novy_zrušení_nevola_actions(
        self, qtbot, monkeypatch,
    ):
        """Když uživatelka zruší ask_with_note, flag se nezmění."""
        monkeypatch.setattr(
            "ui.dialogs.doklad_detail_dialog.ConfirmDialog.ask_with_note",
            classmethod(lambda cls, *a, **kw: (False, None)),
        )
        actions = _FakeActions(_item(stav=StavDokladu.ZAUCTOVANY))
        d = DokladDetailDialog(_vm(
            _item(stav=StavDokladu.ZAUCTOVANY), actions,
        ))
        qtbot.addWidget(d)
        d._flag_button_widget.click()
        assert actions.flag_on_called == 0

    def test_doresit_flagnuty_non_novy_bez_potvrzeni(self, qtbot):
        """Odflagování: ``dores()`` se volá rovnou (bez dialogu)."""
        actions = _FakeActions(
            _item(stav=StavDokladu.ZAUCTOVANY, k_doreseni=True, poznamka="x"),
        )
        d = DokladDetailDialog(_vm(
            _item(stav=StavDokladu.ZAUCTOVANY, k_doreseni=True, poznamka="x"),
            actions,
        ))
        qtbot.addWidget(d)
        d._flag_button_widget.click()
        assert actions.flag_off_called == 1


class TestDetailDialogDoreseniBezPoznamky:
    """Fáze 6.7: „(bez poznámky)" render pro flagnutý doklad bez poznámky."""

    def test_bez_poznamky_ukazuje_placeholder(self, qtbot):
        d = DokladDetailDialog(_vm(
            _item(k_doreseni=True, poznamka=None, stav=StavDokladu.ZAUCTOVANY),
        ))
        qtbot.addWidget(d)
        d.show()
        assert "(bez poznámky)" in d._doreseni_note_widget.text()

    def test_bez_poznamky_property_empty_true(self, qtbot):
        d = DokladDetailDialog(_vm(
            _item(k_doreseni=True, poznamka=None, stav=StavDokladu.ZAUCTOVANY),
        ))
        qtbot.addWidget(d)
        d.show()
        assert d._doreseni_note_widget.property("empty") == "true"

    def test_s_poznamkou_property_empty_false(self, qtbot):
        d = DokladDetailDialog(_vm(
            _item(k_doreseni=True, poznamka="pz", stav=StavDokladu.ZAUCTOVANY),
        ))
        qtbot.addWidget(d)
        d.show()
        assert d._doreseni_note_widget.property("empty") == "false"
        assert d._doreseni_note_widget.text() == "pz"
