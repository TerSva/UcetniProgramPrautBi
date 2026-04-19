"""Smoke testy pro UI skeleton.

Ověřuje:
  * Fonty se načtou (Space Grotesk + DM Sans)
  * MainWindow má 19 stránek v stacku (BV removed from sub-pages)
  * Sidebar má 5 sekcí s celkem 18 navigovatelnými položkami
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
from ui.widgets.sidebar import ACTIVE_KEYS, SIDEBAR_STRUCTURE, Sidebar


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


def test_main_window_has_twenty_pages(main_window):
    assert main_window.stack.count() == 19


def test_main_window_starts_on_dashboard(main_window):
    assert main_window.stack.currentIndex() == 0


# ──────────────────────────────────────────────
# Sidebar struktura
# ──────────────────────────────────────────────


def test_sidebar_has_five_sections(main_window):
    assert len(SIDEBAR_STRUCTURE) == 5
    section_names = [s.title for s in SIDEBAR_STRUCTURE]
    assert section_names == ["Přehled", "Účetnictví", "Evidence", "Výstupy", "Systém"]


def test_sidebar_has_navigable_items(main_window):
    """Všechny navigovatelné klíče jsou v ACTIVE_KEYS."""
    assert len(ACTIVE_KEYS) == 18


def test_doklady_has_sub_items(main_window):
    """Doklady parent má 5 sub-items (BV removed)."""
    for section in SIDEBAR_STRUCTURE:
        for item in section.items:
            if item.key == "doklady":
                assert len(item.sub_items) == 5
                sub_keys = [s.key for s in item.sub_items]
                assert "doklady_fv" in sub_keys
                assert "doklady_fp" in sub_keys
                return
    pytest.fail("Doklady item not found")


# ──────────────────────────────────────────────
# Interakce
# ──────────────────────────────────────────────


def test_click_sub_item_navigates(main_window, qtbot):
    """Klik na sub-item emituje signál s jeho klíčem."""
    # Expand doklady sub-menu first
    parent_btn = main_window.sidebar._parent_buttons.get("doklady")
    assert parent_btn is not None
    parent_btn.click()

    with qtbot.waitSignal(main_window.sidebar.page_selected, timeout=1000) as sig:
        main_window.sidebar._buttons["doklady_fv"].click()
    assert sig.args == ["doklady_fv"]


def test_click_parent_expands_sub_menu(main_window, qtbot):
    """Klik na parent item expanduje/collapsuje sub-menu."""
    container = main_window.sidebar._sub_containers.get("doklady")
    assert container is not None
    assert container.isHidden()  # default collapsed

    parent_btn = main_window.sidebar._parent_buttons["doklady"]
    parent_btn.click()
    assert not container.isHidden()  # expanded

    parent_btn.click()
    assert container.isHidden()  # collapsed again


def test_click_nastaveni_switches_stack(main_window, qtbot):
    with qtbot.waitSignal(main_window.sidebar.page_selected, timeout=1000):
        main_window.sidebar._buttons["nastaveni"].click()
    idx = main_window.page_index["nastaveni"]
    assert main_window.stack.currentIndex() == idx


def test_set_active_does_not_emit_signal(main_window, qtbot):
    with qtbot.assertNotEmitted(main_window.sidebar.page_selected):
        main_window.sidebar.set_active("dashboard")


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
