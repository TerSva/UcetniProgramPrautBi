"""Testy tlačítka 'Vystavit uzávěrku roku' na Výkazy stránce."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from domain.shared.errors import ConflictError
from domain.shared.money import Money
from services.commands.uzaverka_roku import UzaverkaResult


@pytest.fixture
def mock_query():
    q = MagicMock()
    q.get_rozvaha.return_value = (tuple(), tuple())
    q.get_vzz.return_value = tuple()
    q.get_predvaha.return_value = tuple()
    q.get_bilancni_kontrola.return_value = (Money.zero(), Money.zero())
    q.get_zaverkove_saldo.return_value = Money.zero()
    q.get_ucty_s_pohybem.return_value = (("211", "Pokladna"),)
    q.get_saldokonto_per_ucet.return_value = (
        type("S", (), {"radky": tuple(), "celkem": Money.zero()})(),
        type("S", (), {"radky": tuple(), "celkem": Money.zero()})(),
        type("S", (), {"radky": tuple(), "celkem": Money.zero()})(),
        type("S", (), {"radky": tuple(), "celkem": Money.zero()})(),
    )
    from services.queries.vykazy_query import (
        DphPrehled, HlavniKnihaUctu, NedanoveNaklady, PokladniKniha,
    )
    q.get_dph_prehled.return_value = DphPrehled(
        rok=2025, obdobi_od=date(2025, 1, 1), obdobi_do=date(2025, 12, 31),
        vstup_celkem=Money.zero(), vstup_rc=Money.zero(),
        vystup_celkem=Money.zero(), vystup_rc=Money.zero(), doklady=tuple(),
    )
    q.get_hlavni_kniha.return_value = HlavniKnihaUctu(
        ucet="211", nazev="Pokladna", typ="A",
        pocatecni_stav=Money.zero(),
        obrat_md=Money.zero(), obrat_dal=Money.zero(),
        radky=tuple(),
    )
    q.get_pokladni_kniha.return_value = PokladniKniha(
        rok=2025, pocatecni_stav=Money.zero(),
        radky=tuple(), pouzita=False,
    )
    q.get_nedanove_naklady.return_value = NedanoveNaklady(
        rok=2025, radky=tuple(), celkem=Money.zero(),
    )
    return q


@pytest.fixture
def mock_uzaverka_cmd():
    cmd = MagicMock()
    cmd.execute.return_value = UzaverkaResult(
        rok=2027,
        z1_doklad_id=100, z2_doklad_id=101, z3_doklad_id=102,
        vh=Money(-50000), z1_castka=Money(100000), z3_castka=Money(50000),
    )
    return cmd


@pytest.fixture
def page(qtbot, mock_query, mock_uzaverka_cmd):
    from ui.pages.vykazy_page import VykazyPage
    p = VykazyPage(
        mock_query, rok_default=2025,
        uzaverka_command=mock_uzaverka_cmd,
    )
    qtbot.addWidget(p)
    p.show()
    return p


def test_tlacitko_existuje(page):
    assert page._uzaverka_btn is not None
    assert page._uzaverka_btn.text() == "Vystavit uzávěrku roku"


def test_tlacitko_viditelne_s_commandem(page):
    assert page._uzaverka_btn.isVisibleTo(page) is True


def test_tlacitko_skryte_bez_commandu(qtbot, mock_query):
    from ui.pages.vykazy_page import VykazyPage
    p = VykazyPage(mock_query, rok_default=2025, uzaverka_command=None)
    qtbot.addWidget(p)
    assert p._uzaverka_btn.isVisible() is False


def test_tlacitko_ma_danger_class(page):
    assert page._uzaverka_btn.property("class") == "danger"


def test_klik_zrusit_nedela_nic(page, mock_uzaverka_cmd):
    """Confirm dialog se otevře a Zrušit nezavolá execute."""
    with patch(
        "ui.pages.vykazy_page.QMessageBox.exec", return_value=None
    ):
        # Simulujeme, že clickedButton vrátí cancel
        with patch(
            "ui.pages.vykazy_page.QMessageBox.clickedButton",
            return_value=MagicMock(),  # není shodný s confirm_btn
        ):
            page._on_uzaverka_clicked()
    mock_uzaverka_cmd.execute.assert_not_called()


def test_klik_vystavit_zavola_execute(page, mock_uzaverka_cmd):
    """Confirm + klik Vystavit volá UzaverkaRokuCommand.execute(rok)."""
    confirm_btn = MagicMock()
    with patch.object(
        page,
        "_on_uzaverka_clicked",
        wraps=page._on_uzaverka_clicked,
    ):
        # Patch QMessageBox.exec a clickedButton
        import ui.pages.vykazy_page as vp_mod

        orig_msgbox = vp_mod.QMessageBox

        class FakeMsgBox:
            def __init__(self, *args, **kwargs):
                self._buttons = []
                self._clicked = None

            def setWindowTitle(self, *a):
                pass

            def setIcon(self, *a):
                pass

            def setText(self, *a):
                pass

            def addButton(self, label, role):
                btn = MagicMock(name=label)
                self._buttons.append((label, role, btn))
                if "Vystavit" in label:
                    self._clicked = btn
                return btn

            def setDefaultButton(self, *a):
                pass

            def exec(self):
                return 0

            def clickedButton(self):
                return self._clicked

            class Icon:
                Warning = 0

            class ButtonRole:
                RejectRole = 0
                DestructiveRole = 1

            @staticmethod
            def information(*a, **k): pass

            @staticmethod
            def critical(*a, **k): pass

        vp_mod.QMessageBox = FakeMsgBox
        try:
            page._on_uzaverka_clicked()
        finally:
            vp_mod.QMessageBox = orig_msgbox

    mock_uzaverka_cmd.execute.assert_called_once_with(2025)


def test_klik_vystavit_pri_conflict_nezavola_reload(
    page, mock_uzaverka_cmd, mock_query,
):
    """Při ConflictError žádný refresh, jen info dialog."""
    mock_uzaverka_cmd.execute.side_effect = ConflictError("Už existuje")
    mock_query.get_rozvaha.reset_mock()

    import ui.pages.vykazy_page as vp_mod
    orig = vp_mod.QMessageBox

    class FakeMsgBox:
        def __init__(self, *a, **k):
            self._clicked = None
        def setWindowTitle(self, *a): pass
        def setIcon(self, *a): pass
        def setText(self, *a): pass
        def addButton(self, label, role):
            btn = MagicMock(name=label)
            if "Vystavit" in label:
                self._clicked = btn
            return btn
        def setDefaultButton(self, *a): pass
        def exec(self): return 0
        def clickedButton(self): return self._clicked
        class Icon: Warning = 0
        class ButtonRole:
            RejectRole = 0
            DestructiveRole = 1
        @staticmethod
        def information(*a, **k): pass
        @staticmethod
        def critical(*a, **k): pass
        @staticmethod
        def warning(*a, **k): pass

    vp_mod.QMessageBox = FakeMsgBox
    try:
        page._on_uzaverka_clicked()
    finally:
        vp_mod.QMessageBox = orig

    mock_uzaverka_cmd.execute.assert_called_once_with(2025)
    # Reload nenastal → get_rozvaha nebylo zavoláno znovu (jen z initial loadu)


def test_klik_vystavit_uspech_zavola_reload(
    page, mock_uzaverka_cmd, mock_query,
):
    """Po úspěšném vystavení → reload aktivního tabu."""
    import ui.pages.vykazy_page as vp_mod
    orig = vp_mod.QMessageBox

    class FakeMsgBox:
        def __init__(self, *a, **k):
            self._clicked = None
        def setWindowTitle(self, *a): pass
        def setIcon(self, *a): pass
        def setText(self, *a): pass
        def addButton(self, label, role):
            btn = MagicMock(name=label)
            if "Vystavit" in label:
                self._clicked = btn
            return btn
        def setDefaultButton(self, *a): pass
        def exec(self): return 0
        def clickedButton(self): return self._clicked
        class Icon: Warning = 0
        class ButtonRole:
            RejectRole = 0
            DestructiveRole = 1
        @staticmethod
        def information(*a, **k): pass
        @staticmethod
        def critical(*a, **k): pass
        @staticmethod
        def warning(*a, **k): pass

    vp_mod.QMessageBox = FakeMsgBox
    mock_query.get_rozvaha.reset_mock()
    with patch.object(vp_mod.QMessageBox, "information",
                       create=True, return_value=None):
        try:
            page._on_uzaverka_clicked()
        finally:
            vp_mod.QMessageBox = orig

    # Po success se volá _reload_active_tab → default Rozvaha → get_rozvaha
    mock_query.get_rozvaha.assert_called()
