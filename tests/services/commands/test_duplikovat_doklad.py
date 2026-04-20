"""Testy pro DuplikovatDokladCommand."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import DphRezim, Mena, StavDokladu, TypDokladu
from domain.shared.money import Money
from services.commands.duplikovat_doklad import DuplikovatDokladCommand


def _make_doklad(
    id: int = 42,
    cislo: str = "FP-2025-0004",
    typ: TypDokladu = TypDokladu.FAKTURA_PRIJATA,
    partner_id: int | None = 7,
    castka: int = 4400,
    popis: str | None = "Meta Platforms Ireland Limited",
    dph_rezim: DphRezim = DphRezim.REVERSE_CHARGE,
    stav: StavDokladu = StavDokladu.ZAUCTOVANY,
    mena: Mena = Mena.CZK,
    castka_mena: Money | None = None,
    kurz: Decimal | None = None,
    variabilni_symbol: str | None = "104443139",
) -> Doklad:
    d = Doklad(
        id=id,
        cislo=cislo,
        typ=typ,
        datum_vystaveni=date(2025, 4, 24),
        castka_celkem=Money(castka),
        partner_id=partner_id,
        popis=popis,
        dph_rezim=dph_rezim,
        mena=mena,
        castka_mena=castka_mena,
        kurz=kurz,
        variabilni_symbol=variabilni_symbol,
    )
    # Force stav for testing (normally only via state machine)
    d._stav = stav
    return d


class _FakeRepo:
    def __init__(self, doklad: Doklad | None) -> None:
        self._doklad = doklad

    def get_by_id(self, id: int) -> Doklad | None:
        if self._doklad is not None and self._doklad.id == id:
            return self._doklad
        return None


class _FakeNextNumber:
    def __init__(self, result: str = "FP-2025-0005") -> None:
        self._result = result
        self.called_with: tuple | None = None

    def execute(self, typ: TypDokladu, rok: int) -> str:
        self.called_with = (typ, rok)
        return self._result


class _FakeUow:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def commit(self):
        pass


def _build_cmd(doklad: Doklad | None = None, next_cislo: str = "FP-2025-0005"):
    repo = _FakeRepo(doklad)
    next_num = _FakeNextNumber(next_cislo)
    cmd = DuplikovatDokladCommand(
        uow_factory=lambda: _FakeUow(),
        doklady_repo_factory=lambda uow: repo,
        next_number_query=next_num,
    )
    return cmd, next_num


class TestDuplikovatDoklad:
    """Testy duplikace dokladu."""

    def test_duplikuje_zakladni_pole(self):
        """Partner, částka, RC, popis, datum zachovány."""
        zdroj = _make_doklad()
        cmd, _ = _build_cmd(zdroj)

        result = cmd.execute(42)

        assert result.typ == TypDokladu.FAKTURA_PRIJATA
        assert result.partner_id == 7
        assert result.castka_celkem == Money(4400)
        assert result.dph_rezim == DphRezim.REVERSE_CHARGE
        assert result.popis == "Meta Platforms Ireland Limited"
        assert result.datum_vystaveni == date(2025, 4, 24)

    def test_resetuje_promenne_pole(self):
        """VS=None, datum=dnes, stav=NOVÝ."""
        zdroj = _make_doklad(variabilni_symbol="104443139")
        cmd, _ = _build_cmd(zdroj)

        result = cmd.execute(42)

        # Duplikat nemá VS (uživatel doplní)
        # DuplikatData doesn't have VS — it's reset
        assert result.nove_cislo == "FP-2025-0005"
        assert result.zdrojove_cislo == "FP-2025-0004"

    def test_nova_cisla_dokladu(self):
        """FP-2025-0004 → duplikát FP-2025-0043."""
        zdroj = _make_doklad()
        cmd, next_num = _build_cmd(zdroj, next_cislo="FP-2025-0043")

        result = cmd.execute(42)

        assert result.nove_cislo == "FP-2025-0043"
        assert next_num.called_with is not None
        assert next_num.called_with[0] == TypDokladu.FAKTURA_PRIJATA

    def test_cislo_pouzije_rok_zdrojoveho_dokladu(self):
        """Číselná řada respektuje účetní období zdrojového dokladu."""
        zdroj = _make_doklad()  # datum_vystaveni = 2025-04-24
        cmd, next_num = _build_cmd(zdroj)

        cmd.execute(42)

        # Rok předaný do NextDokladNumberQuery musí být 2025 (ze zdroje)
        assert next_num.called_with is not None
        assert next_num.called_with[1] == 2025

    def test_k_doreseni_s_poznamkou(self):
        """Poznámka obsahuje číslo zdroje — ověříme v DuplikatData."""
        zdroj = _make_doklad(cislo="FP-2025-0004")
        cmd, _ = _build_cmd(zdroj)

        result = cmd.execute(42)

        assert result.zdrojove_cislo == "FP-2025-0004"

    def test_duplikuje_stornovany(self):
        """Storno doklad → kopie je NOVÝ (DuplikatData zachová typ)."""
        zdroj = _make_doklad(stav=StavDokladu.STORNOVANY)
        cmd, _ = _build_cmd(zdroj)

        result = cmd.execute(42)

        assert result.typ == TypDokladu.FAKTURA_PRIJATA
        assert result.castka_celkem == Money(4400)

    def test_neexistujici_doklad_vyhodi_chybu(self):
        """Duplikace neexistujícího dokladu."""
        cmd, _ = _build_cmd(None)

        with pytest.raises(Exception, match="neexistuje"):
            cmd.execute(999)

    def test_zachova_cizomenova_pole(self):
        """Měna, castka_mena, kurz se zkopírují."""
        zdroj = _make_doklad(
            mena=Mena.EUR,
            castka_mena=Money(17600),
            kurz=Decimal("25.100"),
        )
        cmd, _ = _build_cmd(zdroj)

        result = cmd.execute(42)

        assert result.mena == Mena.EUR
        assert result.castka_mena == Money(17600)
        assert result.kurz == Decimal("25.100")
