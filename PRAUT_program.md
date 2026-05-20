# PRAUT účetní program — core dokumentace

> Foundational dokument — historie a architektura.
> Pro aktuální stav viz `PRAUT_kontext.md`.
> Naposledy aktualizováno: **2026-05-20** (commit `18535d5`).
> Pro novější změny viz `PRAUT_kontext.md` a `git log`.
>
> Fakta v tomto dokumentu jsou dohledatelná v jednom ze zdrojů:
> git historie (commit hash), kód repozitáře (cesta:řádek), DB
> (`ucetni.db`), nebo `CLAUDE.md` / `ROADMAP.md` / `LESSONS_LEARNED.md`.
> Citace jsou inline v závorkách.

---

## 1. Účel programu

Desktopový účetní systém pro **české podvojné účetnictví** (s.r.o.,
identifikovaná osoba) — postavený jako MVP do termínu daňového přiznání
k DPPO za rok 2025 (`ROADMAP.md`, `c36c6f9` *strategic pivot to tax
deadline 4.5.2026*).

| Údaj | Hodnota | Zdroj |
|------|---------|-------|
| Firma | **PRAUT s.r.o.** | `ucetni.db` → `firma` |
| IČO | 22545107 | `ucetni.db` → `firma.ico` |
| DIČ | CZ22545107 | `ucetni.db` → `firma.dic` |
| Typ plátce | **Identifikovaná osoba §6g ZDPH** | komentáře v kódu (`services/queries/dph_prehled.py`), commit `ec06965` |
| Uživatelka | Tereza (účetní) | (kontext) |

Program **není určen pro veřejnou distribuci** — je to interní nástroj
PRAUT s.r.o. Architektonický rewrite původní aplikace (viz
`LESSONS_LEARNED.md`).

---

## 2. Tech stack a architektura

| Vrstva | Technologie | Zdroj |
|--------|-------------|-------|
| Jazyk | Python 3.11+ | `CLAUDE.md` |
| UI | PyQt6 Widgets (žádný QML) | `CLAUDE.md` |
| Databáze | SQLite (WAL mód) | `CLAUDE.md` |
| PDF | WeasyPrint | `CLAUDE.md` |
| Testy | pytest + pytest-qt | `CLAUDE.md` |

**Architektonický styl:** DDD-lite + Repository + UoW + Command/Query
oddělení (samostatné `services/commands/` a `services/queries/`).

```
domain/         # Pure Python — entity, value objects, repo interfaces
infrastructure/ # SQLite repositories, UoW, migrace, ARES, OCR, export
services/       # Aplikační logika (Commands + Queries)
ui/             # PyQt6 Widgets + ViewModely
tests/
```

**Závislostní pravidlo:** `domain/` neimportuje z `infrastructure/`,
`services/` ani `ui/` (`CLAUDE.md`).

---

## 3. Adresářová struktura

```
domain/         banka, dan, doklady, finance, firma, majetek,
                mzdy, ocr, partneri, shared, ucetnictvi
infrastructure/ banka, database, ocr, storage
services/       banka, commands, export, queries
ui/             assets, dialogs, pages, theme, viewmodels, widgets
tests/          domain, fixtures, infrastructure, integration,
                services, ui
```

**Poznámka (odvozeno):** `domain/dan/`, `domain/majetek/`, `domain/mzdy/`
jsou prázdné placeholdery — žádná business logika v aktuální verzi.

---

## 4. Doménové entity (klíčové)

### `Doklad` (`domain/doklady/doklad.py`)

Centrální agregát. **8 typů** (`domain/doklady/typy.py`):

| Kód | Význam |
|-----|--------|
| FV | Faktura vydaná |
| FP | Faktura přijatá |
| ZF | Zálohová faktura |
| FPR | Faktura přijatá reverse charge (samostatná řada, `3000be8`) |
| BV | Bankovní výpis |
| PD | Pokladní doklad |
| ID | Interní doklad |
| OD | Opravný doklad |

**Stavy:** `novy`, `zauctovany`, `uhrazeny`, `castecne_uhrazeny`,
`stornovany` (`domain/doklady/typy.py`).

**Přechody stavů:**

```
novy → zauctovany → uhrazeny
                  → castecne_uhrazeny → uhrazeny
                  → stornovany
```

