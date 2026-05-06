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

    def test_uprav_castku_novy_czk(self):
        """NOVY CZK doklad — castka jde upravit."""
        d = _doklad()
        d.uprav_castku(Money.from_koruny("2500"))
        assert d.castka_celkem == Money.from_koruny("2500")

    def test_uprav_castku_zauctovany_zakazano(self):
        d = _doklad()
        d.zauctuj()
        with pytest.raises(ValidationError, match="NOVY"):
            d.uprav_castku(Money.from_koruny("999"))

    def test_uprav_castku_eur_vyzaduje_kurz_a_castka_mena(self):
        from decimal import Decimal as _D
        from domain.doklady.typy import Mena
        d = _doklad(
            mena=Mena.EUR,
            castka_mena=Money.from_koruny("100"),
            kurz=_D("25.00"),
        )
        # Změna na novou částku 200 EUR @ 25 = 5000 CZK
        d.uprav_castku(
            Money.from_koruny("5000"),
            castka_mena=Money.from_koruny("200"),
            kurz=_D("25.00"),
        )
        assert d.castka_celkem == Money.from_koruny("5000")
        assert d.castka_mena == Money.from_koruny("200")

    def test_uprav_castku_czk_nesmi_obsahovat_kurz(self):
        from decimal import Decimal as _D
        d = _doklad()  # default CZK
        with pytest.raises(ValidationError, match="CZK"):
            d.uprav_castku(
                Money.from_koruny("1000"),
                kurz=_D("25"),
            )

    def test_uprav_castku_zmena_mena_czk_na_eur(self):
        """Změna měny CZK → EUR musí mít kurz a castka_mena."""
        from decimal import Decimal as _D
        from domain.doklady.typy import Mena
        d = _doklad()  # default CZK
        d.uprav_castku(
            Money.from_koruny("2500"),
            castka_mena=Money.from_koruny("100"),
            kurz=_D("25.00"),
            nova_mena=Mena.EUR,
        )
        assert d.mena == Mena.EUR
        assert d.castka_celkem == Money.from_koruny("2500")
        assert d.castka_mena == Money.from_koruny("100")
        assert d.kurz == _D("25.00")

    def test_uprav_castku_zmena_mena_eur_na_czk_vyclisti_kurz(self):
        """Změna měny EUR → CZK vyčistí kurz a castka_mena."""
        from decimal import Decimal as _D
        from domain.doklady.typy import Mena
        d = _doklad(
            mena=Mena.EUR,
            castka_mena=Money.from_koruny("100"),
            kurz=_D("25"),
        )
        d.uprav_castku(
            Money.from_koruny("2500"),
            nova_mena=Mena.CZK,
        )
        assert d.mena == Mena.CZK
        assert d.castka_celkem == Money.from_koruny("2500")
        assert d.castka_mena is None
        assert d.kurz is None


class TestEditDatumVystaveni:

    def test_uprav_datum_novy(self):
        d = _doklad(datum_vystaveni=date(2026, 4, 1))
        d.uprav_datum_vystaveni(date(2025, 4, 1))
        assert d.datum_vystaveni == date(2025, 4, 1)

    def test_uprav_datum_zauctovany_povoleno(self):
        d = _doklad(datum_vystaveni=date(2026, 4, 1))
        d.zauctuj()
        d.uprav_datum_vystaveni(date(2025, 12, 31))
        assert d.datum_vystaveni == date(2025, 12, 31)

    def test_uprav_datum_castecne_uhrazeny_povoleno(self):
        d = _doklad(datum_vystaveni=date(2026, 4, 1))
        d.zauctuj()
        d.oznac_castecne_uhrazeny()
        d.uprav_datum_vystaveni(date(2025, 5, 1))
        assert d.datum_vystaveni == date(2025, 5, 1)

    def test_uprav_datum_uhrazeny_povoleno(self):
        """UHRAZENY je povolený — úhrada (BV) má vlastní datum, oprava
        data faktury úhradu neovlivní."""
        d = _doklad(datum_vystaveni=date(2026, 4, 1))
        d.zauctuj()
        d.oznac_uhrazeny()
        d.uprav_datum_vystaveni(date(2025, 12, 31))
        assert d.datum_vystaveni == date(2025, 12, 31)

    def test_uprav_datum_stornovany_zakazano(self):
        d = _doklad()
        d.zauctuj()
        d.stornuj()
        with pytest.raises(ValidationError, match="stornovany"):
            d.uprav_datum_vystaveni(date(2025, 1, 1))

    def test_uprav_datum_po_splatnosti_zakazano(self):
        d = _doklad(
            datum_vystaveni=date(2026, 4, 1),
            datum_splatnosti=date(2026, 5, 1),
        )
        # Pokus posunout vystavení AŽ ZA splatnost — invariant zlomený
        with pytest.raises(ValidationError, match="splatnosti"):
            d.uprav_datum_vystaveni(date(2026, 6, 1))


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


# ═══════════════════════════════════════════════════════════════
# Fáze 4.5: flag k_doreseni + poznamka_doreseni
# ═══════════════════════════════════════════════════════════════


