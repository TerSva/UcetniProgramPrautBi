"""Testy pro DokladFormViewModel — pure Python, bez Qt."""

from __future__ import annotations

from datetime import date

from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import ConflictError
from domain.shared.money import Money
from services.commands.create_doklad import CreateDokladInput
from services.queries.doklady_list import DokladyListItem
from ui.viewmodels.doklad_form_vm import DokladFormViewModel


# ─── Stubs ────────────────────────────────────────────────────────────


class _StubNextNumberQuery:
    def __init__(self, cislo: str = "FV-2026-007"):
        self.cislo = cislo
        self.calls: list[tuple[TypDokladu, int]] = []

    def execute(self, typ: TypDokladu, rok: int) -> str:
        self.calls.append((typ, rok))
        return self.cislo


class _ErrorNextNumberQuery:
    def execute(self, typ: TypDokladu, rok: int) -> str:
        raise RuntimeError("next boom")


class _StubCreateCommand:
    def __init__(self, returned: DokladyListItem):
        self.returned = returned
        self.calls: list[CreateDokladInput] = []

    def execute(self, data: CreateDokladInput) -> DokladyListItem:
        self.calls.append(data)
        return self.returned


class _ErrorCreateCommand:
    def __init__(self, exc: Exception):
        self.exc = exc

    def execute(self, data: CreateDokladInput) -> DokladyListItem:
        raise self.exc


def _sample_item() -> DokladyListItem:
    return DokladyListItem(
        id=42,
        cislo="FV-2026-007",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 3, 1),
        datum_splatnosti=date(2026, 3, 15),
        partner_nazev=None,
        castka_celkem=Money.from_koruny("1000"),
        stav=StavDokladu.NOVY,
        k_doreseni=False,
        poznamka_doreseni=None,
        popis="Test",
    )


def _sample_input() -> CreateDokladInput:
    return CreateDokladInput(
        cislo="FV-2026-007",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 3, 1),
        castka_celkem=Money.from_koruny("1000"),
        datum_splatnosti=date(2026, 3, 15),
        popis="Test",
    )


# ─── Tests ────────────────────────────────────────────────────────────


class TestPocatecniStav:

    def test_created_item_je_none(self):
        vm = DokladFormViewModel(
            _StubNextNumberQuery(),
            _StubCreateCommand(_sample_item()),
        )
        assert vm.created_item is None
        assert vm.error is None


class TestSuggestCislo:

    def test_volani_query_s_argumenty(self):
        q = _StubNextNumberQuery("FP-2026-001")
        vm = DokladFormViewModel(q, _StubCreateCommand(_sample_item()))
        cislo = vm.suggest_cislo(TypDokladu.FAKTURA_PRIJATA, 2026)
        assert cislo == "FP-2026-001"
        assert q.calls == [(TypDokladu.FAKTURA_PRIJATA, 2026)]

    def test_chyba_vrati_prazdny_string(self):
        vm = DokladFormViewModel(
            _ErrorNextNumberQuery(),
            _StubCreateCommand(_sample_item()),
        )
        cislo = vm.suggest_cislo(TypDokladu.FAKTURA_VYDANA, 2026)
        assert cislo == ""
        assert vm.error == "next boom"


class TestSubmit:

    def test_uspesny_submit(self):
        item = _sample_item()
        cmd = _StubCreateCommand(item)
        vm = DokladFormViewModel(_StubNextNumberQuery(), cmd)
        result = vm.submit(_sample_input())
        assert result is item
        assert vm.created_item is item
        assert vm.error is None
        assert len(cmd.calls) == 1

    def test_conflict_error_nastavi_error(self):
        cmd = _ErrorCreateCommand(ConflictError("Doklad FV-001 už existuje."))
        vm = DokladFormViewModel(_StubNextNumberQuery(), cmd)
        result = vm.submit(_sample_input())
        assert result is None
        assert vm.created_item is None
        assert "už existuje" in (vm.error or "")

    def test_nechytene_vyjimka_fallback_na_typ(self):
        cmd = _ErrorCreateCommand(RuntimeError(""))
        vm = DokladFormViewModel(_StubNextNumberQuery(), cmd)
        vm.submit(_sample_input())
        assert vm.error == "RuntimeError"

    def test_opakovany_submit_prepise_created(self):
        item1 = _sample_item()
        cmd = _StubCreateCommand(item1)
        vm = DokladFormViewModel(_StubNextNumberQuery(), cmd)
        vm.submit(_sample_input())
        assert vm.created_item is item1
        # Error round-trip pak úspěch
        vm._create_command = _ErrorCreateCommand(  # type: ignore[attr-defined]
            RuntimeError("x")
        )
        vm.submit(_sample_input())
        assert vm.created_item is None