**Důležité flagy:**
- `k_doreseni: bool` + `poznamka_doreseni: str` (commit `ee1be35`,
  migrace 003) — uživatelský příznak že doklad vyžaduje pozornost
- `dph_rezim: DphRezim` (TUZEMSKO / REVERSE_CHARGE / OSVOBOZENO /
  MIMO_DPH) — migrace 018, commit `ec06965`
- `je_vystavena: bool | None` — relevantní jen pro ZF (rozlišení
  vystavená vs. přijatá záloha; commit `a9348bd`)
- `je_zaverka: bool` (migrace 031, commit `18535d5`) — označuje
  systémový doklad (Z1/Z2/Z3 z uzávěrky + otevírací ID-{rok}-PS)
  který nepatří do běžných výkazů

### `Money` (`domain/shared/money.py`)

Value object pro peníze. **Interně INTEGER v haléřích** — žádný float,
žádný Decimal, žádný str pro peněžní částky v doméně (`CLAUDE.md`,
commit `e22885e`).

```python
Money.koruny("1234.50")   # ze stringu
Money.halere(123450)      # z DB
m.format_cz()             # "1 234,50 Kč"
```

DB sloupce pro částky: `INTEGER NOT NULL DEFAULT 0` (haléře).

### `UcetniZaznam` (`domain/ucetnictvi/ucetni_zaznam.py`)

Jeden účetní zápis MD/Dal. **Storno mechanismus** (migrace 004,
commit `97e0784`):
- `je_storno: bool` (default False)
- `stornuje_zaznam_id: int | None` (FK na originál)

Storno = **opravný protizápis** s prohozenými MD/Dal, ne soft-delete.
Originál i protizápis zůstávají v deníku → audit trail.

### `Ucet` (`domain/ucetnictvi/ucet.py`)

Účet v účtové osnově. **5 typů** (`domain/ucetnictvi/typy.py`):

| Typ | Význam | Třídy |
|-----|--------|-------|
| A | Aktiva | 0xx, 1xx, 2xx, 3xx debet |
| P | Pasiva | 3xx kredit, 4xx |
| N | Náklady | 5xx |
| V | Výnosy | 6xx |
| Z | Závěrkové (výpočtové) | 7xx |

Plus flag **`je_danovy: bool`** (migrace 022, commit `eaaeeb6`) —
rozlišuje daňově uznatelné vs. neuznatelné účty (DPPO ř. 40).

### Další entity
- `Partner` (kategorie, ARES, fuzzy matching — commit `c643c1a`)
- `BankovniVypis`, `BankovniTransakce` (commit `ac4ee44`)
- `OcrUpload` (commit `02dcaab`)
- `PocatecniStav` (`domain/firma/pocatecni_stav.py`, migrace 009)
- `Firma` (metadata + pole pro závěrku — migrace 021)

---

## 5. Klíčové služby

### Queries (`services/queries/`)

| Třída | Co dělá | Commit |
|-------|---------|--------|
| `VykazyQuery` | **Centrální query** — Rozvaha, VZZ, Předvaha, Hlavní kniha, Saldokonto, DPH přehled, Pokladna, Nedaňové, drilldown | `030c6ce`, `18535d5` |
| `DphPrehledQuery` + `DphMesicDetailQuery` + `DphPriznaniQuery` | DPH měsíční přehled, detail, řádky EPO | `12f7dd7` |
| `ViesQuery` | Souhrnné hlášení (poskytnuté služby do EU) | `12f7dd7` |
| `DashboardQuery` | KPI karty | `dd9844d` |
| `PredvahaQuery`, `HlavniKnihaQuery` | (legacy — V/A modul) | `82caa54` |
| `DokladyListQuery` | Seznam dokladů s filtry | `375b9f3` |
| `ZalohyPartneraQuery` | ZF vazba na partnera | `a9348bd` |

### Commands (`services/commands/`)

