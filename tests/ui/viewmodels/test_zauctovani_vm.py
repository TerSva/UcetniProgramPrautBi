"""Testy pro ZauctovaniViewModel — pure Python, bez Qt."""

from __future__ import annotations

from datetime import date

from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import PodvojnostError
from domain.shared.money import Money
from domain.ucetnictvi.typy import TypUctu
from services.commands.zauctovat_doklad import ZauctovatDokladInput
from services.queries.doklady_list import DokladyListItem
from services.queries.uctova_osnova import UcetItem
from ui.viewmodels.zauctovani_vm import PredpisRadek, ZauctovaniViewModel


# ─── Stubs ────────────────────────────────────────────────────────────


class _StubOsnovaQuery:
    def __init__(self, ucty: list[UcetItem]):
        self._ucty = ucty

    def execute(self, jen_aktivni: bool = True) -> list[UcetItem]:
        return list(self._ucty)


class _StubZauctovatCommand:
    def __init__(self, returned: DokladyListItem):
        self.returned = returned
        self.calls: list[ZauctovatDokladInput] = []

    def execute(self, data: ZauctovatDokladInput) -> DokladyListItem:
        self.calls.append(data)
        return self.returned


class _ErrorZauctovatCommand:
    def __init__(self, exc: Exception):
        self.exc = exc

    def execute(self, data: ZauctovatDokladInput) -> DokladyListItem:
        raise self.exc


def _sample_doklad(
    castka: str = "12100",
    stav: StavDokladu = StavDokladu.NOVY,
) -> DokladyListItem:
    return DokladyListItem(
        id=7,
        cislo="FV-2026-001",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 3, 1),
        datum_splatnosti=None,
        partner_id=None, partner_nazev=None,
        castka_celkem=Money.from_koruny(castka),
        stav=stav,
        k_doreseni=False,
        poznamka_doreseni=None,
        popis=None,
    )


def _sample_ucty() -> list[UcetItem]:
    return [
        UcetItem(cislo="311", nazev="Odběratelé", typ=TypUctu.AKTIVA),
        UcetItem(cislo="343", nazev="DPH", typ=TypUctu.PASIVA),
        UcetItem(cislo="601", nazev="Tržby", typ=TypUctu.VYNOSY),
    ]


def _zauctovany_result() -> DokladyListItem:
    return _sample_doklad(stav=StavDokladu.ZAUCTOVANY)


# ─── Tests ────────────────────────────────────────────────────────────


class TestLoad:

    def test_nacte_ucty(self):
        vm = ZauctovaniViewModel(
            doklad=_sample_doklad(),
            uctova_osnova_query=_StubOsnovaQuery(_sample_ucty()),
            zauctovat_command=_StubZauctovatCommand(_zauctovany_result()),
        )
        vm.load()
        assert len(vm.ucty) == 3
        assert vm.is_loaded is True

    def test_prefilluje_jeden_radek_s_celkovou_castkou(self):
        vm = ZauctovaniViewModel(
            doklad=_sample_doklad("5000"),
            uctova_osnova_query=_StubOsnovaQuery(_sample_ucty()),
            zauctovat_command=_StubZauctovatCommand(_zauctovany_result()),
        )
        vm.load()
        assert len(vm.radky) == 1
        assert vm.radky[0].castka == Money.from_koruny("5000")
        assert vm.radky[0].md_ucet == ""
        assert vm.radky[0].dal_ucet == ""

    def test_opakovany_load_neprepise_radky(self):
        vm = ZauctovaniViewModel(
            doklad=_sample_doklad(),
            uctova_osnova_query=_StubOsnovaQuery(_sample_ucty()),
            zauctovat_command=_StubZauctovatCommand(_zauctovany_result()),
        )
        vm.load()
        vm.update_row(0, md_ucet="311", dal_ucet="601")
        vm.load()  # znovu
        assert vm.radky[0].md_ucet == "311"


