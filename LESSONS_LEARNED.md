# Lessons Learned — UcetniProgram

Dokument shrnuje stav projektu k dubnu 2026 po ~2 měsících vývoje.
Cílem je zachytit, co funguje, co ne, a co bych dnes udělal jinak.

---

## 1. Co projekt dělá (Feature Inventory)

**Jádro projektu:** Desktopový účetní systém pro české podvojné účetnictví (s.r.o., identifikovaná osoba), postavený na PyQt6 + SQLite.

### Kompletní moduly (core)

| Modul | Soubor | Co dělá |
|-------|--------|---------|
| **Účetní deník** | `core/ucetni_denik.py` | Podvojné zápisy MD/Dal, obratová předvaha, hlavní kniha |
| **Doklady** | `core/doklady.py` | CRUD dokladů (FV, FP, ZF, BV, PD, ID, OD), storno s opravným dokladem |
| **Účtová osnova** | `core/uctova_osnova.py` | Seed z SQL, analytické účty, validace |
| **Partneři** | `core/partneri.py` | CRUD, ARES integrace, fuzzy matching (Levenshtein) |
| **Saldokonto** | `core/saldokonto.py` | Otevřené položky, aging report (0/30/60/90+), auto-párování |
| **DPH** | `core/dph.py` | Měsíční/roční přehledy, termíny, kontrola obratu 2M, XML přiznání |
| **DPPO** | `core/dppo.py` | Výpočet daně z příjmů, daňově neuznatelné náklady |
| **Majetek** | `core/majetek.py` | Zařazení/vyřazení DHM/DNM/drobný, inventární karty |
| **Odpisy** | `core/odpisy.py` | Rovnoměrné + zrychlené odpisy dle ZDP, odpisový plán |
| **Mzdy** | `core/mzdy.py` | DPP/DPČ/HPP výpočty, srážková/zálohová daň, SP/ZP, mzdové listy |
| **Výkazy** | `core/vykazy.py` | Rozvaha + VZZ dle vyhlášky 500/2002 Sb., bilanční kontrola |
| **Závěrka** | `core/zaverka.py` | Uzavření roku, převod VH do 428/429, kontroly |
| **Accounting Engine** | `core/accounting_engine.py` | Návrhy předkontací (historie, klíčová slova, OCR, typ dokladu) |
| **Zálohový cyklus** | `core/accounting_engine.py` | ZF → BV → DZ → KF kompletní workflow |
| **CSV import** | `core/import_csv.py` | Import bank. pohybů, přepočet řetězce zůstatků |
| **Bank parser** | `core/bank_import.py` | Parsování CSV z Fio, KB, ČS, Moneta (auto-detect formátu) |
| **Bank OCR** | `core/bank_ocr.py` | OCR extrakce z PDF výpisů (pyobjc Vision + Tesseract fallback) |
| **Párování** | `core/parovani.py` | Auto + ruční párování bank ↔ faktury, pokladní úhrady |
| **Číselné řady** | `core/ciselne_rady.py` | Automatická čísla dokladů FV-2026-001 |
| **Zálohy** | `core/backup.py` | SQLite Online Backup API, rotace, auto-backup při startu |

### UI (PyQt6)

| Stránka | Řádků | Popis |
|---------|-------|-------|
| `bankovni_vypisy_ui.py` | 1740 | Výpisy, PDF upload, OCR kontrola, analýza rozdílů |
| `doklady_ui.py` | 1087 | Seznam dokladů, filtrování, nový doklad dialog |
| `design_tokens.py` | 904 | Barvy, typografie, spacing, globální QSS stylesheet |
| `penize_ui.py` | 699 | Banka + pokladna, zůstatky, pohyby |
| `dashboard.py` | ~400 | KPI karty, cashflow graf, upozornění (DPH termíny) |
| + 15 dalších stránek | ~5000 | Partneři, osnova, deník, výkazy, majetek, mzdy, nastavení... |

### UI komponenty

Command palette (Ctrl+K), sidebar navigace, topbar, KPI karty, tabulky, formulářové karty, undo toast, průvodce prvním nastavením, klávesové zkratky (Ctrl+N, F5, F11 zen mode).

### Testy

14 test souborů, ~6400 řádků. Pokrývají: deník, doklady, DPH, DPPO, export, integraci, majetek, mzdy, OCR, osnovu, partnery, saldokonto, účetní logiku, výkazy.

### Export

PDF generátor (WeasyPrint), CSV export, XML export (DPH přiznání EPO), QR platba, faktura šablona.

---

## 2. Co funguje dobře (zachovat)

### Architektura

- **Čistá separace core / UI / export / import** — core moduly nemají žádnou závislost na PyQt6. Dá se nad nimi postavit jiné UI (web, CLI) bez změny.
- **Singleton Database s WAL režimem** — pragmy (WAL, FK, busy_timeout, cache_size) nastaveny správně pro desktopovou SQLite aplikaci.
- **Migrační systém** — jednoduchý, funkční, sekvenční SQL soubory s verzováním. Pro jednouživatelskou desktop app ideální.
- **Automatická záloha při startu** s rotací (30 záloh) přes SQLite Online Backup API — bezpečné, atomic.
- **Vlastní exception hierarchie** — `UcetniError` → `PodvojnostError`, `SaldokontoError`, `ValidaceError` atd. Konzistentní, dobře pojmenované.

### Doménová logika

- **Účetní deník validuje vše**: existenci účtů, aktivnost, kladné částky, stav dokladu, otevřenost období. Poctivé.
- **Storno přes opravný doklad** (OD) s prohozenými MD/Dal — správný účetní postup, ne soft-delete.
- **Zálohový cyklus ZF→BV→DZ→KF** — kompletní workflow včetně sledování stavu.
- **Aging report** — korektní kategorizace (před splatností / 0-30 / 31-60 / 61-90 / 90+).
- **Mzdové výpočty** — DPP/DPČ/HPP s korektními sazbami 2026, srážková vs. zálohová daň, limity.
- **Rozvaha a VZZ** dle vyhlášky 500/2002 Sb. — struktura odpovídá předpisu, bilanční kontrola.
- **Seed dat** — účtová osnova z SQL souboru, číselné řady, speciální partneři (ČSSZ, VZP, FÚ), nastavení.

### UI

- **Design tokens** — centralizované barvy, typografie, spacing. Žádné magické hodnoty roztroušené v kódu.
- **Lazy loading stránek** — factory pattern v MainWindow, stránky se nevytvářejí dokud nejsou potřeba.
- **Fusion style** — řeší problém macOS native stylu ignorujícího QSS (dokumentováno v komentáři).
- **Command palette** (Ctrl+K) — profesionální UX pro power usery.
- **Dořeším panel** — pragmatické řešení pro doklady vyžadující pozornost.

### Ostatní

- **Audit triggery v SQLite** — automatické logování INSERT/UPDATE na doklady, účetní záznamy, majetek, partnery.
- **Bank parser auto-detect** — detekce formátu Fio/KB/ČS/Moneta z hlavičky CSV.
- **OCR s dual-engine** — pyobjc Vision (macOS nativní) s fallbackem na Tesseract.

---

## 3. Co je špatně navržené (technický dluh)

### KRITICKÉ: Částky jako TEXT v SQLite

**Problém:** Všechny finanční částky jsou uloženy jako `TEXT NOT NULL DEFAULT '0'` v databázi.

**Důsledky:**
- Každý SQL dotaz agregující částky musí používat `CAST(castka AS REAL)` — nalezeno **31 výskytů** v kódu. REAL je float (IEEE 754), takže se ztrácí přesnost, kterou TEXT→Decimal v Pythonu má zajistit.
- Nesoulad: v Pythonu se pracuje s `Decimal`, ale SQLite agregace projde přes `REAL` (float64). Zaokrouhlovací chyby u velkých objemů.
- Nelze použít SQL `SUM()`, `ORDER BY castka` přímo — vždy nutný CAST nebo Python agregace.

**Co bych dnes udělal jinak:** Uložit částky jako `INTEGER` v haléřích (nejmenší jednotka). `12345` = 123,45 Kč. Přesné, řaditelné, agregovatelné v SQL. Konverze jen na UI hranici.

### Nekonzistentní commit patterny

**Problém:** Projekt míchá dva přístupy k transakcím:

1. `with self._db.transaction() as cur:` — správný, atomický, auto-rollback
2. `self._db.execute(...); self._db.connection.commit()` — manuální commit mimo transakci

Nalezeno **70 výskytů** `connection.commit()` mimo transakční kontext. To znamená:
- Částečné zápisy při chybě (žádný rollback)
- V `parovani.py` se commitují 3 operace (zaúčtování, zápis úhrady, update pohybu) bez společné transakce

**Co bych dnes udělal jinak:** Všechny mutace výhradně přes `with db.transaction()`. Žádný přímý `connection.commit()`.

### UI přímo volá SQL dotazy

**Problém:** UI stránky (`bankovni_vypisy_ui.py` — 1740 řádků) obsahují přímé SQL dotazy:

```python
# v UI kódu:
_stats = self._db.fetchone(
    "SELECT COALESCE(SUM(CAST(castka AS REAL)), 0) AS obrat, "
    "COUNT(*) AS cnt FROM bankovni_pohyby WHERE vypis_id = ?",
    (vypis_id,),
)
```

Nalezeno ve všech větších UI souborech. UI tak obsahuje business logiku (přepočty zůstatků, OCR kontroly, párování).

**Co bych dnes udělal jinak:** UI volá pouze metody z core modulů. Žádný SQL v UI vrstvě. `bankovni_vypisy_ui.py` by měl mít 500 řádků, ne 1740.

### `bankovni_vypisy_ui.py` — god object

Jeden soubor (1740 řádků) řeší:
- Seznam výpisů a pohybů
- PDF upload a OCR
- Live re-kontrolu OCR proti aktuálním pohybům
- Analýzu rozdílů
- Smazání výpisu s přepočtem
- Přesun pohybů mezi měsíci
- Duplikáty

Mělo by to být rozložené do 3-4 souborů + core modul pro business logiku bankovních výpisů.

### Duplicita `_najdi_obdobi()` a `_dalsi_cislo()`

Metoda `_najdi_obdobi()` je implementovaná zvlášť v:
- `core/doklady.py:516`
- `core/accounting_engine.py:793`

Metoda `_dalsi_cislo()` v:
- `core/accounting_engine.py:810` (vlastní implementace)
- `core/ciselne_rady.py` (správná centrální implementace)

AccountingEngine by měl používat CiselneRady, ne vlastní kopii.

### Kontrola podvojnosti je noop

V `ucetni_denik.py:295-312`:

```python
def kontrola_podvojnosti_dokladu(self, doklad_id: int) -> bool:
    total_md = sum(Decimal(r["castka"]) for r in rows)
    total_dal = sum(Decimal(r["castka"]) for r in rows)  # <- stejný výraz!
    return total_md == total_dal  # <- vždy True
```

Model ukládá jeden řádek s jednou částkou pro MD i Dal, takže kontrola podvojnosti je tautologie. Pokud se někdy změní datový model (split MD/Dal), tato kontrola to nezachytí.

### Agents modul nedělá nic užitečného

`agents/ocr_agent.py`, `agents/preprocessing.py`, `agents/validation_agent.py` — připravené struktury pro AI agenty (OCR preprocessing, validace), ale reálná OCR logika je v `core/ocr_scanner.py` a `core/bank_ocr.py`. Agents modul je mrtvý kód / nedokončený refaktoring.

### Dva import moduly pro banku

- `core/bank_import.py` — parser CSV (hlavní, používaný)
- `import/bank_import.py` + `import/bank_profiles/` — alternativní import s bank profily

Existují paralelně, není jasné který je "ten správný". `import/` modul má bank profily (KB, ČS), `core/` má generický parser. Měl by být jeden.

### Test coverage díry

Netestováno:
- `core/parovani.py` — žádný `test_parovani.py`
- `core/bank_import.py` — parsování CSV z bank
- `core/backup.py` — zálohy
- `core/zaverka.py` — účetní závěrka
- `core/ciselne_rady.py` — číselné řady (pouze přes integrační test)
- Žádný UI test (pytest-qt je v requirements, ale žádný test UI neexistuje)

### check_same_thread=False bez ochrany

