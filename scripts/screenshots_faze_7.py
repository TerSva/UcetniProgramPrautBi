"""Screenshoty pro Fázi 7 — Účtová osnova.

Produkuje 3 PNG:
  1. faze_7_osnova_tree       — Strom účtů s rozbalenými třídami
  2. faze_7_osnova_filtered   — Filtr: pouze aktivní účty
  3. faze_7_analytika_dialog  — Dialog přidání analytiky

Run:
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m scripts.screenshots_faze_7
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QFontDatabase  # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton  # noqa: E402

from domain.ucetnictvi.typy import TypUctu  # noqa: E402
from services.queries.chart_of_accounts import (  # noqa: E402
    ChartOfAccountsItem,
    TridaGroup,
)
from ui.dialogs.analytika_dialog import AnalytikaDialog  # noqa: E402
from ui.pages.chart_of_accounts_page import ChartOfAccountsPage  # noqa: E402
from ui.theme import build_stylesheet  # noqa: E402
from ui.viewmodels.chart_of_accounts_vm import ChartOfAccountsViewModel  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "screenshots"
FONTS = Path(__file__).resolve().parent.parent / "ui" / "assets" / "fonts"


# ─── Fake data ───────────────────────────────────────────

def _item(cislo, nazev, typ=TypUctu.NAKLADY, active=True, analytiky=()):
    return ChartOfAccountsItem(
        cislo=cislo, nazev=nazev, typ=typ,
        is_active=active, is_analytic="." in cislo,
        parent_kod=cislo.split(".")[0] if "." in cislo else None,
        popis=None, analytiky=analytiky,
    )


FAKE_TRIDY = [
    TridaGroup(
        trida=2, nazev="Krátkodobý finanční majetek a peněžní prostředky",
        ucty=(
            _item("211", "Pokladna", TypUctu.AKTIVA),
            _item("221", "Bankovní účty", TypUctu.AKTIVA, analytiky=(
                _item("221.001", "Money Banka", TypUctu.AKTIVA),
                _item("221.002", "Fio banka", TypUctu.AKTIVA),
            )),
        ),
        active_count=2, total_count=2,
    ),
    TridaGroup(
        trida=3, nazev="Zúčtovací vztahy",
        ucty=(
            _item("311", "Pohledávky z obchodních vztahů", TypUctu.AKTIVA),
            _item("321", "Dluhy z obchodních vztahů", TypUctu.PASIVA),
            _item("343", "DPH", TypUctu.AKTIVA, active=False),
        ),
        active_count=2, total_count=3,
    ),
    TridaGroup(
        trida=5, nazev="Náklady",
        ucty=(
            _item("501", "Spotřeba materiálu", analytiky=(
                _item("501.100", "Kancelářské potřeby"),
                _item("501.200", "Obalový materiál"),
            )),
            _item("518", "Ostatní služby", analytiky=(
                _item("518.100", "Účetní služby"),
                _item("518.200", "IT služby"),
            )),
        ),
        active_count=2, total_count=2,
    ),
    TridaGroup(
        trida=6, nazev="Výnosy",
        ucty=(
            _item("602", "Tržby za služby", TypUctu.VYNOSY),
            _item("604", "Tržby za zboží", TypUctu.VYNOSY, active=False),
        ),
        active_count=1, total_count=2,
    ),
]


class FakeQuery:
    def execute(self, show_inactive=True):
        if not show_inactive:
            # Filtruj neaktivní
            result = []
            for t in FAKE_TRIDY:
                active_ucty = tuple(u for u in t.ucty if u.is_active)
                if active_ucty:
                    result.append(TridaGroup(
                        trida=t.trida, nazev=t.nazev, ucty=active_ucty,
                        active_count=t.active_count,
                        total_count=len(active_ucty),
                    ))
            return result
        return FAKE_TRIDY


class FakeCommand:
    def activate_ucet(self, cislo): pass
    def deactivate_ucet(self, cislo): pass
    def add_analytika(self, *a, **kw): pass
    def update_analytika(self, *a, **kw): pass


# ─── Screenshot helpers ─────────────────────────────────


def _setup() -> QApplication:
    app = QApplication.instance() or QApplication(sys.argv)
    for fp in sorted(FONTS.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyleSheet(build_stylesheet())
    return app


def _grab(widget, name: str, width=900, height=700) -> None:
    widget.resize(width, height)
    widget.show()
    widget.repaint()
    pixmap = widget.grab()
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{name}.png"
    pixmap.save(str(path))
    print(f"  ✓ {path}")


# ─── Screenshots ─────────────────────────────────────────


def main() -> None:
    app = _setup()

    vm = ChartOfAccountsViewModel(FakeQuery(), FakeCommand())

    # 1. Osnova tree — expand first two groups
    page = ChartOfAccountsPage(vm)
    # Expand groups by clicking headers
    headers = page.findChildren(QPushButton)
    trida_headers = [h for h in headers if h.property("class") == "osnova-trida-header"]
    for h in trida_headers[:3]:  # expand first 3
        h.setChecked(True)
    _grab(page, "faze_7_osnova_tree")
    print("1/3 Osnova tree view")

    # 2. Filtered view (only active)
    page2 = ChartOfAccountsPage(vm)
    page2._show_inactive_widget.setChecked(False)
    headers2 = page2.findChildren(QPushButton)
    trida_headers2 = [h for h in headers2 if h.property("class") == "osnova-trida-header"]
    for h in trida_headers2[:3]:
        h.setChecked(True)
    _grab(page2, "faze_7_osnova_filtered")
    print("2/3 Osnova filtered (active only)")

    # 3. Analytika dialog
    dialog = AnalytikaDialog("501", "Spotřeba materiálu")
    dialog._suffix_widget.set_value("300")
    dialog._nazev_widget.set_value("Pohonné hmoty")
    dialog._popis_widget.set_value("Benzín, nafta pro služební vozidla")
    _grab(dialog, "faze_7_analytika_dialog", width=450, height=400)
    print("3/3 Analytika dialog")

    print(f"\nHotovo! {len(list(OUT.glob('faze_7_*.png')))} screenshotů v {OUT}/")


if __name__ == "__main__":
    main()
