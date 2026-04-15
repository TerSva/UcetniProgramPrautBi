"""Vyrenderuj 4 screenshoty dialogů Fáze 6 / Krok 4.

Použije ``offscreen`` Qt platformu + ``QWidget.grab()`` → PNG.

Run:
    QT_QPA_PLATFORM=offscreen python -m scripts.screenshots_step4
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
from services.commands.create_doklad import CreateDokladInput  # noqa: E402
from services.commands.zauctovat_doklad import (  # noqa: E402
    ZauctovatDokladInput,
)
from services.queries.doklady_list import DokladyListItem  # noqa: E402
from services.queries.uctova_osnova import UcetItem  # noqa: E402
from ui.dialogs.confirm_dialog import ConfirmDialog  # noqa: E402
from ui.dialogs.doklad_detail_dialog import DokladDetailDialog  # noqa: E402
from ui.dialogs.doklad_form_dialog import DokladFormDialog  # noqa: E402
from ui.dialogs.zauctovani_dialog import ZauctovaniDialog  # noqa: E402
from ui.theme import build_stylesheet  # noqa: E402
from ui.viewmodels.doklad_detail_vm import DokladDetailViewModel  # noqa: E402
from ui.viewmodels.doklad_form_vm import DokladFormViewModel  # noqa: E402
from ui.viewmodels.zauctovani_vm import ZauctovaniViewModel  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "screenshots"
FONTS = Path(__file__).resolve().parent.parent / "ui" / "assets" / "fonts"


def _item(
    stav: StavDokladu = StavDokladu.NOVY,
    popis: str | None = "Faktura za vývoj účetního programu.",
    k_doreseni: bool = False,
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
        k_doreseni=k_doreseni,
        poznamka_doreseni=None,
        popis=popis,
    )


class _FakeNextNumber:
    def execute(self, typ: TypDokladu, rok: int) -> str:
        return "FV-2026-001"


class _FakeCreate:
    def execute(self, data: CreateDokladInput) -> DokladyListItem:
        return _item()


class _FakeOsnova:
    def execute(self, jen_aktivni: bool = True) -> list[UcetItem]:
        return [
            UcetItem(cislo="311", nazev="Odběratelé", typ="A"),
            UcetItem(cislo="601", nazev="Tržby z prodeje služeb", typ="V"),
            UcetItem(cislo="343", nazev="DPH", typ="P"),
        ]


class _FakeZauctovat:
    def execute(self, data: ZauctovatDokladInput) -> DokladyListItem:
        return replace(_item(), stav=StavDokladu.ZAUCTOVANY)


class _FakeActions:
    def stornovat(self, doklad_id: int) -> DokladyListItem:
        return replace(_item(), stav=StavDokladu.STORNOVANY)

    def smazat(self, doklad_id: int) -> None:
        pass

    def oznac_k_doreseni(
        self, doklad_id: int, poznamka: str | None = None,
    ) -> DokladyListItem:
        return replace(_item(), k_doreseni=True, poznamka_doreseni=poznamka)

    def dores(self, doklad_id: int) -> DokladyListItem:
        return replace(_item(), k_doreseni=False, poznamka_doreseni=None)

    def upravit_popis_a_splatnost(
        self, doklad_id: int, popis: str | None, splatnost: date | None,
    ) -> DokladyListItem:
        return replace(_item(), popis=popis, datum_splatnosti=splatnost)


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

    # 1) DokladFormDialog
    form_vm = DokladFormViewModel(
        next_number_query=cast(object, _FakeNextNumber()),
        create_command=cast(object, _FakeCreate()),
    )  # type: ignore[arg-type]
    form = DokladFormDialog(form_vm)
    form._castka_widget.line_widget.setText("12100")
    form._popis_input.set_value("Faktura za vývoj účetního programu.")
    form.show()
    app.processEvents()
    _grab(form, OUT / "01_form_dialog.png")

    # 2) ZauctovaniDialog
    z_vm = ZauctovaniViewModel(
        doklad=_item(),
        uctova_osnova_query=cast(object, _FakeOsnova()),
        zauctovat_command=cast(object, _FakeZauctovat()),
    )  # type: ignore[arg-type]
    z = ZauctovaniDialog(z_vm)
    row = z._rows_list[0]
    row.md_combo.set_value("311")
    row.dal_combo.set_value("601")
    z._on_row_castka_changed(0)
    z._sync_ui()
    z.show()
    app.processEvents()
    _grab(z, OUT / "02_zauctovani_dialog.png")

    # 3) DokladDetailDialog — edit mode
    d_vm = DokladDetailViewModel(
        doklad=_item(),
        actions_command=cast(object, _FakeActions()),
    )  # type: ignore[arg-type]
    detail = DokladDetailDialog(d_vm)
    detail.show()
    app.processEvents()
    detail._edit_button_widget.click()
    app.processEvents()
    _grab(detail, OUT / "03_detail_editable.png")

    # 4) ConfirmDialog — destructive (storno)
    # POZN (Fáze 6.5): V aktuálním Kroku 4 je Storno tlačítko v detail
    # dialogu disabled, takže tento confirm dialog uživatelka reálně neuvidí,
    # dokud nebude Fáze 6.5 (storno přes opravný účetní předpis). Screenshot
    # ale zůstává v repu jako reference — vizuál confirm dialogu se nemění,
    # jen až bude storno re-enabled, znovu ho vyrobíme ve workflow.
    confirm = ConfirmDialog(
        title="Stornovat doklad",
        message=(
            "Opravdu chcete stornovat doklad FV-2026-001? "
            "Tato akce je nevratná."
        ),
        confirm_text="Ano, stornovat",
        destructive=True,
    )
    confirm.show()
    app.processEvents()
    _grab(confirm, OUT / "04_confirm_storno.png")

    return 0


if __name__ == "__main__":
    sys.exit(main())