`database.py:43-46`:
```python
self._conn = sqlite3.connect(
    str(self._db_path),
    check_same_thread=False,
)
```

Multi-thread přístup k SQLite bez jakéhokoli lockingu na aplikační úrovni. V desktopové single-thread PyQt appce to funguje, ale je to časovaná bomba pokud se přidá background worker (OCR, import).

---

## 4. Co bych dnes udělal jinak

### 1. Peníze jako INTEGER v haléřích

Eliminuje celou kategorii bugů. Žádný `str(castka)`, žádný `Decimal(str(row["castka"]))`, žádný `CAST(... AS REAL)`. Konverze na `Decimal` jen na hranici UI.

### 2. Repository pattern místo přímého SQL

Každý core modul (`doklady.py`, `partneri.py`, ...) si sám skládá SQL. Při 30+ tabulkách to vede k nekonzistencím. Centrální repository/DAO vrstva by:
- Odstranila SQL z UI
- Umožnila jednotné transakční řízení
- Zjednodušila testování (mock repository místo mock DB)

### 3. Oddělení bankovní agendy do core modulu

Vytvořit `core/bankovni_vypisy.py` s celou business logikou (CRUD výpisů, přepočet zůstatků, OCR kontrola, přesun pohybů). UI by volal jen metody.

### 4. Typovaný config místo key-value nastavení

Tabulka `nastaveni` je key-value store s `TEXT` hodnotami. Lepší by byl `@dataclass NastaveniFiremy` s typovanými poli, serializovaný do JSON nebo dedikované tabulky.

### 5. Event systém pro přepočty

Aktuálně se po každé změně (import, smazání, přesun pohybu) manuálně volají přepočty zůstatků na 3-5 místech. Event/signal systém (`on_pohyb_changed → recalculate_chain`) by eliminoval zapomenuté přepočty.

### 6. Nepoužívat singleton Database v produkci

Singleton komplikuje testy (nutný `Database.reset()` po každém testu) a znemožňuje paralelní testy. Dependency injection přes konstruktor je čistější — a v podstatě už se tak volá (`db=db`), jen s fallbackem na singleton.

### 7. Výkazy přes konfiguraci, ne hardcoded

`vykazy.py` má 516 řádků hardcoded rozvahy a VZZ — konkrétní čísla účtů, mapování na řádky výkazu. Mělo by být konfigurovatelné (YAML/JSON), aby se dalo:
- Přizpůsobit pro jiný typ subjektu
- Aktualizovat při změně vyhlášky bez zásahu do kódu

### 8. Jeden bankovní parser s plugin systémem

Místo dvou paralelních modulů (`core/bank_import.py` + `import/bank_import.py`) jeden parser s registrovanými profily pro jednotlivé banky. Přidat novou banku = přidat jeden soubor.

---

## 5. Pohled účetního — legislativa, přesnost, workflow

*Co by změnil člověk, který v tom systému musí vést účetnictví a zodpovídat za něj.*

### Legislativní díry

#### 5.1 Chybí Kontrolní hlášení DPH

Systém generuje přiznání k DPH, ale ne Kontrolní hlášení (povinné od 2016 pro plátce, a při přeregistraci i pro identifikovanou osobu). Bez KH hrozí pokuta 10 000–500 000 Kč. Strukturálně chybí evidence jednotlivých plnění s DIČ protistrany, kódem plnění a členěním A1/A4/A5/B1/B2/B3.

#### 5.2 Chybí Souhrnné hlášení (VIES)

Při reverse charge z EU je povinné Souhrnné hlášení. Systém eviduje RC transakce (detekce v `accounting_engine.py`), ale negeneruje XML pro VIES. Povinnost identifikované osoby dle §102 ZDPH.

#### 5.3 DPH zpětný výpočet základu je nepřesný

`dph.py:114-118` odvozuje základ daně zpětně z DPH částky (`DPH × 100 / 21`). Správně má být základ evidovaný přímo na dokladu, ne dopočítávaný. Navíc je hardcoded sazba 21 % — u snížené sazby 12 % počítá špatně. Chybí rozlišení sazeb v evidenci.

#### 5.4 DUZP vs. datum vystavení

Systém používá `datum_vystaveni` jako datum účetního zápisu. Pro DPH je ale rozhodující DUZP (datum uskutečnění zdanitelného plnění) — a to se může od data vystavení lišit. Měsíční přehled DPH (`dph.py:86-96`) filtruje dle data záznamu v deníku, ne dle DUZP. Může zařadit plnění do špatného období.

#### 5.5 Chybí strukturovaná evidence přijatých plnění z EU

Identifikovaná osoba musí vést evidenci přijatých služeb z EU s: DIČ dodavatele, datum plnění, základ daně, sazba DPH, vypočtená daň. Systém to nesleduje strukturovaně — informace jsou roztroušené v dokladech a účetních záznamech.

#### 5.6 Kurzové rozdíly při závěrce

`zaverka.py` neřeší přecenění cizoměnových pohledávek a závazků k 31.12. kurzem ČNB. Povinné dle §4 odst. 12 zákona o účetnictví. Kurzové rozdíly se účtují na 563 (ztráta) / 663 (zisk). Tabulka `kurzy` existuje, ale závěrka ji nepoužívá.

#### 5.7 Chybí časové rozlišení

Žádná podpora pro náklady/výnosy příštích období (účty 381, 383, 384, 385). Účty existují v osnově a v rozvaze, ale není workflow pro vytvoření časového rozlišení a jeho automatické rozpuštění v následujícím období. Účetní to musí řešit ručně interními doklady.

#### 5.8 Opravné položky k pohledávkám

Účet 391 je v rozvaze (`vykazy.py:148`), ale nikde se opravné položky nevytváří. Po 90+ dnech po splatnosti by systém měl nabídnout tvorbu zákonné opravné položky dle §8a zákona o rezervách. Data pro to má — aging report v saldokontu.

### Přesnost a správnost

#### 5.9 Haléřové vyrovnání při párování

Při párování úhrad může vzniknout haléřový rozdíl (banka zaokrouhlí jinak než faktura). Systém neumí automaticky zaúčtovat haléřové vyrovnání na 568 (kurzová ztráta) / 668 (kurzový zisk). Účetní to musí řešit ručně interním dokladem pokaždé, když je rozdíl 0,01–1,00 Kč.

#### 5.10 Storno má špatné datum

`doklady.py:345` účtuje storno záznamy s `date.today()`. Správně by měly mít datum opravného dokladu (které může zadat uživatel, ne nutně dnešní). A pokud je stornovaný doklad v uzavřeném období, storno musí jít do aktuálního období — to není ošetřené, `_validuj_obdobi()` to hodí jako chybu.

#### 5.11 Kumulace DPP u jednoho zaměstnavatele

Mzdový modul počítá každou DPP zvlášť. Ale pokud má zaměstnanec víc DPP u stejného zaměstnavatele, limity pro odvody SP/ZP se posuzují kumulativně — součet všech DPP v daném měsíci. Systém to neřeší, může tak vypočítat nižší odvody než je zákonná povinnost.

#### 5.12 Technické zhodnocení mění základ odpisů

Systém při technickém zhodnocení (`majetek.py:317`) zvýší vstupní cenu i zůstatkovou cenu, ale odpisový plán (`odpisy.py`) stále počítá s původní vstupní cenou a původním koeficientem. Správně se po TZ mění koeficient (používá se koeficient pro zvýšenou vstupní cenu dle §31/§32 ZDP).

#### 5.13 VZZ neobsahuje všechny povinné řádky

Výkaz zisku a ztráty (`vykazy.py:247-374`) neobsahuje:
- Řádek B. "Změna stavu zásob vlastní činnosti" (účty 58x)
- Řádek C. "Aktivace" (účty 62x)
- Řádek H.+I. "Rezervy" (účty 552, 554, 574)

Pro výrobní firmy nebo firmy s vlastní výrobou jsou povinné dle přílohy č. 2 vyhlášky 500/2002 Sb.

### Workflow pro účetního

#### 5.14 Chybí měsíční uzávěrka

Účetní potřebuje "uzavřít měsíc" — zamknout období proti editaci, vytisknout deník za měsíc, zkontrolovat předvahu, ověřit DPH. Systém má jen roční uzávěrku v `zaverka.py`. Měsíční uzávěrka by zachytila chyby průběžně, ne až na konci roku.

#### 5.15 Žádná kontrola duplicitních přijatých faktur

Pokud účetní zaeviduje dvakrát stejnou fakturu od dodavatele (stejné číslo FP, stejný partner, stejná částka), systém to nezachytí. Kontrola by měla být na kombinaci: partner_id + externí číslo faktury + částka. Dvojitá platba dodavateli je jeden z nejčastějších účetních omylů.

#### 5.16 Chybí kontrolní report "Co je špatně"

Účetní potřebuje denní/týdenní přehled:
- Neuhrazené faktury po splatnosti (má v saldokontu, ale ne na dashboardu proaktivně)
- Nezaúčtované doklady (doklady bez účetních záznamů)
- Nesparované bankovní pohyby
- Doklady bez přílohy (faktura bez PDF)
- Chybějící DUZP na daňových dokladech
- Otevřené měsíce bez uzávěrky

#### 5.17 Pokladní limit

Zákon 254/2004 Sb. omezuje hotovostní platby na 270 000 Kč denně mezi dvěma subjekty. Systém nekontroluje — účetní může vytvořit pokladní doklad nad limit bez varování.

#### 5.18 Archivační lhůty

Zákonná povinnost archivovat účetní doklady 5 let (§31 ZoÚ), daňové doklady 10 let (§35 ZDPH). Systém nesleduje dobu archivace, neupozorňuje na možnost skartace, a při obnově ze zálohy se mohou ztratit záznamy o splněné archivační povinnosti.

#### 5.19 Hromadné zaúčtování

Účetní dostane 20–50 faktur měsíčně. Potřebuje je zaúčtovat hromadně — ideálně zobrazit tabulku s navrženými předkontacemi, upravit kde je potřeba, a potvrdit vše jedním tlačítkem. Aktuálně musí otevřít každý doklad zvlášť.

### Co zjednodušit

#### 5.20 Příliš mnoho typů dokladů

10 typů v CHECK constraintu (`001_initial.sql:87-93`). Účetní reálně pracuje s 5 typy: FV, FP, BV, PD, ID. Zálohové doklady (ZF, ZFP, DZ, KF) by měly být podtyp nebo stav faktury, ne samostatný typ — zjednodušilo by to navigaci i číselné řady.

#### 5.21 Účtová osnova neumožňuje snadné úpravy

Seed vloží fixní osnovu z SQL. Ale každá firma si osnovu upravuje — deaktivuje nepoužívané účty, přidává analytiky. UI pro to existuje (`uctova_osnova_ui.py`), ale chybí:
- Hromadná deaktivace nepoužívaných účtů
- Import/export osnovy (přenos mezi firmami)
- Vizuální rozlišení používaných vs. nepoužívaných účtů

#### 5.22 Navigace neodpovídá denní práci účetního

80 % času účetní dělá: zaúčtuj přijatou fakturu, zaúčtuj bankovní výpis, zkontroluj předvahu. To by mělo být 1–2 kliky z dashboardu, ne navigace přes sidebar → podsekci → tab → dialog. Dashboard by měl mít "rychlé akce": Nová FP, Import výpisu, Předvaha tento měsíc.

#### 5.23 Chybí tisk standardních sestav

Účetní potřebuje tisknout/exportovat do PDF:
- Účetní deník za měsíc (chronologicky)
- Hlavní knihu vybraného účtu
- Předvahu za období
- Saldokontní sestavu k datu
- Rekapitulaci DPH

Export modul (`export/`) umí PDF faktur a CSV, ale ne standardní účetní sestavy. Ty se zobrazují jen v UI.

---

## 6. Plánované funkce — inteligentní účetní asistent

*Funkce, které z programu udělají nástroj, ve kterém se i junior účetní zorientuje a nepotřebuje nad každou operací přemýšlet 10 minut.*

### 6.1 Kontextový průvodce předkontací

