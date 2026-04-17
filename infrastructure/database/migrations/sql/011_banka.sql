-- Fáze 13: Bankovní modul — účty, výpisy, transakce

CREATE TABLE bankovni_ucty (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazev TEXT NOT NULL,
    cislo_uctu TEXT NOT NULL,
    ucet_kod TEXT NOT NULL,
    format_csv TEXT NOT NULL DEFAULT 'obecny',
    mena TEXT NOT NULL DEFAULT 'CZK',
    je_aktivni INTEGER NOT NULL DEFAULT 1,
    poznamka TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE bankovni_vypisy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bankovni_ucet_id INTEGER NOT NULL REFERENCES bankovni_ucty(id),
    rok INTEGER NOT NULL,
    mesic INTEGER NOT NULL CHECK (mesic BETWEEN 1 AND 12),
    pocatecni_stav INTEGER NOT NULL,
    konecny_stav INTEGER NOT NULL,
    pdf_path TEXT NOT NULL,
    csv_path TEXT,
    bv_doklad_id INTEGER NOT NULL REFERENCES doklady(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(bankovni_ucet_id, rok, mesic)
);

CREATE TABLE bankovni_transakce (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bankovni_vypis_id INTEGER NOT NULL REFERENCES bankovni_vypisy(id),
    datum_transakce TEXT NOT NULL,
    datum_zauctovani TEXT NOT NULL,
    castka INTEGER NOT NULL,
    smer TEXT NOT NULL CHECK (smer IN ('P', 'V')),
    variabilni_symbol TEXT,
    konstantni_symbol TEXT,
    specificky_symbol TEXT,
    protiucet TEXT,
    popis TEXT,
    stav TEXT NOT NULL DEFAULT 'nesparovano'
        CHECK (stav IN ('nesparovano', 'sparovano', 'auto_zauctovano', 'ignorovano')),
    sparovany_doklad_id INTEGER REFERENCES doklady(id),
    ucetni_zapis_id INTEGER,
    row_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_transakce_vypis ON bankovni_transakce(bankovni_vypis_id);
CREATE INDEX idx_transakce_stav ON bankovni_transakce(stav);
CREATE INDEX idx_transakce_zauctovani ON bankovni_transakce(datum_zauctovani);
CREATE INDEX idx_transakce_vs ON bankovni_transakce(variabilni_symbol)
    WHERE variabilni_symbol IS NOT NULL;
CREATE UNIQUE INDEX idx_transakce_hash ON bankovni_transakce(row_hash);