| Třída | Co dělá | Commit |
|-------|---------|--------|
| `ZauctovaniDokladuService` | Zaúčtuje doklad (předpis MD/Dal) + storno přes protizápis | `82caa54`, `97e0784` |
| `PocatecniStavyCommand` | CRUD PS + `generovat_id_doklad` (vytvoří ID-{rok}-PS s je_zaverka=True) | `d6fb86d`, `18535d5` |
| `PrenosZustatkuCommand` | KZ rozvahových účtů → PS následujícího roku | `358b5c8` |
| `UzaverkaRokuCommand` | Vystaví Z1 (5xx/6xx→710), Z2 (VH→431), Z3 (rozvahové→702) s je_zaverka=True. Idempotentní. | `18535d5` |
| `VkladZKCommand` | Wizard pro vklad základního kapitálu | `d6fb86d` |
| `DphPodaniCommand` | Označení DPH za měsíc jako podaného | `12f7dd7` |
| `ImportVypisuCommand` | CSV+PDF import bank. výpisů s validací | `ac4ee44`, `43c1933` |

### Export (`services/export/`)

| Modul | Co | Commit |
|-------|-----|--------|
| `pdf_export.py` (WeasyPrint) | Účetní závěrka — Cover + Rozvaha + VZZ + příloha + saldokonto | `030c6ce`, `d7227e2` |
| `dph_export.py` | PDF DPH přehled za rozsah měsíců | `7bfdf57` |

---

## 6. Účetní specifika PRAUT

### 6.1 Identifikovaná osoba (§6g ZDPH)

PRAUT je **identifikovaná osoba**, ne plátce DPH (komentáře v
`services/queries/dph_prehled.py`, `domain/doklady/typy.py`,
`DphPrehledQuery` docstring; commit `ec06965 feat(dph): reverse charge
VAT for identified person`).

**Co to znamená v programu:**
- DPH se počítá jen pro **reverse charge** plnění (služby z EU)
- Účty: `343.100` (DPH vstup) + `343.200` (DPH výstup) — migrace 019
- Doklad má flag `dph_rezim` (`TUZEMSKO` / `REVERSE_CHARGE`) — migrace 018
- DPH přiznání: jen řádky 7, 9–11, 43–48, 62, 64, 66 (formulář EPO);
  ř. 64 (odpočet) **vždy 0** — to je vlastní podstata identifikované
  osoby (komentář v `DphPriznaniRadky.from_transakce`)
- VIES souhrnné hlášení pro FV s RC do EU (`ViesQuery`)
- **Kontrolní hlášení NEPODÁVÁ** (info-box v `ui/pages/dph_page.py`)
- Reverse charge faktury mají vlastní číselnou řadu **FPR** (commit
  `3000be8`)

### 6.2 ⚠️ Hetzner — running issue

> **Running issue:** Hetzner Online GmbH (DE812871812) účtuje PRAUT
> 21 % CZ DPH a odvádí ji za PRAUT přes **OSS** (One Stop Shop) —
> protože PRAUT **nemá u Hetzneru v účtu uvedené CZ DIČ**. Tj. nejde
> o klasické reverse charge plnění.
>
> Externí zdroj: https://docs.hetzner.com/general/others/vat/
>
> Doloženo v DB: popis dokladu `ID-2026-001` (oprava chyby min.
> období dle ČÚS 019), `ucetni_zaznamy.popis`. Doklad vystaven
> ručně 20.5.2026 jako reklasifikace z RC na ne-RC.
>
> **TODO:** doplnit DIČ do Hetzner účtu PRAUT → od příští faktury
> bude Hetzner účtovat bez DPH (klasický RC). Tato oprava je
> uživatelská akce mimo program.

### 6.3 Závěrka roku — mechanismus

Závěrka má **dva paralelní mechanismy** (commit `18535d5` —
rozhodnutí "dual mechanism" v ROADMAP TODO):

1. **PS přenos** (`PrenosZustatkuCommand`, commit `358b5c8`) —
   primární tok dat:
   - Spočítá KZ rozvahových účtů za rok N
   - Zapíše do tabulky `pocatecni_stavy` pro rok N+1
   - Volitelně generuje doklad `ID-{N+1}-PS` (audit stopa v deníku)

2. **Uzavírací doklady** (`UzaverkaRokuCommand`, commit `18535d5`) —
   formální stránka uzávěrky:
   - **Z1** — uzavření výsledkových účtů (5xx, 6xx) → 710.100
   - **Z2** — převod hospodářského výsledku (710.100 → 431.100)
   - **Z3** — uzavření rozvahových účtů (1xx–4xx → 702.100)
   - Všechny s `je_zaverka=True`, datum 31.12.{rok}, idempotentní

