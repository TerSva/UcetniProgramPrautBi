"""Testy pro Ucet entitu — pure Python, bez DB."""

import pytest

from domain.shared.errors import ValidationError
from domain.ucetnictvi.typy import TypUctu
from domain.ucetnictvi.ucet import Ucet


def _ucet(**kwargs) -> Ucet:
    defaults = dict(cislo="311", nazev="Pohledávky", typ=TypUctu.AKTIVA)
    defaults.update(kwargs)
    return Ucet(**defaults)


class TestKonstruktor:

    def test_validni(self):
        u = _ucet()
        assert u.cislo == "311"
        assert u.nazev == "Pohledávky"
        assert u.typ == TypUctu.AKTIVA
        assert u.je_aktivni is True

    def test_neaktivni(self):
        u = _ucet(je_aktivni=False)
        assert u.je_aktivni is False

    def test_6_cislic(self):
        u = _ucet(cislo="311100")
        assert u.cislo == "311100"

    def test_3_cislice(self):
        u = _ucet(cislo="211")
        assert u.cislo == "211"


class TestValidaceCislo:

    def test_prazdne(self):
        with pytest.raises(ValidationError, match="prázdné"):
            _ucet(cislo="")

    def test_jen_mezery(self):
        with pytest.raises(ValidationError, match="prázdné"):
            _ucet(cislo="   ")

    def test_2_cislice(self):
        with pytest.raises(ValidationError, match="3-6"):
            _ucet(cislo="31")

    def test_7_cislic(self):
        with pytest.raises(ValidationError, match="3-6"):
            _ucet(cislo="3111001")

    def test_pismena(self):
        with pytest.raises(ValidationError, match="3-6"):
            _ucet(cislo="ABC")

    def test_tecka(self):
        with pytest.raises(ValidationError, match="3-6"):
            _ucet(cislo="311.10")

    def test_mezera(self):
        with pytest.raises(ValidationError, match="3-6"):
            _ucet(cislo="31 1")


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
