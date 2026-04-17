"""Screenshot script for Fáze 12: OCR + Inbox.

Generates 5 screenshots:
1. faze_12_inbox_prazdny — empty inbox page
2. faze_12_inbox_9_meta — inbox with 9 Meta uploads
3. faze_12_detail_upload — detail dialog with side-by-side view
4. faze_12_pytlovani_warning — pytlování detection warning
5. faze_12_dashboard_notifikace — dashboard with OCR notification
"""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication

from domain.doklady.typy import Mena, TypDokladu
from domain.ocr.ocr_upload import OcrUpload, StavUploadu
from domain.shared.money import Money
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.ocr_upload_repository import (
    SqliteOcrUploadRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.commands.ocr_upload import OcrUploadCommand
from services.queries.ocr_inbox import OcrInboxItem, OcrInboxQuery
from ui.design_tokens import Colors
from ui.dialogs.ocr_upload_detail_dialog import OcrUploadDetailDialog
from ui.pages.nahrat_doklady_page import NahratDokladyPage
from ui.theme import build_stylesheet
from ui.viewmodels.ocr_inbox_vm import OcrInboxViewModel


SCREENSHOTS_DIR = Path(__file__).parent.parent / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)
TEMP_DIR = SCREENSHOTS_DIR / "_tmp"
TEMP_DIR.mkdir(exist_ok=True)

MIGRATIONS_DIR = (
    Path(__file__).parent.parent
    / "infrastructure" / "database" / "migrations" / "sql"
)


def _create_sample_pdf(path: Path) -> None:
    """Create a minimal PDF that looks like a Meta invoice for preview."""
    # Minimal PDF with text content (valid PDF 1.4)
    content = """\
Meta Platforms Ireland Limited
4 Grand Canal Square, Grand Canal Harbour
Dublin 2, Ireland

Tax Identification: IE9692928F

Invoice: FBADS-404-10000
Date: 01.04.2025

Advertiser: PRAUT s.r.o.
Martin Svanda

Description                    Amount
------------------------------------------
Facebook Ads - April 2025      44,00 CZK

Total:                         44,00 CZK
"""
    # Build a real text-bearing PDF using raw PDF operators
    stream = content.encode("latin-1", errors="replace")
    stream_ops = b"BT\n/F1 11 Tf\n50 750 Td\n14 TL\n"
    for line in content.split("\n"):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_ops += f"({escaped}) '\n".encode("latin-1", errors="replace")
    stream_ops += b"ET\n"

    objects = []
    # 1: Catalog
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    # 2: Pages
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    # 3: Page
    objects.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    )
    # 4: Stream
    objects.append(
        f"4 0 obj\n<< /Length {len(stream_ops)} >>\nstream\n".encode()
        + stream_ops
        + b"endstream\nendobj\n"
    )
    # 5: Font
    objects.append(
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    )

    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj

    xref_start = len(pdf)
    pdf += b"xref\n"
    pdf += f"0 {len(objects) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += b"trailer\n"
    pdf += f"<< /Root 1 0 R /Size {len(objects) + 1} >>\n".encode()
    pdf += b"startxref\n"
    pdf += f"{xref_start}\n".encode()
    pdf += b"%%EOF\n"

    path.write_bytes(pdf)


def _make_app() -> QApplication:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(build_stylesheet())
    return app


def _make_factory(tmp_dir: Path) -> ConnectionFactory:
    db_path = tmp_dir / "screenshot_test.db"
    f = ConnectionFactory(db_path)
    MigrationRunner(f, MIGRATIONS_DIR).migrate()
    return f


def _make_meta_item(idx: int, stav: str = "zpracovany") -> OcrInboxItem:
    """Create a fake Meta invoice inbox item."""
    return OcrInboxItem(
        id=100 + idx,
        file_name=f"meta_ads_2025_{idx:02d}.pdf",
        mime_type="application/pdf",
        stav=stav,
        created_at=None,
        parsed_typ="fp",
        parsed_dodavatel="Meta Platforms Ireland Limited",
        parsed_castka=Money(4400 + idx * 100),
        parsed_datum=date(2025, 4, idx + 1),
        parsed_cislo=f"FBADS-404-{10000 + idx}",
        is_pytlovani=True,
        pytlovani_jmeno="Martin Svanda",
        ocr_method="pdf_text",
        ocr_confidence=98,
        file_path=None,
    )


def _make_pytlovani_item() -> OcrInboxItem:
    return OcrInboxItem(
        id=200,
        file_name="meta_ads_2025_pytlovani.pdf",
        mime_type="application/pdf",
        stav="zpracovany",
        created_at=None,
        parsed_typ="fp",
        parsed_dodavatel="Meta Platforms Ireland Limited",
        parsed_castka=Money(15000),
        parsed_datum=date(2025, 4, 15),
        parsed_cislo="FBADS-404-99999",
        is_pytlovani=True,
        pytlovani_jmeno="Martin Svanda",
        ocr_method="pdf_text",
        ocr_confidence=97,
        file_path=None,
    )