**Klíčový filtr** `je_zaverka` (migrace 031) — `VykazyQuery._nacti_obraty_a_ps(vcetne_zaverky=False)`
defaultně vynechává zápisy z dokladů s `je_zaverka=1`. Tím se eliminuje
duplicita PS (tabulka × doklad-zápisy).

### 6.4 Storno

Storno = **opravný účetní předpis** (protizápis), ne soft-delete
(`97e0784 feat(doklady): storno via corrective accounting entry`,
`a8134ea`, `1d8bd11`). Po stornu má doklad stav `stornovany`, originál
a protizápis jsou oba aktivní v deníku, navzájem se ruší v součtech
(VykazyQuery to zohledňuje — komentář v `vykazy_query.py:1517-1519`).

### 6.5 Klíčové analytické účty (z DB)

| Účet | Název | Použití |
|------|-------|---------|
| 211.100 | Pokladna CZK | Pokladní pohyby |
| 221.001 | Bankovní účet — Money Banka | Hlavní bankovní účet |
| 221.002 | Bankovní účet — Česká spořitelna | Druhý bankovní účet |
| 261.100 | Peníze na cestě | Bank → pokladna přesun |
| 311.100 | Pohledávky CZK | FV neuhrazené |
| 321.100 / .001 / .002 | Závazky | FP — CZK / tuzemsko / EU |
| 324.100 | Přijaté zálohy CZK | ZF přijaté |
| 343.100 / .200 | DPH vstup / výstup | Reverse charge |
| 355.100, 355.300 | Pohledávky za společníky | Švanda, Hůf |
| 365.001, 365.002 | Závazky ke společníkům | Švanda, Hůf |
| 411.100 | Základní kapitál | Vklad ZK 10 Kč |
| 426.100 | Jiný VH minulých let — oprava chyb | ČÚS 019 |
| 431.100 | VH ve schvalovacím řízení | Po Z2 z uzávěrky |
| 479.100 | Dlouhodobá půjčka | Půjčka od společníka |
| 501.x, 513, 518.x | Drobný DHM, reprezentace, služby | Hlavní nákladové |
| 602.100 | Tržba z prodeje služeb | Hlavní výnos |
| 701.100 / 702.100 / 710.100 | Závěrkové účty | Z1/Z2/Z3 + ID-PS |

Aktuálně **112 aktivních účtů** (`SELECT COUNT(*) FROM uctova_osnova WHERE je_aktivni=1`).

---

## 7. Workflow běžné práce

Stručný přehled, jak Tereza s programem pracuje:

1. **Bankovní výpisy** — import CSV/PDF přes Banka modul, automatická
   detekce duplicit, párování transakcí na faktury / vytvoření
   ID dokladu pro nedohledané (commits `ac4ee44`, `947bd06`,
   `0f15d74`).
2. **Příchozí faktury (FP)** — z OCR inbox (commit `02dcaab`,
   `0b15897` `OCR approve creates NOVY document with PDF attachment`)
   nebo manuálně. Kontace dle účtové osnovy, RC pro EU plnění
   (`dph_rezim=REVERSE_CHARGE`).
3. **Vystavené faktury (FV)** — vytvoření, zaúčtování, sledování úhrady
   přes Banka (commit `e52ec8d`).
4. **Měsíční kontrola DPH** — stránka *Přehledy DPH* (identifikovaná
   osoba, RC plnění), export pro EPO portál Finanční správy
   (textový clipboard nebo PDF za rozsah měsíců — commit `7bfdf57`).
5. **Roční uzávěrka** — `PrenosZustatkuCommand` zapíše PS pro
   následující rok; tlačítko *Vystavit uzávěrku roku* ve Výkazech
   spustí `UzaverkaRokuCommand` (Z1/Z2/Z3). Vše s `je_zaverka=True`
   (commit `18535d5`).
6. **Průběžná kontrola výkazů** — Rozvaha, VZZ, Předvaha, Hlavní kniha
   ve Výkazech. Pro audit po uzávěrce switch *„Včetně závěrkových
   zápisů"* (default ON v Hlavní knize, OFF jinde).

