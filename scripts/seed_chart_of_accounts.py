"""Seed směrné účtové osnovy dle vyhlášky 500/2002 Sb., příloha č. 4.

Importuje ~100 syntetických účtů. Defaultně jsou všechny is_active=False,
kromě pár klíčových účtů pro základní workflow.

Spuštění:
    python scripts/seed_chart_of_accounts.py <db_path>

Nebo programaticky:
    seed_chart_of_accounts(factory)
"""

from __future__ import annotations

import sys
from pathlib import Path

from domain.ucetnictvi.typy import TypUctu
from domain.ucetnictvi.ucet import Ucet
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.repositories.uctova_osnova_repository import (
    SqliteUctovaOsnovaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork

A = TypUctu.AKTIVA
P = TypUctu.PASIVA
N = TypUctu.NAKLADY
V = TypUctu.VYNOSY
Z = TypUctu.VYPOCTOVY

#: Účty, které jsou defaultně aktivní (nejzákladnější pro každou firmu).
_DEFAULT_ACTIVE = {
    # Třída 0 — Dlouhodobý majetek
    "022", "082",
    # Třída 2 — Peněžní prostředky
    "211", "221", "261",
    # Třída 3 — Zúčtovací vztahy
    "311", "314", "321", "331", "336",
    "341", "342", "343", "345",
    "355", "365", "378", "379", "381",
    # Třída 4 — Kapitálové účty
    "411", "428", "429", "431",
    # Třída 5 — Náklady
    "501", "512", "513", "518",
    "521", "524", "538", "551",
    "562", "563", "568", "591",
    # Třída 6 — Výnosy
    "601", "602", "644", "662", "663",
    # Třída 7 — Závěrkové
    "701", "702", "710",
}

# ─── Směrná účtová osnova dle vyhlášky 500/2002 Sb. ─────────────────

SMERNA_OSNOVA: list[tuple[str, str, TypUctu]] = [
    # Třída 0 — Dlouhodobý majetek
    ("012", "Nehmotné výsledky výzkumu a vývoje", A),
    ("013", "Software", A),
    ("014", "Ostatní ocenitelná práva", A),
    ("015", "Goodwill", A),
    ("019", "Jiný dlouhodobý nehmotný majetek", A),
    ("021", "Stavby", A),
    ("022", "Hmotné movité věci a jejich soubory", A),
    ("025", "Pěstitelské celky trvalých porostů", A),
    ("026", "Dospělá zvířata a jejich skupiny", A),
    ("029", "Jiný dlouhodobý hmotný majetek", A),
    ("031", "Pozemky", A),
    ("032", "Umělecká díla a sbírky", A),
    ("041", "Nedokončený dlouhodobý nehmotný majetek", A),
    ("042", "Nedokončený dlouhodobý hmotný majetek", A),
    ("043", "Pořizovaný dlouhodobý finanční majetek", A),
    ("051", "Poskytnuté zálohy na DNM", A),
    ("052", "Poskytnuté zálohy na DHM", A),
    ("053", "Poskytnuté zálohy na DFM", A),
    ("061", "Podíly — ovládaná nebo ovládající osoba", A),
    ("062", "Podíly — podstatný vliv", A),
    ("063", "Ostatní dlouhodobé cenné papíry a podíly", A),
    ("065", "Dluhové cenné papíry držené do splatnosti", A),
    ("066", "Zápůjčky a úvěry — ovládaná/ovládající osoba", A),
    ("067", "Ostatní zápůjčky a úvěry", A),
    ("068", "Jiný dlouhodobý finanční majetek", A),
    ("069", "Oceňovací rozdíly k nabytému majetku", A),
    ("072", "Oprávky k softwaru", A),
    ("073", "Oprávky k ocenitelným právům", A),
    ("074", "Oprávky ke goodwillu", A),
    ("075", "Oprávky k jinému DNM", A),
    ("079", "Oprávky k ostatnímu DNM", A),
    ("081", "Oprávky ke stavbám", A),
    ("082", "Oprávky k hmotným movitým věcem", A),
    ("085", "Oprávky k pěstitelským celkům", A),
    ("086", "Oprávky k dospělým zvířatům", A),
    ("089", "Oprávky k jinému DHM", A),
    ("091", "Opravné položky k DNM", A),
    ("092", "Opravné položky k DHM", A),
    ("093", "Opravné položky k nedokončenému DNM", A),
    ("094", "Opravné položky k nedokončenému DHM", A),
    ("095", "Opravné položky k poskytnutým zálohám na DM", A),
    ("096", "Opravné položky k DFM", A),

    # Třída 1 — Zásoby
    ("111", "Pořízení materiálu", A),
    ("112", "Materiál na skladě", A),
    ("119", "Materiál na cestě", A),
    ("121", "Nedokončená výroba", A),
    ("122", "Polotovary vlastní výroby", A),
    ("123", "Výrobky", A),
    ("124", "Mladá a ostatní zvířata a jejich skupiny", A),
    ("131", "Pořízení zboží", A),
    ("132", "Zboží na skladě a v prodejnách", A),
    ("139", "Zboží na cestě", A),
    ("151", "Poskytnuté zálohy na materiál", A),
    ("152", "Poskytnuté zálohy na zboží", A),
    ("153", "Poskytnuté zálohy na zvířata", A),
    ("191", "Opravné položky k materiálu", A),
    ("196", "Opravné položky ke zboží", A),
    ("197", "Opravné položky k zásobám vlastní činnosti", A),

    # Třída 2 — Krátkodobý finanční majetek a peněžní prostředky
    ("211", "Pokladna", A),
    ("213", "Ceniny", A),
    ("221", "Bankovní účty", A),
    ("231", "Krátkodobé bankovní úvěry", P),
    ("232", "Eskontní úvěry", P),
    ("241", "Emitované krátkodobé dluhopisy", P),
    ("249", "Ostatní krátkodobé finanční výpomoci", P),
    ("251", "Majetkové cenné papíry k obchodování", A),
    ("252", "Vlastní akcie a vlastní obchodní podíly", A),
    ("253", "Dluhové cenné papíry k obchodování", A),
    ("255", "Vlastní dluhopisy", A),
    ("256", "Dluhové cenné papíry se splatností do 1 roku", A),
    ("259", "Pořízení krátkodobého finančního majetku", A),
    ("261", "Peníze na cestě", A),
    ("291", "Opravné položky ke krátkodobému finančnímu majetku", A),

    # Třída 3 — Zúčtovací vztahy
    ("311", "Pohledávky z obchodních vztahů", A),
    ("314", "Poskytnuté provozní zálohy a závdavky", A),
    ("315", "Ostatní pohledávky", A),
    ("321", "Dluhy z obchodních vztahů", P),
    ("324", "Přijaté provozní zálohy a závdavky", P),
    ("325", "Ostatní dluhy", P),
    ("331", "Zaměstnanci", P),
    ("336", "Zúčtování s institucemi soc. zabezpečení a zdr. pojištění", P),
    ("341", "Daň z příjmů", P),
    ("342", "Ostatní přímé daně", P),
    ("343", "Daň z přidané hodnoty", P),
    ("345", "Ostatní daně a poplatky", P),
    ("351", "Pohledávky — ovládaná/ovládající osoba", A),
    ("352", "Pohledávky — podstatný vliv", A),
    ("353", "Pohledávky za upsaný základní kapitál", A),
    ("354", "Pohledávky za společníky při úhradě ztráty", A),
    ("355", "Ostatní pohledávky za společníky", A),
    ("358", "Pohledávky za účastníky sdružení", A),
    ("361", "Dluhy — ovládaná/ovládající osoba", P),
    ("364", "Dluhy ke společníkům při rozdělování zisku", P),
    ("365", "Ostatní dluhy ke společníkům", P),
    ("366", "Dluhy ke společníkům ze závislé činnosti", P),
    ("367", "Dluhy z upsaných nesplacených cenných papírů a vkladů", P),
    ("368", "Dluhy k účastníkům sdružení", P),
    ("371", "Pohledávky z prodeje podniku", A),
    ("372", "Dluhy z koupě podniku", P),
    ("373", "Pohledávky a dluhy z pevných terminových operací", A),
    ("374", "Pohledávky z pronájmu", A),
    ("375", "Pohledávky z emitovaných dluhopisů", A),
    ("376", "Nakoupené opce", A),
    ("377", "Prodané opce", P),
    ("378", "Jiné pohledávky", A),
    ("379", "Jiné dluhy", P),
    ("381", "Náklady příštích období", A),
    ("382", "Komplexní náklady příštích období", A),
    ("383", "Výdaje příštích období", P),
    ("384", "Výnosy příštích období", P),
    ("385", "Příjmy příštích období", A),
    ("388", "Dohadné účty aktivní", A),
    ("389", "Dohadné účty pasivní", P),
    ("391", "Opravné položky k pohledávkám", A),
    ("395", "Vnitřní zúčtování", A),
    ("398", "Spojovací účet při sdružení", A),

    # Třída 4 — Kapitálové účty a dlouhodobé závazky
    ("411", "Základní kapitál", P),
    ("412", "Ážio", P),
    ("413", "Ostatní kapitálové fondy", P),
    ("414", "Oceňovací rozdíly z přecenění majetku a závazků", P),
    ("416", "Rozdíly z ocenění při přeměnách obchodních korporací", P),
    ("417", "Rozdíly z přeměn obchodních korporací", P),
    ("418", "Oceňovací rozdíly z přecenění při přeměnách", P),
    ("419", "Změny základního kapitálu", P),
    ("421", "Rezervní fond", P),
    ("427", "Ostatní fondy", P),
    ("428", "Nerozdělený zisk minulých let", P),
    ("429", "Neuhrazená ztráta minulých let", P),
    ("431", "Výsledek hospodaření ve schvalovacím řízení", P),
    ("451", "Rezervy zákonné", P),
    ("453", "Rezerva na daň z příjmů", P),
    ("459", "Ostatní rezervy", P),
    ("461", "Dlouhodobé bankovní úvěry", P),
    ("471", "Dlouhodobé závazky — ovládaná/ovládající osoba", P),
    ("473", "Emitované dluhopisy", P),
    ("474", "Závazky z pronájmu", P),
    ("475", "Dlouhodobé přijaté zálohy", P),
    ("478", "Dlouhodobé směnky k úhradě", P),
    ("479", "Jiné dlouhodobé dluhy", P),

    # Třída 5 — Náklady
    ("501", "Spotřeba materiálu", N),
    ("502", "Spotřeba energie", N),
    ("503", "Spotřeba ostatních neskladovatelných dodávek", N),
    ("504", "Prodané zboží", N),
    ("511", "Opravy a udržování", N),
    ("512", "Cestovné", N),
    ("513", "Náklady na reprezentaci", N),
    ("518", "Ostatní služby", N),
    ("521", "Mzdové náklady", N),
    ("522", "Příjmy společníků obch. korporace ze závislé činnosti", N),
    ("523", "Odměny členům orgánů obch. korporace", N),
    ("524", "Zákonné sociální a zdravotní pojištění", N),
    ("525", "Ostatní sociální pojištění", N),
    ("527", "Zákonné sociální náklady", N),
    ("528", "Ostatní sociální náklady", N),
    ("531", "Daň silniční", N),
    ("532", "Daň z nemovitých věcí", N),
    ("538", "Ostatní daně a poplatky", N),
    ("541", "Zůstatková cena prodaného DNM a DHM", N),
    ("542", "Prodaný materiál", N),
    ("543", "Dary", N),
    ("544", "Smluvní pokuty a úroky z prodlení", N),
    ("545", "Ostatní pokuty a penále", N),
    ("546", "Odpis pohledávky", N),
    ("548", "Ostatní provozní náklady", N),
    ("549", "Manka a škody z provozní činnosti", N),
    ("551", "Odpisy DNM a DHM", N),
    ("552", "Tvorba a zúčtování rezerv v provozní oblasti", N),
    ("557", "Zúčtování oprávky k oceňovacímu rozdílu k nabytému majetku", N),
    ("558", "Tvorba a zúčtování opravných položek v provozní oblasti", N),
    ("561", "Prodané cenné papíry a podíly", N),
    ("562", "Úroky", N),
    ("563", "Kurzové ztráty", N),
    ("564", "Náklady z přecenění reálnou hodnotou", N),
    ("566", "Náklady z finančního majetku", N),
    ("567", "Náklady z derivátových operací", N),
    ("568", "Ostatní finanční náklady", N),
    ("569", "Manka a škody na finančním majetku", N),
    ("574", "Tvorba a zúčtování finančních rezerv", N),
    ("579", "Tvorba a zúčtování opravných položek ve finanční oblasti", N),
    ("591", "Daň z příjmů — splatná", N),
    ("592", "Daň z příjmů — odložená", N),
    ("595", "Dodatečné odvody daně z příjmů", N),
    ("596", "Převod podílu na VH společníkům", N),
    ("597", "Převod provozních nákladů", N),
    ("598", "Převod finančních nákladů", N),

    # Třída 6 — Výnosy
    ("601", "Tržby za vlastní výrobky", V),
    ("602", "Tržby z prodeje služeb", V),
    ("604", "Tržby za zboží", V),
    ("611", "Změna stavu nedokončené výroby", V),
    ("612", "Změna stavu polotovarů vlastní výroby", V),
    ("613", "Změna stavu výrobků", V),
    ("614", "Změna stavu zvířat", V),
    ("621", "Aktivace materiálu a zboží", V),
    ("622", "Aktivace vnitropodnikových služeb", V),
    ("623", "Aktivace dlouhodobého nehmotného majetku", V),
    ("624", "Aktivace dlouhodobého hmotného majetku", V),
    ("641", "Tržby z prodeje DNM a DHM", V),
    ("642", "Tržby z prodeje materiálu", V),
    ("644", "Smluvní pokuty a úroky z prodlení", V),
    ("646", "Výnosy z odepsaných pohledávek", V),
    ("648", "Ostatní provozní výnosy", V),
    ("661", "Tržby z prodeje cenných papírů a podílů", V),
    ("662", "Úroky", V),
    ("663", "Kurzové zisky", V),
    ("664", "Výnosy z přecenění reálnou hodnotou", V),
    ("665", "Výnosy z dlouhodobého finančního majetku", V),
    ("666", "Výnosy z krátkodobého finančního majetku", V),
    ("667", "Výnosy z derivátových operací", V),
    ("668", "Ostatní finanční výnosy", V),
    ("697", "Převod provozních výnosů", V),
    ("698", "Převod finančních výnosů", V),

    # Třída 7 — Závěrkové a podrozvahové
    ("701", "Počáteční účet rozvažný", Z),
    ("702", "Konečný účet rozvažný", Z),
    ("710", "Účet zisků a ztrát", Z),
]


def seed_chart_of_accounts(factory: ConnectionFactory) -> int:
    """Importuje směrnou účtovou osnovu do DB. Přeskočí existující účty.

    Returns:
        Počet nově vložených účtů.
    """
    count = 0
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteUctovaOsnovaRepository(uow)
        for kod, nazev, typ in SMERNA_OSNOVA:
            if repo.existuje(kod):
                continue
            is_active = kod in _DEFAULT_ACTIVE
            ucet = Ucet(cislo=kod, nazev=nazev, typ=typ, je_aktivni=is_active)
            repo.add(ucet)
            count += 1
        uow.commit()
    return count


def seed_praut_analytiky(factory: ConnectionFactory) -> int:
    """Přidá analytické účty specifické pro PRAUT s.r.o.

    Returns:
        Počet nově vytvořených analytik.
    """
    analytiky: list[tuple[str, str, TypUctu, str, str | None]] = [
        ("221.001", "Money Banka", A, "221", "Hlavní firemní účet"),
        ("221.002", "Česká spořitelna", A, "221", "Sekundární účet"),
        ("321.001", "Tuzemští dodavatelé CZK", P, "321", None),
        ("321.002", "Zahraniční dodavatelé EUR", P, "321", None),
        ("343.100", "DPH na vstupu z EU", P, "343", "Reverse charge vstup"),
        ("343.200", "DPH k odvodu", P, "343", "Reverse charge výstup"),
        ("355.001", "Pohledávky za společníkem Martin", A, "355", "Martin Švanda 90 %"),
        ("365.001", "Závazky ke společníkovi Martin", P, "365", "Martin Švanda"),
        ("501.100", "Drobný hmotný majetek", N, "501", "Pod hranicí DHM (80 000 Kč)"),
        ("518.100", "Reklama a marketing", N, "518", None),
        ("518.200", "IT služby / Hosting", N, "518", "Servery, domény, SaaS"),
    ]

    count = 0
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteUctovaOsnovaRepository(uow)
        for kod, nazev, typ, parent, popis in analytiky:
            if repo.existuje(kod):
                continue
            # Aktivuj parent syntetický účet pokud ještě není
            try:
                parent_ucet = repo.get_by_cislo(parent)
                if not parent_ucet.je_aktivni:
                    parent_ucet.aktivuj()
                    repo.update(parent_ucet)
            except Exception:
                pass
            ucet = Ucet(
                cislo=kod, nazev=nazev, typ=typ,
                je_aktivni=True, parent_kod=parent, popis=popis,
            )
            repo.add(ucet)
            count += 1
        uow.commit()
    return count


def seed_praut_active_accounts(factory: ConnectionFactory) -> int:
    """Aktivuje syntetické účty relevantní pro PRAUT s.r.o.

    Returns:
        Počet nově aktivovaných účtů.
    """
    praut_active = {
        # Třída 0 — Dlouhodobý majetek
        "022", "082",
        # Třída 2 — Peněžní prostředky
        "211", "221", "261",
        # Třída 3 — Zúčtovací vztahy
        "311", "314", "321", "331", "336",
        "341", "342", "343", "345",
        "355", "365", "378", "379", "381",
        # Třída 4 — Kapitálové účty
        "411", "428", "429", "431",
        # Třída 5 — Náklady
        "501", "512", "513", "518",
        "521", "524", "538", "551",
        "562", "563", "568", "591",
        # Třída 6 — Výnosy
        "601", "602", "644", "662", "663",
        # Třída 7 — Závěrkové
        "701", "702", "710",
    }
    count = 0
    uow = SqliteUnitOfWork(factory)
    with uow:
        repo = SqliteUctovaOsnovaRepository(uow)
        for kod in sorted(praut_active):
            try:
                ucet = repo.get_by_cislo(kod)
                if not ucet.je_aktivni:
                    ucet.aktivuj()
                    repo.update(ucet)
                    count += 1
            except Exception:
                pass
        uow.commit()
    return count


def main() -> int:
    if len(sys.argv) != 2:
        print("Použití: python scripts/seed_chart_of_accounts.py <db_path>")
        return 1
    db_path = Path(sys.argv[1])

    from infrastructure.database.migrations.runner import MigrationRunner
    migrations_dir = (
        Path(__file__).resolve().parent.parent
        / "infrastructure" / "database" / "migrations" / "sql"
    )
    factory = ConnectionFactory(db_path)
    MigrationRunner(factory, migrations_dir).migrate()

    n_osnova = seed_chart_of_accounts(factory)
    n_active = seed_praut_active_accounts(factory)
    n_analytiky = seed_praut_analytiky(factory)
    print(f"  ✓ Směrná osnova: {n_osnova} účtů importováno")
    print(f"  ✓ PRAUT aktivní: {n_active} účtů aktivováno")
    print(f"  ✓ PRAUT analytiky: {n_analytiky} analytik vytvořeno")
    return 0


if __name__ == "__main__":
    sys.exit(main())
