"""Testy pro domain/firma/pocatecni_stav.py — PocatecniStav entita."""

from __future__ import annotations

import pytest

from domain.firma.pocatecni_stav import PocatecniStav
from domain.shared.errors import ValidationError
from domain.shared.money import Money


def test_pocatecni_stav_md():
    s = PocatecniStav(ucet_kod="221", castka=Money(100000), strana="MD", rok=2025)
    assert s.ucet_kod == "221"
    assert s.strana == "MD"
    assert s.rok == 2025


def test_pocatecni_stav_dal():
    s = PocatecniStav(ucet_kod="411", castka=Money(20000000), strana="DAL", rok=2025)
    assert s.strana == "DAL"


def test_pocatecni_stav_empty_ucet_raises():
    with pytest.raises(ValidationError, match="Účet"):
        PocatecniStav(ucet_kod="", castka=Money(100), strana="MD", rok=2025)


def test_pocatecni_stav_zero_castka_raises():
    with pytest.raises(ValidationError, match="Částka"):
        PocatecniStav(ucet_kod="221", castka=Money(0), strana="MD", rok=2025)


def test_pocatecni_stav_negative_castka_raises():
    with pytest.raises(ValidationError, match="Částka"):
        PocatecniStav(ucet_kod="221", castka=Money(-100), strana="MD", rok=2025)


def test_pocatecni_stav_invalid_strana_raises():
    with pytest.raises(ValidationError, match="Strana"):
        PocatecniStav(ucet_kod="221", castka=Money(100), strana="X", rok=2025)


def test_pocatecni_stav_invalid_rok_raises():
    with pytest.raises(ValidationError, match="Rok"):
        PocatecniStav(ucet_kod="221", castka=Money(100), strana="MD", rok=1999)


def test_pocatecni_stav_is_frozen():
    s = PocatecniStav(ucet_kod="221", castka=Money(100), strana="MD", rok=2025)
    with pytest.raises(AttributeError):
        s.ucet_kod = "311"  # type: ignore[misc]
