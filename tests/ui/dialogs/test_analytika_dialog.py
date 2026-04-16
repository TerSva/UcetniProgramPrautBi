"""Testy pro AnalytikaDialog — Fáze 7."""

from __future__ import annotations

import pytest

from ui.dialogs.analytika_dialog import AnalytikaDialog


class TestAddMode:

    def test_add_dialog_title(self, qtbot):
        dialog = AnalytikaDialog("501", "Spotřeba materiálu")
        qtbot.addWidget(dialog)
        assert "501" in dialog.windowTitle()
        assert "Přidat" in dialog.windowTitle()

    def test_suffix_not_hidden_in_add_mode(self, qtbot):
        dialog = AnalytikaDialog("501", "Spotřeba materiálu")
        qtbot.addWidget(dialog)
        assert not dialog._suffix_widget.isHidden()

    def test_submit_valid(self, qtbot):
        dialog = AnalytikaDialog("501", "Spotřeba materiálu")
        qtbot.addWidget(dialog)
        dialog._suffix_widget.set_value("100")
        dialog._nazev_widget.set_value("Kancelář")
        dialog._popis_widget.set_value("Papíry")
        dialog._on_submit()
        assert dialog.result is not None
        assert dialog.result.suffix == "100"
        assert dialog.result.nazev == "Kancelář"
        assert dialog.result.popis == "Papíry"

    def test_submit_empty_suffix_shows_error(self, qtbot):
        dialog = AnalytikaDialog("501", "Spotřeba materiálu")
        qtbot.addWidget(dialog)
        dialog._suffix_widget.set_value("")
        dialog._nazev_widget.set_value("Kancelář")
        dialog._on_submit()
        assert dialog.result is None
        assert not dialog._error_widget.isHidden()

    def test_submit_invalid_suffix_shows_error(self, qtbot):
        dialog = AnalytikaDialog("501", "Spotřeba materiálu")
        qtbot.addWidget(dialog)
        dialog._suffix_widget.set_value("toolong")
        dialog._nazev_widget.set_value("Kancelář")
        dialog._on_submit()
        assert dialog.result is None
        assert not dialog._error_widget.isHidden()

    def test_submit_empty_nazev_shows_error(self, qtbot):
        dialog = AnalytikaDialog("501", "Spotřeba materiálu")
        qtbot.addWidget(dialog)
        dialog._suffix_widget.set_value("100")
        dialog._nazev_widget.set_value("")
        dialog._on_submit()
        assert dialog.result is None
        assert not dialog._error_widget.isHidden()


class TestEditMode:

    def test_edit_dialog_title(self, qtbot):
        dialog = AnalytikaDialog(
            "501", "Spotřeba materiálu",
            edit_cislo="501.100", edit_nazev="Kancelář",
        )
        qtbot.addWidget(dialog)
        assert "Upravit" in dialog.windowTitle()
        assert "501.100" in dialog.windowTitle()

    def test_suffix_hidden_in_edit_mode(self, qtbot):
        dialog = AnalytikaDialog(
            "501", "Spotřeba materiálu",
            edit_cislo="501.100", edit_nazev="Kancelář",
        )
        qtbot.addWidget(dialog)
        assert dialog._suffix_widget.isHidden()

    def test_edit_prefills_values(self, qtbot):
        dialog = AnalytikaDialog(
            "501", "Spotřeba materiálu",
            edit_cislo="501.100", edit_nazev="Kancelář",
            edit_popis="Papíry a tonery",
        )
        qtbot.addWidget(dialog)
        assert dialog._nazev_widget.value() == "Kancelář"
        assert dialog._popis_widget.value() == "Papíry a tonery"

    def test_edit_submit_valid(self, qtbot):
        dialog = AnalytikaDialog(
            "501", "Spotřeba materiálu",
            edit_cislo="501.100", edit_nazev="Kancelář",
        )
        qtbot.addWidget(dialog)
        dialog._nazev_widget.set_value("Nový název")
        dialog._on_submit()
        assert dialog.result is not None
        assert dialog.result.nazev == "Nový název"
