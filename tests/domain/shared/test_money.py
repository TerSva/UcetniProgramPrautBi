"""Testy pro Money value object — vyčerpávající pokrytí."""

from decimal import Decimal

import pytest

from domain.shared.money import Money


class TestKonstruktor:
    """Přímý konstruktor Money(halire: int)."""

    def test_kladne_halire(self):
        m = Money(12345)
        assert m.halire == 12345

    def test_zaporne_halire(self):
        m = Money(-5000)
        assert m.halire == -5000

    def test_nula(self):
        m = Money(0)
        assert m.halire == 0

    def test_odmitne_float(self):
        with pytest.raises(TypeError, match="očekává int"):
            Money(123.45)  # type: ignore[arg-type]

    def test_odmitne_str(self):
        with pytest.raises(TypeError, match="očekává int"):
            Money("100")  # type: ignore[arg-type]

    def test_odmitne_decimal(self):
        with pytest.raises(TypeError, match="očekává int"):
            Money(Decimal("100"))  # type: ignore[arg-type]


class TestFromKoruny:
    """Factory Money.from_koruny() — Decimal, str, int vstupy."""

    # --- Decimal vstupy ---

    def test_decimal_zakladni(self):
        m = Money.from_koruny(Decimal("123.45"))
        assert m.halire == 12345

    def test_decimal_zaporne(self):
        m = Money.from_koruny(Decimal("-99.99"))
        assert m.halire == -9999

    def test_decimal_cele_cislo(self):
        m = Money.from_koruny(Decimal("100"))
        assert m.halire == 10000

    def test_decimal_zaokrouhleni_half_up(self):
        # 1.005 → 1.01 (ROUND_HALF_UP)
        m = Money.from_koruny(Decimal("1.005"))
        assert m.halire == 101

    def test_decimal_zaokrouhleni_dolu(self):
        # 1.004 → 1.00
        m = Money.from_koruny(Decimal("1.004"))
        assert m.halire == 100

    # --- Int vstupy ---

    def test_int_kladny(self):
        m = Money.from_koruny(100)
        assert m.halire == 10000

    def test_int_zaporny(self):
        m = Money.from_koruny(-50)
        assert m.halire == -5000

    def test_int_nula(self):
        m = Money.from_koruny(0)
        assert m.halire == 0

    # --- String vstupy — české formáty ---

    def test_str_ceska_carka(self):
        m = Money.from_koruny("123,45")
        assert m.halire == 12345

    def test_str_tecka(self):
        m = Money.from_koruny("123.45")
        assert m.halire == 12345

    def test_str_mezera_tisice(self):
        m = Money.from_koruny("1 234,56")
        assert m.halire == 123456

    def test_str_nbsp_tisice(self):
        m = Money.from_koruny("1\u00a0234,56")
        assert m.halire == 123456

    def test_str_cele_cislo(self):
        m = Money.from_koruny("1234")
        assert m.halire == 123400

    def test_str_zaporne(self):
        m = Money.from_koruny("-123,45")
        assert m.halire == -12345

    def test_str_zaporne_s_mezerou(self):
        m = Money.from_koruny("- 1 234,56")
        assert m.halire == -123456

    def test_str_jedna_desetinna(self):
        # "123,5" → 123,50
        m = Money.from_koruny("123,5")
        assert m.halire == 12350

    def test_str_velke_cislo(self):
        m = Money.from_koruny("1 000 000,00")
        assert m.halire == 100000000

    # --- String vstupy — odmítnuté formáty ---

    def test_str_anglicky_format_odmitnut(self):
        """'1,234.56' — čárka + tečka je zakázaná kombinace."""
        with pytest.raises(ValueError, match="Smíšení čárky a tečky"):
            Money.from_koruny("1,234.56")

    def test_str_prazdny(self):
        with pytest.raises(ValueError, match="Neplatný formát"):
            Money.from_koruny("")

    def test_str_pismena(self):
        with pytest.raises(ValueError, match="Neplatný formát"):
            Money.from_koruny("abc")

    def test_str_jen_znak(self):
        with pytest.raises(ValueError, match="Neplatný formát"):
            Money.from_koruny("-")

    def test_str_vice_desetinnych(self):
        """Více než 2 desetinná místa odmítnuto."""
        with pytest.raises(ValueError, match="Neplatný formát"):
            Money.from_koruny("123,456")

    # --- Float odmítnut ---

    def test_float_odmitnut(self):
        with pytest.raises(TypeError, match="nepřijímá float"):
            Money.from_koruny(123.45)  # type: ignore[arg-type]

    def test_float_nula_odmitnut(self):
        with pytest.raises(TypeError, match="nepřijímá float"):
            Money.from_koruny(0.0)  # type: ignore[arg-type]


