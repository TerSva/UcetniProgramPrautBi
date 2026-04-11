"""Testy pro Doklad entitu — pure Python, bez DB."""

from datetime import date, timedelta

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import ValidationError
from domain.shared.money import Money


def _doklad(**kwargs) -> Doklad:
    """Helper: vytvoří validní doklad s defaulty."""
    defaults = dict(
        cislo="FV-2026-001",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 1, 15),
        castka_celkem=Money(100000),
    )
    defaults.update(kwargs)
    return Doklad(**defaults)


class TestKonstruktor:

    def test_validni_doklad(self):
        d = _doklad()
        assert d.cislo == "FV-2026-001"
        assert d.typ == TypDokladu.FAKTURA_VYDANA
        assert d.datum_vystaveni == date(2026, 1, 15)
        assert d.castka_celkem == Money(100000)
        assert d.stav == StavDokladu.NOVY
        assert d.id is None

    def test_validni_s_id(self):
        d = _doklad(id=42)
        assert d.id == 42

    def test_validni_bez_id(self):
        d = _doklad()
        assert d.id is None

    def test_vsechny_pole(self):
        d = Doklad(
            cislo="FP-2026-001",
            typ=TypDokladu.FAKTURA_PRIJATA,
            datum_vystaveni=date(2026, 3, 1),
            castka_celkem=Money(50000),
            partner_id=5,
            datum_zdanitelneho_plneni=date(2026, 3, 1),
            datum_splatnosti=date(2026, 3, 15),
            popis="Služby za březen",
            stav=StavDokladu.ZAUCTOVANY,
            id=10,
        )
        assert d.partner_id == 5
        assert d.datum_zdanitelneho_plneni == date(2026, 3, 1)
        assert d.datum_splatnosti == date(2026, 3, 15)
        assert d.popis == "Služby za březen"

    def test_zaporna_castka_ok(self):
        """Záporná částka je validní (storna)."""
        d = _doklad(castka_celkem=Money(-50000))
        assert d.castka_celkem.halire == -50000

    def test_nulova_castka_ok(self):
        """Nulová částka je validní (interní doklady)."""
        d = _doklad(castka_celkem=Money(0))
        assert d.castka_celkem.halire == 0


class TestValidaceCislo:

    def test_prazdne(self):
        with pytest.raises(ValidationError, match="prázdné"):
            _doklad(cislo="")

    def test_jen_mezery(self):
        with pytest.raises(ValidationError, match="prázdné"):
            _doklad(cislo="   ")

    def test_prilis_dlouhe(self):
        with pytest.raises(ValidationError, match="max 50"):
            _doklad(cislo="A" * 51)

    def test_neplatne_znaky(self):
        with pytest.raises(ValidationError, match="neplatné znaky"):
            _doklad(cislo="FV 2026 001")  # mezera

    def test_neplatne_znaky_specialni(self):
        with pytest.raises(ValidationError, match="neplatné znaky"):
            _doklad(cislo="FV#2026")

    def test_platne_znaky(self):
        """Alfanumerické + -, /, _ jsou OK."""
        d = _doklad(cislo="FV-2026/001_A")
        assert d.cislo == "FV-2026/001_A"


class TestValidaceCastka:

    def test_int_misto_money(self):
        with pytest.raises(TypeError, match="Money"):
            _doklad(castka_celkem=10000)  # type: ignore[arg-type]

    def test_str_misto_money(self):
        with pytest.raises(TypeError, match="Money"):
            _doklad(castka_celkem="100.00")  # type: ignore[arg-type]


