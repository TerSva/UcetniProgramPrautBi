-- 001_init_schema.sql
-- Inicializační schema: partneri, uctova_osnova, doklady, ucetni_zaznamy
-- Všechny finanční sloupce INTEGER (haléře). Žádný REAL/TEXT pro částky.

CREATE TABLE partneri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ico TEXT,
    dic TEXT,
    nazev TEXT NOT NULL,
    typ TEXT NOT NULL DEFAULT 'dodavatel'
        CHECK (typ IN ('dodavatel', 'odberatel', 'oboji', 'zamestnanec', 'urad')),
    ulice TEXT,
    mesto TEXT,
    psc TEXT,
    stat TEXT NOT NULL DEFAULT 'CZ',
    vytvoreno TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    upraveno TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

CREATE TABLE uctova_osnova (
    cislo TEXT PRIMARY KEY,
    nazev TEXT NOT NULL,
    typ TEXT NOT NULL CHECK (typ IN ('A', 'P', 'N', 'V')),
    je_aktivni INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE doklady (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cislo TEXT UNIQUE NOT NULL,
    typ TEXT NOT NULL CHECK (typ IN ('FV', 'FP', 'ZF', 'BV', 'PD', 'ID', 'OD')),
    datum_vystaveni TEXT NOT NULL,
    datum_zdanitelneho_plneni TEXT,
    datum_splatnosti TEXT,
    partner_id INTEGER REFERENCES partneri(id) ON DELETE RESTRICT,
    castka_celkem INTEGER NOT NULL DEFAULT 0,
    mena TEXT NOT NULL DEFAULT 'CZK',
    stav TEXT NOT NULL DEFAULT 'novy'
        CHECK (stav IN ('novy', 'zauctovany', 'uhrazeny', 'castecne_uhrazeny', 'stornovany')),
    popis TEXT,
    vytvoreno TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    upraveno TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

CREATE TABLE ucetni_zaznamy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doklad_id INTEGER NOT NULL REFERENCES doklady(id) ON DELETE RESTRICT,
    datum TEXT NOT NULL,
    md_ucet TEXT NOT NULL REFERENCES uctova_osnova(cislo) ON DELETE RESTRICT,
    dal_ucet TEXT NOT NULL REFERENCES uctova_osnova(cislo) ON DELETE RESTRICT,
    castka INTEGER NOT NULL CHECK (castka > 0),
    popis TEXT,
    vytvoreno TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

-- Indexy
CREATE INDEX idx_doklady_partner_id ON doklady(partner_id);
CREATE INDEX idx_doklady_datum_vystaveni ON doklady(datum_vystaveni);
CREATE INDEX idx_ucetni_zaznamy_doklad_id ON ucetni_zaznamy(doklad_id);
CREATE INDEX idx_ucetni_zaznamy_datum ON ucetni_zaznamy(datum);