class TestZero:
    """Factory Money.zero()."""

    def test_zero(self):
        m = Money.zero()
        assert m.halire == 0
        assert m.is_zero


class TestAritmetika:
    """Aritmetické operace — vrací nový Money, nemutují."""

    # --- Sčítání ---

    def test_scitani(self):
        assert (Money(100) + Money(200)).halire == 300

    def test_scitani_zaporne(self):
        assert (Money(100) + Money(-50)).halire == 50

    def test_scitani_s_int_typeerror(self):
        with pytest.raises(TypeError, match="Money s int"):
            Money(100) + 50  # type: ignore[operator]

    def test_scitani_s_float_typeerror(self):
        with pytest.raises(TypeError, match="Money s float"):
            Money(100) + 1.5  # type: ignore[operator]

    # --- Odčítání ---

    def test_odcitani(self):
        assert (Money(500) - Money(200)).halire == 300

    def test_odcitani_do_zaporna(self):
        assert (Money(100) - Money(300)).halire == -200

    def test_odcitani_s_int_typeerror(self):
        with pytest.raises(TypeError, match="int"):
            Money(100) - 50  # type: ignore[operator]

    # --- Násobení skalárem ---

    def test_nasobeni_int(self):
        assert (Money(1000) * 3).halire == 3000

    def test_nasobeni_int_zaporny(self):
        assert (Money(1000) * -1).halire == -1000

    def test_nasobeni_decimal_dph_21(self):
        """Typický DPH výpočet: základ 10000 hal × 0.21 = 2100 hal."""
        zaklad = Money(10000)  # 100,00 Kč
        dph = zaklad * Decimal("0.21")
        assert dph.halire == 2100  # 21,00 Kč

    def test_nasobeni_decimal_zaokrouhleni(self):
        """33,33 Kč × 0.21 = 699.93 hal → 700 hal (ROUND_HALF_UP)."""
        m = Money(3333)
        result = m * Decimal("0.21")
        assert result.halire == 700

    def test_nasobeni_decimal_zaokrouhleni_presne_na_pul(self):
        """Přesně na půl → zaokrouhlit nahoru (ROUND_HALF_UP)."""
        # 5 * 0.5 = 2.5 → 3
        m = Money(5)
        result = m * Decimal("0.5")
        assert result.halire == 3  # ne 2

    def test_nasobeni_money_money_typeerror(self):
        """Money × Money nedává účetní smysl."""
        with pytest.raises(TypeError, match="Money × Money"):
            Money(100) * Money(200)  # type: ignore[operator]

    def test_nasobeni_float_typeerror(self):
        with pytest.raises(TypeError, match="float"):
            Money(100) * 0.21  # type: ignore[operator]

    def test_rmul_int(self):
        """3 * Money(100) funguje díky __rmul__."""
        assert (3 * Money(1000)).halire == 3000

    # --- Dělení skalárem ---

    def test_deleni_int(self):
        assert (Money(10000) / 4).halire == 2500

    def test_deleni_int_zaokrouhleni(self):
        """10001 / 4 = 2500.25 → 2500 (ROUND_HALF_UP)."""
        assert (Money(10001) / 4).halire == 2500

    def test_deleni_int_presne_na_pul(self):
        """10002 / 4 = 2500.5 → 2501 (ROUND_HALF_UP)."""
        assert (Money(10002) / 4).halire == 2501

    def test_deleni_decimal(self):
        assert (Money(10000) / Decimal("2.5")).halire == 4000

    def test_deleni_nulou_int(self):
        with pytest.raises(ZeroDivisionError):
            Money(100) / 0

    def test_deleni_nulou_decimal(self):
        with pytest.raises(ZeroDivisionError):
            Money(100) / Decimal("0")

    def test_deleni_money_money_typeerror(self):
        with pytest.raises(TypeError, match="Money / Money"):
            Money(100) / Money(50)  # type: ignore[operator]

    def test_deleni_float_typeerror(self):
        with pytest.raises(TypeError, match="float"):
            Money(100) / 2.0  # type: ignore[operator]