class TestValidaceDat:

    def test_splatnost_pred_vystavenim(self):
        with pytest.raises(ValidationError, match="splatnosti"):
            _doklad(
                datum_vystaveni=date(2026, 3, 15),
                datum_splatnosti=date(2026, 3, 1),
            )

    def test_splatnost_rovna_vystaveni_ok(self):
        d = _doklad(
            datum_vystaveni=date(2026, 3, 1),
            datum_splatnosti=date(2026, 3, 1),
        )
        assert d.datum_splatnosti == date(2026, 3, 1)

    def test_zp_vic_nez_rok_po_vystaveni(self):
        with pytest.raises(ValidationError, match="rok"):
            _doklad(
                datum_vystaveni=date(2026, 1, 1),
                datum_zdanitelneho_plneni=date(2027, 1, 3),
            )

    def test_zp_rok_po_vystaveni_ok(self):
        """366 dní je OK (leap year)."""
        d = _doklad(
            datum_vystaveni=date(2026, 1, 1),
            datum_zdanitelneho_plneni=date(2027, 1, 2),
        )
        assert d.datum_zdanitelneho_plneni == date(2027, 1, 2)


class TestValidacePartner:

    def test_none_ok(self):
        d = _doklad(partner_id=None)
        assert d.partner_id is None

    def test_kladny_ok(self):
        d = _doklad(partner_id=1)
        assert d.partner_id == 1

    def test_nula(self):
        with pytest.raises(ValidationError, match="kladný"):
            _doklad(partner_id=0)

    def test_zaporny(self):
        with pytest.raises(ValidationError, match="kladný"):
            _doklad(partner_id=-1)

    def test_str_type_error(self):
        with pytest.raises(TypeError, match="int nebo None"):
            _doklad(partner_id="abc")  # type: ignore[arg-type]

    def test_float_type_error(self):
        with pytest.raises(TypeError, match="int nebo None"):
            _doklad(partner_id=1.5)  # type: ignore[arg-type]


class TestValidacePopis:

    def test_501_znaku(self):
        with pytest.raises(ValidationError, match="max 500"):
            _doklad(popis="A" * 501)

    def test_500_znaku_ok(self):
        d = _doklad(popis="A" * 500)
        assert len(d.popis) == 500


class TestStavovyStroj:
    """Povolené a zakázané stavové přechody."""

    # --- Povolené přechody ---

    def test_novy_zauctuj(self):
        d = _doklad()
        d.zauctuj()
        assert d.stav == StavDokladu.ZAUCTOVANY

    def test_zauctovany_oznac_uhrazeny(self):
        d = _doklad()
        d.zauctuj()
        d.oznac_uhrazeny()
        assert d.stav == StavDokladu.UHRAZENY

    def test_zauctovany_castecne_uhrazeny(self):
        d = _doklad()
        d.zauctuj()
        d.oznac_castecne_uhrazeny()
        assert d.stav == StavDokladu.CASTECNE_UHRAZENY

    def test_castecne_uhrazeny_uhrazeny(self):
        d = _doklad()
        d.zauctuj()
        d.oznac_castecne_uhrazeny()
        d.oznac_uhrazeny()
        assert d.stav == StavDokladu.UHRAZENY

    def test_novy_stornuj(self):
        d = _doklad()
        d.stornuj()
        assert d.stav == StavDokladu.STORNOVANY

    def test_zauctovany_stornuj(self):
        d = _doklad()
        d.zauctuj()
        d.stornuj()
        assert d.stav == StavDokladu.STORNOVANY

    def test_castecne_uhrazeny_stornuj(self):
        d = _doklad()
        d.zauctuj()
        d.oznac_castecne_uhrazeny()
        d.stornuj()
        assert d.stav == StavDokladu.STORNOVANY

    # --- Zakázané přechody ---

    def test_novy_oznac_uhrazeny_zakazano(self):
        d = _doklad()
        with pytest.raises(ValidationError, match="novy"):
            d.oznac_uhrazeny()

    def test_novy_castecne_uhrazeny_zakazano(self):
        d = _doklad()
        with pytest.raises(ValidationError, match="novy"):
            d.oznac_castecne_uhrazeny()

    def test_uhrazeny_stornuj_zakazano(self):
        d = _doklad()
        d.zauctuj()
        d.oznac_uhrazeny()
        with pytest.raises(ValidationError, match="UHRAZENY"):
            d.stornuj()

    def test_stornovany_zauctuj_zakazano(self):
        d = _doklad()
        d.stornuj()
        with pytest.raises(ValidationError, match="stornovany"):
            d.zauctuj()

    def test_stornovany_stornuj_zakazano(self):
        d = _doklad()
        d.stornuj()
        with pytest.raises(ValidationError, match="stornovany"):
            d.stornuj()

    def test_dvojite_zauctuj_zakazano(self):
        d = _doklad()
        d.zauctuj()
        with pytest.raises(ValidationError, match="zauctovany"):
            d.zauctuj()

    def test_castecne_uhrazeny_znovu_zakazano(self):
        """CASTECNE_UHRAZENY → oznac_castecne_uhrazeny() → ValidationError."""
        d = _doklad()
        d.zauctuj()
        d.oznac_castecne_uhrazeny()
        with pytest.raises(ValidationError, match="castecne_uhrazeny"):
            d.oznac_castecne_uhrazeny()

    def test_uhrazeny_je_terminal(self):
        d = _doklad()
        d.zauctuj()
        d.oznac_uhrazeny()
        with pytest.raises(ValidationError):
            d.zauctuj()
        with pytest.raises(ValidationError):
            d.oznac_castecne_uhrazeny()


