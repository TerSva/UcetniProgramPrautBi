-- 005_analytika.sql
-- Fáze 7: Analytické účty + popis + TypUctu 'Z' (závěrkové).
--
-- SQLite neumí ALTER CHECK, proto musíme recreate tabulku.

-- 1) Přidáme nové sloupce (parent_kod, popis)
ALTER TABLE uctova_osnova ADD COLUMN parent_kod TEXT
    REFERENCES uctova_osnova(cislo);

ALTER TABLE uctova_osnova ADD COLUMN popis TEXT;

-- 2) Recreate tabulku s rozšířeným CHECK pro typ (přidáno 'Z')
CREATE TABLE uctova_osnova_new (
    cislo TEXT PRIMARY KEY,
    nazev TEXT NOT NULL,
    typ TEXT NOT NULL CHECK (typ IN ('A', 'P', 'N', 'V', 'Z')),
    je_aktivni INTEGER NOT NULL DEFAULT 1,
    parent_kod TEXT REFERENCES uctova_osnova_new(cislo),
    popis TEXT
);

INSERT INTO uctova_osnova_new (cislo, nazev, typ, je_aktivni, parent_kod, popis)
    SELECT cislo, nazev, typ, je_aktivni, parent_kod, popis
    FROM uctova_osnova;

DROP TABLE uctova_osnova;

ALTER TABLE uctova_osnova_new RENAME TO uctova_osnova;

-- 3) Indexy
CREATE INDEX idx_uctova_osnova_parent ON uctova_osnova(parent_kod)
    WHERE parent_kod IS NOT NULL;

-- 4) Recreate FK references from ucetni_zaznamy
-- (SQLite foreign keys reference by name, table rename preserves them)
