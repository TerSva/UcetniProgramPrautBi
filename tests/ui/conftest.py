"""Test fixtures pro UI vrstvu.

`main_window` fixture vytváří MainWindow s načtenými fonty a aplikovaným QSS,
jak by ho viděl uživatel. qtbot zajistí automatický cleanup.
"""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from ui.app import register_fonts
from ui.main_window import MainWindow
from ui.theme import build_stylesheet


@pytest.fixture
def main_window(qtbot):
    """Vytvoř MainWindow s kompletním theme setup.

    Vrací hotové okno po `show()`, po testu ho qtbot automaticky uklidí.
    """
    app = QApplication.instance()
    assert app is not None, "qtbot měl vytvořit QApplication"

    register_fonts()
    app.setStyleSheet(build_stylesheet())

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    return window
