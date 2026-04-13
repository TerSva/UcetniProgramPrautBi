"""Programmatic screenshot MainWindow do PNG.

Spuštění:
    python scripts/screenshot_main_window.py
    python scripts/screenshot_main_window.py --output scripts/screenshots/foo.png
    python scripts/screenshot_main_window.py --page doklady
    python scripts/screenshots/seed_demo_data.py /tmp/demo.db && \
        python scripts/screenshot_main_window.py --db /tmp/demo.db \
            --output scripts/screenshots/faze_6_krok_2_dashboard_with_data.png
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from ui.app import _build_dashboard_vm, _setup_database, register_fonts
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
        "--db",
        default=None,
        help="Cesta k SQLite DB. None → tempfile (prázdná DB).",
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

    if args.db:
        db_path = Path(args.db)
    else:
        # Tempfile, ať produkční ucetni.db nezůstane na disku
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        db_path = Path(tmp.name)

    factory = _setup_database(db_path)
    dashboard_vm = _build_dashboard_vm(factory)

    window = MainWindow(dashboard_vm=dashboard_vm)

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
