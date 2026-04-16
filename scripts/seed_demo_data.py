"""Naplní zadanou SQLite DB demo daty pro Dashboard screenshot.

Vytváří 4 doklady:
  * FV-2026-001 — zaúčtovaná FV 12 100 Kč (z toho 2 100 DPH)
  * FV-2026-002 — NOVÁ FV 5 000 Kč (čeká na zaúčtování)
  * FP-2026-001 — zaúčtovaná FP 6 050 Kč (z toho 1 050 DPH)
  * FV-2026-003 — zaúčtovaná FV 24 200 Kč, příznak k_dořešení (poznámka)

Spuštění:
    python scripts/seed_demo_data.py /tmp/demo.db
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.migrations.runner import MigrationRunner
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.zauctovani_service import ZauctovaniDokladuService

MIGRATIONS_DIR = (
    Path(__file__).resolve().parent.parent
    / "infrastructure"
    / "database"
    / "migrations"
    / "sql"
)


def _add(
    factory: ConnectionFactory,
    cislo: str,
    typ: TypDokladu,
    datum: date,
    castka_kc: str,
    k_doreseni: bool = False,
    poznamka: str | None = None,
) -> int:
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(
            cislo=cislo,
            typ=typ,
            datum_vystaveni=datum,
            castka_celkem=Money.from_koruny(castka_kc),
            k_doreseni=k_doreseni,
            poznamka_doreseni=poznamka,
        ))
        uow.commit()
    return d.id


def seed(db_path: Path) -> None:
    factory = ConnectionFactory(db_path)
    MigrationRunner(factory, MIGRATIONS_DIR).migrate()

    # Fáze 7: naplň směrnou osnovu + PRAUT analytiky
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "seed_chart_of_accounts",
        Path(__file__).resolve().parent / "seed_chart_of_accounts.py",
    )
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    seed_chart_of_accounts = _mod.seed_chart_of_accounts
    seed_praut_active_accounts = _mod.seed_praut_active_accounts
    seed_praut_analytiky = _mod.seed_praut_analytiky
    n_osnova = seed_chart_of_accounts(factory)
    n_active = seed_praut_active_accounts(factory)
    n_analytiky = seed_praut_analytiky(factory)

    zauctovani = ZauctovaniDokladuService(
        uow_factory=lambda: SqliteUnitOfWork(factory),
        doklady_repo_factory=lambda uow: SqliteDokladyRepository(uow),
        denik_repo_factory=lambda uow: SqliteUcetniDenikRepository(uow),
    )

    # 1) FV zaúčtovaná
    d1 = _add(
        factory, "FV-2026-001", TypDokladu.FAKTURA_VYDANA,
        date(2026, 2, 5), "12100",
    )
    zauctovani.zauctuj_doklad(d1, UctovyPredpis(
        doklad_id=d1,
        zaznamy=(
            UcetniZaznam(
                doklad_id=d1, datum=date(2026, 2, 5),
                md_ucet="311", dal_ucet="601",
                castka=Money.from_koruny("10000"),
            ),
            UcetniZaznam(
                doklad_id=d1, datum=date(2026, 2, 5),
                md_ucet="311", dal_ucet="343",
                castka=Money.from_koruny("2100"),
            ),
        ),
    ))

    # 2) FV NOVÁ — k zaúčtování
    _add(
        factory, "FV-2026-002", TypDokladu.FAKTURA_VYDANA,
        date(2026, 4, 8), "5000",
    )

    # 3) FP zaúčtovaná
    d3 = _add(
        factory, "FP-2026-001", TypDokladu.FAKTURA_PRIJATA,
        date(2026, 3, 12), "6050",
    )
    zauctovani.zauctuj_doklad(d3, UctovyPredpis(
        doklad_id=d3,
        zaznamy=(
            UcetniZaznam(
                doklad_id=d3, datum=date(2026, 3, 12),
                md_ucet="518", dal_ucet="321",
                castka=Money.from_koruny("5000"),
            ),
            UcetniZaznam(
                doklad_id=d3, datum=date(2026, 3, 12),
                md_ucet="343", dal_ucet="321",
                castka=Money.from_koruny("1050"),
            ),
        ),
    ))

    # 4) FV zaúčtovaná, k dořešení (chybí EAN, prověřit)
    d4 = _add(
        factory, "FV-2026-003", TypDokladu.FAKTURA_VYDANA,
        date(2026, 4, 1), "24200",
        k_doreseni=True, poznamka="Ověřit dodací list u zákazníka",
    )
    zauctovani.zauctuj_doklad(d4, UctovyPredpis(
        doklad_id=d4,
        zaznamy=(
            UcetniZaznam(
                doklad_id=d4, datum=date(2026, 4, 1),
                md_ucet="311", dal_ucet="602",
                castka=Money.from_koruny("20000"),
            ),
            UcetniZaznam(
                doklad_id=d4, datum=date(2026, 4, 1),
                md_ucet="311", dal_ucet="343",
                castka=Money.from_koruny("4200"),
            ),
        ),
    ))

    print(f"  ✓ seed → {db_path}")
    print(f"    Účtová osnova: {n_osnova} účtů, {n_active} aktivováno, {n_analytiky} analytik")
    print("    4 doklady (3 zaúčtované, 1 NOVÝ, 1 k dořešení)")
    print("    Výnosy YTD: 30 000 Kč · Náklady YTD: 5 000 Kč")
    print("    Hrubý zisk: 25 000 Kč · Daň 19 %: 4 750 Kč")
    print("    Pohledávky 311: 36 300 Kč · Závazky 321: 6 050 Kč")


def main() -> int:
    if len(sys.argv) != 2:
        print("Použití: python scripts/seed_demo_data.py <db_path>")
        return 1
    db_path = Path(sys.argv[1])
    if db_path.exists():
        db_path.unlink()
    seed(db_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
