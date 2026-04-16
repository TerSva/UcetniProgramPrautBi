"""Testy PartnerDialog."""

import pytest

from domain.partneri.partner import KategoriePartnera
from ui.dialogs.partner_dialog import PartnerDialog, PartnerDialogResult


class TestPartnerDialog:

    def test_initial_state(self, qtbot):
        dialog = PartnerDialog()
        qtbot.addWidget(dialog)
        assert dialog.result is None
        assert dialog.windowTitle() == "Nový partner"

    def test_spolecnik_section_visibility(self, qtbot):
        dialog = PartnerDialog()
        qtbot.addWidget(dialog)
        # Default = dodavatel → společník sekce skrytá
        assert dialog._spolecnik_section_widget.isHidden()

        # Switch to společník
        dialog._kategorie_widget.set_value(KategoriePartnera.SPOLECNIK)
        assert not dialog._spolecnik_section_widget.isHidden()

        # Switch back
        dialog._kategorie_widget.set_value(KategoriePartnera.DODAVATEL)
        assert dialog._spolecnik_section_widget.isHidden()

    def test_edit_mode(self, qtbot):
        data = PartnerDialogResult(
            nazev="iStyle CZ",
            kategorie=KategoriePartnera.DODAVATEL,
            ico="27583368",
        )
        dialog = PartnerDialog(edit_data=data)
        qtbot.addWidget(dialog)
        assert dialog.windowTitle() == "Upravit partnera"
        assert dialog._nazev_widget.value() == "iStyle CZ"
        assert dialog._ico_widget.value() == "27583368"

    def test_submit_empty_nazev_shows_error(self, qtbot):
        dialog = PartnerDialog()
        qtbot.addWidget(dialog)
        dialog._nazev_widget.set_value("")
        dialog._submit_widget.click()
        assert dialog.result is None  # dialog stays open