Interaktivní vyhledávání: napíšu situaci běžnou češtinou ("faktura za telefon z prosince zaplacená v lednu", "záloha na služby od slovenského dodavatele") a systém mi krok za krokem vysvětlí jaké účty použít, proč, a nabídne hotovou předkontaci k potvrzení. Kombinace znalostní báze (`core/knowledge.py`) s interaktivním UI — ne jen návrh čísla účtu, ale srozumitelné vysvětlení pro člověka, který se teprve učí.

### 6.2 OCR zpracování dokladů s povinným schválením

Nahrajeme doklady (PDF, scan, foto) přímo do programu. OCR pipeline (rozšíření stávajícího `core/bank_ocr.py` a `core/ocr_scanner.py`) z nich extrahuje:
- Typ dokladu (FP, FV, paragon)
- Dodavatel/odběratel → párování s existujícím partnerem nebo návrh nového z ARES
- IČO, DIČ, číslo faktury, DUZP, datum splatnosti
- Částka, sazba DPH, základ
- Návrh předkontace na základě historie partnera a klíčových slov

**Klíčové pravidlo:** Nic se nezaúčtuje automaticky. Vše co OCR navrhne musí projít schválením uživatele. V UI musí být jasně vizuálně rozlišeno:
- **Neschválené** — OCR návrh, čeká na kontrolu (žlutý stav, ikona oka)
- **Schválené a zaúčtované** — potvrzeno uživatelem, zapsáno v deníku (zelený stav, ikona fajfky)
- **Odmítnuté / opravené** — uživatel změnil návrh OCR (modrý stav, ikona tužky)

Fronta ke schválení na samostatné stránce nebo v Dořeším panelu — tabulka s návrhy, hromadné schválení vybraných, detail pro úpravu jednotlivých.

### 6.3 Napovídání z kontextu partnera

Při vytváření dokladu systém na základě historie partnera automaticky nabídne nejčastější předkontaci. Rozšíření stávajícího `AccountingEngine.navrhni_dle_historie()`:
- Zobrazit vedle návrhu: "Partner XY — posledních 5 faktur účtováno jako 518/321 (služby)"
- Pokud je partner nový, nabídnout předkontaci podle klíčových slov v popisu
- Confidence skóre viditelné pro uživatele: "jistota 95 %" vs. "hádám — zkontroluj"

### 6.4 Rozpoznání opakujících se operací

Systém analyzuje historii bankovních pohybů a identifikuje vzory:
- Stejná částka, stejný protiúčet, pravidelný interval → "Vypadá to jako měsíční nájemné 15 000 Kč. Chceš vytvořit šablonu?"
- Nabídne vytvoření šablony s předvyplněnou předkontací
- Při dalším výskytu automaticky přiřadí šablonu a nabídne ke schválení (ne automatické zaúčtování)

### 6.5 Detekce anomálií

Varovný systém při zadávání dokladů:
- "Faktura od XY za 250 000 Kč — předchozí faktury průměrně 12 000 Kč. Neobvyklá částka."
- "Účet 513 (Reprezentace) — daňově neuznatelný náklad. Opravdu?"
- "Dvě faktury od stejného dodavatele se stejnou částkou v tomto měsíci — duplicita?"
- "Pokladní doklad překračuje limit 270 000 Kč (zákon 254/2004 Sb.)"

Ne blokování — jen varování, uživatel rozhodne. Ale musí to vidět PŘED potvrzením, ne po.

### 6.6 Autocomplete s pamětí

Systém se učí z opakovaných operací:
- Píšu popis "Nájemné" → automaticky nabídne 518.100/321, částku 15 000 Kč, partnera "Pronajímatel s.r.o."
- Po 3 měsících stejného vzoru nabídne předvyplněný doklad jedním klikem
- Rozšíření stávajícího `KLICOVA_SLOVA_FP` v `core/knowledge.py` o dynamická pravidla naučená z historie

### 6.7 Timeline dokladu

Vizualizace celého životního cyklu dokladu na jedné obrazovce:
```
Vystavena 1.3. → Zaúčtována 2.3. → Odeslána 3.3. → Částečně uhrazena 15.3. (50%) → Doplacena 28.3.
```
Jako sledování zásilky — ne 4 různé obrazovky (doklady, deník, saldokonto, banka), ale jeden timeline. Data pro to systém má (audit_log + účetní záznamy + úhrady), jen chybí vizualizace.

### 6.8 Cashflow predikce

Graf s predikovaným zůstatkem na účtu na 30 dnů dopředu:
- Aktuální zůstatek na bankovním účtu
- Mínus splatné závazky (faktury přijaté dle data splatnosti)
- Plus očekávané úhrady (faktury vydané dle data splatnosti)
- Varování: "Za 12 dní klesne zůstatek pod 20 000 Kč"

Data jsou v saldokontu a bankovních účtech — chybí jen vizualizace a výpočet predikce.

### 6.9 "Co mám dnes udělat?" seznam

Automaticky generovaný prioritizovaný to-do list na dashboardu:
- Nespárované bankovní pohyby (kolik, od kdy)
- Nezaúčtované doklady čekající na schválení
- Faktury po splatnosti (s upomínkami)
- Blížící se termíny (DPH do 25., mzdy, závěrka)
- Neuzavřené měsíce

Každá položka je klikací — přejde přímo na konkrétní stránku/akci.

### 6.10 Porovnání měsíc vs. měsíc

Přehled změn oproti předchozímu měsíci:
- "Náklady na služby (518) vzrostly o 40 % — hlavní příčina: 2 nové faktury od dodavatele XY"
- "Tržby (602) klesly o 15 % — chybí 1 faktura oproti průměru"
- Vizuální diff předvahy: zelené/červené zvýraznění výrazných odchylek

Pomáhá zachytit chyby (zapomenuté zaúčtování) i pochopit trendy.

### 6.11 Auto-párování s učením

Rozšíření stávajícího `auto_sparovat_bank()` v `core/parovani.py`:
- Systém spáruje platbu s fakturou, uživatel to odmítne a spáruje jinak
- Systém si zapamatuje korekci a příště nabídne variantu uživatele jako první
- Po měsíci systém páruje 90 %+ sám (s potvrzením uživatele)
- Pravidla se ukládají per-partner: "Platby od XY vždy párovat s nejstarší neuhrazenou FV"

### 6.12 Hromadný import dokladů

Drag & drop více PDF/scanů najednou do importní stránky:
1. OCR zpracuje všechny soubory paralelně
2. Zobrazí tabulku s extrahovanými daty a navrženými předkontacemi
3. Uživatel projde seznam, opraví kde je potřeba
4. Potvrdí vybrané → hromadné zaúčtování jedním klikem

Rozšíření stávající OCR pipeline (`agents/ocr_agent.py`, `core/ocr_scanner.py`) + nová UI stránka pro hromadné zpracování.

### 6.13 Šablony pro opakující se operace

Uložitelné šablony:
- "Mzdy DPP" → 3 nebo 7 účetních záznamů, stačí vyplnit hrubou mzdu
- "Měsíční nájemné" → předvyplněný partner, účty, částka, jeden klik
- "Odvod SP/ZP" → automaticky z posledního mzdového listu

Uživatel si šablonu vytvoří z existujícího dokladu ("Uložit jako šablonu") nebo z průvodce. Šablony dostupné přes Command Palette (Ctrl+K → "nájemné").

### 6.14 Automatické upomínky

Faktura je N dnů po splatnosti → systém nabídne:
- 1. upomínka (7 dní): zdvořilé připomenutí s číslem faktury a QR kódem
- 2. upomínka (21 dní): důraznější, s úrokem z prodlení
- 3. upomínka (45 dní): předžalobní výzva

Předvyplněný text, uživatel potvrdí odeslání (email nebo PDF k tisku). Historie upomínek u dokladu v timeline.

### 6.15 Undo s historií

Plná historie změn s možností vrátit se k libovolnému bodu:
- "Vrátit poslední zaúčtování" (ne jen Ctrl+Z na UI akci, ale revert účetních zápisů)
- "Vrátit se do stavu před importem výpisu z 5. března"
- Audit log (`audit_log` tabulka) už existuje — chybí UI pro procházení a revert

Každá operace zobrazí dialog: "Toto vrátí 3 účetní záznamy a 1 doklad. Pokračovat?"

### 6.16 Kontrolní checklist před roční závěrkou

Interaktivní checklist zobrazený při spuštění roční závěrky (`core/zaverka.py`):

- [ ] Všechny měsíce uzavřeny
- [ ] Bankovní výpisy 1–12 zkontrolovány a souhlasí s bankou
- [ ] Všechny faktury zaúčtovány (žádné nezaúčtované doklady)
- [ ] Nesparované pohyby = 0
- [ ] Mzdy zaúčtovány za všech 12 měsíců
- [ ] Odpisy DHM/DNM provedeny
- [ ] Časové rozlišení vytvořeno
- [ ] Kurzové rozdíly k 31.12. přeceněny
- [ ] Opravné položky k pohledávkám po splatnosti
- [ ] Předvaha — bilanční kontrola OK
- [ ] DPH přehledy za všech 12 měsíců souhlasí

Zelená/červená u každého bodu. Systém automaticky zkontroluje co může (počet nezaúčtovaných dokladů, bilanční kontrola), zbytek potvrdí uživatel ručně. Závěrku nelze spustit s červenými body bez explicitního přeskočení.

### 6.17 Párová kontrola účtů a vzájemné zápočty

Systém aktivně hledá příležitosti ke zjednodušení:
- "Na účtu 311 máš pohledávku 50 000 Kč za XY, na 321 závazek 35 000 Kč vůči XY. Chceš provést vzájemný zápočet?"
- Nabídne předvyplněný interní doklad pro zápočet
- Evidence zápočtů s propojením na původní doklady

### 6.18 Varování při nebezpečných operacích

Systémová varování PŘED potvrzením operace:
- Účtování na daňově neuznatelný účet (513, 543, 545)
- Překročení pokladního limitu 270 000 Kč
- Storno dokladu v uzavřeném období
- Účtování do minulého roku bez otevřeného období
- Doklad bez přílohy u faktury (upozornění, ne blokace)

### 6.19 Účetní chatbot

Integrovaný chatbot pro účetní dotazy v přirozeném jazyce:
- "Můžu si dát oběd s klientem do nákladů?" → vysvětlení s odkazem na účet 513 a daňovou neuznatelnost
- "Jak zaúčtovat zálohu?" → průvodce zálohovým cyklem
- "Jaký je rozdíl mezi 518 a 511?" → porovnání účtů s příklady

Napojený na znalostní bázi (`core/knowledge.py`) a účtovou osnovu. Odpovídá v kontextu konkrétní firmy — ne obecně, ale "u vás na účtu 518 máte tento měsíc 45 000 Kč".

### 6.20 Mobilní dashboard *(budoucí feature)*

*Plánováno pro pozdější fázi — ne součást aktuálního vývoje.*

Mobilní rozhraní (PWA nebo nativní app) s omezeným scope:
- Přehled zůstatků (banka, pokladna)
- Nové platby na účtu (notifikace)
- Faktury po splatnosti
- Fotka paragonu → odeslání do OCR fronty v desktopové aplikaci
- Schválení navržených zaúčtování z OCR

Pouze čtení + fotky + schválení. Žádné účtování z mobilu.

---

## Shrnutí v číslech

| Metrika | Hodnota |
|---------|---------|
| Python souborů (bez venv) | ~80 |
| Core logika | 8 615 řádků |
| UI vrstva | 12 885 řádků + 2 581 komponent |
| Testy | 6 423 řádků / 14 souborů |
| Migrace | 581 řádků / 6 SQL souborů |
| DB tabulek | 22+ |
| Audit triggerů | 10 |
| Celkem | ~31 000+ řádků |

**Verdikt:** Solidní základ s funkčním core a UI. Hlavní dluh je v TEXT částkách, SQL v UI, a nekonzistentním transaction managementu. Nic z toho není neřešitelné, ale refaktoring by měl proběhnout před tím, než se přidají další features.

---

## 7. Vizuální audit a návrh vylepšení (Design Review — Sebastian)

> Tato sekce je psaná pohledem senior designera, který prošel celou UI vrstvu:
> `design_tokens.py`, `sidebar.py`, `topbar.py`, `dashboard.py`, `kpi_card.py`,
> `section_card.py`, `table_widget.py`, `base_dialog.py`, `form_card.py`,
> `empty_state.py`, `doklady_ui.py`, `partneri_ui.py`, `cashflow_chart.py`,
> `command_palette.py` a další. Hodnotí současný stav vizuálu, identifikuje problémy
> a navrhuje konkrétní vylepšení s přesnými hodnotami.

