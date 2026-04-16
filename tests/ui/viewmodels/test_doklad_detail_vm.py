"""Testy pro DokladDetailViewModel — pure Python, bez Qt."""

from __future__ import annotations

from datetime import date

from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import ValidationError
from domain.shared.money import Money
from services.queries.doklady_list import DokladyListItem
from ui.viewmodels.doklad_detail_vm import DokladDetailViewModel


# ─── Stubs ────────────────────────────────────────────────────────────


class _StubActions:
    def __init__(self, result: DokladyListItem | None = None):
        self.result = result
        self.calls: list[tuple[str, dict]] = []

    def stornovat(self, doklad_id: int) -> DokladyListItem:
        self.calls.append(("stornovat", {"id": doklad_id}))
        assert self.result is not None
        return self.result

    def smazat(self, doklad_id: int) -> None:
        self.calls.append(("smazat", {"id": doklad_id}))

    def oznac_k_doreseni(
        self, doklad_id: int, poznamka: str | None = None,
    ) -> DokladyListItem:
        self.calls.append(
            ("oznac_k_doreseni", {"id": doklad_id, "poznamka": poznamka})
        )
        assert self.result is not None
        return self.result

    def dores(self, doklad_id: int) -> DokladyListItem:
        self.calls.append(("dores", {"id": doklad_id}))
        assert self.result is not None
        return self.result

    def upravit_popis_a_splatnost(
        self,
        doklad_id: int,
        popis: str | None,
        splatnost: date | None,
    ) -> DokladyListItem:
        self.calls.append(("upravit", {
            "id": doklad_id, "popis": popis, "splatnost": splatnost,
        }))
        assert self.result is not None
        return self.result

    def upravit_pole_novy_dokladu(
        self,
        doklad_id: int,
        popis: str | None,
        splatnost: date | None,
        k_doreseni: bool,
        poznamka_doreseni: str | None,
    ) -> DokladyListItem:
        self.calls.append(("upravit_pole_novy", {
            "id": doklad_id,
            "popis": popis,
            "splatnost": splatnost,
            "k_doreseni": k_doreseni,
            "poznamka_doreseni": poznamka_doreseni,
        }))
        assert self.result is not None
        return self.result


class _ErrorActions:
    def __init__(self, exc: Exception):
        self.exc = exc

    def stornovat(self, doklad_id):
        raise self.exc

    def smazat(self, doklad_id):
        raise self.exc

    def oznac_k_doreseni(self, doklad_id, poznamka=None):
        raise self.exc

    def dores(self, doklad_id):
        raise self.exc

    def upravit_popis_a_splatnost(self, doklad_id, popis, splatnost):
        raise self.exc

    def upravit_pole_novy_dokladu(
        self, doklad_id, popis, splatnost, k_doreseni, poznamka_doreseni,
    ):
        raise self.exc


def _item(
    stav: StavDokladu = StavDokladu.NOVY,
    k_doreseni: bool = False,
    poznamka: str | None = None,
    popis: str | None = "puvodni",
    splatnost: date | None = date(2026, 3, 15),
) -> DokladyListItem:
    return DokladyListItem(
        id=1,
        cislo="FV-2026-001",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 3, 1),
        datum_splatnosti=splatnost,
        partner_nazev=None,
        castka_celkem=Money.from_koruny("1000"),
        stav=stav,
        k_doreseni=k_doreseni,
        poznamka_doreseni=poznamka,
        popis=popis,
    )


# ─── Tests ────────────────────────────────────────────────────────────


class TestPocatecniStav:

    def test_edit_mode_false(self):
        vm = DokladDetailViewModel(_item(), _StubActions())
        assert vm.edit_mode is False

    def test_draft_kopie_puvodnich(self):
        i = _item()
        vm = DokladDetailViewModel(i, _StubActions())
        assert vm.draft_popis == i.popis
        assert vm.draft_splatnost == i.datum_splatnosti

    def test_doklad_property(self):
        i = _item()
        vm = DokladDetailViewModel(i, _StubActions())
        assert vm.doklad is i