class TestKDoreseniDefault:

    def test_default_false(self):
        d = _doklad()
        assert d.k_doreseni is False
        assert d.poznamka_doreseni is None


class TestKDoreseniKonstruktor:

    def test_flag_true(self):
        d = _doklad(k_doreseni=True)
        assert d.k_doreseni is True
        assert d.poznamka_doreseni is None

    def test_flag_true_s_poznamkou(self):
        d = _doklad(k_doreseni=True, poznamka_doreseni="chybí ICO")
        assert d.k_doreseni is True
        assert d.poznamka_doreseni == "chybí ICO"

    def test_neplatny_typ_string(self):
        with pytest.raises(TypeError, match="k_doreseni musí být bool"):
            _doklad(k_doreseni="ano")

    def test_neplatny_typ_int_1(self):
        with pytest.raises(TypeError, match="k_doreseni musí být bool"):
            _doklad(k_doreseni=1)

    def test_neplatny_typ_int_0(self):
        with pytest.raises(TypeError, match="k_doreseni musí být bool"):
            _doklad(k_doreseni=0)

    def test_neplatny_typ_none(self):
        with pytest.raises(TypeError, match="k_doreseni musí být bool"):
            _doklad(k_doreseni=None)

    def test_stornovany_nelze_flagnout(self):
        with pytest.raises(ValidationError, match="Stornované doklady"):
            _doklad(stav=StavDokladu.STORNOVANY, k_doreseni=True)

    def test_poznamka_bez_flagu(self):
        with pytest.raises(
            ValidationError, match="Poznámka k dořešení může existovat jen"
        ):
            _doklad(k_doreseni=False, poznamka_doreseni="něco")

    def test_poznamka_prilis_dlouha(self):
        with pytest.raises(
            ValidationError, match="Poznámka k dořešení max"
        ):
            _doklad(k_doreseni=True, poznamka_doreseni="x" * 501)

    def test_poznamka_500_znaku_ok(self):
        d = _doklad(k_doreseni=True, poznamka_doreseni="x" * 500)
        assert len(d.poznamka_doreseni) == 500


class TestOznacKDoreseni:

    def test_novy_doklad(self):
        d = _doklad()
        d.oznac_k_doreseni()
        assert d.k_doreseni is True
        assert d.poznamka_doreseni is None

    def test_s_poznamkou(self):
        d = _doklad()
        d.oznac_k_doreseni("chybí ICO")
        assert d.k_doreseni is True
        assert d.poznamka_doreseni == "chybí ICO"

    def test_zauctovany_lze_flagnout(self):
        """Scénář: pokladní lístek zaúčtován, chybí faktura."""
        d = _doklad(stav=StavDokladu.ZAUCTOVANY)
        d.oznac_k_doreseni("vymlátit fakturu od jednatele")
        assert d.k_doreseni is True
        assert d.poznamka_doreseni == "vymlátit fakturu od jednatele"

    def test_uhrazeny_lze_flagnout(self):
        d = _doklad(stav=StavDokladu.UHRAZENY)
        d.oznac_k_doreseni("chybí dokumentace úhrady")
        assert d.k_doreseni is True

    def test_stornovany_nelze(self):
        d = _doklad()
        d.stornuj()
        with pytest.raises(ValidationError, match="Stornované doklady"):
            d.oznac_k_doreseni()

    def test_idempotence_update_poznamky(self):
        """Opakované volání updatuje poznámku — není chyba."""
        d = _doklad()
        d.oznac_k_doreseni("verze 1")
        d.oznac_k_doreseni("verze 2")
        assert d.k_doreseni is True
        assert d.poznamka_doreseni == "verze 2"

    def test_poznamka_prilis_dlouha(self):
        d = _doklad()
        with pytest.raises(ValidationError, match="Poznámka k dořešení max"):
            d.oznac_k_doreseni("x" * 501)


class TestDores:

    def test_zrusi_flag_i_poznamku(self):
        d = _doklad(k_doreseni=True, poznamka_doreseni="něco")
        d.dores()
        assert d.k_doreseni is False
        assert d.poznamka_doreseni is None

    def test_idempotence_na_nefragnutem(self):
        """dores() na doklad bez flagu je no-op, ne chyba."""
        d = _doklad()
        d.dores()  # nesmí vyhodit
        assert d.k_doreseni is False
        assert d.poznamka_doreseni is None

    def test_funguje_ve_vsech_stavech(self):
        for stav in [
            StavDokladu.NOVY,
            StavDokladu.ZAUCTOVANY,
            StavDokladu.CASTECNE_UHRAZENY,
            StavDokladu.UHRAZENY,
        ]:
            d = _doklad(stav=stav, k_doreseni=True, poznamka_doreseni="x")
            d.dores()
            assert d.k_doreseni is False


