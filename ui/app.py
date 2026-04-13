"""Application bootstrap — registrace fontů, aplikace QSS, spuštění.

Jediné místo, kde se volá QApplication.setStyleSheet(). Ostatní widgety
NIKDY nevolají setStyleSheet() — barvy a typografie jdou přes QSS class
properties.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.theme import build_stylesheet


_FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"


def register_fonts() -> list[str]:
    """Načti všechny TTF soubory z ui/assets/fonts/.

    Returns:
        Seznam registrovaných font families (unikátní, seřazený).
    """
    families: set[str] = set()
    for font_path in sorted(_FONTS_DIR.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id == -1:
            continue
        families.update(QFontDatabase.applicationFontFamilies(font_id))
    return sorted(families)


def run() -> int:
    """Spusť aplikaci. Vrací exit code z QApplication.exec()."""
    app = QApplication(sys.argv)

    register_fonts()
    app.setStyleSheet(build_stylesheet())

    window = MainWindow()
    window.show()

    return app.exec()
