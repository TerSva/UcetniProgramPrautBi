-- 009_firma_pocatecni_stavy.sql
-- Firma (singleton) + Počáteční stavy účtů.

CREATE TABLE firma (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    nazev TEXT NOT NULL,
    ico TEXT,
    dic TEXT,
    sidlo TEXT,
    pravni_forma TEXT,
    datum_zalozeni TEXT,
    rok_zacatku_uctovani INTEGER NOT NULL DEFAULT 2025,
    zakladni_kapital INTEGER,
    kategorie_uj TEXT DEFAULT 'mikro',
    je_identifikovana_osoba_dph INTEGER NOT NULL DEFAULT 0,
    je_platce_dph INTEGER NOT NULL DEFAULT 0,
    bankovni_ucet_1 TEXT,
    bankovni_ucet_2 TEXT
);

CREATE TABLE pocatecni_stavy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ucet_kod TEXT NOT NULL,
    castka INTEGER NOT NULL,
    strana TEXT NOT NULL CHECK (strana IN ('MD', 'DAL')),
    rok INTEGER NOT NULL,
    poznamka TEXT,
    FOREIGN KEY (ucet_kod) REFERENCES uctova_osnova(cislo)
);

CREATE INDEX idx_pocatecni_rok ON pocatecni_stavy(rok);