**Pomocné funkce:** automatická záloha DB při startu (`43c64d6`),
manuální storno přes UI, duplicate dokladu pro opakující se faktury
(`cfa9299`).

---

## 8. Historie programu — milestones

Chronologický přehled významných milestones (z `git log --all`).

### 🌱 11.4.2026 — Genesis
- `4980907` chore: initial project structure
- `623c1f9` / `e22885e` Money value object s halíře precision
- `98d9a73` DB connection factory, UoW, migration runner
- `b92e301` Doklad entity + DokladyRepository
- `0e894b1` Účetnictví domain (Ucet, UcetniZaznam, UctovyPredpis)
- `82caa54` ZauctovaniDokladuService + Predvaha/HlavniKniha

### 🏗️ 13.–18.4.2026 — UI MVP
- `e943c93` UI skeleton s design tokeny + sidebar
- `dd9844d` Dashboard s live KPI
- `375b9f3` Doklady list s filtry, detail dialog, drill-down
- `8f60542` Full CRUD MVP (creation, accounting, detail actions)
- `97e0784` **Fáze 6.5:** Storno přes opravný předpis
- `7b1b707` **Fáze 6.7:** Filter-aware UI + form k_doreseni

### 🎯 16.4.2026 — Strategic pivot
- `c36c6f9` docs(roadmap): strategic pivot to tax deadline 4.5.2026

### 📚 16.4. → 30.4.2026 — Sprint k DPPO
- `d795b29` **Fáze 7:** Účtová osnova s analytikami
- `88e9320` **Fáze 8:** Sidebar restructure + sub-menu
- `c643c1a` **Fáze 9:** Partneři + ARES
- `f9f8f55` **Fáze 10:** Multi-currency + shareholder workflow
- `ec06965` **Fáze 11:** Reverse charge DPH (§6g)
- `02dcaab` **Fáze 12:** OCR inbox
- `ac4ee44` **Fáze 13:** Bank module (CSV+PDF import)
- `947bd06` **Fáze 13.5:** Bank payment matching
- `d6fb86d` **Fáze 14:** Initial balances + share capital wizard
- `030c6ce` **Fáze 15:** Finanční výkazy a sestavy

### 🛠️ 1.–8.5.2026 — Pre-podání tuning
- `eaaeeb6` tax/non-tax distinction (DPPO ř. 40, je_danovy)
- `12f7dd7` DPH modul (samostatná stránka)
- `a9348bd` Zálohové faktury workflow
- `8f2ef32` Kurzové rozdíly na analytice
- `90983f3` Compact closing PDF + saldokonto + unified filters
- `f8cf9f7` Drilldown na řádek VZZ / rozvahy
- `d7227e2` Volba „čistá závěrka" (PDF bez přílohy)

### 🏁 květen 2026 — DPPO 2025 podáno

- Termín 4.5.2026 splněn (`ROADMAP.md`), přesné datum podání **k ověření**.
- **Klíčové pravidlo:** Po tomto bodě se účetní data za rok 2025
  **nesmí měnit**. Opravy chyb minulého období se účtují přes
  `426.100` v běžném období (ČÚS 019) — viz doklad `ID-2026-001`
  (Hetzner reklasifikace z 20.5.2026).

### 🔧 20.5.2026 — Závěrkový refactor
- `358b5c8` feat(uzaverka): přenos KZ → PS následujícího roku
- `04799b7` fix(uzaverka): doklad 701 přes analytiku 701.100
- `7bfdf57` feat(dph): PDF export DPH za rozsah měsíců
- `18535d5` **feat: závěrkový workflow + storno bug fix + skryté
  výkazové filtry** (`je_zaverka` flag, `UzaverkaRokuCommand`,
  sjednocení storno filtrů, oprava účtu 426 v Rozvaze)

---

## 9. Známé limity a TODO

### 9.1 Funkční mezery (uživatelské)

Tyto domain složky existují jako placeholder, ale **žádná business
logika** v aktuální verzi (z `ROADMAP.md` mimo MVP scope):
- **Mzdy** — `domain/mzdy/` prázdné (firma nemá zaměstnance)
- **Majetek + odpisy** — `domain/majetek/` prázdné (nemá DHM nad
  hranici)
- **Kontrolní hlášení (KH)** — info-only v `ui/pages/dph_page.py`
  (identifikovaná osoba KH nepodává)
