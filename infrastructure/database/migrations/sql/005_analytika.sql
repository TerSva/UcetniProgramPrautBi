-- 005_analytika.sql
-- Fáze 7: Analytické účty + popis + TypUctu 'Z' (závěrkové).
--
-- SQLite neumí ALTER CHECK, proto recreate tabulku s rozšířeným CHECK.

-- Recreate tabulku s rozšířeným CHECK pro typ (přidáno 'Z') + nové sloupce
CREATE TABLE uctova_osnova_new (
    cislo TEXT PRIMARY KEY,
    nazev TEXT NOT NULL,
    typ TEXT NOT NULL CHECK (typ IN ('A', 'P', 'N', 'V', 'Z')),
    je_aktivni INTEGER NOT NULL DEFAULT 1,
    parent_kod TEXT REFERENCES uctova_osnova_new(cislo),
    popis TEXT
);

INSERT INTO uctova_osnova_new (cislo, nazev, typ, je_aktivni)
    SELECT cislo, nazev, typ, je_aktivni
    FROM uctova_osnova;

DROP TABLE uctova_osnova;

ALTER TABLE uctova_osnova_new RENAME TO uctova_osnova;

-- Indexy
CREATE INDEX idx_uctova_osnova_parent ON uctova_osnova(parent_kod)
    WHERE parent_kod IS NOT NULL;