class TestComputed:

    def test_novy_vse_povoleno(self):
        vm = DokladDetailViewModel(_item(StavDokladu.NOVY), _StubActions())
        assert vm.can_edit is True
        assert vm.can_edit_splatnost is True
        assert vm.can_storno is True
        assert vm.can_smazat is True
        assert vm.can_toggle_flag is True
        assert vm.can_zauctovat is True

    def test_zauctovany_omezeni(self):
        vm = DokladDetailViewModel(
            _item(StavDokladu.ZAUCTOVANY), _StubActions(),
        )
        assert vm.can_edit is True  # popis lze měnit
        assert vm.can_edit_splatnost is False
        assert vm.can_storno is True
        assert vm.can_smazat is False
        assert vm.can_zauctovat is False

    def test_stornovany_nic(self):
        vm = DokladDetailViewModel(
            _item(StavDokladu.STORNOVANY), _StubActions(),
        )
        assert vm.can_edit is False
        assert vm.can_storno is False
        assert vm.can_smazat is False
        assert vm.can_toggle_flag is False

    def test_uhrazeny_nelze_stornovat(self):
        vm = DokladDetailViewModel(
            _item(StavDokladu.UHRAZENY), _StubActions(),
        )
        assert vm.can_storno is False


class TestEditMode:

    def test_enter_edit_nastavi_flag(self):
        vm = DokladDetailViewModel(_item(), _StubActions())
        vm.enter_edit()
        assert vm.edit_mode is True

    def test_enter_edit_stornovany_nastavi_error(self):
        vm = DokladDetailViewModel(
            _item(StavDokladu.STORNOVANY), _StubActions(),
        )
        vm.enter_edit()
        assert vm.edit_mode is False
        assert vm.error is not None

    def test_cancel_edit_vrati_draft(self):
        vm = DokladDetailViewModel(_item(), _StubActions())
        vm.enter_edit()
        vm.set_draft_popis("jiny")
        vm.cancel_edit()
        assert vm.edit_mode is False
        assert vm.draft_popis == "puvodni"

    def test_save_edit_uspesne(self):
        new_item = _item(popis="novy")
        actions = _StubActions(result=new_item)
        vm = DokladDetailViewModel(_item(), actions)
        vm.enter_edit()
        vm.set_draft_popis("novy")
        result = vm.save_edit()
        assert result is new_item
        assert vm.edit_mode is False
        assert vm.doklad is new_item
        assert actions.calls[0][1]["popis"] == "novy"

    def test_save_edit_error(self):
        vm = DokladDetailViewModel(
            _item(), _ErrorActions(ValidationError("boom")),
        )
        vm.enter_edit()
        vm.set_draft_popis("x")
        assert vm.save_edit() is None
        assert vm.error == "boom"


class TestAkce:

    def test_stornovat(self):
        result = _item(stav=StavDokladu.STORNOVANY)
        vm = DokladDetailViewModel(_item(), _StubActions(result=result))
        vm.stornovat()
        assert vm.doklad is result

    def test_stornovat_error(self):
        vm = DokladDetailViewModel(
            _item(), _ErrorActions(ValidationError("nelze")),
        )
        assert vm.stornovat() is None
        assert vm.error == "nelze"

    def test_smazat_uspesne(self):
        vm = DokladDetailViewModel(_item(), _StubActions())
        assert vm.smazat() is True
        assert vm.is_deleted is True

    def test_smazat_error(self):
        vm = DokladDetailViewModel(
            _item(), _ErrorActions(ValidationError("ne")),
        )
        assert vm.smazat() is False
        assert vm.is_deleted is False

    def test_oznac_k_doreseni(self):
        result = _item(k_doreseni=True, poznamka="pz")
        actions = _StubActions(result=result)
        vm = DokladDetailViewModel(_item(), actions)
        vm.oznac_k_doreseni(poznamka="pz")
        assert vm.doklad.k_doreseni is True
        assert actions.calls[0][1]["poznamka"] == "pz"

    def test_dores(self):
        result = _item(k_doreseni=False)
        vm = DokladDetailViewModel(
            _item(k_doreseni=True, poznamka="x"),
            _StubActions(result=result),
        )
        vm.dores()
        assert vm.doklad.k_doreseni is False

    def test_refresh_from(self):
        vm = DokladDetailViewModel(_item(), _StubActions())
        new = _item(popis="novy", splatnost=date(2026, 4, 1))
        vm.refresh_from(new)
        assert vm.doklad is new
        assert vm.draft_popis == "novy"
        assert vm.edit_mode is False


