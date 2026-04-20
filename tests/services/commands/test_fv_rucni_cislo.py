"""Testy pro ruční číslo dokladu u FV (Commit 6)."""

from __future__ import annotations

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.errors import CisloDokladuJizExistujeError
from domain.doklady.typy import TypDokladu
from domain.shared.money import Money
from services.commands.create_doklad import CreateDokladCommand, CreateDokladInput


class _FakeUow:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def commit(self):
        pass


class _FakeRepo:
    """In-memory repo pro testy."""

    def __init__(self) -> None:
        self._doklady: dict[str, Doklad] = {}
        self._next_id = 1

    def add(self, doklad: Doklad) -> Doklad:
        doklad._id = self._next_id
        self._next_id += 1
        self._doklady[doklad.cislo] = doklad
        return doklad

    def existuje_cislo(self, cislo: str) -> bool:
        return cislo in self._doklady


class _FakeNextNumber:
    def __init__(self, result: str = "FV-2025-001") -> None:
        self._result = result

    def execute(self, typ: TypDokladu, rok: int) -> str:
        return self._result


def _build_cmd():
    repo = _FakeRepo()
    cmd = CreateDokladCommand(
        uow_factory=lambda: _FakeUow(),
        doklady_repo_factory=lambda uow: repo,
    )
    return cmd, repo


def _make_input(
    cislo: str = "CANVA-001",
    typ: TypDokladu = TypDokladu.FAKTURA_VYDANA,
) -> CreateDokladInput:
    return CreateDokladInput(
        cislo=cislo,
        typ=typ,
        datum_vystaveni=date(2025, 6, 1),
        castka_celkem=Money(10000),
    )


class TestFvRucniCislo:
    """Testy pro ruční číslo dokladu u FV."""

    def test_fv_auto_cislo_se_generuje(self):
        """Default: auto-generované číslo FV-2025-001 se uloží."""
        cmd, _ = _build_cmd()
        data = _make_input(cislo="FV-2025-001")

        result = cmd.execute(data)

        assert result.cislo == "FV-2025-001"

    def test_fv_rucni_cislo_se_ulozi(self):
        """Ruční číslo CANVA-001 se uloží."""
        cmd, _ = _build_cmd()
        data = _make_input(cislo="CANVA-001")

        result = cmd.execute(data)

        assert result.cislo == "CANVA-001"

    def test_rucni_cislo_duplicita_selze(self):
        """Duplicitní číslo → CisloDokladuJizExistujeError."""
        cmd, _ = _build_cmd()
        data = _make_input(cislo="CANVA-001")

        cmd.execute(data)  # první OK

        with pytest.raises(CisloDokladuJizExistujeError, match="už existuje"):
            cmd.execute(data)  # druhý → chyba

    def test_rucni_cislo_jiny_typ_ok(self):
        """Stejné číslo u FP a FV → OK (různé řetězce prefixem)."""
        cmd, _ = _build_cmd()

        cmd.execute(_make_input(cislo="FP-2025-001", typ=TypDokladu.FAKTURA_PRIJATA))
        result = cmd.execute(_make_input(cislo="FV-2025-001", typ=TypDokladu.FAKTURA_VYDANA))

        assert result.cislo == "FV-2025-001"

    def test_rucni_cislo_jiny_rok_ok(self):
        """Stejné číslo v jiném roce → OK (různé řetězce rokem)."""
        cmd, _ = _build_cmd()

        cmd.execute(_make_input(cislo="CANVA-2025-001"))
        result = cmd.execute(_make_input(cislo="CANVA-2026-001"))

        assert result.cislo == "CANVA-2026-001"
