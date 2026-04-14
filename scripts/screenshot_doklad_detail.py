"""Programmatic screenshot DokladDetailDialog do PNG.

Zobrazí detail dokladu s aktivním „K dořešení" boxem.

Spuštění:
    python scripts/seed_demo_data.py /tmp/demo.db && \
        python scripts/screenshot_doklad_detail.py --db /tmp/demo.db \
            --output scripts/screenshots/faze_6_krok_3_doklad_detail.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from services.queries.doklady_list import DokladyFilter, KDoreseniFilter
from ui.app import _build_doklady_list_vm, _setup_database, register_fonts
from ui.dialogs.doklad_detail_dialog import DokladDetailDialog
from ui.theme import build_stylesheet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="scripts/screenshots/faze_6_krok_3_doklad_detail.png",
    )
    parser.add_argument("--db", required=True)
    parser.add_argument("--delay-ms", type=int, default=400)
    args = parser.parse_args()

    app = QApplication(sys.argv)
    register_fonts()
    app.setStyleSheet(build_stylesheet())

    factory = _setup_database(Path(args.db))
    vm = _build_doklady_list_vm(factory)
    vm.apply_filters(DokladyFilter(k_doreseni=KDoreseniFilter.POUZE))

    if not vm.items:
        # Fallback: vezmi první doklad
        vm.apply_filters(DokladyFilter())
    if not vm.items:
        print("  ✗ žádné doklady v DB")
        return 1

    item = vm.items[0]
    dialog = DokladDetailDialog(item)
    dialog.show()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    def grab_and_quit() -> None:
        pixmap = dialog.grab()
        ok = pixmap.save(str(output), "PNG")
        print(f"  {'✓' if ok else '✗'} screenshot → {output}")
        app.quit()

    QTimer.singleShot(args.delay_ms, grab_and_quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
