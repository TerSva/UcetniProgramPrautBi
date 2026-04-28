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


class TestStornoZZaznamu:
    """Fáze 6.5: factory pro opravný (storno) předpis."""

    def test_jeden_zaznam(self):
        original = _zaznam(id=10, md="311", dal="601", castka_halire=1000000)
        p = UctovyPredpis.storno_z_zaznamu(
            (original,), datum=date(2026, 4, 15),
        )
        assert len(p.zaznamy) == 1
        s = p.zaznamy[0]
        # MD/Dal prohozené
        assert s.md_ucet == "601"
        assert s.dal_ucet == "311"
        # Částka kladná (Varianta A — nepoužíváme červený zápis)
        assert s.castka == Money(1000000)
        # Flag + FK
        assert s.je_storno is True
        assert s.stornuje_zaznam_id == 10
        # Datum = dnes, ne datum originálu
        assert s.datum == date(2026, 4, 15)
        # Popis má prefix
        assert s.popis == "Storno"
        # doklad_id zachován
        assert s.doklad_id == 1

    def test_popis_s_prefixem(self):
        original = _zaznam(id=10, popis="Tržba")
        p = UctovyPredpis.storno_z_zaznamu(
            (original,), datum=date(2026, 4, 15),
        )
        assert p.zaznamy[0].popis == "Storno: Tržba"

    def test_vicero_zaznamu(self):
        """FV s DPH: 2 zápisy → 2 protizápisy."""
        originaly = (
            _zaznam(id=1, md="311", dal="601", castka_halire=1000000,
                    popis="Základ"),
            _zaznam(id=2, md="311", dal="343", castka_halire=210000,
                    popis="DPH"),
        )
        p = UctovyPredpis.storno_z_zaznamu(
            originaly, datum=date(2026, 4, 15),
        )
        assert len(p.zaznamy) == 2
        assert p.zaznamy[0].stornuje_zaznam_id == 1
        assert p.zaznamy[0].md_ucet == "601"
        assert p.zaznamy[0].dal_ucet == "311"
        assert p.zaznamy[1].stornuje_zaznam_id == 2
        assert p.zaznamy[1].md_ucet == "343"
        assert p.zaznamy[1].dal_ucet == "311"

    def test_prazdny_seznam_vyhodi(self):
        with pytest.raises(ValidationError, match="prázdný"):
            UctovyPredpis.storno_z_zaznamu(
                (), datum=date(2026, 4, 15),
            )

    def test_bez_id_vyhodi(self):
        original = _zaznam()  # bez id
        with pytest.raises(ValidationError, match="persistovaný"):
            UctovyPredpis.storno_z_zaznamu(
                (original,), datum=date(2026, 4, 15),
            )

    def test_ruzny_doklad_id_vyhodi(self):
        o1 = _zaznam(id=1, doklad_id=1)
        o2 = _zaznam(id=2, doklad_id=2)
        with pytest.raises(ValidationError, match="různý doklad_id"):
            UctovyPredpis.storno_z_zaznamu(
                (o1, o2), datum=date(2026, 4, 15),
            )

    def test_popis_override_nahradi_default(self):
        """popis_override použije zadaný text místo 'Storno: {orig}'."""
        original = _zaznam(id=10, popis="Tržba")
        p = UctovyPredpis.storno_z_zaznamu(
            (original,), datum=date(2026, 4, 15),
            popis_override="Duplicitní zaúčtování",
        )
        assert p.zaznamy[0].popis == "Storno: Duplicitní zaúčtování"

    def test_popis_override_prazdny_string_pouzije_default(self):
        """Whitespace-only override → použije se default popis."""
        original = _zaznam(id=10, popis="Tržba")
        p = UctovyPredpis.storno_z_zaznamu(
            (original,), datum=date(2026, 4, 15),
            popis_override="   ",
        )
        assert p.zaznamy[0].popis == "Storno: Tržba"

    def test_popis_override_aplikuje_se_na_vsechny_zaznamy(self):
        """Při více originálech dostanou všechny storno zápisy stejný popis."""
        originaly = (
            _zaznam(id=1, md="311", dal="601", castka_halire=1000000,
                    popis="Tržba"),
            _zaznam(id=2, md="311", dal="343", castka_halire=210000,
                    popis="DPH 21%"),
        )
        p = UctovyPredpis.storno_z_zaznamu(
            originaly, datum=date(2026, 4, 15),
            popis_override="Chybná faktura",
        )
        for z in p.zaznamy:
            assert z.popis == "Storno: Chybná faktura"

    def test_uz_stornovany_vyhodi(self):
        original = UcetniZaznam(
            doklad_id=1, datum=date(2026, 4, 1),
            md_ucet="601", dal_ucet="311", castka=Money(100),
            id=42, je_storno=True, stornuje_zaznam_id=10,
        )
        with pytest.raises(ValidationError, match="stornovaný"):
            UctovyPredpis.storno_z_zaznamu(
                (original,), datum=date(2026, 4, 15),
            )

    def test_soucty_jsou_opacne(self):
        """Protizápis má MD originálu na Dal a naopak → po sečtení 0 dopad."""
        original = _zaznam(id=10, md="311", dal="601", castka_halire=1000000)
        p = UctovyPredpis.storno_z_zaznamu(
            (original,), datum=date(2026, 4, 15),
        )
        # Původní: MD 311, Dal 601 = +10 000 na 601 (výnos)
        # Protizápis: MD 601, Dal 311 = -10 000 na 601 (anulace)
        assert "601" in p.soucet_md
        assert "311" in p.soucet_dal
        assert p.celkova_castka == Money(1000000)
