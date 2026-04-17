"""Testy pro BankovniTransakce entity."""

from __future__ import annotations

from datetime import date

import pytest

from domain.banka.bankovni_transakce import BankovniTransakce, StavTransakce
from domain.shared.errors import ValidationError
from domain.shared.money import Money


def _make_tx(**kwargs) -> BankovniTransakce:
    defaults = dict(
        bankovni_vypis_id=1,
        datum_transakce=date(2025, 3, 15),
        datum_zauctovani=date(2025, 3, 15),
        castka=Money(100_00),
        smer="P",
        row_hash="abc123",
    )
    defaults.update(kwargs)
    return BankovniTransakce(**defaults)


class TestBankovniTransakce:

    def test_create_valid(self):
        tx = _make_tx()
        assert tx.stav == StavTransakce.NESPAROVANO
        assert tx.sparovany_doklad_id is None

    def test_invalid_smer_raises(self):
        with pytest.raises(ValidationError, match="směr"):
            _make_tx(smer="X")

    def test_sparuj(self):
        tx = _make_tx()
        tx.sparuj(doklad_id=42)
        assert tx.stav == StavTransakce.SPAROVANO
        assert tx.sparovany_doklad_id == 42

    def test_auto_zauctuj(self):
        tx = _make_tx()
        tx.auto_zauctuj(ucetni_zapis_id=7)
        assert tx.stav == StavTransakce.AUTO_ZAUCTOVANO
        assert tx.ucetni_zapis_id == 7

    def test_ignoruj(self):
        tx = _make_tx()
        tx.ignoruj()
        assert tx.stav == StavTransakce.IGNOROVANO


class TestStavTransakce:

    def test_enum_values(self):
        assert StavTransakce.NESPAROVANO.value == "nesparovano"
        assert StavTransakce.SPAROVANO.value == "sparovano"
        assert StavTransakce.AUTO_ZAUCTOVANO.value == "auto_zauctovano"
        assert StavTransakce.IGNOROVANO.value == "ignorovano"
