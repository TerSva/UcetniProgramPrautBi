"""Testy pro Badge widget."""

import pytest

from domain.doklady.typy import StavDokladu, TypDokladu
from ui.widgets.badge import (
    Badge,
    BadgeVariant,
    badge_variant_for_stav,
    badge_variant_for_typ,
    stav_display_text,
    typ_display_text,
)


class TestBadgeZaklad:

    def test_vychozi_variant_je_neutral(self, qtbot):
        b = Badge("test")
        qtbot.addWidget(b)
        assert b.variant == BadgeVariant.NEUTRAL
        assert b.property("variant") == "neutral"

    def test_nastavi_text(self, qtbot):
        b = Badge("FV")
        qtbot.addWidget(b)
        assert b.text() == "FV"

    def test_set_text_zmeni_text(self, qtbot):
        b = Badge("X")
        qtbot.addWidget(b)
        b.set_text("Y")
        assert b.text() == "Y"

    def test_set_variant_zmeni_property(self, qtbot):
        b = Badge("x", BadgeVariant.NEUTRAL)
        qtbot.addWidget(b)
        b.set_variant(BadgeVariant.SUCCESS)
        assert b.variant == BadgeVariant.SUCCESS
        assert b.property("variant") == "success"


class TestHelpersTyp:

    def test_fv_je_primary(self):
        assert badge_variant_for_typ(TypDokladu.FAKTURA_VYDANA) == BadgeVariant.PRIMARY

    def test_fp_je_info(self):
        assert badge_variant_for_typ(TypDokladu.FAKTURA_PRIJATA) == BadgeVariant.INFO

    def test_typ_display_text_zkratky(self):
        assert typ_display_text(TypDokladu.FAKTURA_VYDANA) == "FV"
        assert typ_display_text(TypDokladu.FAKTURA_PRIJATA) == "FP"
        assert typ_display_text(TypDokladu.OPRAVNY_DOKLAD) == "OD"


class TestHelpersStav:

    def test_novy_je_warning(self):
        assert badge_variant_for_stav(StavDokladu.NOVY) == BadgeVariant.WARNING

    def test_uhrazeny_je_success(self):
        assert badge_variant_for_stav(StavDokladu.UHRAZENY) == BadgeVariant.SUCCESS

    def test_stav_display_text_cesky(self):
        assert stav_display_text(StavDokladu.NOVY) == "Nový"
        assert stav_display_text(StavDokladu.ZAUCTOVANY) == "Zaúčtovaný"
        assert stav_display_text(StavDokladu.STORNOVANY) == "Stornovaný"
