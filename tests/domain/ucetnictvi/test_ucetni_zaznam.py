"""Testy pro UcetniZaznam — frozen dataclass, immutable."""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from domain.shared.errors import ValidationError
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam


def _zaznam(**kwargs) -> UcetniZaznam:
    defaults = dict(
        doklad_id=1,
        datum=date(2026, 4, 1),
        md_ucet="311",
        dal_ucet="601",
        castka=Money(1000000),
    )
    defaults.update(kwargs)
    return UcetniZaznam(**defaults)


class TestKonstruktor:

    def test_validni(self):
        z = _zaznam()
        assert z.doklad_id == 1
        assert z.datum == date(2026, 4, 1)
        assert z.md_ucet == "311"
        assert z.dal_ucet == "601"
        assert z.castka == Money(1000000)
        assert z.popis is None
        assert z.id is None

    def test_s_popisem(self):
        z = _zaznam(popis="Tržba za služby")
        assert z.popis == "Tržba za služby"

    def test_s_id(self):
        z = _zaznam(id=42)
        assert z.id == 42

    def test_6_cislic_ucet(self):
        z = _zaznam(md_ucet="311100", dal_ucet="601000")
        assert z.md_ucet == "311100"


class TestValidaceDokladId:

    def test_nula(self):
        with pytest.raises(ValidationError, match="kladný"):
            _zaznam(doklad_id=0)

    def test_zaporny(self):
        with pytest.raises(ValidationError, match="kladný"):
            _zaznam(doklad_id=-1)

    def test_bool_true(self):
        with pytest.raises(ValidationError, match="kladný"):
            _zaznam(doklad_id=True)

    def test_bool_false(self):
        with pytest.raises(ValidationError, match="kladný"):
            _zaznam(doklad_id=False)


class TestValidaceUctu:

    def test_md_prazdny(self):
        with pytest.raises(ValidationError, match="md_ucet"):
            _zaznam(md_ucet="")

    def test_dal_prazdny(self):
        with pytest.raises(ValidationError, match="dal_ucet"):
            _zaznam(dal_ucet="")

    def test_md_pismena(self):
        with pytest.raises(ValidationError, match="md_ucet"):
            _zaznam(md_ucet="ABC")

    def test_md_2_cislice(self):
        with pytest.raises(ValidationError, match="md_ucet"):
            _zaznam(md_ucet="31")

    def test_md_7_cislic(self):
        with pytest.raises(ValidationError, match="md_ucet"):
            _zaznam(md_ucet="3111001")

    def test_stejny_md_dal(self):
        with pytest.raises(ValidationError, match="sám na sebe"):
            _zaznam(md_ucet="311", dal_ucet="311")


class TestValidaceCastka:

    def test_int_misto_money(self):
        with pytest.raises(TypeError, match="Money"):
            _zaznam(castka=10000)

    def test_nulova(self):
        with pytest.raises(ValidationError, match="kladná"):
            _zaznam(castka=Money(0))

    def test_zaporna(self):
        with pytest.raises(ValidationError, match="kladná"):
            _zaznam(castka=Money(-100))


class TestValidacePopis:

    def test_501_znaku(self):
        with pytest.raises(ValidationError, match="max 500"):
            _zaznam(popis="A" * 501)

    def test_500_znaku_ok(self):
        z = _zaznam(popis="A" * 500)
        assert len(z.popis) == 500


class TestValidaceId:

    def test_nula(self):
        with pytest.raises(ValidationError, match="id"):
            _zaznam(id=0)

    def test_zaporny(self):
        with pytest.raises(ValidationError, match="id"):
            _zaznam(id=-1)

    def test_bool(self):
        with pytest.raises(ValidationError, match="id"):
            _zaznam(id=True)


class TestFrozen:

    def test_castka_immutable(self):
        z = _zaznam()
        with pytest.raises(FrozenInstanceError):
            z.castka = Money(999)  # type: ignore[misc]

    def test_md_ucet_immutable(self):
        z = _zaznam()
        with pytest.raises(FrozenInstanceError):
            z.md_ucet = "999"  # type: ignore[misc]


class TestWithId:

    def test_vraci_novou_instanci(self):
        z = _zaznam()
        z2 = z.with_id(42)
        assert z2.id == 42
        assert z.id is None  # original nezměněn

    def test_zachovava_data(self):
        z = _zaznam(popis="test", doklad_id=5)
        z2 = z.with_id(10)
        assert z2.doklad_id == 5
        assert z2.popis == "test"
        assert z2.castka == z.castka


class TestHashable:

    def test_v_setu(self):
        z1 = _zaznam(id=1)
        z2 = _zaznam(id=2)
        assert len({z1, z2}) == 2

    def test_jako_klic(self):
        z = _zaznam(id=1)
        d = {z: "value"}
        assert d[z] == "value"


class TestStornoFlagy:
    """Fáze 6.5: je_storno + stornuje_zaznam_id."""

    def test_original_ma_vychozi_hodnoty(self):
        z = _zaznam()
        assert z.je_storno is False
        assert z.stornuje_zaznam_id is None

    def test_storno_zaznam_validni(self):
        z = _zaznam(je_storno=True, stornuje_zaznam_id=42)
        assert z.je_storno is True
        assert z.stornuje_zaznam_id == 42

    def test_je_storno_bez_stornuje_id_vyhodi(self):
        with pytest.raises(ValidationError, match="stornuje_zaznam_id"):
            _zaznam(je_storno=True)

    def test_stornuje_id_bez_je_storno_vyhodi(self):
        with pytest.raises(ValidationError, match="jen u storno"):
            _zaznam(stornuje_zaznam_id=7)

    def test_je_storno_non_bool(self):
        with pytest.raises(ValidationError, match="je_storno"):
            _zaznam(je_storno=1, stornuje_zaznam_id=5)  # type: ignore[arg-type]

    def test_stornuje_id_nula_vyhodi(self):
        with pytest.raises(ValidationError, match="stornuje_zaznam_id"):
            _zaznam(je_storno=True, stornuje_zaznam_id=0)

    def test_stornuje_id_zaporny_vyhodi(self):
        with pytest.raises(ValidationError, match="stornuje_zaznam_id"):
            _zaznam(je_storno=True, stornuje_zaznam_id=-1)

    def test_with_id_zachova_storno_pole(self):
        z = _zaznam(
            md_ucet="601", dal_ucet="311",
            je_storno=True, stornuje_zaznam_id=42,
        )
        z2 = z.with_id(100)
        assert z2.id == 100
        assert z2.je_storno is True
        assert z2.stornuje_zaznam_id == 42
