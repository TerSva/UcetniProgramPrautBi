"""Smoke testy pro UI skeleton.

Ověřuje:
  * Fonty se načtou (Space Grotesk + DM Sans)
  * MainWindow má 4 stránky v stacku
  * Sidebar má položky, 4 z nich aktivní dle ACTIVE_KEYS
  * Disabled položky mají tooltip "Přijde v další fázi"
  * Klik na aktivní položku emituje signál a přepne stack
  * load_icon() vrací QIcon
  * load_icon() hází FileNotFoundError pro neexistující ikonu
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QPushButton

from ui.app import register_fonts
from ui.widgets.icon import load_icon
from ui.widgets.sidebar import ACTIVE_KEYS, Sidebar


# ──────────────────────────────────────────────
# Fonts
# ──────────────────────────────────────────────


def test_fonts_register(qtbot):
    families = register_fonts()
    assert "Space Grotesk" in families
    assert "DM Sans" in families


# ──────────────────────────────────────────────
# MainWindow / stack
# ──────────────────────────────────────────────


def test_main_window_has_four_pages(main_window):
    assert main_window.stack.count() == 4


def test_main_window_starts_on_dashboard(main_window):
    assert main_window.stack.currentIndex() == 0


# ──────────────────────────────────────────────
# Sidebar struktura
# ──────────────────────────────────────────────


def test_sidebar_has_twelve_items(main_window):
    buttons = main_window.sidebar.findChildren(QPushButton)
    sidebar_buttons = [
        b for b in buttons if b.property("class") == "sidebar-item"
    ]
    assert len(sidebar_buttons) == 12


def test_active_keys_match_enabled_buttons(main_window):
    buttons = main_window.sidebar.findChildren(QPushButton)
    sidebar_buttons = [
        b for b in buttons if b.property("class") == "sidebar-item"
    ]
    enabled_count = sum(1 for b in sidebar_buttons if b.isEnabled())
    assert enabled_count == len(ACTIVE_KEYS) == 4


def test_disabled_items_have_tooltip(main_window):
    buttons = main_window.sidebar.findChildren(QPushButton)
    sidebar_buttons = [
        b for b in buttons if b.property("class") == "sidebar-item"
    ]
    disabled = [b for b in sidebar_buttons if not b.isEnabled()]
    assert len(disabled) == 8
    for b in disabled:
        assert b.toolTip() == "Přijde v další fázi"


# ──────────────────────────────────────────────
# Interakce
# ──────────────────────────────────────────────


def test_click_doklady_switches_stack(main_window, qtbot):
    with qtbot.waitSignal(main_window.sidebar.page_selected, timeout=1000) as sig:
        main_window.sidebar._buttons["doklady"].click()
    assert sig.args == ["doklady"]
    assert main_window.stack.currentIndex() == 1


def test_click_nastaveni_switches_stack(main_window, qtbot):
    with qtbot.waitSignal(main_window.sidebar.page_selected, timeout=1000):
        main_window.sidebar._buttons["nastaveni"].click()
    assert main_window.stack.currentIndex() == 3


def test_set_active_does_not_emit_signal(main_window, qtbot):
    with qtbot.assertNotEmitted(main_window.sidebar.page_selected):
        main_window.sidebar.set_active("doklady")


# ──────────────────────────────────────────────
# Icons
# ──────────────────────────────────────────────


def test_load_icon_returns_qicon(qtbot):
    icon = load_icon("layout-dashboard", color="#FFFFFF", size=20)
    assert isinstance(icon, QIcon)
    assert not icon.isNull()


def test_load_icon_missing_raises(qtbot):
    with pytest.raises(FileNotFoundError):
        load_icon("neexistujici-ikona", color="#FFFFFF")
