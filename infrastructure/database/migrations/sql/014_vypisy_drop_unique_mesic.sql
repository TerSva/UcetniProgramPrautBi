-- Fáze 14: Odstraň starý UNIQUE(bankovni_ucet_id, rok, mesic) constraint.
-- SQLite neumí ALTER TABLE DROP CONSTRAINT — musíme tabulku přetvořit.

PRAGMA foreign_keys = OFF;

CREATE TABLE bankovni_vypisy_new (
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
    cislo_vypisu TEXT,
    datum_od TEXT,
    datum_do TEXT
);

INSERT INTO bankovni_vypisy_new
    (id, bankovni_ucet_id, rok, mesic, pocatecni_stav, konecny_stav,
     pdf_path, csv_path, bv_doklad_id, created_at, cislo_vypisu, datum_od, datum_do)
SELECT id, bankovni_ucet_id, rok, mesic, pocatecni_stav, konecny_stav,
       pdf_path, csv_path, bv_doklad_id, created_at, cislo_vypisu, datum_od, datum_do
FROM bankovni_vypisy;

DROP TABLE bankovni_vypisy;

ALTER TABLE bankovni_vypisy_new RENAME TO bankovni_vypisy;

-- Znovu vytvoř index na cislo_vypisu (partial unique)
-- Znovu vytvoř index na cislo_vypisu (partial unique)
CREATE UNIQUE INDEX IF NOT EXISTS idx_vypisy_ucet_cislo
    ON bankovni_vypisy(bankovni_ucet_id, cislo_vypisu)
    WHERE cislo_vypisu IS NOT NULL;

PRAGMA foreign_keys = ON;