class TestUpravPoznamkuDoreseni:

    def test_na_flagnutem_zmeni_poznamku(self):
        d = _doklad(k_doreseni=True, poznamka_doreseni="stará")
        d.uprav_poznamku_doreseni("nová")
        assert d.k_doreseni is True
        assert d.poznamka_doreseni == "nová"

    def test_na_none_flag_zustava(self):
        d = _doklad(k_doreseni=True, poznamka_doreseni="původní")
        d.uprav_poznamku_doreseni(None)
        assert d.k_doreseni is True
        assert d.poznamka_doreseni is None

    def test_na_nefragnutem_raises(self):
        d = _doklad()
        with pytest.raises(
            ValidationError, match="Nelze upravovat poznámku"
        ):
            d.uprav_poznamku_doreseni("cokoli")

    def test_na_nefragnutem_none_taky_raises(self):
        """Konzistence: nelze sahat na poznámku nefragnutého dokladu."""
        d = _doklad()
        with pytest.raises(
            ValidationError, match="Nelze upravovat poznámku"
        ):
            d.uprav_poznamku_doreseni(None)

    def test_prilis_dlouha(self):
        d = _doklad(k_doreseni=True)
        with pytest.raises(ValidationError, match="Poznámka k dořešení max"):
            d.uprav_poznamku_doreseni("x" * 501)


class TestStornoClearujeFlag:

    def test_storno_auto_dores(self):
        d = _doklad(k_doreseni=True, poznamka_doreseni="zapomenout")
        d.stornuj()
        assert d.stav == StavDokladu.STORNOVANY
        assert d.k_doreseni is False
        assert d.poznamka_doreseni is None

    def test_storno_uhrazeneho_flag_zustava(self):
        """Atomicita: když stornuj() selže, flag se nesmí změnit."""
        d = _doklad(stav=StavDokladu.UHRAZENY)
        d.oznac_k_doreseni("chybí dokumentace")
        assert d.k_doreseni is True

        with pytest.raises(ValidationError):
            d.stornuj()

        # Flag i poznámka zůstaly beze změny
        assert d.stav == StavDokladu.UHRAZENY
        assert d.k_doreseni is True
        assert d.poznamka_doreseni == "chybí dokumentace"


class TestStavFlagKombinace:

    def test_povolene_kombinace(self):
        """NOVY, ZAUCTOVANY, CASTECNE_UHRAZENY, UHRAZENY + flag jsou OK."""
        for stav in [
            StavDokladu.NOVY,
            StavDokladu.ZAUCTOVANY,
            StavDokladu.CASTECNE_UHRAZENY,
            StavDokladu.UHRAZENY,
        ]:
            d = _doklad(stav=stav, k_doreseni=True, poznamka_doreseni="x")
            assert d.k_doreseni is True
            assert d.stav == stav

    def test_stornovany_flag_zakazano(self):
        with pytest.raises(ValidationError):
            _doklad(stav=StavDokladu.STORNOVANY, k_doreseni=True)


class TestZalohovaFaktura:
    """Zálohové faktury (ZF) — vyžadují je_vystavena pro rozlišení směru."""

    def test_zf_vystavena(self):
        d = _doklad(typ=TypDokladu.ZALOHA_FAKTURA, je_vystavena=True)
        assert d.je_vystavena is True

    def test_zf_prijata(self):
        d = _doklad(typ=TypDokladu.ZALOHA_FAKTURA, je_vystavena=False)
        assert d.je_vystavena is False

    def test_zf_bez_je_vystavena_selze(self):
        with pytest.raises(ValidationError, match="je_vystavena"):
            _doklad(typ=TypDokladu.ZALOHA_FAKTURA)

    def test_non_zf_je_vystavena_je_none(self):
        """Pro non-ZF typy je je_vystavena None — směr derivovaný z typu."""
        d = _doklad(typ=TypDokladu.FAKTURA_VYDANA)
        assert d.je_vystavena is None
        d = _doklad(typ=TypDokladu.FAKTURA_PRIJATA)
        assert d.je_vystavena is None

    def test_zf_nesmi_byt_typ_string(self):
        with pytest.raises(TypeError):
            _doklad(typ=TypDokladu.ZALOHA_FAKTURA, je_vystavena="ano")  # type: ignore[arg-type]

    def test_zf_lze_oznac_uhrazeny_z_novy(self):
        """ZF se neúčtuje — přechod NOVY → UHRAZENY je povolený."""
        d = _doklad(typ=TypDokladu.ZALOHA_FAKTURA, je_vystavena=True)
        assert d.stav == StavDokladu.NOVY
        d.oznac_uhrazeny()
        assert d.stav == StavDokladu.UHRAZENY

    def test_zf_lze_oznac_castecne_uhrazeny_z_novy(self):
        """Částečná platba ZF z NOVY → CASTECNE_UHRAZENY."""
        d = _doklad(typ=TypDokladu.ZALOHA_FAKTURA, je_vystavena=False)
        assert d.stav == StavDokladu.NOVY
        d.oznac_castecne_uhrazeny()
        assert d.stav == StavDokladu.CASTECNE_UHRAZENY

    def test_fv_nelze_oznac_uhrazeny_z_novy(self):
        """Pro FV/FP zůstává: NOVY → UHRAZENY je zakázán (přes ZAUCTOVANY)."""
        d = _doklad(typ=TypDokladu.FAKTURA_VYDANA)
        with pytest.raises(ValidationError):
            d.oznac_uhrazeny()