class TestPorovnani:
    """Porovnání — jen mezi Money instancemi."""

    def test_rovnost(self):
        assert Money(100) == Money(100)

    def test_nerovnost(self):
        assert Money(100) != Money(200)

    def test_vetsi(self):
        assert Money(200) > Money(100)

    def test_mensi(self):
        assert Money(100) < Money(200)

    def test_vetsi_rovno(self):
        assert Money(100) >= Money(100)
        assert Money(200) >= Money(100)

    def test_mensi_rovno(self):
        assert Money(100) <= Money(100)
        assert Money(100) <= Money(200)

    def test_rovnost_s_ne_money_vrati_false(self):
        assert Money(100) != 100
        assert Money(100) != "100"

    def test_porovnani_s_int_not_implemented(self):
        """Money > 50 nemá vyhazovat chybu, ale vracet NotImplemented."""
        # Python to zpracuje jako TypeError při použití
        with pytest.raises(TypeError):
            Money(100) > 50  # type: ignore[operator]

    def test_zaporne_porovnani(self):
        assert Money(-100) < Money(0)
        assert Money(0) > Money(-100)


class TestVlastnosti:
    """is_zero, is_positive, is_negative, abs(), negate()."""

    def test_is_zero_true(self):
        assert Money(0).is_zero
        assert Money.zero().is_zero

    def test_is_zero_false(self):
        assert not Money(1).is_zero
        assert not Money(-1).is_zero

    def test_is_positive(self):
        assert Money(100).is_positive
        assert not Money(0).is_positive
        assert not Money(-100).is_positive

    def test_is_negative(self):
        assert Money(-100).is_negative
        assert not Money(0).is_negative
        assert not Money(100).is_negative

    def test_abs_kladne(self):
        assert abs(Money(100)).halire == 100

    def test_abs_zaporne(self):
        assert abs(Money(-100)).halire == 100

    def test_abs_nula(self):
        assert abs(Money(0)).halire == 0

    def test_negate_kladne(self):
        assert Money(100).negate().halire == -100

    def test_negate_zaporne(self):
        assert Money(-100).negate().halire == 100

    def test_negate_nula(self):
        assert Money(0).negate().halire == 0

    def test_negate_storno_scenar(self):
        """Storno dokladu: původní částka → opačná."""
        original = Money.from_koruny("1 500,00")
        storno = original.negate()
        assert storno.halire == -150000
        assert (original + storno).is_zero


class TestImmutability:
    """Money je frozen — nelze měnit."""

    def test_nelze_zmenit_halire(self):
        m = Money(100)
        with pytest.raises(AttributeError):
            m.halire = 999  # type: ignore[misc]

    def test_nelze_pridat_atribut(self):
        m = Money(100)
        with pytest.raises(AttributeError):
            m.novy_atribut = "test"  # type: ignore[attr-defined]


class TestHash:
    """Money je hashable — dá se použít jako klíč v dict/set."""

    def test_stejne_money_stejny_hash(self):
        assert hash(Money(100)) == hash(Money(100))

    def test_pouzitelne_jako_klic_dict(self):
        d = {Money(100): "sto", Money(200): "dveste"}
        assert d[Money(100)] == "sto"

    def test_pouzitelne_v_setu(self):
        s = {Money(100), Money(100), Money(200)}
        assert len(s) == 2

    def test_ruzne_money_ruzny_hash_vetsinou(self):
        # Ne garanci, ale v praxi by měly být různé
        assert hash(Money(100)) != hash(Money(200))


