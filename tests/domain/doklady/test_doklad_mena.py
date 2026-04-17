"""Testy cizoměnových polí na Doklad entitě."""

from datetime import date
from decimal import Decimal

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import Mena, StavDokladu, TypDokladu
from domain.shared.errors import ValidationError
from domain.shared.money import Money


class TestMenaEnum:

    def test_values(self):
        assert Mena.CZK.value == "CZK"
        assert Mena.EUR.value == "EUR"
        assert Mena.USD.value == "USD"

    def test_from_string(self):
        assert Mena("EUR") == Mena.EUR


class TestDokladCZK:

    def test_default_mena_is_czk(self):
        d = Doklad(
            cislo="FV-001", typ=TypDokladu.FAKTURA_VYDANA,
            datum_vystaveni=date(2026, 4, 1),
            castka_celkem=Money(100000),
        )
        assert d.mena == Mena.CZK
        assert d.castka_mena is None
        assert d.kurz is None

    def test_czk_with_kurz_raises(self):
        with pytest.raises(ValidationError, match="Pro CZK"):
            Doklad(
                cislo="FV-001", typ=TypDokladu.FAKTURA_VYDANA,
                datum_vystaveni=date(2026, 4, 1),
                castka_celkem=Money(100000),
                mena=Mena.CZK,
                kurz=Decimal("25.1"),
            )

    def test_czk_with_castka_mena_raises(self):
        with pytest.raises(ValidationError, match="Pro CZK"):
            Doklad(
                cislo="FV-001", typ=TypDokladu.FAKTURA_VYDANA,
                datum_vystaveni=date(2026, 4, 1),
                castka_celkem=Money(100000),
                mena=Mena.CZK,
                castka_mena=Money(5000),
            )


class TestDokladEUR:

    def test_valid_eur_doklad(self):
        d = Doklad(
            cislo="FP-001", typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2026, 4, 1),
            castka_celkem=Money(25100),  # 251 Kč
            mena=Mena.EUR,
            castka_mena=Money(1000),  # 10 EUR
            kurz=Decimal("25.10"),
        )
        assert d.mena == Mena.EUR
        assert d.castka_mena == Money(1000)
        assert d.kurz == Decimal("25.10")

    def test_eur_without_kurz_raises(self):
        with pytest.raises(ValidationError, match="kurz povinný"):
            Doklad(
                cislo="FP-001", typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2026, 4, 1),
                castka_celkem=Money(25100),
                mena=Mena.EUR,
                castka_mena=Money(1000),
            )

    def test_eur_without_castka_mena_raises(self):
        with pytest.raises(ValidationError, match="částka v cizí měně povinná"):
            Doklad(
                cislo="FP-001", typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2026, 4, 1),
                castka_celkem=Money(25100),
                mena=Mena.EUR,
                kurz=Decimal("25.10"),
            )

    def test_eur_negative_kurz_raises(self):
        with pytest.raises(ValidationError, match="kurz povinný"):
            Doklad(
                cislo="FP-001", typ=TypDokladu.FAKTURA_PRIJATA,
                datum_vystaveni=date(2026, 4, 1),
                castka_celkem=Money(25100),
                mena=Mena.EUR,
                castka_mena=Money(1000),
                kurz=Decimal("-1"),
            )

    def test_prepocet_castka_mena_times_kurz(self):
        """castka_mena * kurz = castka_celkem (zaokrouhleno)."""
        castka_mena = Money(1000)  # 10,00 EUR
        kurz = Decimal("25.10")
        czk = castka_mena * kurz  # Money.__mul__(Decimal)
        assert czk == Money(25100)  # 251,00 Kč