class TestRowManipulation:

    def _vm(self):
        vm = ZauctovaniViewModel(
            doklad=_sample_doklad("12100"),
            uctova_osnova_query=_StubOsnovaQuery(_sample_ucty()),
            zauctovat_command=_StubZauctovatCommand(_zauctovany_result()),
        )
        vm.load()
        return vm

    def test_update_row(self):
        vm = self._vm()
        vm.update_row(0, md_ucet="311", dal_ucet="601")
        assert vm.radky[0].md_ucet == "311"
        assert vm.radky[0].dal_ucet == "601"
        assert vm.radky[0].castka == Money.from_koruny("12100")

    def test_add_row_s_rozdilem(self):
        vm = self._vm()
        # Sníž první řádek, pak přidej druhý s rozdílem
        vm.update_row(0, castka=Money.from_koruny("10000"))
        vm.add_row()
        assert len(vm.radky) == 2
        assert vm.radky[1].castka == Money.from_koruny("2100")

    def test_remove_row(self):
        vm = self._vm()
        vm.add_row()
        vm.remove_row(0)
        assert len(vm.radky) == 1

    def test_update_row_invalid_index(self):
        vm = self._vm()
        vm.update_row(99, md_ucet="X")  # neselže
        assert vm.radky[0].md_ucet == ""


class TestComputed:

    def _vm(self, castka: str = "12100"):
        vm = ZauctovaniViewModel(
            doklad=_sample_doklad(castka),
            uctova_osnova_query=_StubOsnovaQuery(_sample_ucty()),
            zauctovat_command=_StubZauctovatCommand(_zauctovany_result()),
        )
        vm.load()
        return vm

    def test_podvojne_s_jednim_radkem(self):
        vm = self._vm("1000")
        vm.update_row(0, md_ucet="311", dal_ucet="601")
        assert vm.je_podvojne is True
        assert vm.rozdil == Money.zero()

    def test_nepodvojne_kdyz_castka_nizsi(self):
        vm = self._vm("1000")
        vm.update_row(0, castka=Money.from_koruny("500"))
        assert vm.je_podvojne is False
        assert vm.rozdil == Money.from_koruny("500")

    def test_je_validni_bez_uctu_false(self):
        vm = self._vm("1000")
        assert vm.je_validni is False

    def test_je_validni_s_uctama_a_podvojnosti_true(self):
        vm = self._vm("1000")
        vm.update_row(0, md_ucet="311", dal_ucet="601")
        assert vm.je_validni is True

    def test_je_validni_false_s_nulovou_castkou(self):
        vm = self._vm("1000")
        vm.update_row(0, md_ucet="311", dal_ucet="601",
                      castka=Money.zero())
        assert vm.je_validni is False


class TestSubmit:

    def _valid_vm(self):
        vm = ZauctovaniViewModel(
            doklad=_sample_doklad("1000"),
            uctova_osnova_query=_StubOsnovaQuery(_sample_ucty()),
            zauctovat_command=_StubZauctovatCommand(_zauctovany_result()),
        )
        vm.load()
        vm.update_row(0, md_ucet="311", dal_ucet="601")
        return vm

    def test_uspesny_submit(self):
        vm = self._valid_vm()
        item = vm.submit()
        assert item is not None
        assert item.stav == StavDokladu.ZAUCTOVANY
        assert vm.posted_item is item
        assert vm.error is None

    def test_neplatny_submit_vraci_none(self):
        vm = self._valid_vm()
        vm.update_row(0, castka=Money.from_koruny("500"))  # nepodvojné
        assert vm.submit() is None
        assert vm.error is not None

    def test_command_vyhodi_podvojnost_error(self):
        vm = ZauctovaniViewModel(
            doklad=_sample_doklad("1000"),
            uctova_osnova_query=_StubOsnovaQuery(_sample_ucty()),
            zauctovat_command=_ErrorZauctovatCommand(
                PodvojnostError("server: nesoulad"),
            ),
        )
        vm.load()
        vm.update_row(0, md_ucet="311", dal_ucet="601")
        result = vm.submit()
        assert result is None
        assert "nesoulad" in (vm.error or "")


