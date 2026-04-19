"""Testy pro PrilohaDokladu domain entitu."""

from datetime import datetime

import pytest

from domain.doklady.priloha import PrilohaDokladu
from domain.shared.errors import ValidationError


class TestPrilohaDokladu:
    """Validace konstruktoru a frozen dataclass."""

    def _make(self, **overrides):
        defaults = dict(
            id=None,
            doklad_id=1,
            nazev_souboru="faktura.pdf",
            relativni_cesta="doklady/2025/FP/FP-2025-0001_faktura.pdf",
            velikost_bytes=12345,
            mime_type="application/pdf",
            vytvoreno=datetime(2025, 1, 15, 10, 30),
        )
        defaults.update(overrides)
        return PrilohaDokladu(**defaults)

    def test_valid_construction(self):
        p = self._make()
        assert p.doklad_id == 1
        assert p.nazev_souboru == "faktura.pdf"
        assert p.velikost_bytes == 12345

    def test_empty_nazev_raises(self):
        with pytest.raises(ValidationError, match="prázdný"):
            self._make(nazev_souboru="")

    def test_negative_velikost_raises(self):
        with pytest.raises(ValidationError, match="záporná"):
            self._make(velikost_bytes=-1)

    def test_zero_velikost_ok(self):
        p = self._make(velikost_bytes=0)
        assert p.velikost_bytes == 0

    def test_frozen_cannot_mutate(self):
        p = self._make()
        with pytest.raises(AttributeError):
            p.nazev_souboru = "other.pdf"

    def test_frozen_cannot_mutate_id(self):
        p = self._make(id=5)
        with pytest.raises(AttributeError):
            p.id = 10