- **EPO XML export** — pouze textový clipboard pro ruční přepis
  (`services/queries/dph_prehled.py` → `to_epo_text`)
- **DPH dodatečná přiznání** — modul neumí evidovat dodatečná
  přiznání. Tabulka `dph_podani` je v současné DB **prázdná** —
  modul ukazuje *„K podání"* i pro měsíce, kde už bylo řádné
  přiznání podáno (chybí mechanizmus označení podaného přiznání
  v praxi).
- **Opravné položky, rezervy, časové rozlišení** — mimo MVP scope
- **ARES integrace** — partner entity existuje, ale ARES klient pro
  lookup z IČO **k ověření** (`infrastructure/` nemá zjevný ARES
  modul)

### 9.2 Architektonické TODO (z `ROADMAP.md`)

- **Banka validator** — `test_pdf_errors_propagated` padá pre-existing
  (commit `43c1933` rozbil; PDF parse chyba neoznačí is_valid=False)
- **Rozdělit `je_zaverka`** na `je_uzaviraci` + `je_otviraci` —
  pokud někdy potřeba samostatně auditovat
- **Mapování účtové osnovy** — preventivně ověřit, že všechny aktivní
  A/P účty mají prefix v `ROZVAHA_AKTIVA` / `ROZVAHA_PASIVA` a všechny
  N/V účty v `VZZ_RADKY`. Bez toho se nový účet stane „neviditelný"
  (jak se stalo s 426 do `18535d5`)
- **Bilanční kontrola jako runtime guard** — zvážit `assert
  aktiva == pasiva` v `get_rozvaha` místo tichého warning baneru

---

## 10. Externí integrace

| Integrace | Modul | Status |
|-----------|-------|--------|
| **OCR** | `infrastructure/ocr/` | Funkční (commit `02dcaab` `1c3b6bd` `0b15897`). Vision/Tesseract — **k ověření detail** |
| **Bank CSV import** | `infrastructure/banka/csv_parser.py` (odvozeno) | Moneta, ČS (commits `ac4ee44`, `43c1933`) |
| **Bank PDF parser** | `infrastructure/banka/pdf_statement_parser.py` | ČS PDF (`43c1933`); Moneta PDF **k ověření** |
| **ARES (lookup IČO)** | Partner entity zmiňuje ARES (`c643c1a`), reálný ARES klient v repu **nedohledán** | K ověření |
| **EPO portál** | Pouze textový clipboard pro ruční přepis | Žádný API přístup |

---

## 11. Architektonická rozhodnutí

### Money jako INT haléře
`CLAUDE.md` + commit `e22885e`. Důvod: žádné float chyby, předvídatelné
zaokrouhlování (ROUND_HALF_UP).

### Repository / UoW pattern
`CLAUDE.md` + commit `98d9a73`. Všechny mutace přes `with uow:` blok,
žádný přímý `commit()` mimo UoW.

### Žádný SQL v UI vrstvě
`CLAUDE.md`. UI komunikuje výhradně přes ViewModely → Services.

### České názvy v doméně, anglické v infrastruktuře
`CLAUDE.md`. Doménové entity `Doklad`, `UcetniZaznam`, `Pohledavka`;
technická vrstva `Repository`, `UnitOfWork`, `ConnectionFactory`.

### Storno = protizápis, ne soft-delete
Commit `97e0784`. Per-záznam architektura (`ucetni_zaznamy.je_storno`
+ `stornuje_zaznam_id`). Audit trail zachován.

### Dual mechanism závěrky (PS přenos + uzavírací doklady)
Commit `18535d5` + `ROADMAP.md` TODO. **Rozhodnutí:** ponechat oba —
PS přenos je primární zdroj dat (tabulka `pocatecni_stavy`), uzavírací
doklady (Z1/Z2/Z3) jsou formální stránka uzávěrky. `je_zaverka` filtr
eliminuje duplicitu ve výkazech. *(Odvozené:* alternativa B by byla
přepsat PS přenos a používat jen účty 701/702 — vyšší riziko regrese,
zamítnuto.*)*