class TestEditModeKDoreseni:
    """Fáze 6.7: edit mode pro NOVY doklad zahrnuje k_doreseni + poznámku."""

    def test_draft_k_doreseni_kopie_puvodnich(self):
        i = _item(k_doreseni=True, poznamka="pz")
        vm = DokladDetailViewModel(i, _StubActions())
        assert vm.draft_k_doreseni is True
        assert vm.draft_poznamka_doreseni == "pz"

    def test_set_draft_k_doreseni(self):
        vm = DokladDetailViewModel(_item(), _StubActions())
        vm.enter_edit()
        vm.set_draft_k_doreseni(True)
        vm.set_draft_poznamka_doreseni("nová")
        assert vm.draft_k_doreseni is True
        assert vm.draft_poznamka_doreseni == "nová"

    def test_cancel_edit_vrati_k_doreseni(self):
        vm = DokladDetailViewModel(
            _item(k_doreseni=False, poznamka=None), _StubActions(),
        )
        vm.enter_edit()
        vm.set_draft_k_doreseni(True)
        vm.set_draft_poznamka_doreseni("změna")
        vm.cancel_edit()
        assert vm.draft_k_doreseni is False
        assert vm.draft_poznamka_doreseni is None

    def test_save_edit_novy_vola_upravit_pole_novy(self):
        """NOVY doklad → upravit_pole_novy_dokladu (včetně flagu + poznámky)."""
        result = _item(popis="x", k_doreseni=True, poznamka="pz")
        actions = _StubActions(result=result)
        vm = DokladDetailViewModel(_item(StavDokladu.NOVY), actions)
        vm.enter_edit()
        vm.set_draft_popis("x")
        vm.set_draft_k_doreseni(True)
        vm.set_draft_poznamka_doreseni("pz")
        vm.save_edit()
        assert actions.calls[0][0] == "upravit_pole_novy"
        assert actions.calls[0][1]["popis"] == "x"
        assert actions.calls[0][1]["k_doreseni"] is True
        assert actions.calls[0][1]["poznamka_doreseni"] == "pz"

    def test_save_edit_zauctovany_vola_upravit_popis_a_splatnost(self):
        """Non-NOVY → jen upravit_popis_a_splatnost, bez flagu."""
        result = _item(StavDokladu.ZAUCTOVANY, popis="x")
        actions = _StubActions(result=result)
        vm = DokladDetailViewModel(
            _item(StavDokladu.ZAUCTOVANY), actions,
        )
        vm.enter_edit()
        vm.set_draft_popis("x")
        # k_doreseni draft se nemá aplikovat pro non-NOVY
        vm.set_draft_k_doreseni(True)
        vm.save_edit()
        assert actions.calls[0][0] == "upravit"

    def test_refresh_from_obnovi_k_doreseni(self):
        vm = DokladDetailViewModel(_item(), _StubActions())
        new = _item(k_doreseni=True, poznamka="pz")
        vm.refresh_from(new)
        assert vm.draft_k_doreseni is True
        assert vm.draft_poznamka_doreseni == "pz"