---

### 7.1 Co funguje dobře — a proč to zachovat

#### Token systém (`design_tokens.py`)
Centralizovaný design system se 7 třídami: `Colors`, `Typography`, `Spacing`, `Radius`, `Layout`, `Glass`, `Shadows`, `Icons`. Každý vizuální parametr má jedno kanonické místo. Toto je základ, na kterém jde stavět — většina projektů této velikosti tokeny nemá vůbec.

**Zachovat:** Celou strukturu tokenů, oddělení do logických skupin, sémantické barvy (`SUCCESS_*`, `ERROR_*`, `WARNING_*`, `INFO_*`), účetní specifické barvy (`DEBIT`, `CREDIT`, `ZERO`).

#### Barevná paleta
Teal/green primární paleta (`#134E4A` → `#10B981`) je neobvyklá volba pro účetní software, ale funguje — evokuje klid, stabilitu, přírodu. Akcentová gold (`#EAB308`) vytváří dobrý kontrast pro upozornění. Sémantické barvy (zelená/červená/žlutá/modrá) odpovídají zavedeným konvencím.

**Zachovat:** Celou paletu. Teal sidebar `#134E4A` je vizuální kotva programu.

#### Typografická volba
`Space Grotesk` pro nadpisy, `DM Sans` pro body text, `SF Mono` / `Fira Code` pro monospace. Párování geometric sans (headings) + humanist sans (body) je typograficky správné. Type scale: 11 → 13 → 15 → 18 → 20 → 24 → 30 — konzistentní s přibližně 1.2× ratio (minor third).

**Zachovat:** Font párování i scale. Pouze zvážit, zda 15px base (místo standardních 16px) nezpůsobuje problémy s čitelností na některých DPI.

#### Sidebar architektura
Tmavý sidebar s glass efekty (`rgba(255,255,255,0.10)` hover, `rgba(255,255,255,0.15)` active), rozbalovací skupiny s `QPropertyAnimation` (200ms `InOutQuad`), gold accent na aktivní subpoložce (`border-left: 3px solid #EAB308`), chevron animace.

**Zachovat:** Celou sidebar strukturu, tmavý režim, animované rozbalování, gold accent.

#### Účetní formátování
`format_castka()` s českým formátem (`1 234,50 Kč`), nbsp jako oddělovač tisíců, `font-feature-settings: 'tnum' 1` pro tabulární číslice, barevné rozlišení kladné/záporné/nula. Toto je profesionální detail.

**Zachovat:** Beze změn.

#### BaseDialog pattern
Čistý header/body(scroll)/footer vzor. Šedé pozadí body (`GRAY_50`), bílý header a footer s border separátorem. Primary + Ghost tlačítka ve footeru. Konzistentní spacing.

**Zachovat:** Celý pattern, jen rozšířit o micro-interakce (viz 7.3).

#### Cashflow chart
Bar chart s příjmy (zelená) vs. výdaje (červená) + linie čistého CF (teal). Antialiasing zapnutý, česká jména měsíců, hodnoty v tisících (`%.0f k`). Transparentní pozadí — správně se integruje s kartou.

**Zachovat:** Celý chart. Jen zvážit zaoblení sloupců (viz 7.3).

---

### 7.2 Co nefunguje — konkrétní problémy

#### 7.2.1 Nulové micro-interakce (kritický problém)

Celá aplikace je vizuálně **mrtvá**. Žádný prvek nemá animovaný přechod mezi stavy. QSS v PyQt6 nepodporuje CSS `transition`, takže všechny hover/pressed/focus změny jsou instant snap — 0ms přechod barvy.

**Kde to bolí nejvíc:**
- Tlačítka — barva se změní okamžitě, žádný plynulý přechod
- Karty (KpiCard, SectionCard) — při najetí myší se nic neděje, žádný lift/shadow
- Tabulkové řádky — hover zvýrazní řádek okamžitě bez transition
- Sidebar položky — background se přepne skokem

**Řešení v PyQt6:** Použít `enterEvent` / `leaveEvent` + `QPropertyAnimation` na widgetech, které potřebují smooth přechod. Konkrétně:
- **KpiCard:** Animovat `QGraphicsDropShadowEffect.blurRadius` z 4 → 8 při hover (150ms, `OutCubic`)
- **SectionCard:** Stejný shadow lift pattern
- **Sidebar položky:** Animovat background opacity přes custom `QPropertyAnimation` na paletě
- **Tlačítka:** `pressed` stav s animovaným `scale(0.97)` přes `QGraphicsScale` nebo repainting s transformací

**Priorita:** VYSOKÁ — toto je rozdíl mezi „aplikace z roku 2010" a „moderní software".

#### 7.2.2 Hardcoded hex hodnoty mimo token systém

`table_widget.py` obsahuje 5 hardcoded hex hodnot, které obchází celý token systém:

| Hardcoded | Kde | Mělo by být |
|-----------|-----|-------------|
| `#F8FAFC` | zebra stripe, header bg | `Colors.GRAY_50` |
| `#F1F5F9` | item border-bottom | `Colors.GRAY_100` |
| `#EFF6FF` | selected bg | `Colors.BRAND_SUBTLE` |
| `#1E40AF` | selected text | `Colors.PRIMARY_700` |
| `#64748B` | header text | `Colors.GRAY_600` |

Stejný problém v `kpi_card.py` — accent varianta má `"2px solid #BBF7D0"` hardcoded místo tokenu. V `dashboard.py` je `"border: 1px solid {Colors.SUCCESS_500}"` (ok) vedle `Colors.SUCCESS_50` (ok), ale dořeším empty state mixuje inline styly s token systémem nekonzistentně.

**Řešení:** Všechny hex hodnoty v UI souborech nahradit referencemi na `Colors.*`. Případně přidat chybějící tokeny (`Colors.GRAY_25 = "#F8FAFC"`, `Colors.SUCCESS_200 = "#BBF7D0"`).

**Priorita:** STŘEDNÍ — nerozbije to nic, ale komplikuje budoucí theming a případný dark mode.

#### 7.2.3 Emoji v produkčním UI

Dashboard používá emoji jako ikony:
- `"📥 Import výpisu"` — tlačítko s emoji
- `"✅  Nic k dořešení — všechno máš v pořádku 🎉"` — empty state s emoji
- `"＋ Vydaná faktura"` — fullwidth plus sign (ne emoji, ale nekonzistentní s `Icons.PLUS = "+"`)

Emoji mají **nespolehlivý rendering** — jinak vypadají na macOS, Windows, Linux. Na Windows mohou být černobílé nebo mít jinou velikost. Na starších systémech se zobrazí jako prázdný čtverec.

**Řešení:** Nahradit všechny emoji za unicode znaky z `Icons` třídy, nebo je úplně odstranit. Empty state text přeformulovat bez emoji:
```python
# Místo:
"✅  Nic k dořešení — všechno máš v pořádku 🎉"
# Použít:
f"{Icons.CHECK}  Nic k dořešení — všechno je v pořádku"
# Nebo ještě lépe — jen text, ikona je součástí EmptyState widgetu
```

**Priorita:** STŘEDNÍ — na macOS to vypadá ok, ale cross-platform je to problém.

#### 7.2.4 Duplikované button styly

Tlačítka jsou stylovaná **třemi různými způsoby** současně:

1. **Globální QSS** v `global_stylesheet()` — `QPushButton[variant="primary"]`, `QPushButton[primary="true"]` atd.
2. **Helper funkce** — `make_primary_button()`, `make_secondary_button()` atd. s inline `setStyleSheet()`
3. **Inline styly v UI souborech** — `btn.setStyleSheet(f"QPushButton {{ background: ...")` přímo v doklady_ui, partneri_ui atd.

Problém: inline `setStyleSheet()` přebíjí globální QSS. Pokud někdo změní barvu v `Colors.BRAND`, tlačítka vytvořená přes `make_primary_button()` se aktualizují, ale ty s inline stylem ne. A naopak — globální QSS pravidla se neaplikují na widgety s inline stylesheet.

**Řešení:**
- Sjednotit na **jeden přístup**: buď globální QSS s atributy (`setProperty("variant", "primary")`) **nebo** helper funkce s inline styly — ne obojí
- Doporučení: ponechat helper funkce (jsou explicitnější a čitelnější), ale odebrat duplicitní globální QSS pravidla pro button varianty
- Všechny inline styly v UI souborech (`doklady_ui.py:87-92` atd.) nahradit voláním helper funkcí

**Priorita:** STŘEDNÍ — funguje to, ale údržba je fragile.

#### 7.2.5 Chybějící pressed/disabled stavy

Některé tlačítkové varianty nemají vizuálně odlišený pressed stav:
- `make_secondary_button()` — nemá `:pressed` (jen `:hover`)
- `make_ghost_button()` — nemá `:pressed`
- `make_help_button()` — nemá `:pressed`

Disabled stav v globálním QSS používá `opacity: 0.5` — Qt6 podporuje opacity v QSS jen omezeně (ne na všech platformách). Bezpečnější je explicitně nastavit `background-color` a `color` pro disabled.

**Řešení:** Doplnit `:pressed` a `:disabled` do všech button variant:
```python
# make_secondary_button — přidat:
QPushButton:pressed {{ background-color: {Colors.BRAND_SUBTLE}; border-color: {Colors.PRIMARY_700}; }}
QPushButton:disabled {{ background-color: {Colors.GRAY_100}; color: {Colors.GRAY_400}; border-color: {Colors.GRAY_300}; }}
```

**Priorita:** NÍZKÁ — UX problém jen v edge cases.

#### 7.2.6 Focus ring není dostatečně viditelný

Aktuální focus stav inputů (`QLineEdit:focus`) je jen `border-color: {Colors.BORDER_FOCUS}` — jemná změna barvy borderu z `#E5E7EB` na `#0F766E`. Pro uživatele s klávesovou navigací je to málo viditelné.

Třída `Shadows` definuje `FOCUS_COLOR = "rgba(15, 118, 110, 0.2)"` a `FOCUS_SPREAD = 3`, ale tyto hodnoty **nikde nejsou použité** — žádný widget nemá focus ring implementovaný.

**Řešení:**
- Přidat focus ring přes `QGraphicsDropShadowEffect` v `enterEvent` / `focusInEvent` inputů
- Nebo přidat do QSS: `QLineEdit:focus { border: 2px solid {Colors.BORDER_FOCUS}; padding: 7px 11px; }` (kompenzovat 1px navíc v paddingu)
- Tlačítka: přidat `QPushButton:focus { outline: 2px solid rgba(15, 118, 110, 0.3); outline-offset: 2px; }` (Qt6 QSS `outline` je experimentální, alternativa je border s kompenzací)

**Priorita:** STŘEDNÍ — přístupnost (accessibility, WCAG 2.4.7 focus visible).

#### 7.2.7 Tabulky nemají hover feedback na řádcích

`DataTable` nastavuje `QTableWidget::item:hover { background-color: {Colors.GRAY_50}; }` v globálním QSS, ale inline stylesheet v `table_widget.py` ho přebíjí a **nedefinuje** vlastní `:hover` na `::item`. Výsledek: řádky tabulky nereagují na najetí myší.

**Řešení:** Přidat do inline stylesheet v `DataTable._setup_table()`:
```css
QTableWidget::item:hover {
    background-color: #F0FDFA;  /* Colors.BRAND_SUBTLE */
}
```

**Priorita:** VYSOKÁ — tabulky jsou hlavní interakční prvek celé aplikace.

#### 7.2.8 Nekonzistentní border-radius

Token systém definuje `Radius.SM=4, MD=6, LG=8, XL=12, XXL=16`, ale v praxi:
- `table_widget.py` hardcodes `border-radius: 6px` (= `Radius.MD`, ale psáno přímo)
- `SectionCard` používá `Radius.XL` (12px)
- `KpiCard` používá `Radius.XL` (12px)
- `QDialog` v globálním QSS má `Radius.XL` (12px)
- Filtrovací chipy mají `border-radius: 16px` (= `Radius.XXL`, ale psáno přímo)
- `QTabWidget::pane` má `Radius.LG` (8px)

