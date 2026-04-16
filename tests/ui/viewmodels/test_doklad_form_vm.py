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


class TestSubmitSFlagKDoreseni:
    """Fáze 6.7: submit s k_doreseni=True volá actions_command po create."""

    def test_bez_flagu_neni_volan_actions(self):
        from unittest.mock import MagicMock
        item = _sample_item()
        actions = MagicMock()
        vm = DokladFormViewModel(
            _StubNextNumberQuery(),
            _StubCreateCommand(item),
            actions_command=actions,
        )
        vm.submit(_sample_input(), k_doreseni=False)
        actions.oznac_k_doreseni.assert_not_called()

    def test_s_flagem_vola_actions_s_poznamkou(self):
        from unittest.mock import MagicMock
        item = _sample_item()
        flagged = DokladyListItem(
            id=item.id, cislo=item.cislo, typ=item.typ,
            datum_vystaveni=item.datum_vystaveni,
            datum_splatnosti=item.datum_splatnosti,
            partner_nazev=None, castka_celkem=item.castka_celkem,
            stav=item.stav, k_doreseni=True,
            poznamka_doreseni="chybí IČO", popis=item.popis,
        )
        actions = MagicMock()
        actions.oznac_k_doreseni.return_value = flagged
        vm = DokladFormViewModel(
            _StubNextNumberQuery(),
            _StubCreateCommand(item),
            actions_command=actions,
        )
        result = vm.submit(
            _sample_input(),
            k_doreseni=True,
            poznamka_doreseni="chybí IČO",
        )
        actions.oznac_k_doreseni.assert_called_once_with(42, "chybí IČO")
        assert result is flagged
        assert vm.created_item is flagged
        assert vm.error is None

    def test_flag_bez_poznamky(self):
        from unittest.mock import MagicMock
        item = _sample_item()
        actions = MagicMock()
        actions.oznac_k_doreseni.return_value = item
        vm = DokladFormViewModel(
            _StubNextNumberQuery(),
            _StubCreateCommand(item),
            actions_command=actions,
        )
        vm.submit(_sample_input(), k_doreseni=True, poznamka_doreseni=None)
        actions.oznac_k_doreseni.assert_called_once_with(42, None)

    def test_selhani_flag_kroku_vraci_puvodni_item_s_errorem(self):
        """2-UoW trade-off: doklad existuje, flag se nepodaří — UI informováno."""
        from unittest.mock import MagicMock
        item = _sample_item()
        actions = MagicMock()
        actions.oznac_k_doreseni.side_effect = RuntimeError("DB zamčená")
        vm = DokladFormViewModel(
            _StubNextNumberQuery(),
            _StubCreateCommand(item),
            actions_command=actions,
        )
        result = vm.submit(_sample_input(), k_doreseni=True)
        # Doklad existuje — vrací se původní item, error nastavený.
        assert result is item
        assert vm.created_item is item
        assert vm.error is not None
        assert "DB zamčená" in vm.error

    def test_selhani_create_neda_volat_actions(self):
        from unittest.mock import MagicMock
        actions = MagicMock()
        vm = DokladFormViewModel(
            _StubNextNumberQuery(),
            _ErrorCreateCommand(RuntimeError("boom")),
            actions_command=actions,
        )
        result = vm.submit(_sample_input(), k_doreseni=True)
        assert result is None
        actions.oznac_k_doreseni.assert_not_called()
