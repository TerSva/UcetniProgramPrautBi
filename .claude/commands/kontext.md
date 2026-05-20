---
description: Aktualizuje PRAUT_kontext.md a zobrazí aktuální stav. Argument 'zobraz' = jen zobrazit bez aktualizace.
---

# /kontext — auto-update PRAUT_kontext.md

Použití:
- `/kontext` — spustí `update_kontext.py` a zobrazí aktualizovaný kontext
- `/kontext zobraz` — jen zobrazí aktuální stav (žádný update)

## Postup

1. **Pokud argument není `zobraz`:** spusť aktualizaci skriptem:

   ```bash
   .venv/bin/python .claude/hooks/update_kontext.py
   ```

   Vypiš jen poslední řádek výstupu (potvrzení s timestampem a commit hashem).

2. **Zobraz obsah `PRAUT_kontext.md`** — použij Read tool. Soubor je krátký
   (~125 řádků), takže ho vypiš celý. Pokud uživatel chce jen AUTO sekce
   (mezi `<!-- AUTO_START -->` a `<!-- AUTO_END -->`), zmiň, že MANUAL
   sekce jsou zachované a nemění se přes tento command.

3. **Pokud script selhal** (nesprávná cesta, chyba DB), vypiš error a
   navrhni rerun bez aktualizace:
   > `/kontext zobraz` zobrazí poslední uložený stav bez force-update.

## Důležité

- Skript je idempotentní — opakované spuštění nezpůsobí problém
- MANUAL sekce (`<!-- MANUAL_START:* -->` ... `<!-- MANUAL_END:* -->`)
  se přes `/kontext` **nemění** — uprav je ručně přes Edit tool
- Po úspěšném `/kontext` (s update) je `PRAUT_kontext.md` rozsynchronizovaný
  s gitem (untracked / modified) — `git commit` ho zase potáhne in přes
  auto-amend (viz `.claude/hooks/post-commit`)