class TestEditace:

    def test_uprav_popis_novy(self):
        d = _doklad(popis="Původní")
        d.uprav_popis("Nový popis")
        assert d.popis == "Nový popis"

    def test_uprav_popis_zauctovany(self):
        d = _doklad()
        d.zauctuj()
        d.uprav_popis("Opravený popis")
        assert d.popis == "Opravený popis"

    def test_uprav_popis_stornovany_zakazano(self):
        d = _doklad()
        d.stornuj()
        with pytest.raises(ValidationError, match="stornovaný"):
            d.uprav_popis("Nový")

    def test_uprav_popis_none(self):
        d = _doklad(popis="Něco")
        d.uprav_popis(None)
        assert d.popis is None

    def test_uprav_splatnost_novy(self):
        d = _doklad(datum_vystaveni=date(2026, 1, 1))
        d.uprav_splatnost(date(2026, 2, 1))
        assert d.datum_splatnosti == date(2026, 2, 1)

    def test_uprav_splatnost_zauctovany_zakazano(self):
        d = _doklad()
        d.zauctuj()
        with pytest.raises(ValidationError, match="NOVY"):
            d.uprav_splatnost(date(2026, 6, 1))

    def test_uprav_splatnost_pred_vystavenim(self):
        d = _doklad(datum_vystaveni=date(2026, 3, 15))
        with pytest.raises(ValidationError, match="splatnosti"):
            d.uprav_splatnost(date(2026, 3, 1))

    def test_uprav_splatnost_none(self):
        d = _doklad(datum_splatnosti=date(2026, 6, 1))
        d.uprav_splatnost(None)
        assert d.datum_splatnosti is None


class TestEquality:

    def test_stejne_id_rovny(self):
        d1 = _doklad(id=1)
        d2 = _doklad(id=1, cislo="FP-999")
        assert d1 == d2

    def test_ruzne_id_nerovny(self):
        d1 = _doklad(id=1)
        d2 = _doklad(id=2)
        assert d1 != d2

    def test_bez_id_jen_identity(self):
        d1 = _doklad()
        d2 = _doklad()
        assert d1 != d2
        assert d1 == d1

    def test_ne_doklad_not_implemented(self):
        d = _doklad(id=1)
        assert d != "not a doklad"


class TestHash:

    def test_doklad_jako_klic(self):
        d = _doklad(id=1)
        slovnik = {d: "test"}
        assert slovnik[_doklad(id=1)] == "test"

    def test_bez_id_hash_identity(self):
        d1 = _doklad()
        d2 = _doklad()
        assert hash(d1) != hash(d2)


class TestRepr:

    def test_repr(self):
        d = _doklad(id=42)
        r = repr(d)
        assert "id=42" in r
        assert "FV-2026-001" in r
        assert "FV" in r
        assert "novy" in r
