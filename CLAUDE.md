# Pravidla projektu — Účetní program v2

## Stack a verze

- Python 3.11+
- PyQt6 Widgets (žádný QML)
- SQLite (WAL mód)
- WeasyPrint (PDF export)
- pytest + pytest-qt (testy)

## Architektura

```
domain/         # Pure Python — entity, value objects, repository interfaces
infrastructure/ # SQLite repositories, UoW, migrace, ARES klient, OCR, export
services/       # Aplikační logika — orchestrace domain + infra
ui/             # PyQt6 Widgets + ViewModely
tests/
```

### Závislosti mezi vrstvami

- `domain/` **NEIMPORTUJE** z `infrastructure/`, `services/` ani `ui/`
- `infrastructure/` importuje z `domain/` (implementuje interfaces)
- `services/` importuje z `domain/` a `infrastructure/`
- `ui/` importuje z `services/` a `ui/viewmodels/`, **NIKDY přímo SQL**

## Klíčová pravidla

### Money Value Object

Všechny peněžní částky používají `Money` value object (`domain/shared/money.py`).
Interně INTEGER v haléřích — žádný float, žádný Decimal, žádný str pro částky.

```python
# SPRÁVNĚ:
castka = Money.koruny("1234.50")
castka = Money.halere(123450)  # z DB

# ŠPATNĚ:
castka = Decimal("1234.50")
castka = 1234.50
castka = "1234.50"
```

DB sloupce pro částky: `INTEGER NOT NULL DEFAULT 0` (haléře).
SQL agregace: `SUM(castka_hal)` — žádný CAST.

### Žádný SQL v UI vrstvě

UI stránky a widgety **nikdy** nepíší SQL dotazy. Veškerá data získávají přes:
1. ViewModely (`ui/viewmodels/`) — bridge mezi UI a services
2. Services (`services/`) — aplikační logika

### Všechny mutace přes Unit of Work

Každá operace měnící data musí projít přes `with uow:` blok.
Žádný přímý `connection.commit()` mimo UoW.

```python
# SPRÁVNĚ:
with uow:
    uow.doklady.ulozit(doklad)
    uow.denik.pridat(zaznam)
    # commit automaticky na konci with bloku

# ŠPATNĚ:
db.execute("INSERT INTO ...")
db.connection.commit()
```

### Pojmenování: české v doméně, anglické v infrastruktuře

- Domain entity a value objects: české názvy (`Doklad`, `UcetniZaznam`, `Pohledavka`, `castka_hal`)
- Infrastruktura a technické vzory: anglické názvy (`Repository`, `UnitOfWork`, `ConnectionFactory`)

## Testování

- Domain testy: pure Python, bez DB (`tests/domain/`)
- Infrastructure testy: in-memory SQLite (`tests/infrastructure/`)
- Services testy: s mocky nebo in-memory DB (`tests/services/`)
- Každý nový modul musí mít odpovídající testy

## Co NEDĚLÁME

- Žádný CQRS (stačí services/)
- Žádné Domain Events
- Žádný QML
- Žádný singleton Database — používáme ConnectionFactory + dependency injection

## Kontext

Viz [LESSONS_LEARNED.md](LESSONS_LEARNED.md) pro detailní analýzu původního projektu,
identifikované problémy (TEXT částky, SQL v UI, nekonzistentní transakce),
legislativní díry, a architektonická rozhodnutí za tímto rewrite.
