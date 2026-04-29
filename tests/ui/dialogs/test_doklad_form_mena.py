"""Testy měnové sekce a společníka v DokladFormDialog."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from domain.doklady.typy import Mena, TypDokladu
from domain.partneri.partner import KategoriePartnera
from domain.shared.money import Money
from services.queries.doklady_list import DokladyListItem
from services.queries.partneri_list import PartneriListItem
from ui.dialogs.doklad_form_dialog import DokladFormDialog
from ui.viewmodels.doklad_form_vm import DokladFormViewModel


def _make_vm():
    next_q = MagicMock()
    next_q.execute.return_value = "FP-2026-001"
    create_cmd = MagicMock()
    create_cmd.execute.return_value = DokladyListItem(
        id=1, cislo="FP-2026-001", typ=TypDokladu.FAKTURA_PRIJATA,
        datum_vystaveni=date(2026, 4, 10), datum_splatnosti=None,
        partner_id=None, partner_nazev=None,
        castka_celkem=Money(25100), stav=MagicMock(),
        k_doreseni=False, poznamka_doreseni=None, popis=None,
    )
    return DokladFormViewModel(next_q, create_cmd)


def _make_spolecnik_item():
    return PartneriListItem(
        id=1, nazev="Martin Švanda",
        kategorie=KategoriePartnera.SPOLECNIK,
        ico=None, dic=None, adresa=None,
        je_aktivni=True, podil_procent=Decimal("90"),
    )


class TestMenaSection:

    def test_mena_default_czk(self, qtbot):
        vm = _make_vm()
        d = DokladFormDialog(vm)
        qtbot.addWidget(d)
        assert d._mena_combo_widget.value() == Mena.CZK
        assert d._mena_section_widget.isHidden()

    def test_mena_eur_shows_section(self, qtbot):
        vm = _make_vm()
        d = DokladFormDialog(vm)
        qtbot.addWidget(d)
        d._mena_combo_widget.set_value(Mena.EUR)
        assert not d._mena_section_widget.isHidden()

    def test_mena_czk_hides_section(self, qtbot):
        vm = _make_vm()
        d = DokladFormDialog(vm)
        qtbot.addWidget(d)
        d._mena_combo_widget.set_value(Mena.EUR)
        d._mena_combo_widget.set_value(Mena.CZK)
        assert d._mena_section_widget.isHidden()

    def test_auto_prepocet(self, qtbot):
        vm = _make_vm()
        d = DokladFormDialog(vm)
        qtbot.addWidget(d)
        d._mena_combo_widget.set_value(Mena.EUR)
        d._castka_mena_widget.set_value(Money(1000))  # 10 EUR
        d._kurz_widget.set_value("25,10")
        d._on_foreign_amount_changed()
        # Castka celkem should be auto-set to 251 Kč
        assert d._castka_widget.value() == Money(25100)

    def test_castka_readonly_for_foreign(self, qtbot):
        vm = _make_vm()
        d = DokladFormDialog(vm)
        qtbot.addWidget(d)
        d._mena_combo_widget.set_value(Mena.EUR)
        assert d._castka_widget.line_widget.isReadOnly()

    def test_castka_editable_for_czk(self, qtbot):
        vm = _make_vm()
        d = DokladFormDialog(vm)
        qtbot.addWidget(d)
        assert not d._castka_widget.line_widget.isReadOnly()

    def test_prepocet_je_live_pri_psani_castky(self, qtbot):
        """Při psaní castka_mena se přepočet provádí live (textChanged),
        ne až při ztrátě fokusu. Bez toho race condition: uživatel zadá
        EUR a hned klikne Uložit, CZK pole zůstane prázdné."""
        vm = _make_vm()
        d = DokladFormDialog(vm)
        qtbot.addWidget(d)
        d._mena_combo_widget.set_value(Mena.EUR)
        d._kurz_widget.set_value("25")
        # Simuluj psaní bez ztráty fokusu
        d._castka_mena_widget.line_widget.setText("100,00")
        # Auto-přepočet by měl proběhnout bez explicitního volání:
        assert d._castka_widget.value() == Money(250000)  # 100 * 25 = 2500 Kč

    def test_castka_se_resetuje_pri_invalidnim_vstupu(self, qtbot):
        """Když castka_mena nebo kurz chybí, hlavní CZK pole se vyčistí —
        nesmí tam zůstat zastaralá hodnota z předchozího validního stavu."""
        vm = _make_vm()
        d = DokladFormDialog(vm)
        qtbot.addWidget(d)
        d._mena_combo_widget.set_value(Mena.EUR)
        d._castka_mena_widget.set_value(Money(1000))
        d._kurz_widget.set_value("25")
        d._on_foreign_amount_changed()
        assert d._castka_widget.value() == Money(25000)
        # Vymaž kurz → CZK musí zmizet
        d._kurz_widget.set_value("")
        d._on_foreign_amount_changed()
        assert d._castka_widget.value() is None


class TestSpolecnikCheckbox:

    def test_hidden_for_fv(self, qtbot):
        vm = _make_vm()
        d = DokladFormDialog(vm)
        qtbot.addWidget(d)
        d._typ_combo_widget.set_value(TypDokladu.FAKTURA_VYDANA)
        assert d._spolecnik_section_widget.isHidden()

    def test_visible_for_fp(self, qtbot):
        vm = _make_vm()
        d = DokladFormDialog(vm)
        qtbot.addWidget(d)
        d._typ_combo_widget.set_value(TypDokladu.FAKTURA_PRIJATA)
        assert not d._spolecnik_section_widget.isHidden()

    def test_visible_for_pd(self, qtbot):
        vm = _make_vm()
        d = DokladFormDialog(vm)
        qtbot.addWidget(d)
        d._typ_combo_widget.set_value(TypDokladu.POKLADNI_DOKLAD)
        assert not d._spolecnik_section_widget.isHidden()

    def test_hidden_for_id(self, qtbot):
        vm = _make_vm()
        d = DokladFormDialog(vm)
        qtbot.addWidget(d)
        d._typ_combo_widget.set_value(TypDokladu.INTERNI_DOKLAD)
        assert d._spolecnik_section_widget.isHidden()

    def test_spolecnik_dropdown_hidden_until_checked(self, qtbot):
        vm = _make_vm()
        items = [_make_spolecnik_item()]
        d = DokladFormDialog(vm, partner_items=items)
        qtbot.addWidget(d)
        d._typ_combo_widget.set_value(TypDokladu.FAKTURA_PRIJATA)
        assert d._spolecnik_combo_widget.isHidden()
        d._spolecnik_check_widget.setChecked(True)
        assert not d._spolecnik_combo_widget.isHidden()