### Filtr `vcetne_zaverky` — různé defaulty per modul
Commit `18535d5`. Důvod:
- **Rozvaha / VZZ / Předvaha / DPH / Pokladna / Nedaňové** —
  default `False`: uživatel chce **stav „tak jak rok proběhl"**
  (před závěrkovými operacemi).
- **Hlavní kniha / Drilldown** — default `True`: **audit** musí
  vidět kompletní deník vč. uzavíracích.

### Jeden flag `je_zaverka` pokrývá uzavírací i otevírací
Commit `18535d5`. **Rozhodnutí:** Uzavírací (Z1/Z2/Z3) a otevírací
(`ID-{rok}-PS`) doklady mají stejné **chování vůči výkazům** — oba
jsou systémové zápisy závěrkového mechanismu, ne běžná aktivita.
Jeden flag = jednoduchší kód. (V budoucnu lze rozdělit — viz TODO 9.2.)

### Žádný CQRS, žádné Domain Events, žádný singleton Database
`CLAUDE.md`. „Stačí services/" — programmatický overhead by neodpovídal
velikosti projektu.

---

## 12. Slovníček pojmů

### Účetní zkratky (z DB, kódu, komentářů)

| Zkratka | Význam |
|---------|--------|
| **RC** | Reverse charge — přenesená daňová povinnost (§24 ZDPH) |
| **OSS** | One Stop Shop — režim DPH pro služby spotřebitelům v EU (dříve **MOSS** — Mini One Stop Shop) |
| **DUZP** | Datum uskutečnění zdanitelného plnění |
| **VH** | Výsledek hospodaření |
| **VZZ** | Výkaz zisku a ztráty |
| **PS** | Počáteční stav (účtu na začátku období) |
| **KZ** | Konečný stav (účtu na konci období) |
| **MD** | Má dáti (debetní strana) |
| **Dal** | Dal (kreditní strana) |
| **ZK** | Základní kapitál |
| **DPPO** | Daň z příjmů právnických osob |
| **DPH** | Daň z přidané hodnoty |
| **EPO** | Elektronická podání pro Finanční správu |
| **VIES** | VAT Information Exchange System (souhrnné hlášení EU) |
| **ČÚS** | České účetní standardy (např. ČÚS 019 — oprava chyb min. let) |
| **§6g ZDPH** | Identifikovaná osoba dle zákona o DPH |

### Typy dokladů

| Kód | Význam |
|-----|--------|
| FV | Faktura vydaná |
| FP | Faktura přijatá |
| FPR | Faktura přijatá reverse charge |
| ZF | Zálohová faktura |
| BV | Bankovní výpis |
| PD | Pokladní doklad |
| ID | Interní doklad (vč. závěrkových Z1/Z2/Z3 a otevírací `ID-{rok}-PS`) |
| OD | Opravný doklad |

### Typy účtů

| Typ | Význam | Třídy účtů |
|-----|--------|------------|
| A | Aktiva | 0xx, 1xx, 2xx, 3xx debetní |
| P | Pasiva | 3xx kreditní, 4xx |
| N | Náklady | 5xx |
| V | Výnosy | 6xx |
| Z | Závěrkové (výpočtové) | 7xx |

---

## Poznámky k tomuto dokumentu

**Co je doloženo z dat:**
- Commit hashe a jejich data (`git log --all --format="%h %ai %s"`)
- Soubory a cesty v kódu (přímo dohledatelné)
- Tabulky a sloupce DB (`sqlite3 ucetni.db .schema`)
- Citace z `CLAUDE.md`, `ROADMAP.md`, `LESSONS_LEARNED.md`

**Co je odvozené (vyznačeno *(odvozeno)* nebo „K ověření"):**
- Prázdné domain složky → „placeholder bez logiky"
- Architektonická rozhodnutí, kde commit nepíše „proč"
- Bank PDF parser pro Moneta (jistě jen ČS dle commit msg)
- ARES integrace (entity existuje, klient nedohledán)

**Co bylo VYNECHÁNO** (per Tereziny instrukce — jen fakta z gitu/kódu/DB):
- Datum vzniku PRAUT s.r.o.
- Datum registrace identifikované osoby (§6g)
- Konkrétní datum podání DPPO 2025
- „Echo od FÚ" (kontext z konverzace, ne v repu)

Tyto skutečnosti může Tereza doplnit v dalším release dokumentu.
