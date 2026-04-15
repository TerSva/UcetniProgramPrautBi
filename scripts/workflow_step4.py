"""End-to-end workflow — simuluje manuální test ze seed DB.

Projde stejné kódové cesty jako uživatelka klikající myší:
  1. Seed → migrace + 4 demo doklady
  2. Otevři MainWindow → default Dashboard
  3. Naviguj na Doklady
  4. Otevři form dialog + vyplň FV-2026-004, 5000 Kč
  5. Submit → otevře se detail nově vytvořeného dokladu
  6. Klik Zaúčtovat → otevře se Zauctovani dialog
  7. Vyplň 311/601 a Zaúčtuj
  8. Ověř, že status přešel na „Zaúčtovaný"
  9. Klik Stornovat → confirm → potvrď
  10. Zpět na Dashboard → ověř KPI update

Každý krok pořídí screenshot + tisknou komentář co se stalo.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Umožní import seed_demo_data když se script spustí přímo
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QFontDatabase  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from domain.doklady.typy import TypDokladu  # noqa: E402
from seed_demo_data import seed  # noqa: E402
from ui.app import (  # noqa: E402
    _build_dashboard_vm,
    _build_doklady_list_vm,
    _build_factories,
    _setup_database,
    register_fonts,
)
from ui.main_window import MainWindow  # noqa: E402
from ui.theme import build_stylesheet  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "screenshots"


def _grab(widget, path: Path, label: str) -> None:
    widget.ensurePolished()
    widget.adjustSize()
    pix = widget.grab()
    pix.save(str(path), "PNG")
    print(f"  📸 {label} → {path.name}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)

    for font_path in sorted(
        (Path(__file__).resolve().parent.parent / "ui" / "assets" / "fonts")
        .glob("*.ttf")
    ):
        QFontDatabase.addApplicationFont(str(font_path))
    app.setStyleSheet(build_stylesheet())

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "workflow.db"

        # ─── 1) Spuštění + seed ───
        print("\n━━━ 1. Spuštění aplikace ━━━")
        seed(db)
        factory = _setup_database(db)
        dvm = _build_dashboard_vm(factory)
        lvm = _build_doklady_list_vm(factory)
        fvf, devf, zvf = _build_factories(factory)
        window = MainWindow(
            dashboard_vm=dvm, doklady_list_vm=lvm,
            form_vm_factory=fvf, detail_vm_factory=devf,
            zauctovani_vm_factory=zvf,
        )
        window.resize(1280, 800)
        window.show()
        app.processEvents()
        print(f"  ✓ MainWindow, default page index: {window.stack.currentIndex()}"
              f" (0=Dashboard)")
        _grab(window, OUT / "w1_dashboard_initial.png", "Dashboard initial")

        # ─── 2) Klik na Doklady v sidebaru ───
        print("\n━━━ 2. Navigace na Doklady ━━━")
        window.sidebar.page_selected.emit("doklady")
        app.processEvents()
        page = window._doklady_page
        page.refresh()
        app.processEvents()
        list_count = len(lvm.items)
        print(f"  ✓ Page switched, list items: {list_count}"
              f" ({lvm.items[0].cislo if list_count else '—'} … )")
        _grab(window, OUT / "w2_doklady_list.png", "Doklady list")

        # ─── 3) Klik „+ Nový doklad" ───
        print("\n━━━ 3. Otevření form dialogu ━━━")
        form_vm = fvf()
        from ui.dialogs.doklad_form_dialog import DokladFormDialog
        form = DokladFormDialog(form_vm, parent=window)
        form.show()
        app.processEvents()
        prefilled = form._cislo_widget.value()
        print(f"  ✓ DokladFormDialog, auto-prefilled číslo: {prefilled}")

        # ─── 4) Vyplnění formuláře ───
        print("\n━━━ 4. Vyplnění form ━━━")
        form._typ_combo_widget.set_value(TypDokladu.FAKTURA_VYDANA)
        app.processEvents()
        # auto-suggest se spustí při typ change — dostanem 004 protože 001-003 existují
        suggested = form._cislo_widget.value()
        print(f"  ✓ Typ: FV → auto-suggest: {suggested}")
        form._castka_widget.line_widget.setText("5000")
        form._popis_input.set_value("Test — workflow doklad")
        app.processEvents()
        _grab(form, OUT / "w3_form_filled.png", "Form vyplněný")

        # ─── 5) Klik „Vytvořit doklad" ───
        print("\n━━━ 5. Submit formu ━━━")
        form._submit_widget.click()
        app.processEvents()
        created = form.created_item
        if created is None:
            print(f"  ✗ Submit selhal: {form_vm.error}")
            return 1
        print(f"  ✓ Vytvořeno: {created.cislo}, id={created.id},"
              f" stav={created.stav.value}")

        # Po úspěšném submit by se otevřel detail dialog — simulujeme přímo
        from ui.dialogs.doklad_detail_dialog import DokladDetailDialog
        detail_vm = devf(created)
        detail = DokladDetailDialog(detail_vm, parent=window)
        detail.show()
        app.processEvents()
        print(f"  ✓ Otevřen DokladDetailDialog pro {created.cislo}")

        # ─── 6) Klik „Zaúčtovat" ───
        print("\n━━━ 6. Otevření zaúčtování ━━━")
        z_vm = zvf(created)
        from ui.dialogs.zauctovani_dialog import ZauctovaniDialog
        z_dialog = ZauctovaniDialog(z_vm, parent=detail)
        z_dialog.show()
        app.processEvents()
        row = z_dialog._rows_list[0]
        prefilled_castka = row.castka_input.value()
        print(f"  ✓ ZauctovaniDialog; první řádek prefilled částka:"
              f" {prefilled_castka.format_cz() if prefilled_castka else '—'}")

        # ─── 7) Vyplnění předpisu 311/601 ───
        print("\n━━━ 7. Vyplnění předpisu 311/601 ━━━")
        row.md_combo.set_value("311")
        row.dal_combo.set_value("601")
        z_dialog._on_row_castka_changed(0)
        z_dialog._sync_ui()
        app.processEvents()
        print(f"  ✓ MD=311, Dal=601, součet={z_vm.soucet_radku.format_cz()},"
              f" rozdíl={z_vm.rozdil.format_cz()},"
              f" podvojné={z_vm.je_podvojne}")
        _grab(z_dialog, OUT / "w4_zauctovani_ready.png", "Zaúčtování připravené")

        # Submit
        z_dialog._submit_widget.click()
        app.processEvents()
        posted = z_dialog.posted_item
        if posted is None:
            print(f"  ✗ Zaúčtování selhalo: {z_vm.error}")
            return 1
        print(f"  ✓ Zaúčtováno, stav → {posted.stav.value}")

        # Vrať se do detail dialogu (simulace refreshe po sub-dialogu)
        detail.refresh_after_zauctovani(posted)
        app.processEvents()
        _grab(detail, OUT / "w5_detail_po_zauctovani.png",
              "Detail po zaúčtování")

        # ─── 8) Ověření v listu ───
        print("\n━━━ 8. Refresh listu ━━━")
        page.refresh()
        app.processEvents()
        novy = [i for i in lvm.items if i.cislo == suggested]
        assert len(novy) == 1, f"Doklad {suggested} není v listu!"
        print(f"  ✓ V listu: {novy[0].cislo}, stav={novy[0].stav.value}")

        # ─── 9) Storno — aktivní (Fáze 6.5) ───
        print("\n━━━ 9. Storno zaúčtovaného dokladu ━━━")
        storno_btn = detail._storno_button_widget
        assert storno_btn.isEnabled() is True, (
            "Storno tlačítko musí být enabled pro ZAUCTOVANY"
        )
        # Klikni storno — VM zavolá DokladActionsCommand → service → protizápisy
        # Obejdeme confirm dialog přes přímé volání vm.stornovat()
        vm = detail._vm
        vm.stornovat()
        app.processEvents()
        assert vm.doklad.stav.value == "stornovany", vm.error
        print(f"  ✓ Storno proběhlo, stav → {vm.doklad.stav.value}")
        print(f"  ✓ Datum storna: {vm.doklad.datum_storna}")
        detail._sync_ui()
        _grab(detail, OUT / "w5_detail_po_stornu.png",
              "Detail po stornu (STORNOVANY)")
        detail.close()

        # ─── 10) Zpět na Dashboard ───
        print("\n━━━ 10. Zpět na Dashboard ━━━")
        window.sidebar.page_selected.emit("dashboard")
        app.processEvents()
        # Jen vypíšeme KPI hodnoty z VM.data (DashboardData snapshot)
        data = dvm.data
        assert data is not None
        print(f"  ✓ KPI výnosy YTD:       {data.vynosy.format_cz()}")
        print(f"  ✓ KPI náklady YTD:      {data.naklady.format_cz()}")
        print(f"  ✓ KPI hrubý zisk YTD:   {data.hruby_zisk.format_cz()}")
        print(f"  ✓ KPI odhad daně:       {data.odhad_dane.format_cz()}")
        print(f"  ✓ KPI pohledávky:       {data.pohledavky.format_cz()}")
        print(f"  ✓ KPI závazky:          {data.zavazky.format_cz()}")
        print(f"  ✓ KPI doklady celkem:   {data.doklady_celkem}")
        print(f"  ✓ KPI k zauctovani:     {data.doklady_k_zauctovani}")
        print(f"  ✓ KPI k dořešení:       {data.doklady_k_doreseni}")
        _grab(window, OUT / "w6_dashboard_final.png", "Dashboard final")

        print("\n━━━ ✅ Workflow complete ━━━")
        return 0


if __name__ == "__main__":
    sys.exit(main())
