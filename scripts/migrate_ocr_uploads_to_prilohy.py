"""Migrace: pro každý OCR upload s vytvořeným dokladem vytvoř záznam
v prilohy_dokladu a zkopíruj PDF z uploads/ocr_inbox/ do
uploads/doklady/{rok}/{typ}/.

Skript je idempotentní — při druhém spuštění přeskočí již migrované.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Přidej projekt root do sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ocr_upload_repository import (
    SqliteOcrUploadRepository,
)
from infrastructure.database.repositories.priloha_repository import (
    SqlitePrilohaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from infrastructure.storage.priloha_storage import PrilohaStorage
from services.commands.priloha_commands import PrilohaCommands

DB_PATH = PROJECT_ROOT / "ucetni.db"
MIGRATIONS_DIR = PROJECT_ROOT / "infrastructure" / "database" / "migrations" / "sql"
OCR_INBOX_DIR = PROJECT_ROOT / "uploads" / "ocr_inbox"


def migrate() -> None:
    factory = ConnectionFactory(DB_PATH)

    # Nejprve zajisti, že migrace 016 je aplikovaná
    runner = MigrationRunner(factory, MIGRATIONS_DIR)
    applied = runner.migrate()
    if applied:
        print(f"Aplikované migrace: {applied}")

    uow = SqliteUnitOfWork(factory)
    storage = PrilohaStorage(root=PROJECT_ROOT / "uploads" / "doklady")
    commands = PrilohaCommands(
        uow_factory=lambda: SqliteUnitOfWork(factory),
        storage=storage,
    )

    with uow:
        ocr_repo = SqliteOcrUploadRepository(uow)
        drepo = SqliteDokladyRepository(uow)
        prepo = SqlitePrilohaRepository(uow)

        uploads = ocr_repo.list_with_created_doklad()
        print(f"Nalezeno {len(uploads)} OCR uploadů s vytvořeným dokladem.")

        migrated = 0
        for upload in uploads:
            doklad = drepo.get_by_id(upload.vytvoreny_doklad_id)

            # Idempotence: přeskoč pokud doklad už má přílohu
            existing = prepo.list_by_doklad(doklad.id)
            if existing:
                print(f"  ✓ Doklad {doklad.cislo} už má přílohu, přeskakuji")
                continue

            # Najdi zdrojový PDF
            source = OCR_INBOX_DIR / f"{upload.file_hash}.pdf"
            if not source.exists():
                print(f"  ⚠️ Chybí soubor: {source}")
                continue

            # Použij commands — ale potřebujeme vlastní UoW uvnitř
            # Proto voláme storage a repo přímo (jsme už v UoW)
            rel_path, size = storage.save(
                source,
                doklad_typ=doklad.typ.value,
                doklad_cislo=doklad.cislo,
                original_name=upload.file_name,
                rok=doklad.datum_vystaveni.year,
            )

            from datetime import datetime

            from domain.doklady.priloha import PrilohaDokladu

            priloha = PrilohaDokladu(
                id=None,
                doklad_id=doklad.id,
                nazev_souboru=upload.file_name,
                relativni_cesta=rel_path,
                velikost_bytes=size,
                mime_type="application/pdf",
                vytvoreno=datetime.now(),
            )
            prepo.add(priloha)
            print(f"  ✅ Migrováno: {doklad.cislo} ← {upload.file_name}")
            migrated += 1

        uow.commit()

    print(f"\nHotovo. Migrováno {migrated} příloh.")


if __name__ == "__main__":
    migrate()
