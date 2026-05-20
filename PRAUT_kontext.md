# PRAUT — aktivní kontext

> Živý dokument — auto-aktualizován po každém git commitu.
> Pro foundational dokumentaci viz `PRAUT_program.md`.
>
> Naposledy aktualizováno: 2026-05-20 22:42 (commit 357aea5)

---

## 🎯 Top of mind (MANUÁLNÍ — uprav ručně)

<!-- MANUAL_START:top_of_mind -->
1. **DPH modul — implementace přístupu C** (flag pro skryté Hetzner faktury) — PRIORITA ZÍTRA
2. **Doplnit CZ DIČ do Hetzner účtu PRAUT** — viz running issue v PRAUT_program.md §6.2
3. **Napárovat bankovní platby FÚ ze 4.5.2026** (8 plateb, celkem 7 508 Kč)
4. **Import bank. výpisů za 2026** (zatím 0 transakcí v DB za 2026)
<!-- MANUAL_END:top_of_mind -->

---

## 📊 Aktuální účetní stav

<!-- AUTO_START:ucetni_stav -->
### Rok 2025
- Doklady: **180**
- Účetně uzavřen (Z1/Z2/Z3): **ANO**
- VH: **-415 626,75 Kč**

### Rok 2026
- Doklady: **2**
- Bilance: A=9 314,55 Kč, P=9 314,55 Kč  ✅
- VH minulých let (431.100 saldo): **-415 626,75 Kč**
- 343.200 (DPH závazek): **7 015,49 Kč**
- 426.100 (oprava chyb min. let): **10 032,45 Kč**
<!-- AUTO_END:ucetni_stav -->

---

## 🔧 Git stav

<!-- AUTO_START:git -->
**Branch:** main
**Poslední commit:** 357aea5 feat: PRAUT_kontext.md auto-update systém
**Commitů za posledních 7 dní:** 6
**Uncommitted relevantní soubory** (.py/.md/.sql/...): 0

### Posledních 5 commitů
- 357aea5 (2026-05-20) feat: PRAUT_kontext.md auto-update systém
- 40169cb (2026-05-20) docs: add PRAUT_program.md (foundational documentation)
- 18535d5 (2026-05-20) feat: závěrkový workflow + storno bug fix + skryté výkazové filtry
- 7bfdf57 (2026-05-20) feat(dph): PDF export DPH přehledu za rozsah měsíců
- 04799b7 (2026-05-20) fix(uzaverka): doklad 701 účtuje přes analytiku 701.100
<!-- AUTO_END:git -->

---

## 📋 Otevřené úkoly

<!-- AUTO_START:todo -->
### Funkční mezery (z PRAUT_program.md §9.1)
- Mzdový modul — placeholder bez logiky (firma nemá zaměstnance)
- Majetek + odpisy — placeholder (firma nemá DHM)
- Kontrolní hlášení (KH) — info-only (identif. osoba ho nepodává)
- EPO XML export — pouze textový clipboard
- DPH dodatečná přiznání + dph_podani tabulka prázdná
- Opravné položky, rezervy, časové rozlišení
- ARES integrace — entity existuje, klient k ověření

### Architektonické (- [ ] z ROADMAP.md)
- [ ] **Banka validator** — `test_pdf_errors_propagated` padá pre-existing.
- [ ] **Rozdělit je_zaverka** na `je_uzaviraci` + `je_otviraci` —
- [ ] **Mapování účtové osnovy** — preventivně ověřit, že všechny
- [ ] **Bilanční kontrola jako runtime guard** — zvážit asserting
<!-- AUTO_END:todo -->

---

## 💾 Stav DB

<!-- AUTO_START:db -->
**Cesta:** ucetni.db
**Velikost:** 552 KB
**Poslední migrace:** 31
**Tabulek:** 14

### Poslední 3 zálohy
- ucetni.db.backup_pred_variant_A_20260520_174631 (544 KB)
- ucetni.db.backup_pred_odoo_oprava_20260508_091943 (544 KB)
- ucetni.db.backup_pred_353_to_355_20260507_130210 (536 KB)
<!-- AUTO_END:db -->

---

## 🧪 Stav testů

<!-- AUTO_START:tests -->
**Poslední run:** auto-nepouštěno (commit hook)
**Pro nový run:** `.venv/bin/python -m pytest --ignore=tests/ui -q`
**Známé failures:** `tests/services/banka/test_validator.py::TestCsvPdfValidator::test_pdf_errors_propagated` (pre-existing, commit 43c1933 — viz ROADMAP TODO)
<!-- AUTO_END:tests -->

---

## 📝 Manuální poznámky

<!-- MANUAL_START:poznamky -->
Volné místo na zápisky, dlouhodobé úvahy, kontext k dlouhým úkolům.

### Hetzner OSS oprava (20.5.2026)
Hetzner Online GmbH (DE812871812) doposud účtuje 21% CZ DPH přes OSS,
protože v účtu PRAUT chybí CZ DIČ. Doklad ID-2026-001 (343.200 / 426.100
= 10 032,45 Kč) opravil minulé období dle ČÚS 019.

TODO uživatelská akce: doplnit DIČ do Hetzner účtu, od příští faktury
bude Hetzner účtovat bez DPH (klasický reverse charge).

Externí dokumentace: https://docs.hetzner.com/general/others/vat/

### Závěrkový refactor (20.5.2026)
Commit 18535d5 — viz PRAUT_program.md §6.3 a §11. Klíčové změny:
- `je_zaverka` flag (migrace 031)
- VykazyQuery filtr `vcetne_zaverky` s defaulty per modul
- UzaverkaRokuCommand (Z1/Z2/Z3 idempotentní)
- Storno bug fix (sjednoceno bez filtru je_storno=0)
- Účet 426 doplněn do ROZVAHA_PASIVA A.IV.
<!-- MANUAL_END:poznamky -->