**Řešení:** Stanovit jasná pravidla:
- Karty, dialogy, velké kontejnery: `Radius.XL` (12px)
- Inputy, tlačítka, menší prvky: `Radius.MD` (6px)
- Chipy, badge, pills: `Radius.FULL` (9999px)
- Všechny inline `border-radius: Npx` nahradit tokenem

**Priorita:** NÍZKÁ — vizuálně to neruší, ale nekonzistence komplikuje údržbu.

---

### 7.3 Návrhy vylepšení — moderní účetní program

#### 7.3.1 Micro-interakce: hover lift na kartách

Každá `KpiCard` a `SectionCard` by měla při najetí myší dostat **subtle shadow lift** — přechod z `Shadows.SM` (blur 4, offset 1) na `Shadows.MD` (blur 8, offset 2) během 150ms.

**Implementace:**
```python
class KpiCard(QFrame):
    def enterEvent(self, event):
        apply_card_shadow(self, "md")  # blur 8, offset 2, alpha 20
        super().enterEvent(event)

    def leaveEvent(self, event):
        apply_card_shadow(self, "sm")  # blur 4, offset 1, alpha 13
        super().leaveEvent(event)
```

Pro plynulejší efekt použít `QPropertyAnimation` na `blurRadius` property shadow effectu:
```python
def _animate_shadow(self, target_blur: int, target_offset: int, duration: int = 150):
    effect = self.graphicsEffect()
    if not isinstance(effect, QGraphicsDropShadowEffect):
        return
    anim = QPropertyAnimation(effect, b"blurRadius", self)
    anim.setDuration(duration)
    anim.setStartValue(effect.blurRadius())
    anim.setEndValue(target_blur)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
```

#### 7.3.2 Micro-interakce: pressed scale na tlačítkách

Při kliknutí na tlačítko přidat jemný scale-down efekt (0.97×) — dává taktilní feedback.

**Implementace přes QSS (omezené):**
Qt6 QSS nepodporuje `transform: scale()`. Alternativa:
```python
class AnimatedButton(QPushButton):
    def mousePressEvent(self, event):
        # Vizuální pressed efekt — zmenšit padding o 1px
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
```

Realističtější řešení: vytvořit `AnimatedButton` subclass s `QPropertyAnimation` na `geometry` (1px shrink) nebo na custom `_scale` property s `paintEvent` override. Doporučení: začít jen s shadow lift na kartách, scale na tlačítkách je nice-to-have.

#### 7.3.3 Tabulkové řádky: hover highlight + kurzor

Přidat jemný teal hover na řádky tabulky a `cursor: pointer` při klikatelných řádcích:

```css
QTableWidget::item:hover {
    background-color: rgba(240, 253, 250, 0.8);  /* BRAND_SUBTLE at 80% */
}
```

U tabulek s klikatelným detail (doklady, partneři) nastavit `setCursor(PointingHandCursor)`.

#### 7.3.4 Dashboard: vylepšení KPI stripu

Aktuální KPI strip (3 karty v řadě) je funkční, ale flat. Vylepšení:

