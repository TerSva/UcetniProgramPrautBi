"""Programmatic screenshot MainWindow do PNG.

Spuštění:
    python scripts/screenshot_main_window.py
    python scripts/screenshot_main_window.py --output scripts/screenshots/foo.png
    python scripts/screenshot_main_window.py --page doklady
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from ui.app import register_fonts
from ui.main_window import MainWindow
from ui.theme import build_stylesheet


DEFAULT_OUTPUT = "scripts/screenshots/faze_6_krok_1_skeleton.png"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Cesta k výstupnímu PNG (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--page",
        default="dashboard",
        choices=["dashboard", "doklady", "nastaveni"],
        help="Která stránka má být aktivní (default: dashboard)",
    )
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=400,
        help="Delay před screenshotem (default: 400 ms)",
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)

    register_fonts()
    app.setStyleSheet(build_stylesheet())

    window = MainWindow()

    # Přepni na požadovanou stránku (bez kliknutí — přímo API)
    if args.page != "dashboard":
        window.sidebar.set_active(args.page)
        window.sidebar.page_selected.emit(args.page)

    window.show()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    def grab_and_quit() -> None:
        pixmap = window.grab()
        ok = pixmap.save(str(output), "PNG")
        print(f"  {'✓' if ok else '✗'} screenshot → {output}")
        app.quit()

    QTimer.singleShot(args.delay_ms, grab_and_quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
