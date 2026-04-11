"""Testy pro UctovyPredpis — srdce podvojného účetnictví."""

from datetime import date

import pytest

from domain.shared.errors import ValidationError
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis


def _zaznam(md="311", dal="601", castka_halire=1000000, **kwargs) -> UcetniZaznam:
    defaults = dict(
        doklad_id=1,
        datum=date(2026, 4, 1),
        md_ucet=md,
        dal_ucet=dal,
        castka=Money(castka_halire),
    )
    defaults.update(kwargs)
    return UcetniZaznam(**defaults)


class TestJednoduchyPredpis:

    def test_validni(self):
        p = UctovyPredpis.jednoduchy(
            doklad_id=1,
            datum=date(2026, 4, 1),
            md_ucet="311",
            dal_ucet="601",
            castka=Money(1000000),
        )
        assert len(p.zaznamy) == 1
        assert p.doklad_id == 1
        assert p.celkova_castka == Money(1000000)

    def test_s_popisem(self):
        p = UctovyPredpis.jednoduchy(
            doklad_id=1,
            datum=date(2026, 4, 1),
            md_ucet="311",
            dal_ucet="602",
            castka=Money(50000),
            popis="Služby",
        )
        assert p.zaznamy[0].popis == "Služby"


class TestFakturaSDph:

    def test_dva_zapisy_validni(self):
        """FV 12 100 Kč: základ 10 000 + DPH 21% = 2 100."""
        z1 = _zaznam(md="311", dal="601", castka_halire=1000000)
        z2 = _zaznam(md="311", dal="343", castka_halire=210000)
        p = UctovyPredpis(doklad_id=1, zaznamy=(z1, z2))
        assert p.celkova_castka == Money(1210000)

    def test_soucet_md(self):
        z1 = _zaznam(md="311", dal="601", castka_halire=1000000)
        z2 = _zaznam(md="311", dal="343", castka_halire=210000)
        p = UctovyPredpis(doklad_id=1, zaznamy=(z1, z2))
        assert p.soucet_md == {"311": Money(1210000)}

    def test_soucet_dal(self):
        z1 = _zaznam(md="311", dal="601", castka_halire=1000000)
        z2 = _zaznam(md="311", dal="343", castka_halire=210000)
        p = UctovyPredpis(doklad_id=1, zaznamy=(z1, z2))
        assert p.soucet_dal == {"601": Money(1000000), "343": Money(210000)}


class TestValidace:

    def test_prazdny_zaznamy(self):
        with pytest.raises(ValidationError, match="alespoň jeden"):
            UctovyPredpis(doklad_id=1, zaznamy=())

    def test_mix_doklad_id(self):
        z1 = _zaznam(doklad_id=1)
        z2 = UcetniZaznam(
            doklad_id=2, datum=date(2026, 4, 1),
            md_ucet="311", dal_ucet="343", castka=Money(100),
        )
        with pytest.raises(ValidationError, match="doklad_id=2"):
            UctovyPredpis(doklad_id=1, zaznamy=(z1, z2))

    def test_mix_datumu(self):
        z1 = _zaznam(datum=date(2026, 4, 1))
        z2 = UcetniZaznam(
            doklad_id=1, datum=date(2026, 4, 2),
            md_ucet="311", dal_ucet="343", castka=Money(100),
        )
        with pytest.raises(ValidationError, match="různá data"):
            UctovyPredpis(doklad_id=1, zaznamy=(z1, z2))

    def test_duplicitni_zapis(self):
        """Dva identické záznamy → ValidationError."""
        z1 = _zaznam(md="311", dal="601", castka_halire=1000000)
        z2 = _zaznam(md="311", dal="601", castka_halire=1000000)
        with pytest.raises(ValidationError, match="Duplicitní"):
            UctovyPredpis(doklad_id=1, zaznamy=(z1, z2))

    def test_ruzna_castka_neni_duplicita(self):
        """Stejné účty ale jiná částka — není duplicita."""
        z1 = _zaznam(md="311", dal="601", castka_halire=1000000)
        z2 = _zaznam(md="311", dal="601", castka_halire=500000)
        p = UctovyPredpis(doklad_id=1, zaznamy=(z1, z2))
        assert len(p.zaznamy) == 2

    def test_stejne_ucty_jiny_popis_neni_duplicita(self):
        """Stejné účty a částka ale jiný popis — není duplicita."""
        z1 = _zaznam(md="311", dal="601", castka_halire=1000000, popis="A")
        z2 = _zaznam(md="311", dal="601", castka_halire=1000000, popis="B")
        p = UctovyPredpis(doklad_id=1, zaznamy=(z1, z2))
        assert len(p.zaznamy) == 2


class TestStornoScenar:

    def test_prohozene_strany_validni(self):
        """Storno = prohozené MD/Dal — validní předpis."""
        z = UcetniZaznam(
            doklad_id=1, datum=date(2026, 4, 1),
            md_ucet="601", dal_ucet="311", castka=Money(1000000),
        )
        p = UctovyPredpis(doklad_id=1, zaznamy=(z,))
        assert p.celkova_castka == Money(1000000)


class TestCelkovaCastka:

    def test_vice_zapisu(self):
        z1 = _zaznam(md="311", dal="601", castka_halire=1000000)
        z2 = _zaznam(md="311", dal="343", castka_halire=210000)
        z3 = _zaznam(md="518", dal="321", castka_halire=50000, popis="Služba")
        p = UctovyPredpis(doklad_id=1, zaznamy=(z1, z2, z3))
        assert p.celkova_castka == Money(1260000)


class TestFrozen:

    def test_immutable(self):
        p = UctovyPredpis.jednoduchy(
            doklad_id=1, datum=date(2026, 4, 1),
            md_ucet="311", dal_ucet="601", castka=Money(100),
        )
        with pytest.raises(AttributeError):
            p.doklad_id = 2  # type: ignore[misc]
