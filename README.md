# Účetní program v2

Desktopový účetní systém pro české podvojné účetnictví (s.r.o., identifikovaná osoba).

## Stack

- **Python 3.11+**
- **PyQt6** (Widgets) — UI
- **SQLite** — databáze (WAL mód, částky jako INTEGER v haléřích)
- **WeasyPrint** — PDF export
- **pytest + pytest-qt** — testování

## Architektura

```
domain/         # Entity, value objects, repository interfaces — pure Python
infrastructure/ # SQLite repositories, UoW, migrace, ARES, OCR, export
services/       # Aplikační logika (orchestrace domain + infra)
ui/             # PyQt6 Widgets + ViewModely
tests/
```

## Status

V aktivním rewrite, MVP fáze. Původní verze archivována v samostatném repozitáři.

## Kontext

Viz [LESSONS_LEARNED.md](LESSONS_LEARNED.md) pro detailní analýzu původního projektu a rozhodnutí za architekturou rewrite.
