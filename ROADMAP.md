# Roadmap účetního programu

Tento dokument zachycuje plánované fáze rozvoje aplikace **po dokončení
základního MVP** (Fáze 6 — UI). Strategický pivot: sprint k termínu
podání daňového přiznání k DPPO za rok 2025 — **4. května 2026**.

Aktualizováno: po dokončení Fáze 6.7 (filter-aware UI, form k_doreseni, dashboard drill-down).

---

## ✅ Dokončeno

### Fáze 1-5: Backend (doména, persistence, services)
- Money value object s INTEGER haléři + ROUND_HALF_UP
- Doklad entity s flag k_doreseni
- Účetnictví: Ucet, UcetniZaznam, UctovyPredpis, podvojnost
- SQLite persistence + UoW + migrace
- Services: ZauctovaniDokladu, queries (Predvaha, HlavniKniha, Dashboard, DokladyList)

### Fáze 6: UI MVP
- Krok 1: Skeleton aplikace + sidebar + design tokens
- Krok 2: Dashboard s živými KPI kartami
- Krok 3: Doklady list s filtry + read-only detail
- Krok 4: Vytváření dokladu + zaúčtování + akce (dořešit, smazat).
- Krok 5: Polish, finální screenshoty

### Fáze 6.5: Storno přes opravný účetní předpis ✅ HOTOVO
Storno zaúčtovaného dokladu nyní vytváří opravný účetní předpis (protizápis,
varianta A — prohozené MD ↔ Dal, kladná částka) a anuluje dopad původního
zaúčtování ve Předvaze, Hlavní knize i Dashboard KPI. Per-záznam architektura
(`ucetni_zaznamy.je_storno` + `stornuje_zaznam_id`), migrace 004, idempotentní
`ZauctovaniDokladuService.stornuj_doklad`, UI re-enabled s novým confirm textem.

### Fáze 6.7: Filter-aware UI + Form k_doreseni + Dashboard drill-down ✅ HOTOVO
FilterBar s dynamickým "Filtr aktivní" badge, status bar "Zobrazeno X z Y
dokladů · N filtrů aktivní" s českou pluralizací. Form dialog s checkboxem
"Označit jako k dořešení" + poznámka (toggle visible). Dashboard drill-down
pro Pohledávky (FV) a Závazky (FP) karty. Detail edit mode s k_doreseni
sekcí. CountAllDokladyQuery pro total_count. 844 testů.

---

## Plánované fáze — Sprint pro daňové přiznání 4. 5. 2026

**Kontext:** Uživatelka podává daňové přiznání k DPPO za rok 2025 do 4. 5. 2026. 
Firma je PRAUT s.r.o. (IČO 22545107), mikro účetní jednotka, identifikovaná osoba DPH.
Cílem sprintu je postavit plně funkční aplikaci umožňující zaúčtovat celý rok 2025 
a vygenerovat výkazy pro ruční přepis do portálu Finanční správy.

### Fáze 7: Osnova + Analytika (PRIORITA 1, NÁSLEDUJE)

**Rozsah:**
- Import standardní směrné účtové osnovy dle vyhlášky 500/2002 Sb., příloha č. 4
- Celá osnova ~100 syntetických účtů (třídy 0-7)
- UI pro aktivaci/deaktivaci účtů (ne všechny musí být v aplikaci)
- UI pro vytváření analytických účtů (formát: `syntetický.analytika`, např. `501.100`)
- Předkonfigurovaná sada účtů pro PRAUT s.r.o. (~25 účtů)
- Management účtové osnovy jako samostatná stránka v sekci Evidence

**Klíčová rozhodnutí:**
- Formát analytiky: `xxx.yyy` (např. 501.100, 518.200)
- Analytické účty vytváří uživatel sám přes UI
- Syntetický účet má flag `is_active` — skrýt z dropdownů ty, které firma nepoužívá
- Směrná osnova je **seed data** (součást aplikace), firemní osnova se ukládá do DB

### Fáze 8: Sidebar + Struktura Aplikace

**Rozsah:**
- Rozklikovatelná sekce "Doklady" v sidebaru:
  - Vydané faktury (FV)
  - Přijaté faktury (FP)
  - Pokladní doklady (PD)
  - Bankovní výpisy (BV)
  - Interní doklady (ID)
  - Opravné doklady (OD)
- Nová položka "📥 Nahrát doklady" v sekci Účetnictví (nad Doklady) — Lucide ikona `inbox`
- Aktivace placeholder sekcí: Banka, Pokladna, Účetní deník, Partneři, Účtová osnova, Výkazy, DPH, Saldokonto
- Majetek a Mzdy odstraněny ze sidebaru (mimo MVP scope)
- Každý typ dokladu má vlastní stránku s pre-applied typ filtrem

### Fáze 9: Partneři + Společníci

