# Roadmap účetního programu

Tento dokument zachycuje plánované fáze rozvoje aplikace **po dokončení
základního MVP** (Fáze 6 — UI). Fáze nejsou nutně sekvenční; výběr další
priority bude záviset na reálném používání aplikace a zpětné vazbě
z účetní praxe.

Aktualizováno: po dokončení Fáze 6.5 (storno přes opravný účetní předpis).

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

---

## 📋 Plánované fáze

### Fáze 7: Sidebar sekce per typ dokladu
**Co:** Rozdělit dnešní jednotnou položku „Doklady" v sidebaru na samostatné
sekce odpovídající typům dokladů — typicky „Vydané faktury" (FV),
„Přijaté faktury" (FP), „Pokladna" (PD), „Bankovní výpisy" (BV), atd.

**Proč:** Účetní mají mentální model rozdělené evidence — když pracují
s vydanými fakturami, nepřepínají se mezi typy. Sidebar má reflektovat
reálný workflow, ne datovou strukturu.

**Implementace:** Refactor MainWindow navigation, vytvoření DokladyByTypePage
s předfilovaným typem, úprava sidebar struktury.

### Fáze 8: Partneři (odběratelé / dodavatelé)
**Co:** Plnohodnotná Partner entita s evidencí. Doklady budou odkazovat
na Partner přes partner_id (FK), místo dnešního textového názvu.

**Funkce:**
- Page „Partneři" v sidebaru s tabulkou
- Vytvoření / úprava partnera (IČO, DIČ, adresa, kontakty)
- V dialogu nového dokladu dropdown se stávajícími partnery + tlačítko
  „+ Nový partner" otevírající modal pro rychlé vytvoření
- ARES integrace (volitelně) — vyplnění firmy podle IČO

**Implementace:** Nová doména `domain/partneri/`, nová page, dialog,
migrace partner FK na doklady.

### Fáze 9: Konfigurovatelné číselné řady
**Co:** Místo dnešního hardcoded `FV-2026-001` formátu si Tereza nastaví
vlastní řady na začátku roku (nebo při zakládání firmy).

**Příklady:**
- „FV-2026-XXX, počítadlo začíná od 1"
- „Faktury: 26F0001, 26F0002, ..." (vlastní formát)
- Samostatné řady pro různé typy: PV (pokladní výdej) má jinou řadu
  než PP (pokladní příjem)

**Implementace:** Doména `CiselnaRada` (mask, sequence, typ), Nastavení page
pro správu řad, integrace do auto-číslování v dialogu.

### Fáze 10: Přílohy a náhled souborů v dialogu
**Co:** Možnost přiložit PDF/obrázek k dokladu. V dialogu nového dokladu
i v detailu je vlevo formulář, vpravo náhled přiloženého souboru.

**Funkce:**
- Drag & drop upload nebo file picker
- PDF rendering (PyMuPDF nebo Qt 6.5+ QtPdf)
- Image rendering (QPixmap)
- File storage v lokální složce vedle DB
- Možnost přiložit více souborů (smlouva + faktura)

**Implementace:** Nová tabulka `prilohy` (FK na doklad), file storage helper,
rozšíření dialogu o pravý panel s náhledem.

### Fáze 11: OCR pipeline
**Co:** Tereza nahraje PDF/obrázek faktury, aplikace ho rozpozná OCR
službou a vyplní formulář předvyplněnými daty (částka, datum, partner,
číslo faktury). Tereza jen zkontroluje a uloží.

**Implementace:**
- Volba OCR služby (lokální Tesseract vs. cloud — Google Vision,
  AWS Textract, Azure)
- Parsing rozpoznaného textu (regex / NER pro extrakci polí)
- UI pro upload + preview + extracted fields
- Fallback na manuální zadání, pokud OCR selže

### Fáze 12: Bankovní výpisy a sesouhlasení
**Co:** Nahraní PDF bankovního výpisu (z měsíčního výpisu z banky),
parsing transakcí, kontrola proti CSV exportu z internet bankingu.

**Funkce:**
- Bankovní účty (entita)
- Import PDF výpisu → automatická extrakce transakcí
- Import CSV z internet bankingu
- Matching algoritmus (PDF transakce ↔ CSV transakce ↔ existující doklady
  s úhradou)
- Označení nesouladů (transakce v PDF, kterou není v CSV nebo naopak)

**Implementace:** Nová doména `banka/`, parser PDF výpisu (závisí na
konkrétní bance), matching engine.

---

## 🎯 Po dokončení všech fází

Aplikace bude pokrývat **kompletní účetní workflow malé firmy / s.r.o.**:
- Evidence dokladů s rozdělením podle typu
- Partneři + ARES
- Konfigurovatelné číslování
- Přílohy + OCR pro automatizaci
- Banka + sesouhlasení
- Reporty (předvaha, hlavní kniha, VZZ, rozvaha — některé už hotové)
- DPH přiznání (samostatná fáze, TBD)

Cíl: účetní program použitelný pro reálnou s.r.o. s ~stovkami dokladů ročně.
