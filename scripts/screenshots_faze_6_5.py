"""Screenshoty pro Fázi 6.5 — Storno přes opravný účetní předpis.

Produkuje 3 PNG:
  1. faze_6_5_detail_storno_enabled — detail ZAUCTOVANY, storno enabled
  2. faze_6_5_confirm_storno_new_text — confirm dialog s novým textem
  3. faze_6_5_detail_stornovany — detail STORNOVANY s datem storna

Run:
    QT_QPA_PLATFORM=offscreen python -m scripts.screenshots_faze_6_5
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QFontDatabase  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from domain.doklady.typy import StavDokladu, TypDokladu  # noqa: E402
from domain.shared.money import Money  # noqa: E402
from services.queries.doklady_list import DokladyListItem  # noqa: E402
from ui.dialogs.confirm_dialog import ConfirmDialog  # noqa: E402
from ui.dialogs.doklad_detail_dialog import DokladDetailDialog  # noqa: E402
from ui.theme import build_stylesheet  # noqa: E402
from ui.viewmodels.doklad_detail_vm import DokladDetailViewModel  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "screenshots"
FONTS = Path(__file__).resolve().parent.parent / "ui" / "assets" / "fonts"


def _item(
    stav: StavDokladu = StavDokladu.ZAUCTOVANY,
    datum_storna: date | None = None,
) -> DokladyListItem:
    return DokladyListItem(
        id=1,
        cislo="FV-2026-001",
        typ=TypDokladu.FAKTURA_VYDANA,
        datum_vystaveni=date(2026, 4, 1),
        datum_splatnosti=date(2026, 4, 15),
        partner_nazev="Tereza Svanda",
        castka_celkem=Money.from_koruny("12100"),
        stav=stav,
        k_doreseni=False,
        poznamka_doreseni=None,
        popis="Faktura za vývoj účetního programu.",
        datum_storna=datum_storna,
    )


class _FakeActions:
    """Stub ``DokladActionsCommand`` pro offscreen renderování."""

    def stornovat(self, doklad_id: int) -> DokladyListItem:
        return replace(
            _item(), stav=StavDokladu.STORNOVANY,
            datum_storna=date(2026, 4, 20),
        )

    def smazat(self, doklad_id: int) -> None:
        pass

    def oznac_k_doreseni(
        self, doklad_id: int, poznamka: str | None = None,
    ) -> DokladyListItem:
        return _item()

    def dores(self, doklad_id: int) -> DokladyListItem:
        return _item()

    def upravit_popis_a_splatnost(
        self, doklad_id: int, popis: str | None, splatnost: date | None,
    ) -> DokladyListItem:
        return _item()


def _grab(widget, path: Path) -> None:
    widget.ensurePolished()
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

    # 1) Detail ZAUCTOVANY — storno enabled
    vm_enabled = DokladDetailViewModel(
        doklad=_item(stav=StavDokladu.ZAUCTOVANY),
        actions_command=cast(object, _FakeActions()),  # type: ignore[arg-type]
    )
    detail_enabled = DokladDetailDialog(vm_enabled)
    detail_enabled.show()
    app.processEvents()
    _grab(detail_enabled, OUT / "faze_6_5_detail_storno_enabled.png")

    # 2) Confirm dialog s novým textem
    confirm = ConfirmDialog(
        title="Stornovat doklad",
        message=(
            "Opravdu chcete stornovat doklad FV-2026-001?\n"
            "Vytvoří se opravný účetní předpis (protizápis), "
            "který anuluje dopad původního zaúčtování "
            "ve Předvaze, Hlavní knize a v KPI na Dashboardu. "
            "Akce je nevratná."
        ),
        confirm_text="Ano, stornovat",
        destructive=True,
    )
    confirm.show()
    app.processEvents()
    _grab(confirm, OUT / "faze_6_5_confirm_storno_new_text.png")

    # 3) Detail STORNOVANY — s datem storna
    vm_stornovany = DokladDetailViewModel(
        doklad=_item(
            stav=StavDokladu.STORNOVANY,
            datum_storna=date(2026, 4, 20),
        ),
        actions_command=cast(object, _FakeActions()),  # type: ignore[arg-type]
    )
    detail_stornovany = DokladDetailDialog(vm_stornovany)
    detail_stornovany.show()
    app.processEvents()
    _grab(detail_stornovany, OUT / "faze_6_5_detail_stornovany.png")

    return 0


if __name__ == "__main__":
    sys.exit(main())
