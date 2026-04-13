-- 003_doklady_doreseni.sql
-- Fáze 4.5: flag "k dořešení" pro doklady.
-- Ortogonální ke stavu, informativní pro uživatelku, neovlivňuje výkazy.

ALTER TABLE doklady ADD COLUMN k_doreseni INTEGER NOT NULL DEFAULT 0
    CHECK (k_doreseni IN (0, 1));

ALTER TABLE doklady ADD COLUMN poznamka_doreseni TEXT;

-- Konzistence "poznámka jen když flag=1" vynucuje entita v Pythonu
-- (SQLite neumí přidat CHECK constraint přes ALTER TABLE).

-- Partial index pro rychlé list_k_doreseni() — drží jen flagnuté řádky.
-- Typicky bude většina dokladů k_doreseni=0, takže partial index je
-- výrazně menší a rychlejší než full index.
CREATE INDEX idx_doklady_k_doreseni ON doklady(k_doreseni) WHERE k_doreseni = 1;
