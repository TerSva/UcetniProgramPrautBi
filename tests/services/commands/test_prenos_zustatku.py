"""Testy pro PrenosZustatkuCommand — přenos KZ → PS následujícího roku."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import TypDokladu
from domain.shared.errors import ValidationError
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
from scripts.seed_chart_of_accounts import seed_chart_of_accounts
from services.commands.pocatecni_stavy import PocatecniStavyCommand
from services.commands.prenos_zustatku import PrenosZustatkuCommand


MIGRATIONS_SQL_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "infrastructure" / "database" / "migrations" / "sql"
)


@pytest.fixture
def factory(tmp_path) -> ConnectionFactory:
    db_path = tmp_path / "test.db"
    f = ConnectionFactory(db_path)
    MigrationRunner(f, MIGRATIONS_SQL_DIR).migrate()
    seed_chart_of_accounts(f)
    return f


@pytest.fixture
def cmd(factory) -> PrenosZustatkuCommand:
    return PrenosZustatkuCommand(uow_factory=lambda: SqliteUnitOfWork(factory))


@pytest.fixture
def ps_cmd(factory) -> PocatecniStavyCommand:
    return PocatecniStavyCommand(uow_factory=lambda: SqliteUnitOfWork(factory))


_DOKLAD_CITAC = [0]


def _zauctuj(factory: ConnectionFactory, datum: date, zapisy: list[tuple[str, str, int]]) -> None:
    """Vytvoří doklad + zaúčtuje seznam zápisů (md, dal, halire)."""
    _DOKLAD_CITAC[0] += 1
    uow = SqliteUnitOfWork(factory)
    with uow:
        drepo = SqliteDokladyRepository(uow)
        denik = SqliteUcetniDenikRepository(uow)
        celkem = Money.zero()
        for _, _, hal in zapisy:
            celkem = celkem + Money(hal)
        cislo = f"ID-{datum.isoformat()}-{_DOKLAD_CITAC[0]}"
        doklad = Doklad(
            cislo=cislo,
            typ=TypDokladu.INTERNI_DOKLAD,
            datum_vystaveni=datum,
            castka_celkem=celkem,
            popis="test",
        )
        drepo.add(doklad)
        loaded = drepo.get_by_cislo(cislo)
        zaznamy = tuple(
            UcetniZaznam(
                doklad_id=loaded.id,
                datum=datum,
                md_ucet=md,
                dal_ucet=dal,
                castka=Money(hal),
            )
            for md, dal, hal in zapisy
        )
        denik.zauctuj(UctovyPredpis(doklad_id=loaded.id, zaznamy=zaznamy))
        loaded.zauctuj()
        drepo.update(loaded)
        uow.commit()


def test_prenos_zustatku_bilancuje(cmd, factory, ps_cmd):
    """Po přenosu MD = DAL."""
    # 2025: pokladna 1000 ← banka 1000 (aktivní účty, ZK 1000 z 411)
    _zauctuj(factory, date(2025, 6, 1), [("211", "411", 100000)])
    _zauctuj(factory, date(2025, 7, 1), [("221", "411", 50000)])
    # Trochu nákladů a výnosů
    _zauctuj(factory, date(2025, 8, 1), [("518", "321", 30000)])  # náklad 300
    _zauctuj(factory, date(2025, 9, 1), [("321", "221", 30000)])  # úhrada

    vysledek = cmd.prenest(z_roku=2025, do_roku=2026)

    assert vysledek.bilancuje is True
    assert vysledek.soucet_md == vysledek.soucet_dal


def test_vysledkove_ucty_se_neprenaseji(cmd, factory):
    """Účty 5xx (N) a 6xx (V) nemají PS, jen se převedou do VH na 431."""
    # Vklad ZK + nákup služby
    _zauctuj(factory, date(2025, 6, 1), [("221", "411", 100000)])
    _zauctuj(factory, date(2025, 7, 1), [("518", "221", 20000)])  # náklad 200

    cmd.prenest(z_roku=2025, do_roku=2026)

    uow = SqliteUnitOfWork(factory)
    from infrastructure.database.repositories.pocatecni_stavy_repository import (
        SqlitePocatecniStavyRepository,
    )
    with uow:
        repo = SqlitePocatecniStavyRepository(uow)
        ps = repo.list_by_rok(2026)

    kody = {p.ucet_kod for p in ps}
    assert "518" not in kody
    assert "602" not in kody
    assert "601" not in kody


def test_vh_na_431_ztrata(cmd, factory):
    """Ztráta (V < N) → 431 strana MD."""
    # Vklad ZK 1000, náklad 200 (žádné výnosy) → ztráta 200
    _zauctuj(factory, date(2025, 6, 1), [("221", "411", 100000)])
    _zauctuj(factory, date(2025, 7, 1), [("518", "221", 20000)])

    vysledek = cmd.prenest(z_roku=2025, do_roku=2026)

    assert vysledek.vh == Money(-20000)
    assert vysledek.vh.is_negative

    from infrastructure.database.repositories.pocatecni_stavy_repository import (
        SqlitePocatecniStavyRepository,
    )
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqlitePocatecniStavyRepository(uow)
        ps_431 = [p for p in repo.list_by_rok(2026) if p.ucet_kod == "431.100"]
    assert len(ps_431) == 1
    assert ps_431[0].strana == "MD"
    assert ps_431[0].castka == Money(20000)


def test_vh_na_431_zisk(cmd, factory):
    """Zisk (V > N) → 431 strana DAL."""
    # Tržba 500, náklad 100 → zisk 400
    _zauctuj(factory, date(2025, 6, 1), [("311", "602", 50000)])
    _zauctuj(factory, date(2025, 7, 1), [("518", "321", 10000)])

    vysledek = cmd.prenest(z_roku=2025, do_roku=2026)

    assert vysledek.vh == Money(40000)
    assert vysledek.vh.is_positive

    from infrastructure.database.repositories.pocatecni_stavy_repository import (
        SqlitePocatecniStavyRepository,
    )
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqlitePocatecniStavyRepository(uow)
        ps_431 = [p for p in repo.list_by_rok(2026) if p.ucet_kod == "431.100"]
    assert len(ps_431) == 1
    assert ps_431[0].strana == "DAL"
    assert ps_431[0].castka == Money(40000)


def test_zaverkove_ucty_se_neprenaseji(cmd, factory):
    """Účty 701/702/710 (typ Z) se nepřenášejí."""
    # Simulace otevíracího zápisu na 701
    _zauctuj(factory, date(2025, 1, 1), [("221", "701", 100000)])
    _zauctuj(factory, date(2025, 1, 1), [("701", "411", 100000)])

    cmd.prenest(z_roku=2025, do_roku=2026)

    from infrastructure.database.repositories.pocatecni_stavy_repository import (
        SqlitePocatecniStavyRepository,
    )
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqlitePocatecniStavyRepository(uow)
        ps = repo.list_by_rok(2026)
    kody = {p.ucet_kod for p in ps}
    assert "701" not in kody
    assert "702" not in kody
    assert "710" not in kody


def test_prenos_jen_do_nasledujiciho_roku(cmd):
    """Není dovoleno přeskočit rok."""
    with pytest.raises(ValidationError):
        cmd.prenest(z_roku=2025, do_roku=2027)


def test_prenos_idempotentni_chyba_pri_existujicich_ps(cmd, factory, ps_cmd):
    """Pokud cílový rok už má PS, raise."""
    _zauctuj(factory, date(2025, 6, 1), [("221", "411", 100000)])
    # Manuálně přidáme PS pro 2026
    ps_cmd.pridat(rok=2026, ucet_kod="221", castka=Money(10000), strana="MD")

    with pytest.raises(ValidationError, match="už existují"):
        cmd.prenest(z_roku=2025, do_roku=2026)


def test_nulove_zustatky_se_preskakuji(cmd, factory):
    """Účty s KZ = 0 se nepřenášejí (pohledávka vystavena i uhrazena)."""
    # 311 vzniká i zaniká — KZ = 0
    _zauctuj(factory, date(2025, 6, 1), [("311", "602", 50000)])  # FV
    _zauctuj(factory, date(2025, 7, 1), [("221", "311", 50000)])  # úhrada

    cmd.prenest(z_roku=2025, do_roku=2026)

    from infrastructure.database.repositories.pocatecni_stavy_repository import (
        SqlitePocatecniStavyRepository,
    )
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqlitePocatecniStavyRepository(uow)
        ps = repo.list_by_rok(2026)
    kody = {p.ucet_kod for p in ps}
    assert "311" not in kody  # KZ = 0
