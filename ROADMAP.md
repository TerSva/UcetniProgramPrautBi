# Roadmap účetního programu

Tento dokument zachycuje plánované fáze rozvoje aplikace **po dokončení
základního MVP** (Fáze 6 — UI). Fáze nejsou nutně sekvenční; výběr další
priority bude záviset na reálném používání aplikace a zpětné vazbě
z účetní praxe.

Aktualizováno: po dokončení Fáze 6 (UI MVP).

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
- Krok 4: Vytváření dokladu + zaúčtování + akce (dořešit, smazat). Storno
  zatím přes UI zakázané — viz Fáze 6.5.
- Krok 5: Polish, finální screenshoty

---

## 📋 Plánované fáze

### Fáze 6.5: Storno přes opravný účetní předpis
**Co:** Kompletně přepracovat akci „Stornovat" na detail dokladu tak, aby
kromě změny stavu vytvářela i **opravný účetní předpis** (protizápis) —
stornování zaúčtovaného dokladu musí vynulovat jeho dopad ve výkazech.

**Proč:** Aktuální `Doklad.stornuj()` jen změní stav na `STORNOVANY`, ale
**nevytváří protizápis**. Důsledek: po stornu zaúčtovaného dokladu jsou
účetní výkazy (Předvaha, Hlavní kniha, VZZ, Dashboard KPI) **nekonzistentní**
— zápisy v hlavní knize pořád existují, ale v seznamu dokladů svítí „Stornovaný".
Účetní zkrátka nesmí stornovat jinak než opravným účetním předpisem.

Proto je v UI tlačítko „Stornovat" v detail dialogu aktuálně **disabled
s tooltipem** „Storno přes opravný účetní předpis bude přidáno v příští
fázi (Fáze 6.5)." Ostatní akce (Upravit, Označit k dořešení, Dořešeno,
Smazat) zůstávají plně funkční.

**Co bude obsahovat:**
- **Nová logika v doméně:** `Doklad.stornuj()` musí vytvořit opravný `UctovyPredpis`
  s obrácenými stranami (MD ↔ Dal) původních zápisů. Nový předpis nese
  flag `je_storno=True` a odkaz na původní předpis (`stornuje_predpis_id`).
- **Command `StornovatDoklad`** v `services/commands/`: idempotentní, transakční
  (v jedné UoW vytvoří protizápis + změní stav). Validace: lze stornovat
  jen ZAUCTOVANY nebo CASTECNE_UHRAZENY (ne UHRAZENY → vrácení peněz, ne NOVY
  → stačí Smazat).
- **Migrace SQL:** přidání sloupců `je_storno BOOLEAN` a `stornuje_predpis_id FK`
  do `ucetni_predpisy`.
- **UI — enable storno tlačítko:** odstranit permanentní disabled + tooltip;
  respektovat `DokladDetailViewModel.can_storno`.
- **UI — vizualizace protizápisu:** v detail dialogu (pokud je doklad
  stornovaný) ukázat jak původní, tak opravný předpis, s jasným označením
  „Storno ze dne {datum}".
- **Queries — Dashboard + Predvaha + HlavniKniha:** ověřit, že opravné
  zápisy správně ruší dopad původních (součty výnosů/nákladů musí po stornu
  odpovídat nule pro daný doklad).
- **Testy:** doména (Doklad.stornuj s novým chováním), command (transakce,
  idempotence), integration (po stornu jsou KPI konzistentní).

**Otevřená otázka k vyřešení během této fáze:** Jak přesně vypadá opravný
předpis v české podvojné účetní praxi? Storno se dělá:
- (a) **protizápisem** — nový předpis s prohozenými stranami (MD ↔ Dal)
  a stejnou kladnou částkou, nebo
- (b) **červeným zápisem** — nový předpis se stejnými stranami, ale zápornou
  částkou (v účetním softwaru se tiskne červeně)?

Obě varianty mají stejný matematický efekt na součty, ale liší se v trailu
(deník, hlavní kniha) a v tom, jak se to čte. Zeptám se Terezy podle její
reálné praxe, než začnu implementovat doménu.

**Kdy:** Před Fází 7. Je to zbytkový dluh z Fáze 6 — bez toho nelze aplikaci
reálně nasadit, protože storno je běžná operace a nesmí rozbít výkazy.

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