1. **Barevné accent pruhy** — každá KPI karta by měla mít 3px horní border v unikátní barvě:
   - Banka: `Colors.PRIMARY_500` (#059669)
   - Pokladna: `Colors.INFO_500` (#0EA5E9)
   - DPPO: `Colors.ACCENT_500` (#B47D04)
   ```css
   #kpiCard { border-top: 3px solid {accent_color}; }
   ```

2. **Ikona vedle titulku** — přidat malou ikonu (z `Icons` třídy) vlevo od label textu:
   - Banka: `Icons.BANKA` (⎕)
   - Pokladna: `Icons.DOKLADY` (☷)
   - DPPO: `Icons.VYKAZY` (▤)

3. **Trend indikátor** — pod hodnotou přidat řádek s porovnáním oproti minulému měsíci:
   - `↑ 12 300 Kč` (zelená) nebo `↓ 5 200 Kč` (červená)
   - Mechanismus: porovnat aktuální zůstatek s hodnotou k poslednímu dni předchozího měsíce

#### 7.3.5 Dashboard: lepší vizuální hierarchie zón

Aktuální „JAK SI STOJÍME" / „CO MUSÍM UDĚLAT" zone labels jsou teal uppercase text. Vylepšení:

```python
# Místo pouhého textu — tenký horizontální separátor s labelem:
# ─────── JAK SI STOJÍME ───────
zone_label.setStyleSheet(f"""
    color: {Colors.BRAND};
    font-size: {Typography.SIZE_XS}px;
    font-weight: 700;
    letter-spacing: 1.5px;
    padding: {Spacing.S4}px 0;
    border-top: 1px solid {Colors.GRAY_200};
    margin-top: {Spacing.S4}px;
""")
```

#### 7.3.6 Sidebar: subtle gradient místo flat barvy

Aktuální sidebar je flat `#134E4A`. Jemnější varianta:

```python
# Vertikální gradient — tmavší nahoře, o stupeň světlejší dole
background: qlineargradient(y1:0, y2:1,
    stop:0 #0F3D38,    /* o stupeň tmavší než SIDEBAR */
    stop:1 #164E4A);   /* SIDEBAR */
```

Alternativa: přidat jemný noise/texture overlay přes `QPixmap` — 2% opacity pattern pro „living surface" efekt. Ale to je nice-to-have.

#### 7.3.7 TopBar: search bar s lepším focus stavem

Aktuální search trigger (`QPushButton` stylovaný jako input) má jen hover (`border-color: GRAY_300`). Vylepšení:

1. **Větší ikonka hledání** — zvětšit z 14px na 16px
2. **Placeholder text jemněji** — opacity 0.5 místo plné `GRAY_500`
3. **Focus/hover ring** — přidat jemný box-shadow efekt (simulovaný přes `QGraphicsDropShadowEffect`)
4. **Šířka** — zvážit dynamickou šířku (min 280px → max 400px), aby se search bar přizpůsobil obsahu

#### 7.3.8 Dialogy: overlay/backdrop

`BaseDialog` se otevírá jako modální dialog, ale nemá backdrop (tmavý overlay za dialogem). V Qt6 se to řeší:

```python
# V BaseDialog.__init__:
self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

# Přidat custom paintEvent pro backdrop:
# — nebo jednodušeji: parent window setStyleSheet("opacity: 0.5") při otevření
```

Hodnota overlaye z tokenů: `Glass.OVERLAY_BG = "rgba(10, 15, 13, 0.50)"` — token existuje, ale nikde se nepoužívá.

#### 7.3.9 Empty states: ilustrace místo unicode

Aktuální `EmptyState` widget používá 48px unicode znaky (`□`, `☰`, `▦`, `○`, `▢`) jako ikony. Na většině systémů to vypadá jako generický font glyph — ne jako záměrný design prvek.

**Řešení (od jednoduchého po ideální):**
1. **Minimální:** Zvětšit ikonu na 64px, nastavit barvu na `Colors.GRAY_200` (místo `GRAY_300`), přidat kruhový background:
   ```css
   font-size: 48px; color: {Colors.GRAY_300};
   background: {Colors.GRAY_100}; border-radius: 50%;
   width: 80px; height: 80px; /* centrovaný kruh */
   ```
2. **Lepší:** Nahradit unicode za SVG ikony — Qt6 podporuje `QSvgWidget` a `QIcon` ze SVG
3. **Ideální:** Jemné ilustrace (SVG) ve stylu produktu — teal linie, minimalistické

#### 7.3.10 Cashflow chart: zaoblené sloupce

`QBarSet` v Qt6 nemá nativní `border-radius`, ale je možné přepsat `QBarSeries` na custom `QAbstractBarSeries` s rounded rect rendering. Alternativa: použít `QPainterPath` s `addRoundedRect` v custom chart widgetu.

Doporučení: nechat to jako je — standardní Qt chart vypadá profesionálně. Pokud by se měnilo, pak celý chart přepsat na custom `paintEvent` widget, kde se bude kreslit přímo do QPainter — to dá plnou kontrolu nad zaoblením, gradienty, animacemi.

#### 7.3.11 Formuláře: floating labels

Aktuální `FormCard` má label nad inputem (standardní pattern). Moderní varianta: **floating label** — label začíná jako placeholder uvnitř inputu a při focus/vyplnění se animuje nahoru a zmenší se.

**Implementace:**
```python
class FloatingInput(QWidget):
    """Input s animovaným floating labelem."""
    def __init__(self, label_text: str):
        self._label = QLabel(label_text)
        self._input = QLineEdit()
        # QPropertyAnimation na label position (y: 12 → -8) a font-size (15 → 11)
        # Trigger: focusInEvent / focusOutEvent + text change
```

Doporučení: implementovat jako volitelný mód `FormCard.add_field(floating=True)`, ne jako výchozí — klasické labely jsou pro účetní software srozumitelnější.

#### 7.3.12 Barevná přístupnost (WCAG)

Kontrola kontrastních poměrů klíčových párů:

| Pár | Barva textu | Pozadí | Poměr | WCAG AA (4.5:1) |
|-----|-------------|--------|-------|-----------------|
| Body text | `GRAY_900` #111827 | `PAGE` #F8FAFB | ~16:1 | PASS |
| Subtitle | `GRAY_500` #6B7280 | `PAGE` #F8FAFB | ~5.5:1 | PASS |
| Sidebar text | rgba(255,255,255,0.82) | `SIDEBAR` #134E4A | ~8:1 | PASS |
| Sidebar inactive sub | rgba(255,255,255,0.75) | `SIDEBAR` #134E4A | ~7:1 | PASS |
| KPI title | `GRAY_500` #6B7280 | `KPI_BG` rgba(255,255,255,0.82) | ~4.5:1 | BORDERLINE |
| Header text v tabulce | `GRAY_600` #4B5563 | `GRAY_50` #F9FAFB | ~7:1 | PASS |
| Badge aktivni text | `PRIMARY_700` #065F46 | `BRAND_SUBTLE` #F0FDFA | ~8:1 | PASS |
| Disabled text | `GRAY_400` #9CA3AF | `WHITE` #FFFFFF | ~2.7:1 | FAIL |

**Problém:** Disabled stav (`GRAY_400` na bílé) nesplňuje WCAG AA. Řešení: použít `GRAY_500` (#6B7280) pro disabled text — stále vypadá „utlumeně", ale je čitelný.

#### 7.3.13 Spacing konzistence

Token systém definuje spacing scale na 4px grid (4, 8, 12, 16, 20, 24, 32, 40, 48). Většina UI ho respektuje, ale:

- `SidebarSubItem` má padding `6px 12px 6px 44px` — 6px a 44px nejsou na gridu (mělo by být 8px a 44→48px)
- `SidebarDirectLink` má padding `8px 12px` — ok (S2, S3)
- `chevron.move(btn_w - 28, 12)` — magic numbers 28 a 12
- `QFormLayout.setSpacing(Spacing.S3)` v `doklady_ui.py` — ok

**Řešení:** Audit všech padding/margin hodnot v sidebar a doklady — nahradit magic numbers za `Spacing.*` tokeny nebo alespoň za 4px-aligned hodnoty.

---

### 7.4 Shrnutí priorit

| # | Problém | Priorita | Obtížnost | Dopad |
|---|---------|----------|-----------|-------|
| 1 | Micro-interakce (shadow lift na kartách) | VYSOKÁ | Nízká | Okamžitý moderní pocit |
| 2 | Hover highlight na řádcích tabulky | VYSOKÁ | Minimální | Lepší orientace v datech |
| 3 | Hardcoded hex → tokeny | STŘEDNÍ | Nízká | Udržitelnost, budoucí theming |
| 4 | Emoji → unicode/SVG | STŘEDNÍ | Nízká | Cross-platform konzistence |
| 5 | Focus ring implementace | STŘEDNÍ | Nízká | Přístupnost (a11y) |
| 6 | Duplikované button styly sjednotit | STŘEDNÍ | Střední | Údržba, konzistence |
| 7 | KPI accent pruhy + ikony | NÍZKÁ | Nízká | Vizuální identita |
| 8 | Pressed/disabled stavy doplnit | NÍZKÁ | Minimální | Kompletnost interakcí |
| 9 | Empty state ikony v kruhovém bg | NÍZKÁ | Nízká | Lepší vizuální kvalita |
| 10 | Dashboard zón separátory | NÍZKÁ | Minimální | Čitelnější hierarchie |
| 11 | Dialog backdrop overlay | NÍZKÁ | Střední | Modernější modály |
| 12 | Floating labels (volitelné) | NÍZKÁ | Vysoká | Nice-to-have, ne nutnost |
| 13 | Cashflow chart zaoblení | NÍZKÁ | Vysoká | Kosmetický detail |

**Doporučený postup:** Začít body 1–5 (high impact, low effort), pak 6–10. Body 11–13 jsou nice-to-have a nemají business hodnotu.

---

### 7.5 Design pravidla pro budoucí vývoj

1. **Žádné hardcoded hex v UI souborech** — vždy `Colors.*`, případně rozšířit token paletu
2. **Žádné emoji** — pouze `Icons.*` nebo SVG
3. **Každý interaktivní prvek musí mít 4 stavy:** default, hover, pressed/active, disabled
4. **Každá karta musí mít hover lift** — `enterEvent` / `leaveEvent` s shadow animací
5. **Focus ring na všech focusable prvcích** — min. `border: 2px solid BORDER_FOCUS`
6. **Padding/margin na 4px gridu** — žádné magic numbers
7. **Jeden button styling přístup** — helper funkce NEBO globální QSS, ne obojí
8. **Nové komponenty** dědit z existujících base tříd (`SectionCard`, `BaseDialog`, `FormCard`) místo psaní od nuly
9. **Barevné páry testovat na WCAG AA** (4.5:1 minimum pro text)
10. **Animace:** 150ms pro micro (hover, press), 200ms pro medium (expand/collapse), 300ms pro large (page transition). Vždy `OutCubic` nebo `InOutQuad`.

---

## 8. Doporučená architektura pro rewrite

> Tato sekce odpovídá na otázku: „Kdybych začínal znovu od nuly se vším co dnes vím,
> jak bych systém navrhla?" Pokrývá stack, strukturu složek, klíčové vzory,
> orchestraci AI agentů a rozdělení práce do fází.

---

### 8.1 Rozhodnutí o stacku

#### 8.1.1 Proč zůstat u Pythonu

Python je správná volba pro tento projekt. Důvody:
- **Doménová logika** — účetní výpočty, DPH, odpisy, mzdy — je v Pythonu čitelná a testovatelná
- **Decimal** — nativní podpora přesné aritmetiky, žádné floating-point problémy
- **Ekosystém** — ARES klient, OCR (pyobjc Vision, Tesseract), CSV parsing, XML generování
- **AI agenti** — Claude Code, LangChain, vlastní agenti — vše v Pythonu
- **Jeden jazyk** pro celý stack = jednodušší údržba pro malý tým

#### 8.1.2 UI framework: z PyQt6 na PySide6 + QML

| Aspekt | PyQt6 (současný) | PySide6 + QML (doporučený) |
|--------|-------------------|---------------------------|
| Licence | GPL / komerční | LGPL (volně použitelné i komerčně) |
| Animace | QPropertyAnimation (imperative) | QML Behavior, Transition (deklarativní) |
| Styling | QSS (omezený CSS subset, žádné transitions) | QML properties + States + Transitions |
| Hot reload | Ne | Ano (QML soubory se načítají za běhu) |
| Micro-interakce | Nutné subclassovat widget + enterEvent | `Behavior on scale { ... }` — 1 řádek |
| Dark mode | Ruční přepínání celého QSS | Material/Universal style s vestavěným dark mode |
| Responsivita | Ruční breakpointy | QML Layout adaptéry |
| Složitost | ~13 000 řádků Python UI kódu | Odhadem ~4 000 řádků QML + ~3 000 Python backend |

**Klíčový důvod:** Všechny problémy ze sekce 7 (nulové micro-interakce, chybějící transitions, hardcoded styly) jsou **strukturální limitace QSS**. V QML se řeší deklarativně:

```qml
// KPI karta s hover lift — v QML je to 8 řádků
Rectangle {
    radius: 12
    color: "#FFFFFF"
    border.color: "#E5E7EB"

    scale: hovered ? 1.02 : 1.0
    Behavior on scale { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }

    layer.enabled: true
    layer.effect: DropShadow {
        radius: hovered ? 8 : 4
        Behavior on radius { NumberAnimation { duration: 150 } }
    }
}
```

**Alternativa pokud QML ne:** Zůstat u PyQt6/PySide6 Widgets, ale vytvořit vlastní `AnimatedWidget` base class s `enterEvent`/`leaveEvent` + `QPropertyAnimation`. Funguje, ale každou animaci musíte napsat imperativně.

**Alternativa web stack:** Electron/Tauri + React/Vue by dal nejlepší animace, ale přidává JavaScript, build pipeline, a Chromium dependency (~150 MB). Pro desktop účetní program pro jednoho uživatele je to overkill.

#### 8.1.3 Databáze: zůstat u SQLite, opravit typy

SQLite je pro single-user desktop účetní program **správná volba**:
- Nulová konfigurace, žádný server
- Backup = kopie jednoho souboru
- WAL mód pro bezpečný concurrent read/write
- Online Backup API (už implementované)

**Co opravit:**
```sql
-- PŘED (současný stav):
castka TEXT NOT NULL DEFAULT '0'    -- Decimal as TEXT, CAST(castka AS REAL) v dotazech

-- PO (rewrite):
castka_hal INTEGER NOT NULL DEFAULT 0   -- Částka v haléřích (12345 = 123,45 Kč)
```

**Proč INTEGER v haléřích (minor units):**
- SQLite nativně sčítá, porovnává, indexuje INTEGER
- Žádné `CAST(... AS REAL)` — přesnost zaručena
- `SUM(castka_hal)` funguje přímo, bez konverze
- Python Decimal konverze: `Decimal(row["castka_hal"]) / 100`
- Standardní praxe v bankovních systémech a platebních bránách (Stripe, banky)

**Migrace z TEXT → INTEGER:**
```sql
ALTER TABLE doklady ADD COLUMN castka_hal INTEGER;
UPDATE doklady SET castka_hal = CAST(ROUND(CAST(castka AS REAL) * 100) AS INTEGER);
-- Po ověření:
-- ALTER TABLE doklady DROP COLUMN castka;  -- SQLite 3.35+
```

#### 8.1.4 Testování

| Vrstva | Framework | Co testuje |
|--------|-----------|------------|
| Domain logika | `pytest` | Value objects, entity pravidla, domain services |
| Repository / DB | `pytest` + in-memory SQLite | CRUD, dotazy, migrace |
| Use cases | `pytest` + mocky | Orchestrace, validace, business pravidla |
| UI | `pytest-qt` nebo QML `TestCase` | Widgety, signály, navigace |
| E2E | Playwright (po exportu do webu) nebo `pytest-qt` | Celé workflow |
| Legislativa | `pytest` parametrizované | DPH výpočty, odpisy, mzdy — tabulkové testy |

---

### 8.2 Struktura složek

```
UcetniProgram/
│
├── main.py                          # Entry point — inicializace, DI container, spuštění UI
├── config.py                        # Cesty, konstanty, daňové sazby
├── container.py                     # Dependency injection — mapování interface → implementace
│
├── domain/                          # ═══ JÁDRO — čistá doménová logika, ŽÁDNÉ importy z infra/ui ═══
│   │
│   ├── shared/                      # Sdílené doménové primitiva
│   │   ├── money.py                 # Value Object: Money(castka_hal: int, mena: str)
│   │   ├── obdobi.py                # Value Object: UcetniObdobi(rok, stav)
│   │   ├── ucet.py                  # Value Object: CisloUctu("221.100") s validací
│   │   ├── events.py                # Domain Events: DokladVytvoren, UhradaProvedena, ...
│   │   └── errors.py                # Doménové výjimky (UcetniError, PodvojnostError, ...)
│   │
│   ├── ucetnictvi/                  # Bounded Context: Účetní deník + osnova
│   │   ├── entities.py              # UcetniZaznam, Ucet
│   │   ├── predvaha.py              # Obratová předvaha, hlavní kniha
│   │   ├── podvojnost.py            # Validace MD = Dal (fungující, ne noop)
│   │   └── repository.py            # Interface: UcetniDenikRepository (abstract)
│   │
│   ├── doklady/                     # Bounded Context: Doklady
│   │   ├── entities.py              # Doklad, Priloha, StavDokladu enum
│   │   ├── ciselne_rady.py          # Generování čísel dokladů
│   │   ├── predkontace.py           # Pravidla předkontací (z accounting_engine)
│   │   ├── zalohovy_cyklus.py       # ZF → BV → DZ → KF workflow
│   │   └── repository.py            # Interface: DokladyRepository (abstract)
│   │
│   ├── finance/                     # Bounded Context: Peníze, banka, pokladna
│   │   ├── entities.py              # BankovniUcet, Pokladna, BankovniPohyb
│   │   ├── parovani.py              # Auto/ruční párování bank ↔ faktury
│   │   ├── import_parser.py         # BankImportParser (Fio, KB, ČS, Moneta)
│   │   └── repository.py            # Interface: FinanceRepository (abstract)
│   │
│   ├── partneri/                    # Bounded Context: Partneři
│   │   ├── entities.py              # Partner, TypPartnera enum
│   │   ├── matching.py              # Fuzzy matching (Levenshtein)
│   │   └── repository.py            # Interface: PartneriRepository (abstract)
│   │
│   ├── dan/                         # Bounded Context: Daně (DPH, DPPO)
│   │   ├── dph.py                   # DPH výpočty, přiznání, kontrolní hlášení
│   │   ├── dppo.py                  # DPPO výpočet
│   │   └── repository.py            # Interface: DanRepository (abstract)
│   │
│   ├── majetek/                     # Bounded Context: Dlouhodobý majetek + odpisy
│   │   ├── entities.py              # Majetek, OdpisovaSkupina, InventarniKarta
│   │   ├── odpisy.py                # Výpočet odpisů (rovnoměrný/zrychlený)
│   │   └── repository.py            # Interface: MajetekRepository (abstract)
│   │
│   ├── mzdy/                        # Bounded Context: Mzdy
│   │   ├── entities.py              # MzdovyList, TypUvazku enum
│   │   ├── vypocet.py               # Výpočet čisté mzdy, odvodů
│   │   └── repository.py            # Interface: MzdyRepository (abstract)
│   │
│   └── vykazy/                      # Bounded Context: Výkazy
│       ├── rozvaha.py               # Rozvaha dle vyhlášky 500/2002
│       ├── vzz.py                   # Výkaz zisku a ztráty
│       └── saldokonto.py            # Saldokonto s aging reportem
│
├── application/                     # ═══ USE CASES — orchestrace doménové logiky ═══
│   │
│   ├── commands/                    # Command handlers (write operace)
│   │   ├── vytvor_doklad.py         # VytvorDokladCommand + handler
│   │   ├── zauctuj_doklad.py        # ZauctujDokladCommand + handler
│   │   ├── proved_uhradu.py         # ProvedUhraduCommand + handler
│   │   ├── importuj_vypis.py        # ImportujVypisCommand + handler
│   │   ├── zpracuj_ocr.py           # ZpracujOcrCommand + handler
│   │   └── ...
│   │
│   ├── queries/                     # Query handlers (read operace)
│   │   ├── dashboard_data.py        # DashboardQuery → KPI, saldokonto, dořeším
│   │   ├── predvaha.py              # PredvahaQuery → obratová předvaha
│   │   ├── hlavni_kniha.py          # HlavniKnihaQuery → pohyby účtu
│   │   ├── aging_report.py          # AgingReportQuery → stáří pohledávek
│   │   └── ...
│   │
│   └── services/                    # Aplikační služby (cross-cutting)
│       ├── accounting_engine.py     # Orchestrace předkontací + confidence scoring
│       ├── zaverka_service.py       # Závěrkový workflow (checklist, kontroly, uzavření)
│       ├── export_service.py        # PDF/XML/CSV export
│       └── backup_service.py        # Záloha + restore
│
├── infrastructure/                  # ═══ IMPLEMENTACE — DB, OCR, ARES, filesystem ═══
│   │
│   ├── database/
│   │   ├── connection.py            # SQLite connection factory (NE singleton)
│   │   ├── unit_of_work.py          # UnitOfWork — jedna transakce pro celý use case
│   │   ├── migrations/
│   │   │   ├── runner.py            # MigrationManager
│   │   │   ├── 001_initial.sql
│   │   │   ├── 002_xxx.sql
│   │   │   └── ...
│   │   └── repositories/            # Konkrétní SQLite implementace repository interfaces
│   │       ├── doklady_repo.py      # SqliteDokladyRepository implements DokladyRepository
│   │       ├── ucetni_denik_repo.py
│   │       ├── finance_repo.py
│   │       ├── partneri_repo.py
│   │       ├── majetek_repo.py
│   │       ├── mzdy_repo.py
│   │       └── dan_repo.py
│   │
│   ├── ocr/
│   │   ├── engine.py                # OCR abstrakce (Vision / Tesseract / budoucí API)
│   │   ├── apple_vision.py          # macOS Vision implementace
│   │   ├── tesseract.py             # Tesseract fallback
│   │   └── preprocessing.py         # Předzpracování obrazu
│   │
│   ├── ares/
│   │   ├── client.py                # ARES HTTP klient
│   │   └── mapper.py                # ARES response → Partner entity
│   │
│   └── export/
│       ├── pdf_generator.py         # PDF faktury, výkazy
│       ├── xml_generator.py         # DPH přiznání EPO XML
│       └── templates/               # Šablony
│
├── ui/                              # ═══ PREZENTAČNÍ VRSTVA ═══
│   │
│   ├── qml/                         # QML soubory (pokud PySide6 + QML)
│   │   ├── main.qml
│   │   ├── theme/
│   │   │   ├── Theme.qml            # Centrální design tokeny
│   │   │   ├── Colors.qml
│   │   │   └── Typography.qml
│   │   ├── components/
│   │   │   ├── KpiCard.qml
│   │   │   ├── SectionCard.qml
│   │   │   ├── DataTable.qml
│   │   │   ├── AnimatedButton.qml
│   │   │   └── ...
│   │   └── pages/
│   │       ├── Dashboard.qml
│   │       ├── Doklady.qml
│   │       ├── Partneri.qml
│   │       └── ...
│   │
│   ├── widgets/                     # Pokud PyQt6 Widgets (alternativa)
│   │   ├── design_tokens.py
│   │   ├── components/
│   │   └── pages/
│   │
│   └── viewmodels/                  # ViewModel vrstva — bridge mezi UI a application
│       ├── dashboard_vm.py          # DashboardViewModel — data pro dashboard
│       ├── doklady_vm.py            # DokladyViewModel — CRUD, filtry, stránkování
│       ├── partneri_vm.py
│       └── ...
│
├── agents/                          # ═══ AI AGENTI ═══
│   ├── ocr_agent.py                 # OCR zpracování + extrakce dat z dokladů
│   ├── predkontace_agent.py         # AI návrhy předkontací
│   ├── validation_agent.py          # Kontrola konzistence dat
│   ├── chatbot_agent.py             # Účetní chatbot (plánovaná funkce 6.19)
│   └── preprocessing.py             # Sdílené předzpracování
│
├── tests/
│   ├── unit/
│   │   ├── domain/                  # Testy doménové logiky (bez DB)
│   │   │   ├── test_money.py
│   │   │   ├── test_podvojnost.py
│   │   │   ├── test_odpisy.py
│   │   │   ├── test_mzdy.py
│   │   │   └── test_dph.py
│   │   └── application/             # Testy use cases (s mocky)
│   │       ├── test_vytvor_doklad.py
│   │       └── test_zauctuj.py
│   ├── integration/                 # Testy s reálnou DB
│   │   ├── test_doklady_repo.py
│   │   ├── test_migrace.py
│   │   └── test_parovani.py
│   ├── legislative/                 # Tabulkové testy legislativních výpočtů
│   │   ├── test_dph_sazby.py
│   │   ├── test_odpisy_skupiny.py
│   │   └── test_mzdy_2026.py
│   └── fixtures/
│       ├── sample_invoices/
│       └── bank_csv/
│
└── data/                            # Statická data
    ├── uctova_osnova.json           # Výchozí účtový rozvrh
    └── predkontace_rules.json       # Pravidla předkontací
```

---

### 8.3 Klíčové architektonické vzory

#### 8.3.1 Money Value Object — konec TEXT částek

Nejkritičtější změna celého rewrite. Jeden objekt, který **zaručuje přesnost**:

```python
# domain/shared/money.py
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

@dataclass(frozen=True)
class Money:
    """Immutable value object pro peněžní částky.

    Interně ukládá haléře (int) pro bezeztrátové SQL operace.
    """
    _halere: int
    mena: str = "CZK"

    @classmethod
    def koruny(cls, castka: Decimal | str | int | float, mena: str = "CZK") -> Money:
        """Vytvoří Money z částky v korunách: Money.koruny("1234.50")"""
        d = Decimal(str(castka)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return cls(_halere=int(d * 100), mena=mena)

    @classmethod
    def halere(cls, hal: int, mena: str = "CZK") -> Money:
        """Vytvoří Money z haléřů (pro načtení z DB): Money.halere(123450)"""
        return cls(_halere=hal, mena=mena)

    @property
    def castka(self) -> Decimal:
        """Vrátí částku jako Decimal: Decimal('1234.50')"""
        return Decimal(self._halere) / Decimal(100)

    @property
    def halere_int(self) -> int:
        """Pro uložení do DB: 123450"""
        return self._halere

    def __add__(self, other: Money) -> Money:
        assert self.mena == other.mena, f"Nelze sčítat {self.mena} + {other.mena}"
        return Money(self._halere + other._halere, self.mena)

    def __sub__(self, other: Money) -> Money:
        assert self.mena == other.mena
        return Money(self._halere - other._halere, self.mena)

    def __neg__(self) -> Money:
        return Money(-self._halere, self.mena)

    def __abs__(self) -> Money:
        return Money(abs(self._halere), self.mena)

    def __gt__(self, other): return self._halere > (other._halere if isinstance(other, Money) else 0)
    def __lt__(self, other): return self._halere < (other._halere if isinstance(other, Money) else 0)
    def __ge__(self, other): return self._halere >= (other._halere if isinstance(other, Money) else 0)
    def __eq__(self, other): return isinstance(other, Money) and self._halere == other._halere and self.mena == other.mena

    def __bool__(self) -> bool:
        return self._halere != 0

    def format_cz(self) -> str:
        """'1 234,50 Kč'"""
        sign = "-" if self._halere < 0 else ""
        abs_hal = abs(self._halere)
        cela = abs_hal // 100
        des = abs_hal % 100
        cela_str = f"{cela:,}".replace(",", "\u00A0")
        symbol = {"CZK": "Kč", "EUR": "€", "USD": "$"}.get(self.mena, self.mena)
        return f"{sign}{cela_str},{des:02d} {symbol}"

    ZERO_CZK: ClassVar[Money]  # definováno pod třídou

Money.ZERO_CZK = Money(0, "CZK")
```

**Dopad na zbytek systému:**
- DB sloupce: `castka_hal INTEGER NOT NULL DEFAULT 0`
- SQL dotazy: `SUM(castka_hal)` místo `SUM(CAST(castka AS REAL))`
- Python: `Money.halere(row["castka_hal"])` místo `Decimal(str(row["castka"]))`
- UI: `kpi.set_value(money.format_cz())` — beze změny

#### 8.3.2 Repository pattern — konec SQL v UI

Abstraktní interface v `domain/*/repository.py`, konkrétní implementace v `infrastructure/database/repositories/`:

```python
# domain/doklady/repository.py (interface)
from abc import ABC, abstractmethod

class DokladyRepository(ABC):
    @abstractmethod
    def ulozit(self, doklad: Doklad) -> int: ...
    @abstractmethod
    def najit_dle_id(self, doklad_id: int) -> Optional[Doklad]: ...
    @abstractmethod
    def seznam(self, filtr: DokladFiltr) -> list[Doklad]: ...
    @abstractmethod
    def smazat(self, doklad_id: int) -> None: ...

# infrastructure/database/repositories/doklady_repo.py (implementace)
class SqliteDokladyRepository(DokladyRepository):
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def seznam(self, filtr: DokladFiltr) -> list[Doklad]:
        sql = "SELECT * FROM doklady WHERE 1=1"
        params = []
        if filtr.typ:
            sql += " AND typ = ?"
            params.append(filtr.typ)
        # ... další filtry
        rows = self._conn.execute(sql, params).fetchall()
        return [self._map_row(r) for r in rows]
```

**Důsledek:** UI nikdy nevidí SQL. ViewModel volá repository, repository vrací doménové entity. Aktuálních **116 přímých DB volání v UI** zmizí.

#### 8.3.3 Unit of Work — konec nekonzistentních commitů

Nahrazuje současný pattern kde `db.connection.commit()` je volaný **9× manuálně** v různých core souborech, často po sérii operací bez sdílené transakce (např. `parovani.py` dělá 3 INSERTy + 1 UPDATE bez transakce):

```python
# infrastructure/database/unit_of_work.py
class UnitOfWork:
    """Jedna transakce pro celý use case."""

    def __init__(self, conn_factory):
        self._conn_factory = conn_factory

    def __enter__(self):
        self._conn = self._conn_factory()
        self._conn.execute("BEGIN")
        # Vytvořit repositories s touto connection
        self.doklady = SqliteDokladyRepository(self._conn)
        self.denik = SqliteUcetniDenikRepository(self._conn)
        self.finance = SqliteFinanceRepository(self._conn)
        self.partneri = SqlitePartneriRepository(self._conn)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()

    def commit(self):
        self._conn.commit()
```

**Použití v command handlerech:**
```python
class ZauctujDokladHandler:
    def __init__(self, uow_factory):
        self._uow_factory = uow_factory

    def handle(self, cmd: ZauctujDokladCommand) -> None:
        with self._uow_factory() as uow:
            doklad = uow.doklady.najit_dle_id(cmd.doklad_id)
            zaznam = UcetniZaznam(...)
            uow.denik.pridat(zaznam)
            uow.doklady.aktualizovat_stav(doklad.id, "zauctovany")
            # COMMIT proběhne automaticky na konci with bloku
            # ROLLBACK proběhne při jakékoli výjimce
```

#### 8.3.4 ViewModel pattern — bridge UI ↔ domain

Místo přímého volání DB z UI widgetů:

```python
# ui/viewmodels/dashboard_vm.py
class DashboardViewModel:
    """Připravuje data pro dashboard. UI na něm volá metody, nikdy SQL."""

    def __init__(self, query_handler):
        self._query = query_handler

    def load_kpi(self) -> DashboardKPI:
        return self._query.handle(DashboardQuery())

    def load_doresim(self) -> list[DoresimItem]:
        return self._query.handle(DoresimQuery(limit=10))

# Datová třída pro UI — žádné Decimal, žádné Row objekty
@dataclass
class DashboardKPI:
    banka_formatted: str          # "1 234 567,00 Kč"
    banka_trend: str              # "↑ 12 300 Kč"
    banka_trend_positive: bool
    pokladna_formatted: str
    dppo_formatted: str
    # ... UI-ready data
```

#### 8.3.5 Connection Factory místo Singletonu

Současný `Database` singleton s `check_same_thread=False` je rizikový. Náhrada:

```python
# infrastructure/database/connection.py
class ConnectionFactory:
    """Vytváří SQLite connections. Žádný singleton."""

    def __init__(self, db_path: Path):
        self._db_path = db_path

    def create(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn
```

Pro UI vlákno: jedna connection. Pro background operace (OCR, import): vlastní connection. WAL mód povoluje concurrent readers.

#### 8.3.6 Domain Events — decoupling

Místo přímého volání cross-cutting logiky (audit log, přepočet saldokonta, refresh badge):

```python
# domain/shared/events.py
@dataclass(frozen=True)
class DokladZauctovan:
    doklad_id: int
    ucet_md: str
    ucet_dal: str
    castka: Money
    datum: date

@dataclass(frozen=True)
class UhradaProvedena:
    doklad_id: int
    castka: Money
    zdroj: str  # "bank" | "pokladna"

# Event handler — registrovaný v DI containeru
class RefreshSaldokontoHandler:
    def handle(self, event: DokladZauctovan) -> None:
        # Přepočítat saldokonto pro dotčené účty
        ...

class AuditLogHandler:
    def handle(self, event: DokladZauctovan) -> None:
        # Zapsat do audit_log
        ...
```

---

### 8.4 Dependency Injection

Jednoduchý DI container bez externích knihoven:

```python
# container.py
class Container:
    """Ruční DI — explicitní wiring, žádná magie."""

    def __init__(self, db_path: Path):
        self._conn_factory = ConnectionFactory(db_path)

    def uow_factory(self) -> UnitOfWork:
        return UnitOfWork(self._conn_factory.create)

    def dashboard_vm(self) -> DashboardViewModel:
        return DashboardViewModel(
            query_handler=DashboardQueryHandler(self._conn_factory)
        )

    def doklady_vm(self) -> DokladyViewModel:
        return DokladyViewModel(
            uow_factory=self.uow_factory,
            ciselne_rady=CiselneRady(),
            predkontace=PredkontaceEngine(),
        )
    # ...
```

Inicializace v `main.py`:
```python
container = Container(db_path=DB_PATH)
window = MainWindow(container)
```

UI stránky přijímají **ViewModel**, ne `db`:
```python
class DokladyPage(QWidget):
    def __init__(self, vm: DokladyViewModel, parent=None):
        self._vm = vm
        # ŽÁDNÉ self._db
```

---

### 8.5 Orchestrace AI agentů a rozdělení práce

#### 8.5.1 Kdo je kdo

Rewrite se dělí do **specializovaných pracovních bloků**. Každý blok může zpracovávat jeden Claude Code agent v izolovaném worktree:

| Agent / Blok | Zodpovědnost | Vstup | Výstup |
|-------------|--------------|-------|--------|
| **Architect** | Definice interfaces, domain events, Money VO | LESSONS_LEARNED.md | `domain/`, `container.py` |
| **Domain:Ucetnictvi** | UcetniZaznam, předvaha, hlavní kniha, podvojnost | Interfaces z Architect | `domain/ucetnictvi/`, testy |
| **Domain:Doklady** | Doklad entity, číselné řady, storno, zálohový cyklus | Interfaces z Architect | `domain/doklady/`, testy |
| **Domain:Finance** | Párování, import bank výpisů, pokladna | Interfaces z Architect | `domain/finance/`, testy |
| **Domain:Dan** | DPH, DPPO, kontrolní hlášení | Interfaces z Architect | `domain/dan/`, testy |
| **Domain:Majetek** | Majetek, odpisy, inventární karty | Interfaces z Architect | `domain/majetek/`, testy |
| **Domain:Mzdy** | Mzdové výpočty, odvody, mzdové listy | Interfaces z Architect | `domain/mzdy/`, testy |
| **Infra:DB** | SQLite repositories, UoW, migrace | Domain interfaces | `infrastructure/database/` |
| **Infra:External** | ARES klient, OCR engine, export | Domain interfaces | `infrastructure/ares,ocr,export/` |
| **App:Commands** | Command handlers — write operace | Domain + Infra | `application/commands/` |
| **App:Queries** | Query handlers — read operace | Domain + Infra | `application/queries/` |
| **UI:Design** | Design tokeny, QML theme, komponenty | Sekce 7 z LESSONS_LEARNED | `ui/qml/theme,components/` |
| **UI:Pages** | Stránky, ViewModely, navigace | Design + App vrstva | `ui/qml/pages/`, `ui/viewmodels/` |
| **Tests:Legislative** | Parametrizované testy DPH, odpisů, mezd | Legislativa 2026 | `tests/legislative/` |
| **Migration** | Datová migrace TEXT → INTEGER, staré schéma → nové | Obě schémata | `infrastructure/database/migrations/` |

#### 8.5.2 Pořadí práce (dependency graph)

```
Fáze 0: PŘÍPRAVA
  └── Architect → domain/shared/ (Money, errors, events, interfaces)

Fáze 1: DOMÉNA (paralelně, nezávislé na sobě)
  ├── Domain:Ucetnictvi
  ├── Domain:Doklady
  ├── Domain:Finance
  ├── Domain:Dan
  ├── Domain:Majetek
  └── Domain:Mzdy

Fáze 2: INFRASTRUKTURA (závisí na fázi 1)
  ├── Infra:DB (repositories + UoW + migrace)
  └── Infra:External (ARES + OCR + export)

Fáze 3: APLIKAČNÍ VRSTVA (závisí na fázi 1 + 2)
  ├── App:Commands
  └── App:Queries

Fáze 4: UI (závisí na fázi 3)
  ├── UI:Design (paralelně s Commands/Queries)
  ├── UI:Pages (závisí na Design + App)
  └── Tests:Legislative (paralelně s UI)

Fáze 5: INTEGRACE
  ├── Migration (stará DB → nová DB)
  ├── E2E testy
  └── Final QA
```

#### 8.5.3 Pravidla pro agenty

1. **Žádný agent neimportuje z jiné vrstvy nahoru:** `domain/` NIKDY neimportuje z `infrastructure/` nebo `ui/`. `application/` importuje z `domain/` ale NIKDY z `ui/`. `ui/` importuje z `application/` (viewmodely) ale NIKDY přímo z `domain/` entity.

2. **Každý agent píše testy pro svůj kód:** Doménové testy bez DB (pure Python), repository testy s in-memory SQLite, UI testy s pytest-qt.

3. **Interface first:** Architect definuje všechny repository interfaces a domain events PŘED tím, než doménové agenty začnou pracovat. To zajistí kompatibilitu.

4. **Money everywhere:** Žádný agent nesmí použít `Decimal` přímo pro částky. Vždy `Money` value object. Žádný `str` pro částky. Žádný `float`.

5. **Český jazyk v doméně:** Entity, value objects, a business logika používají české názvy (Doklad, UcetniZaznam, Pohledavka). Technická infrastruktura používá angličtinu (Repository, UnitOfWork, ConnectionFactory).

#### 8.5.4 Jak agent dostane kontext

Každý agent dostane:
1. **Tento dokument** (LESSONS_LEARNED.md) — celkový kontext
2. **Svůj bounded context ze starého kódu** — např. Domain:Doklady agent dostane `core/doklady.py`, `core/accounting_engine.py`, `core/ciselne_rady.py`
3. **Interfaces z fáze 0** — `domain/shared/`, `domain/doklady/repository.py`
4. **Legislativní požadavky ze sekce 5** — relevantní pro daný kontext
5. **CLAUDE.md s pravidly projektu**

#### 8.5.5 Jak agenty koordinovat v praxi

**Varianta A — Sekvenční (jednodušší, pomalejší):**
Jeden Claude Code session, fáze po fázi. Architect napíše interfaces, pak se přepne na doménové moduly jeden po druhém.

**Varianta B — Paralelní s worktree (rychlejší):**
```bash
# Fáze 0: Architect v main branch
claude "Vytvoř domain/shared/ s Money, errors, events, repository interfaces"

# Fáze 1: Paralelní doménové agenty ve worktree
claude --worktree "Implementuj domain/ucetnictvi/ dle interfaces" &
claude --worktree "Implementuj domain/doklady/ dle interfaces" &
claude --worktree "Implementuj domain/finance/ dle interfaces" &
# Merge worktree branches do main

# Fáze 2: Infra
claude "Implementuj infrastructure/database/repositories/ pro všechny domain interfaces"
# ...
```

**Varianta C — Agent SDK (nejsofistikovanější):**
Vytvořit orchestrační skript s Claude Agent SDK, který:
1. Spustí Architect agenta
2. Čeká na jeho výstup (interfaces)
3. Spustí 6 doménových agentů paralelně
4. Čeká na všechny
5. Spustí infra + app agenty
6. Nakonec UI agenta

---

### 8.6 Co zachovat ze starého kódu

Ne všechno se zahazuje. Tyto části se dají přenést s minimálními úpravami:

| Modul | Co přenést | Kam v nové struktuře | Úpravy |
|-------|------------|---------------------|--------|
| `bank_import.py` | Parser logika, detect_format | `domain/finance/import_parser.py` | Nahradit Decimal → Money |
| `design_tokens.py` | Celý token systém | `ui/qml/theme/` nebo `ui/widgets/design_tokens.py` | Jen přeformátovat na QML properties |
| `odpisy.py` | Výpočetní logika | `domain/majetek/odpisy.py` | Jen Money VO |
| `mzdy.py` | Výpočetní vzorce | `domain/mzdy/vypocet.py` | Money VO + opravit DPP kumulaci |
| `dph.py` | DPH výpočty, XML export | `domain/dan/dph.py` + `infrastructure/export/xml_generator.py` | Rozdělit na 2 soubory |
| `vykazy.py` | Rozvaha + VZZ mapování | `domain/vykazy/rozvaha.py`, `vzz.py` | Doplnit chybějící řádky |
| `exceptions.py` | Celá hierarchie výjimek | `domain/shared/errors.py` | Beze změn |
| `config.py` | Konstanty, sazby | `config.py` | Beze změn |
| `backup.py` | Online Backup API logika | `application/services/backup_service.py` | Beze změn |
| Sidebar config | SIDEBAR_CONFIG struktura | `ui/qml/` nebo `ui/widgets/sidebar.py` | Beze změn |
| Testy | Všechny test soubory | `tests/` | Adaptovat na nové interfaces |

**Co se NEZACHOVÁVÁ:**
- `database.py` singleton → nahradit ConnectionFactory
- `bankovni_vypisy_ui.py` (1740 řádků god object) → rozdělit na ViewModel + QML/Widget
- Veškerý SQL v UI souborech (116 volání) → přesunout do repositories
- `accounting_engine.py` duplikované metody → vyčistit do `domain/doklady/predkontace.py`
- `ucetni_denik.py` noop podvojnost check → přepsat na funkční validaci

---

### 8.7 Rizika rewrite a mitigace

| Riziko | Pravděpodobnost | Dopad | Mitigace |
|--------|-----------------|-------|----------|
| Rewrite trvá příliš dlouho, starý kód se mezitím neudržuje | Vysoká | Vysoký | Stanovit max. 4 týdny pro MVP. Paralelní agenti. |
| Nový kód nemá feature paritu se starým | Střední | Vysoký | Checklist feature parity odvozený ze sekce 1. Test suite jako záruka. |
| Datová migrace TEXT → INTEGER ztratí přesnost | Nízká | Kritický | Migrační skript s dry-run módem. Porovnání SUM před/po. Záloha před migrací. |
| QML learning curve zpomalí UI práci | Střední | Střední | Alternativa: zůstat u PyQt6 Widgets s AnimatedWidget base class. QML je nice-to-have. |
| Domain events přidávají komplexitu | Nízká | Nízký | Začít bez eventů, přidat je až když přímé volání začne být problém. YAGNI. |
| Over-engineering — příliš mnoho abstrakcí pro jednouživatelský program | Střední | Střední | Repository + UoW + Money jsou nutné. ViewModel je nutný. Zbytek (CQRS, events) jen pokud to reálně potřebujeme. |

---

### 8.8 MVP rewrite — co musí být hotové jako první

Minimální viable rewrite, po kterém se dá přepnout ze starého kódu:

1. **`domain/shared/money.py`** + testy — základ všeho
2. **`infrastructure/database/`** — connection factory, UoW, migrace TEXT → INTEGER
3. **`domain/doklady/`** + `SqliteDokladyRepository` — CRUD dokladů
4. **`domain/ucetnictvi/`** + `SqliteUcetniDenikRepository` — účetní zápisy, předvaha
5. **`application/commands/vytvor_doklad.py`** + `zauctuj_doklad.py` — základní workflow
6. **`application/queries/dashboard_data.py`** — data pro dashboard
7. **`ui/viewmodels/doklady_vm.py`** + `dashboard_vm.py` — bridge pro UI
8. **Napojení stávající UI** na nové ViewModely (postupná migrace stránek)

Pořadí je záměrné: doklady + deník pokrývají ~60 % denního používání programu. Zbytek (majetek, mzdy, DPH, export) se migruje postupně, modul po modulu, zatímco program běží na hybridní architektuře.
