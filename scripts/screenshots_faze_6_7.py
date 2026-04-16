"""Screenshoty pro Fázi 6.7 — filter-aware UI, form k dořešení, dashboard drill.

Produkuje 5 PNG:
  1. faze_6_7_filter_aware_default     — Doklady list, default stav
  2. faze_6_7_filter_aware_active      — Doklady list, filtr „Pouze k dořešení"
  3. faze_6_7_form_dialog_with_doreseni — Nový doklad dialog s checkboxem
  4. faze_6_7_detail_edit_with_doreseni — Detail dialog v edit mode
  5. faze_6_7_dashboard_drilldown       — Dashboard s 4 KPI kartami

Run:
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m scripts.screenshots_faze_6_7
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QFontDatabase  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from domain.doklady.typy import StavDokladu, TypDokladu  # noqa: E402
from domain.shared.money import Money  # noqa: E402
from services.queries.doklady_list import (  # noqa: E402
    DokladyFilter,
    DokladyListItem,
    KDoreseniFilter,
)
from ui.dialogs.doklad_detail_dialog import DokladDetailDialog  # noqa: E402
from ui.dialogs.doklad_form_dialog import DokladFormDialog  # noqa: E402
from ui.pages.dashboard_page import DashboardPage  # noqa: E402
from ui.pages.doklady_page import DokladyPage  # noqa: E402
from ui.theme import build_stylesheet  # noqa: E402
from ui.viewmodels import DashboardViewModel, DokladyListViewModel  # noqa: E402
from ui.viewmodels.doklad_detail_vm import DokladDetailViewModel  # noqa: E402
from ui.viewmodels.doklad_form_vm import DokladFormViewModel  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "screenshots"
FONTS = Path(__file__).resolve().parent.parent / "ui" / "assets" / "fonts"


# ─── Test data ───────────────────────────────────────────

ITEMS = [
    DokladyListItem(
        id=1,
        cislo="FV-2026-001",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 1, 15),
        datum_splatnosti=date(2026, 2, 15),
        partner_nazev="ABC s.r.o.",
        castka_celkem=Money.from_koruny("12100"),
        stav=StavDokladu.ZAUCTOVANY,
        k_doreseni=False,
        poznamka_doreseni=None,
        popis="Faktura za konzultace.",
        datum_storna=None,
    ),
    DokladyListItem(
        id=2,
        cislo="FV-2026-002",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 2, 1),
        datum_splatnosti=date(2026, 3, 1),
        partner_nazev="XYZ a.s.",
        castka_celkem=Money.from_koruny("24200"),
        stav=StavDokladu.NOVY,
        k_doreseni=False,
        poznamka_doreseni=None,
        popis="Faktura za vývoj.",
        datum_storna=None,
    ),
    DokladyListItem(
        id=3,
        cislo="FV-2026-003",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 3, 10),
        datum_splatnosti=date(2026, 4, 10),
        partner_nazev="Tereza Svanda",
        castka_celkem=Money.from_koruny("5000"),
        stav=StavDokladu.ZAUCTOVANY,
        k_doreseni=True,
        poznamka_doreseni="Chybí příloha smlouvy",
        popis="Faktura za školení.",
        datum_storna=None,
    ),
    DokladyListItem(
        id=4,
        cislo="FP-2026-001",
        typ=TypDokladu.FAKTURA_PRIJATA,
        datum_vystaveni=date(2026, 3, 20),
        datum_splatnosti=date(2026, 4, 20),
        partner_nazev="Dodavatel s.r.o.",
        castka_celkem=Money.from_koruny("6050"),
        stav=StavDokladu.ZAUCTOVANY,
        k_doreseni=False,
        poznamka_doreseni=None,
        popis="Nákup kancelářských potřeb.",
        datum_storna=None,
    ),
]


class _FakeDokladyListQuery:
    """Returns items filtered by KDoreseniFilter."""

    def execute(self, f: DokladyFilter) -> list[DokladyListItem]:
        result = list(ITEMS)
        if f.k_doreseni == KDoreseniFilter.SKRYT:
            result = [i for i in result if not i.k_doreseni]
        elif f.k_doreseni == KDoreseniFilter.POUZE:
            result = [i for i in result if i.k_doreseni]
        if f.typ is not None:
            result = [i for i in result if i.typ == f.typ]
        return result


class _FakeCountAllQuery:
    def execute(self) -> int:
        return len(ITEMS)


class _FakeActions:
    """Stub DokladActionsCommand."""

    def stornovat(self, doklad_id: int) -> DokladyListItem:
        return ITEMS[0]

    def smazat(self, doklad_id: int) -> None:
        pass

    def oznac_k_doreseni(
        self, doklad_id: int, poznamka: str | None = None,
    ) -> DokladyListItem:
        return ITEMS[0]

    def dores(self, doklad_id: int) -> DokladyListItem:
        return ITEMS[0]

    def upravit_popis_a_splatnost(
        self, doklad_id: int, popis: str | None, splatnost: date | None,
    ) -> DokladyListItem:
        return ITEMS[0]


class _FakeNextNumberQuery:
    def execute(self, typ: TypDokladu, rok: int) -> str:
        return "FV-2026-005"


class _FakeCreateCommand:
    def execute(self, data) -> DokladyListItem:
        return ITEMS[0]


class _FakeDashboardQuery:
    """Provides static dashboard data."""

    def execute(self):
        from services.queries.dashboard import DashboardData
        return DashboardData(
            doklady_celkem=4,
            doklady_k_zauctovani=1,
            doklady_k_doreseni=1,
            pohledavky=Money.from_koruny("36300"),
            zavazky=Money.from_koruny("6050"),
            rok=2026,
            vynosy=Money.from_koruny("30000"),
            naklady=Money.from_koruny("5000"),
            hruby_zisk=Money.from_koruny("25000"),
            odhad_dane=Money.from_koruny("4750"),
        )


def _grab(widget, path: Path, size: tuple[int, int] | None = None) -> None:
    """Grab widget screenshot."""
    widget.ensurePolished()
    if size:
        widget.resize(*size)
    else:
        widget.adjustSize()
    pix = widget.grab()
    pix.save(str(path), "PNG")
    print(f"  → {path.relative_to(OUT.parent)}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv)
    for font_path in sorted(FONTS.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(font_path))
    app.setStyleSheet(build_stylesheet())

    # ─── 1. Doklady — default (K dořešení = Skrýt) ───
    vm1 = DokladyListViewModel(
        _FakeDokladyListQuery(),
        count_query=_FakeCountAllQuery(),
    )
    page1 = DokladyPage(vm1)
    page1.show()
    app.processEvents()
    _grab(page1, OUT / "faze_6_7_filter_aware_default.png", (1000, 600))

    # ─── 2. Doklady — filtr „Pouze k dořešení" ───
    vm2 = DokladyListViewModel(
        _FakeDokladyListQuery(),
        count_query=_FakeCountAllQuery(),
    )
    page2 = DokladyPage(vm2)
    page2.apply_k_doreseni_filter()
    page2.show()
    app.processEvents()
    _grab(page2, OUT / "faze_6_7_filter_aware_active.png", (1000, 600))

    # ─── 3. Form dialog — checkbox K dořešení ───
    form_vm = DokladFormViewModel(
        next_number_query=_FakeNextNumberQuery(),
        create_command=_FakeCreateCommand(),
        actions_command=cast(object, _FakeActions()),
    )
    form_dialog = DokladFormDialog(form_vm)
    # Pre-fill some fields and check the k_doreseni box
    form_dialog._typ_combo.set_value(TypDokladu.FAKTURA_VYDANA)
    form_dialog._castka_input.set_value(Money.from_koruny("5000"))
    form_dialog._popis_input.set_value("Test 6.7")
    form_dialog._k_doreseni_check_widget.setChecked(True)
    form_dialog._poznamka_doreseni_widget.set_value("test workflow")
    form_dialog.show()
    app.processEvents()
    _grab(form_dialog, OUT / "faze_6_7_form_dialog_with_doreseni.png")

    # ─── 4. Detail dialog — edit mode s k_doreseni ───
    novy_item = ITEMS[1]  # FV-2026-002 NOVY
    detail_vm = DokladDetailViewModel(
        doklad=novy_item,
        actions_command=cast(object, _FakeActions()),
    )
    detail_dialog = DokladDetailDialog(detail_vm)
    detail_dialog.show()
    app.processEvents()
    # Trigger edit mode
    detail_dialog._edit_button.click()
    app.processEvents()
    _grab(detail_dialog, OUT / "faze_6_7_detail_edit_with_doreseni.png")

    # ─── 5. Dashboard ───
    dashboard_vm = DashboardViewModel(_FakeDashboardQuery())
    dashboard = DashboardPage(dashboard_vm)
    dashboard.show()
    app.processEvents()
    _grab(dashboard, OUT / "faze_6_7_dashboard_drilldown.png", (1000, 600))

    print(f"\n✅ 5 screenshotů uloženo do {OUT}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