class TestKonverze:
    """to_koruny(), to_halire(), format_cz()."""

    def test_to_koruny(self):
        assert Money(12345).to_koruny() == Decimal("123.45")

    def test_to_koruny_zaporne(self):
        assert Money(-5000).to_koruny() == Decimal("-50.00")

    def test_to_koruny_nula(self):
        assert Money(0).to_koruny() == Decimal("0")

    def test_to_halire(self):
        assert Money(12345).to_halire() == 12345

    def test_format_cz_zakladni(self):
        assert Money(123456).format_cz() == "1\u00a0234,56\u00a0Kč"

    def test_format_cz_nula(self):
        assert Money(0).format_cz() == "0,00\u00a0Kč"

    def test_format_cz_zaporne(self):
        assert Money(-123456).format_cz() == "-1\u00a0234,56\u00a0Kč"

    def test_format_cz_male_cislo(self):
        assert Money(50).format_cz() == "0,50\u00a0Kč"

    def test_format_cz_velke_cislo(self):
        assert Money(123456789).format_cz() == "1\u00a0234\u00a0567,89\u00a0Kč"

    def test_format_cz_nbsp(self):
        """Všechny mezery jsou non-breaking space (\\u00A0) — tisíce i před Kč."""
        formatted = Money(123456).format_cz()
        assert "\u00a0" in formatted
        # Normální mezera tam NENÍ — vše je nbsp
        assert " " not in formatted

    def test_str_je_format_cz(self):
        m = Money(12345)
        assert str(m) == m.format_cz()

    def test_repr(self):
        assert repr(Money(12345)) == "Money(12345)"

    def test_repr_zaporny(self):
        assert repr(Money(-100)) == "Money(-100)"


class TestDbRoundtrip:
    """Simulace uložení do DB a načtení zpět."""

    def test_roundtrip(self):
        original = Money.from_koruny("1 234,56")
        # uložení do DB
        db_value = original.to_halire()
        assert db_value == 123456
        # načtení z DB
        loaded = Money(db_value)
        assert loaded == original

    def test_sql_sum(self):
        """Simulace SQL SUM(castka_hal) — prostý součet intů."""
        castky = [
            Money.from_koruny("100,10"),
            Money.from_koruny("200,20"),
            Money.from_koruny("300,30"),
        ]
        sql_sum = sum(m.to_halire() for m in castky)
        assert sql_sum == 60060
        assert Money(sql_sum) == Money.from_koruny("600,60")


class TestDphVypocty:
    """Reálné účetní scénáře s DPH — přesnost zaokrouhlování."""

    def test_dph_21_ze_zakladu(self):
        """Základ 1 000 Kč → DPH 21% = 210 Kč."""
        zaklad = Money.from_koruny(1000)
        dph = zaklad * Decimal("0.21")
        assert dph == Money.from_koruny(210)

    def test_dph_21_z_necelych(self):
        """Základ 1 523,50 Kč → DPH 21% = 319,94 Kč (zaokrouhleno)."""
        zaklad = Money.from_koruny("1523,50")
        dph = zaklad * Decimal("0.21")
        # 152350 * 0.21 = 31993.5 → 31994 (ROUND_HALF_UP)
        assert dph.halire == 31994

    def test_dph_12_snizena(self):
        """Základ 500 Kč → DPH 12% = 60 Kč."""
        zaklad = Money.from_koruny(500)
        dph = zaklad * Decimal("0.12")
        assert dph == Money.from_koruny(60)

    def test_zaklad_z_celkove_castky(self):
        """Celkem 1 210 Kč s DPH 21% → základ = celkem / 1.21."""
        celkem = Money.from_koruny(1210)
        zaklad = celkem / Decimal("1.21")
        assert zaklad == Money.from_koruny(1000)

    def test_rozpocteni_na_polozky(self):
        """Faktura 3 000 Kč rozdělená na 3 položky."""
        celkem = Money.from_koruny(3000)
        polozka = celkem / 3
        assert polozka == Money.from_koruny(1000)
