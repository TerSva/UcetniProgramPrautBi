"""Testy pro Ucet entitu — pure Python, bez DB."""

import pytest

from domain.shared.errors import ValidationError
from domain.ucetnictvi.typy import TypUctu
from domain.ucetnictvi.ucet import Ucet


def _ucet(**kwargs) -> Ucet:
    defaults = dict(cislo="311", nazev="Pohledávky", typ=TypUctu.AKTIVA)
    defaults.update(kwargs)
    return Ucet(**defaults)


def _analytika(**kwargs) -> Ucet:
    defaults = dict(
        cislo="501.100", nazev="Drobný DHM",
        typ=TypUctu.NAKLADY, parent_kod="501",
    )
    defaults.update(kwargs)
    return Ucet(**defaults)


class TestKonstruktor:

    def test_validni(self):
        u = _ucet()
        assert u.cislo == "311"
        assert u.nazev == "Pohledávky"
        assert u.typ == TypUctu.AKTIVA
        assert u.je_aktivni is True
        assert u.parent_kod is None
        assert u.popis is None

    def test_neaktivni(self):
        u = _ucet(je_aktivni=False)
        assert u.je_aktivni is False

    def test_3_cislice(self):
        u = _ucet(cislo="211")
        assert u.cislo == "211"

    def test_s_popisem(self):
        u = _ucet(popis="Testovací popis")
        assert u.popis == "Testovací popis"


class TestValidaceCislo:

    def test_prazdne(self):
        with pytest.raises(ValidationError, match="prázdné"):
            _ucet(cislo="")

    def test_jen_mezery(self):
        with pytest.raises(ValidationError, match="prázdné"):
            _ucet(cislo="   ")

    def test_2_cislice(self):
        with pytest.raises(ValidationError, match="3 číslice"):
            _ucet(cislo="31")

    def test_4_cislice_neni_synteticky(self):
        with pytest.raises(ValidationError, match="3 číslice"):
            _ucet(cislo="3111")

    def test_pismena(self):
        with pytest.raises(ValidationError, match="3 číslice"):
            _ucet(cislo="ABC")

    def test_mezera(self):
        with pytest.raises(ValidationError, match="3 číslice"):
            _ucet(cislo="31 1")

    def test_tecka_bez_parent_kod(self):
        with pytest.raises(ValidationError, match="parent_kod"):
            _ucet(cislo="311.10")


class TestAnalytika:

    def test_validni_analytika(self):
        u = _analytika()
        assert u.cislo == "501.100"
        assert u.is_analytic is True
        assert u.syntetic_kod == "501"
        assert u.parent_kod == "501"

    def test_parent_kod_required(self):
        with pytest.raises(ValidationError, match="parent_kod"):
            Ucet(cislo="501.100", nazev="Test", typ=TypUctu.NAKLADY)

    def test_parent_kod_mismatch(self):
        with pytest.raises(ValidationError, match="neodpovídá"):
            Ucet(
                cislo="501.100", nazev="Test",
                typ=TypUctu.NAKLADY, parent_kod="518",
            )

    def test_synteticky_nema_parent(self):
        with pytest.raises(ValidationError, match="nesmí mít parent_kod"):
            Ucet(
                cislo="501", nazev="Test",
                typ=TypUctu.NAKLADY, parent_kod="501",
            )

    def test_is_analytic_synteticky(self):
        u = _ucet()
        assert u.is_analytic is False

    def test_syntetic_kod_synteticky(self):
        u = _ucet(cislo="311")
        assert u.syntetic_kod == "311"

    def test_syntetic_kod_analyticky(self):
        u = _analytika(cislo="321.002", parent_kod="321")
        assert u.syntetic_kod == "321"

    def test_bad_analytic_format(self):
        with pytest.raises(ValidationError, match="Neplatný kód analytiky"):
            Ucet(
                cislo="50.1", nazev="Test",
                typ=TypUctu.NAKLADY, parent_kod="50",
            )


class TestValidaceNazev:

    def test_prazdny(self):
        with pytest.raises(ValidationError, match="prázdný"):
            _ucet(nazev="")

    def test_jen_mezery(self):
        with pytest.raises(ValidationError, match="prázdný"):
            _ucet(nazev="   ")

    def test_201_znaku(self):
        with pytest.raises(ValidationError, match="max 200"):
            _ucet(nazev="A" * 201)

    def test_200_znaku_ok(self):
        u = _ucet(nazev="A" * 200)
        assert len(u.nazev) == 200


class TestDeaktivace:

    def test_deaktivuj(self):
        u = _ucet()
        u.deaktivuj()
        assert u.je_aktivni is False

    def test_aktivuj(self):
        u = _ucet(je_aktivni=False)
        u.aktivuj()
        assert u.je_aktivni is True

    def test_deaktivuj_uz_neaktivni(self):
        u = _ucet(je_aktivni=False)
        u.deaktivuj()
        assert u.je_aktivni is False


class TestUpravNazev:

    def test_zmeni_nazev(self):
        u = _ucet()
        u.uprav_nazev("Nový název")
        assert u.nazev == "Nový název"

    def test_prazdny_nazev(self):
        u = _ucet()
        with pytest.raises(ValidationError, match="prázdný"):
            u.uprav_nazev("")

    def test_prilis_dlouhy(self):
        u = _ucet()
        with pytest.raises(ValidationError, match="max 200"):
            u.uprav_nazev("X" * 201)


class TestUpravPopis:

    def test_zmeni_popis(self):
        u = _ucet()
        u.uprav_popis("Nový popis")
        assert u.popis == "Nový popis"

    def test_smaze_popis(self):
        u = _ucet(popis="Starý")
        u.uprav_popis(None)
        assert u.popis is None


class TestEquality:

    def test_stejne_cislo(self):
        u1 = Ucet(cislo="311", nazev="A", typ=TypUctu.AKTIVA)
        u2 = Ucet(cislo="311", nazev="B", typ=TypUctu.PASIVA)
        assert u1 == u2

    def test_ruzne_cislo(self):
        u1 = _ucet(cislo="311")
        u2 = _ucet(cislo="321")
        assert u1 != u2

    def test_ne_ucet(self):
        u = _ucet()
        assert u != "311"


class TestHash:

    def test_jako_klic(self):
        u = _ucet(cislo="311")
        slovnik = {u: "test"}
        assert slovnik[Ucet(cislo="311", nazev="X", typ=TypUctu.PASIVA)] == "test"

    def test_v_setu(self):
        u1 = _ucet(cislo="311")
        u2 = _ucet(cislo="311")
        assert len({u1, u2}) == 1


class TestRepr:

    def test_repr(self):
        u = _ucet()
        r = repr(u)
        assert "311" in r
        assert "Pohledávky" in r
        assert "A" in r
