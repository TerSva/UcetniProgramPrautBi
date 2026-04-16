"""Testy doménové entity Partner."""

from decimal import Decimal

import pytest

from domain.partneri.partner import KategoriePartnera, Partner
from domain.shared.errors import ValidationError


class TestPartnerValidace:

    def test_nazev_povinny(self):
        with pytest.raises(ValidationError, match="Název"):
            Partner(nazev="", kategorie=KategoriePartnera.DODAVATEL)

    def test_nazev_whitespace(self):
        with pytest.raises(ValidationError, match="Název"):
            Partner(nazev="   ", kategorie=KategoriePartnera.DODAVATEL)

    def test_ico_8_cislic(self):
        with pytest.raises(ValidationError, match="IČO"):
            Partner(
                nazev="Test", kategorie=KategoriePartnera.DODAVATEL,
                ico="1234",
            )

    def test_ico_validni(self):
        p = Partner(
            nazev="Test", kategorie=KategoriePartnera.DODAVATEL,
            ico="12345678",
        )
        assert p.ico == "12345678"

    def test_spolecnik_bez_podilu(self):
        with pytest.raises(ValidationError, match="podíl"):
            Partner(
                nazev="Martin", kategorie=KategoriePartnera.SPOLECNIK,
            )

    def test_spolecnik_s_podilem(self):
        p = Partner(
            nazev="Martin", kategorie=KategoriePartnera.SPOLECNIK,
            podil_procent=Decimal("90"),
        )
        assert p.podil_procent == Decimal("90")
        assert p.kategorie == KategoriePartnera.SPOLECNIK


class TestKategoriePartnera:

    def test_enum_values(self):
        assert KategoriePartnera.ODBERATEL.value == "odberatel"
        assert KategoriePartnera.DODAVATEL.value == "dodavatel"
        assert KategoriePartnera.SPOLECNIK.value == "spolecnik"
        assert KategoriePartnera.KOMBINOVANY.value == "kombinovany"


class TestPartnerUprav:

    def test_uprav_nazev(self):
        p = Partner(nazev="Orig", kategorie=KategoriePartnera.DODAVATEL, id=1)
        p.uprav(nazev="Novy")
        assert p.nazev == "Novy"

    def test_uprav_ico(self):
        p = Partner(nazev="Test", kategorie=KategoriePartnera.DODAVATEL, id=1)
        p.uprav(ico="87654321")
        assert p.ico == "87654321"

    def test_deaktivuj_reaktivuj(self):
        p = Partner(nazev="Test", kategorie=KategoriePartnera.DODAVATEL, id=1)
        assert p.je_aktivni
        p.deaktivuj()
        assert not p.je_aktivni
        p.reaktivuj()
        assert p.je_aktivni