def screenshot_1_inbox_prazdny(app: QApplication) -> None:
    """Screenshot 1: Empty inbox."""
    vm = MagicMock(spec=OcrInboxViewModel)
    vm.items = []
    vm.zpracovane_items = []
    vm.schvalene_items = []
    vm.error = None
    vm.pocet_nezpracovanych = 0

    page = NahratDokladyPage(view_model=vm)
    page.setMinimumSize(1200, 700)
    page.show()
    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    pixmap = page.grab()
    path = SCREENSHOTS_DIR / "faze_12_inbox_prazdny.png"
    pixmap.save(str(path))
    print(f"Saved: {path}")
    page.close()


def screenshot_2_inbox_9_meta(app: QApplication) -> None:
    """Screenshot 2: Inbox with 9 Meta invoices."""
    items = [_make_meta_item(i) for i in range(9)]

    vm = MagicMock(spec=OcrInboxViewModel)
    vm.items = items
    vm.zpracovane_items = items
    vm.schvalene_items = []
    vm.error = None
    vm.pocet_nezpracovanych = 9

    page = NahratDokladyPage(view_model=vm)
    page.setMinimumSize(1200, 700)
    page.show()
    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    pixmap = page.grab()
    path = SCREENSHOTS_DIR / "faze_12_inbox_9_meta.png"
    pixmap.save(str(path))
    print(f"Saved: {path}")
    page.close()


def screenshot_3_detail_upload(app: QApplication) -> None:
    """Screenshot 3: Detail dialog."""
    item = _make_meta_item(0)

    sample_pdf = TEMP_DIR / "meta_ads_2025_00.pdf"
    _create_sample_pdf(sample_pdf)
    dlg = OcrUploadDetailDialog(item=item, file_path=str(sample_pdf))
    dlg.setMinimumSize(900, 600)
    dlg.show()
    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    pixmap = dlg.grab()
    path = SCREENSHOTS_DIR / "faze_12_detail_upload.png"
    pixmap.save(str(path))
    print(f"Saved: {path}")
    dlg.close()


def screenshot_4_pytlovani_warning(app: QApplication) -> None:
    """Screenshot 4: Pytlování warning in detail dialog."""
    item = _make_pytlovani_item()

    sample_pdf = TEMP_DIR / "meta_ads_pytlovani.pdf"
    _create_sample_pdf(sample_pdf)
    dlg = OcrUploadDetailDialog(item=item, file_path=str(sample_pdf))
    dlg.setMinimumSize(900, 600)
    dlg.show()
    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    pixmap = dlg.grab()
    path = SCREENSHOTS_DIR / "faze_12_pytlovani_warning.png"
    pixmap.save(str(path))
    print(f"Saved: {path}")
    dlg.close()


def screenshot_5_dashboard_notifikace(app: QApplication) -> None:
    """Screenshot 5: Dashboard with OCR notification."""
    from ui.pages.dashboard_page import DashboardPage
    from ui.viewmodels.dashboard_vm import DashboardViewModel
    from services.queries.dashboard import DashboardData

    mock_data = DashboardData(
        rok=2025,
        doklady_celkem=42,
        doklady_k_zauctovani=5,
        doklady_k_doreseni=2,
        pohledavky=Money(250000),
        zavazky=Money(180000),
        vynosy=Money(1200000),
        naklady=Money(850000),
        hruby_zisk=Money(350000),
        odhad_dane=Money(66500),
    )

    mock_query = MagicMock()
    mock_query.execute.return_value = mock_data
    dashboard_vm = DashboardViewModel(mock_query)

    page = DashboardPage(
        view_model=dashboard_vm,
        ocr_count_fn=lambda: 9,
    )
    page.setMinimumSize(1200, 700)
    page.show()
    app.processEvents()
    time.sleep(0.3)
    app.processEvents()

    pixmap = page.grab()
    path = SCREENSHOTS_DIR / "faze_12_dashboard_notifikace.png"
    pixmap.save(str(path))
    print(f"Saved: {path}")
    page.close()


def main():
    app = _make_app()

    screenshot_1_inbox_prazdny(app)
    screenshot_2_inbox_9_meta(app)
    screenshot_3_detail_upload(app)
    screenshot_4_pytlovani_warning(app)
    screenshot_5_dashboard_notifikace(app)

    print(f"\nAll 5 screenshots saved to {SCREENSHOTS_DIR}")


if __name__ == "__main__":
    main()