class TestZalohaNeniPrefillovana:
    """ZF se neúčtuje samostatně — žádný auto-prefill řádků se 314/324."""

    def _zf_doklad(self, je_vystavena: bool) -> DokladyListItem:
        return DokladyListItem(
            id=20, cislo="ZF-2025-001",
            typ=TypDokladu.ZALOHA_FAKTURA,
            datum_vystaveni=date(2025, 5, 1),
            datum_splatnosti=None,
            partner_id=None, partner_nazev=None,
            castka_celkem=Money.from_koruny("3000"),
            stav=StavDokladu.NOVY,
            k_doreseni=False, poznamka_doreseni=None, popis=None,
            je_vystavena=je_vystavena,
        )

    def test_zf_vystavena_nema_prefill_uctu(self):
        """ZF se neúčtuje — prefill je generický (1 řádek bez účtů)."""
        d = self._zf_doklad(je_vystavena=True)
        vm = ZauctovaniViewModel(
            d, _StubOsnovaQuery([]), _StubZauctovatCommand(d),
        )
        vm.load()
        assert len(vm.radky) == 1
        # Default — prázdné účty (uživatelka by neměla zaúčtovat ZF)
        assert vm.radky[0].md_ucet == ""
        # dal_ucet bere prefill_dal_ucet, který je default ""

    def test_zf_prijata_nema_prefill_uctu(self):
        d = self._zf_doklad(je_vystavena=False)
        vm = ZauctovaniViewModel(
            d, _StubOsnovaQuery([]), _StubZauctovatCommand(d),
        )
        vm.load()
        assert len(vm.radky) == 1
        assert vm.radky[0].md_ucet == ""


class TestNactiZalohyPartnera:
    """Tlačítko 'Načíst zálohy' v zauctovani FV/FP."""

    def _zaloha_item(self, cislo: str, castka: str, je_vystavena: bool):
        from services.queries.zalohy_partnera import ZalohaItem
        from domain.doklady.typy import Mena
        return ZalohaItem(
            id=1, cislo=cislo, datum=date(2025, 4, 1),
            castka_celkem=Money.from_koruny(castka),
            castka_mena=None, mena=Mena.CZK,
            je_vystavena=je_vystavena,
        )

    def test_fv_nacti_zalohy_snizi_hlavni_a_prida_odecet(self):
        """FV 10000 + záloha 3000 → hlavní 7000 + odečet 3000."""
        d = _sample_doklad(castka="10000")
        vm = ZauctovaniViewModel(
            d, _StubOsnovaQuery([]), _StubZauctovatCommand(d),
            prefill_dal_ucet="601",
        )
        vm.load()
        # Hlavní řádek po prefillu: dal_ucet=601, castka=10000
        vm.update_row(0, md_ucet="311.100", dal_ucet="601")
        vm.nacti_zalohy_partnera([
            self._zaloha_item("ZF-2025-001", "3000", True),
        ])
        assert len(vm.radky) == 2
        # Hlavní snížený: 311.100/601 = 7000
        assert vm.radky[0].castka == Money.from_koruny("7000")
        # Odečet: 324.001/601 = 3000
        assert vm.radky[1].md_ucet == "324.001"
        assert vm.radky[1].dal_ucet == "601"
        assert vm.radky[1].castka == Money.from_koruny("3000")
        # Součet zápisů na MD = 7000 + 3000 = 10000 = castka_celkem ✓
        assert vm.je_podvojne is True


class TestPredpisRadek:

    def test_frozen(self):
        r = PredpisRadek()
        import pytest
        with pytest.raises(Exception):
            r.md_ucet = "X"  # type: ignore[misc]

    def test_defaulty(self):
        r = PredpisRadek()
        assert r.md_ucet == ""
        assert r.dal_ucet == ""
        assert r.castka == Money.zero()
        assert r.popis == ""
