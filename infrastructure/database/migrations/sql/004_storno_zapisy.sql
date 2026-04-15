-- 004_storno_zapisy.sql
-- Fáze 6.5: Storno přes opravný účetní předpis.
--
-- Aby se stornování zaúčtovaného dokladu korektně promítlo do výkazů,
-- musí vzniknout protizápis (opravný účetní záznam) s prohozenými MD/Dal
-- stranami a se shodnou kladnou částkou. Na úrovni jednotlivých zápisů
-- držíme:
--   * je_storno          — flag „tento záznam je protizápisem"
--   * stornuje_zaznam_id — FK na původní záznam, který tento storno-záznam
--                         anuluje (nullable — originální záznamy mají NULL)
--
-- Architektonická poznámka: storno je na úrovni `ucetni_zaznamy`, nikoli
-- `ucetni_predpisy` — tabulka `ucetni_predpisy` v této DB neexistuje,
-- `UctovyPredpis` je čistě doménový transient obalující záznamy.

ALTER TABLE ucetni_zaznamy ADD COLUMN je_storno INTEGER NOT NULL DEFAULT 0
    CHECK (je_storno IN (0, 1));

ALTER TABLE ucetni_zaznamy ADD COLUMN stornuje_zaznam_id INTEGER
    REFERENCES ucetni_zaznamy(id) ON DELETE RESTRICT;

-- Konzistenci „stornuje_zaznam_id IS NOT NULL ⇔ je_storno = 1" vynucuje
-- entita `UcetniZaznam` v Pythonu (SQLite neumí přidat CHECK přes ALTER).

-- Partial index pro dohledání originálu podle jeho storna (malá množina
-- řádků → výrazně menší index než full).
CREATE INDEX idx_zaznamy_stornuje
    ON ucetni_zaznamy(stornuje_zaznam_id)
    WHERE stornuje_zaznam_id IS NOT NULL;