**Rozsah:**
- Partner entita s kategoriemi: ODBERATEL, DODAVATEL, SPOLECNIK, KOMBINOVANE
- Standardní pole: IČO, DIČ, název, adresa, bankovní účet
- **BEZ ARES integrace** (ruční zápis)
- Dropdown v dialogu Nový doklad (typeahead search)
- Prefill společníků PRAUT: Martin Švanda (90%), Tomáš Hůf (10%)
- Pro SPOLECNIK partnery — automatické nastavení účtu 355 (pohledávka) / 365 (závazek)
- Partneři stránka v sekci Evidence

### Fáze 10: ID doklady + Společník workflow ("pytlování")

**Rozsah:**
- Vytvoření interního dokladu (ID) v UI
- Speciální workflow "Platil jednatel ze svého účtu":
  - V dialogu Nový FP checkbox "☑ Placeno ze soukromé karty společníka"
  - Při zaškrtnutí: účtování automaticky MD 518.xxx / Dal 365.001 (místo 321)
  - Vizuální warning v detailu: "Hrazeno přes společníka"
- Workflow "Firma proplatila společníkovi":
  - ID doklad MD 365.001 / Dal 221 (bankovní účet)
  - Propojí se se seznamem všech "pytlování" dokladů
- Saldokonto společníka — běžící celkový závazek

### Fáze 11: DPH Reverse Charge

**Rozsah:**
- Automatický výpočet DPH při zaúčtování FP z EU
- V zaúčtování checkbox "☑ Reverse charge (EU služba)"
- Auto-vytvoření řádků: MD 343.100 / Dal 343.200
- **BLOKACE Kontrolního hlášení** — identifikovaná osoba nesmí
- Souhrnné hlášení VIES (pokud firma poskytla službu do EU)
- Výkaz DPH za měsíc — textový přehled pro ruční přepis do EPO

### Fáze 12: OCR + Inbox

**Rozsah:**
- Drop zone v sekci "Nahrát doklady"
- OCR engine: Tesseract (lokální) + PDF text extraction (digital-born PDFs)
- Auto-detekce typu dokladu (FP/FV/BV/PD) — **editovatelné uživatelem**
- Auto-detekce "pytlování" (faktura na společníka) s warningem
- Dva save módy:
  - **💾 Uložit jako NOVY** (bez účtování, flag k dořešení)
  - **⚡ Schválit a zaúčtovat** (plný workflow)
- Side-by-side náhled (PDF + formulář)
- Batch schvalování více dokladů stejného typu najednou
- Dashboard notifikace počtu nezpracovaných
- Status badge "📋 OCR" v seznamech + filtr "Zdroj: OCR/Ručně"

### Fáze 13: Banka + CSV Import + Párování

**Rozsah:**
- Obecný CSV import (konfigurovatelné sloupce)
- Podpora dvou bank: Money Banka + Česká spořitelna (konfigurace PRAUT)
- Dva bankovní účty (221.001 Money, 221.002 ČS)
- Kontrola PS (počáteční) a KS (konečný stav) proti PDF výpisu
- Auto-párování plateb s doklady podle VS + částky
- Ruční párování — "spáruj platbu s dokladem X"
- Zaúčtování platby: MD/Dal 221 + spárovaný doklad

### Fáze 14: Počáteční stavy + Vklad ZK

**Rozsah:**
- Stránka "Počáteční stavy" pro rok 2025
- Vklad ZK: MD 221 / Dal 411 (10 Kč pro PRAUT)
- Ruční zadání počátečních zůstatků ostatních účtů (pokud začínali s něčím)
- Firma PRAUT: začíná od nuly (založena 3. 2. 2025), takže jen vklad ZK

### Fáze 15: Výkazy + PDF

**Rozsah:**
- Rozvaha ve zkráceném rozsahu (A, B, C, D) → PDF export
- VZZ druhové ve zkráceném rozsahu (římské + písmena) → PDF
- Saldokonto pro účty 311, 321, 355, 365 → PDF
- Šablona "Minimální příloha" (hlavičkové údaje + kategorie + účetní metody) → PDF
- Účelem je ruční přepis hodnot do portálu Finanční správy (formulář 25 5404)
- **BEZ EPO XML exportu** (mimo MVP scope)

## Mimo MVP scope (po podání daně)

- Krok 5 Polish (finální screenshoty, README, klávesové zkratky)
- ARES integrace
- Kontrolní hlášení (neaplikovatelné — jsme identifikovaná osoba)
- EPO XML export
- Časová razítka pro elektronickou archivaci
- Pokladna samostatně (stačí PD doklady)
- Majetek (MacBook je pod hranicí DHM)
- Mzdy (firma nemá zaměstnance)
- Odpisy (není DHM)
- Opravné položky, rezervy, časové rozlišení nad rámec nejjednodušších případů

Cíl: účetní program použitelný pro reálnou s.r.o. s ~stovkami dokladů ročně,
s termínem podání daňového přiznání k DPPO 4. května 2026.
