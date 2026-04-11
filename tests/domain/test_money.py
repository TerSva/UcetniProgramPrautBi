from decimal import Decimal

import pytest

from domain.shared.money import Money


class TestFactory:
    """Testy vytváření Money objektů."""

    def test_koruny_z_str(self):
        m = Money.koruny("1234.50")
        assert m.halere_int == 123450
        assert m.castka == Decimal("1234.50")

    def test_koruny_z_int(self):
        m = Money.koruny(100)
        assert m.halere_int == 10000

    def test_koruny_z_decimal(self):
        m = Money.koruny(Decimal("99.99"))
        assert m.halere_int == 9999

    def test_koruny_zaokrouhleni_nahoru(self):
        m = Money.koruny("1.005")
        assert m.halere_int == 101  # ROUND_HALF_UP

    def test_koruny_zaokrouhleni_dolu(self):
        m = Money.koruny("1.004")
        assert m.halere_int == 100

    def test_halere_z_int(self):
        m = Money.halere(123450)
        assert m.castka == Decimal("1234.50")

    def test_halere_odmitne_float(self):
        with pytest.raises(TypeError, match="očekává int"):
            Money.halere(123.45)  # type: ignore[arg-type]

    def test_nula(self):
        m = Money.nula()
        assert m.halere_int == 0
        assert m.mena == "CZK"

    def test_zero_czk_konstanta(self):
        assert Money.ZERO_CZK.halere_int == 0
        assert Money.ZERO_CZK.mena == "CZK"

    def test_jina_mena(self):
        m = Money.koruny("100", mena="EUR")
        assert m.mena == "EUR"
        assert m.halere_int == 10000


class TestAritmetika:
    """Testy aritmetických operací."""

    def test_scitani(self):
        a = Money.koruny("100.50")
        b = Money.koruny("200.30")
        assert (a + b).halere_int == 30080

    def test_odcitani(self):
        a = Money.koruny("500")
        b = Money.koruny("200.50")
        assert (a - b).halere_int == 29950

    def test_negace(self):
        m = Money.koruny("100")
        assert (-m).halere_int == -10000

    def test_abs_zaporne(self):
        m = Money.halere(-5000)
        assert abs(m).halere_int == 5000

    def test_abs_kladne(self):
        m = Money.koruny("50")
        assert abs(m).halere_int == 5000

    def test_nasobeni_int(self):
        m = Money.koruny("100.50")
        assert (m * 3).halere_int == 30150

    def test_nasobeni_decimal(self):
        m = Money.koruny("100")
        result = m * Decimal("0.21")  # DPH 21%
        assert result.halere_int == 2100

    def test_nasobeni_decimal_zaokrouhleni(self):
        m = Money.koruny("33.33")
        result = m * Decimal("0.21")
        # 3333 * 0.21 = 699.93 → zaokrouhleno na 700
        assert result.halere_int == 700

    def test_nasobeni_spatny_typ(self):
        m = Money.koruny("100")
        with pytest.raises(TypeError):
            m * "2"  # type: ignore[operator]

    def test_scitani_ruzne_meny_vyhodi_chybu(self):
        czk = Money.koruny("100")
        eur = Money.koruny("50", mena="EUR")
        with pytest.raises(ValueError, match="Nelze míchat měny"):
            czk + eur

    def test_odcitani_ruzne_meny_vyhodi_chybu(self):
        czk = Money.koruny("100")
        eur = Money.koruny("50", mena="EUR")
        with pytest.raises(ValueError, match="Nelze míchat měny"):
            czk - eur


class TestPorovnani:
    """Testy porovnávacích operací."""

    def test_vetsi(self):
        assert Money.koruny("200") > Money.koruny("100")

    def test_mensi(self):
        assert Money.koruny("50") < Money.koruny("100")

    def test_vetsi_nebo_rovno(self):
        assert Money.koruny("100") >= Money.koruny("100")
        assert Money.koruny("200") >= Money.koruny("100")

    def test_mensi_nebo_rovno(self):
        assert Money.koruny("100") <= Money.koruny("100")
        assert Money.koruny("50") <= Money.koruny("100")

    def test_rovnost(self):
        assert Money.koruny("100") == Money.koruny("100")

    def test_nerovnost_castka(self):
        assert Money.koruny("100") != Money.koruny("200")

    def test_nerovnost_mena(self):
        assert Money.koruny("100", mena="CZK") != Money.koruny("100", mena="EUR")

    def test_porovnani_s_nulou(self):
        assert Money.koruny("100") > 0
        assert Money.halere(-1) < 0
        assert Money.nula() >= 0
        assert Money.nula() <= 0

    def test_porovnani_ruzne_meny_vyhodi_chybu(self):
        with pytest.raises(ValueError, match="Nelze míchat měny"):
            Money.koruny("100") > Money.koruny("50", mena="EUR")


class TestBool:
    """Testy bool konverze."""

    def test_nenulova_castka_je_true(self):
        assert bool(Money.koruny("1"))
        assert bool(Money.halere(-1))

    def test_nula_je_false(self):
        assert not bool(Money.nula())
        assert not bool(Money.ZERO_CZK)


class TestImmutabilita:
    """Money je frozen dataclass — nelze měnit."""

    def test_nelze_zmenit_halere(self):
        m = Money.koruny("100")
        with pytest.raises(AttributeError):
            m._halere = 999  # type: ignore[misc]

    def test_nelze_zmenit_menu(self):
        m = Money.koruny("100")
        with pytest.raises(AttributeError):
            m.mena = "EUR"  # type: ignore[misc]


class TestHash:
    """Money jako klíč ve slovníku / v setu."""

    def test_stejne_money_stejny_hash(self):
        a = Money.koruny("100")
        b = Money.halere(10000)
        assert hash(a) == hash(b)

    def test_pouzitelne_v_setu(self):
        s = {Money.koruny("100"), Money.koruny("100"), Money.koruny("200")}
        assert len(s) == 2


class TestFormat:
    """Testy formátování pro UI."""

    def test_format_cz_zakladni(self):
        assert Money.koruny("1234.50").format_cz() == "1\u00a0234,50 Kč"

    def test_format_cz_nula(self):
        assert Money.nula().format_cz() == "0,00 Kč"

    def test_format_cz_zaporne(self):
        assert Money.halere(-123450).format_cz() == "-1\u00a0234,50 Kč"

    def test_format_cz_male_cislo(self):
        assert Money.koruny("0.50").format_cz() == "0,50 Kč"

    def test_format_cz_velke_cislo(self):
        assert Money.koruny("1000000").format_cz() == "1\u00a0000\u00a0000,00 Kč"

    def test_format_eur(self):
        assert Money.koruny("100", mena="EUR").format_cz() == "100,00 €"

    def test_repr(self):
        m = Money.koruny("1234.50")
        assert repr(m) == "Money(1234.50, 'CZK')"


class TestDbRoundtrip:
    """Simulace uložení do DB a načtení zpět."""

    def test_roundtrip(self):
        original = Money.koruny("1234.56")
        # uložení do DB
        db_value = original.halere_int
        # načtení z DB
        loaded = Money.halere(db_value)
        assert loaded == original

    def test_sum_v_sql(self):
        """Simulace SQL SUM() — prostý součet intů."""
        castky = [
            Money.koruny("100.10"),
            Money.koruny("200.20"),
            Money.koruny("300.30"),
        ]
        # SQL: SELECT SUM(castka_hal) FROM ...
        sql_sum = sum(m.halere_int for m in castky)
        assert sql_sum == 60060
        assert Money.halere(sql_sum) == Money.koruny("600.60")
