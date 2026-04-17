"""Screenshoty pro Fázi 11 — DPH Reverse Charge.

Produkuje 4 PNG:
  1. faze_11_zauctovani_rc      — Zaúčtování FP s RC checkbox
  2. faze_11_dph_prehled        — DPH stránka s měsíční tabulkou
  3. faze_11_dph_detail         — Detail DPH za duben 2025
  4. faze_11_dph_podano         — Po označení jako podané

Run:
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m scripts.screenshots_faze_11
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QFontDatabase  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.theme import build_stylesheet  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "screenshots"
FONTS = Path(__file__).resolve().parent.parent / "ui" / "assets" / "fonts"


def _setup() -> QApplication:
    app = QApplication.instance() or QApplication(sys.argv)
    for fp in sorted(FONTS.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyleSheet(build_stylesheet())
    return app


def _grab(widget, name: str, width=1100, height=700) -> None:
    widget.resize(width, height)
    widget.show()
    widget.repaint()
    pixmap = widget.grab()
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{name}.png"
    pixmap.save(str(path))
    print(f"  ✓ {path}")


def main() -> None:
    app = _setup()

    from domain.doklady.typy import StavDokladu, TypDokladu
    from domain.shared.money import Money
    from domain.ucetnictvi.typy import TypUctu
    from services.queries.doklady_list import DokladyListItem
    from services.queries.dph_prehled import DphMesicItem, DphTransakceItem
    from services.queries.uctova_osnova import UcetItem
    from ui.dialogs.dph_detail_dialog import DphDetailDialog
    from ui.dialogs.zauctovani_dialog import ZauctovaniDialog
    from ui.pages.dph_page import DphPage
    from ui.viewmodels.dph_vm import DphViewModel
    from ui.viewmodels.zauctovani_vm import ZauctovaniViewModel

    ucty = [
        UcetItem(cislo="321", nazev="Dodavatelé", typ=TypUctu.PASIVA),
        UcetItem(cislo="343.100", nazev="DPH na vstupu z EU", typ=TypUctu.PASIVA),
        UcetItem(cislo="343.200", nazev="DPH k odvodu", typ=TypUctu.PASIVA),
        UcetItem(cislo="518", nazev="Ostatní služby", typ=TypUctu.NAKLADY),
        UcetItem(cislo="518.100", nazev="Reklama", typ=TypUctu.NAKLADY),
    ]

    # ── 1. Zaúčtování s RC ──
    item = DokladyListItem(
        id=1, cislo="FP-2025-001", typ=TypDokladu.FAKTURA_PRIJATA,
        datum_vystaveni=date(2025, 4, 23), datum_splatnosti=None,
        partner_id=1, partner_nazev="Meta Platforms Ireland",
        castka_celkem=Money(4400), stav=StavDokladu.NOVY,
        k_doreseni=False, poznamka_doreseni=None, popis="Instagram reklama",
    )
    osnova = MagicMock()
    osnova.execute.return_value = ucty
    cmd = MagicMock()
    vm = ZauctovaniViewModel(item, osnova, cmd)
    dialog = ZauctovaniDialog(vm)
    # Set base row accounts
    dialog._rows_list[0].md_combo.set_value("518.100")
    dialog._rows_list[0].dal_combo.set_value("321")
    # Enable RC
    dialog._rc_check_widget.setChecked(True)
    _grab(dialog, "faze_11_zauctovani_rc", width=900, height=650)
    print("1/4 Zaúčtování s RC")

    # ── 2. DPH přehled ──
    mesice = []
    for m in range(1, 13):
        if m == 4:
            mesice.append(DphMesicItem(
                rok=2025, mesic=4,
                zaklad_celkem=Money(105000),
                dph_celkem=Money(22050),
                pocet_transakci=9,
                je_podane=False,
            ))
        else:
            mesice.append(DphMesicItem(
                rok=2025, mesic=m,
                zaklad_celkem=Money.zero(),
                dph_celkem=Money.zero(),
                pocet_transakci=0,
                je_podane=False,
            ))

    prehled_q = MagicMock()
    prehled_q.execute.return_value = mesice
    detail_q = MagicMock()
    podani_cmd = MagicMock()
    dph_vm = DphViewModel(prehled_q, detail_q, podani_cmd)
    page = DphPage(dph_vm)
    _grab(page, "faze_11_dph_prehled")
    print("2/4 DPH přehled")

    # ── 3. DPH detail ──
    transakce = []
    for i in range(1, 10):
        castka = Money(4400 + i * 1100)
        dph = Money(round(castka.to_halire() * 21 / 100))
        transakce.append(DphTransakceItem(
            doklad_cislo=f"FP-2025-{i:03d}",
            doklad_datum=date(2025, 4, i + 5),
            partner_nazev="Meta Platforms Ireland",
            zaklad=castka,
            dph=dph,
            sazba=Decimal("21.0"),
        ))

    mesic_item = DphMesicItem(
        rok=2025, mesic=4,
        zaklad_celkem=Money(105000),
        dph_celkem=Money(22050),
        pocet_transakci=9,
        je_podane=False,
    )
    detail_dialog = DphDetailDialog(dph_vm, 4, mesic_item, transakce)
    _grab(detail_dialog, "faze_11_dph_detail", width=750, height=650)
    print("3/4 DPH detail")

    # ── 4. DPH podáno ──
    mesic_podane = DphMesicItem(
        rok=2025, mesic=4,
        zaklad_celkem=Money(105000),
        dph_celkem=Money(22050),
        pocet_transakci=9,
        je_podane=True,
    )
    detail_podane = DphDetailDialog(dph_vm, 4, mesic_podane, transakce)
    _grab(detail_podane, "faze_11_dph_podano", width=750, height=650)
    print("4/4 DPH podáno")

    print(f"\nHotovo! {len(list(OUT.glob('faze_11_*.png')))} screenshotů v {OUT}/")


if __name__ == "__main__":
    main()
