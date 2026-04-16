-- 006_partneri_v2.sql
-- Fáze 9: Partneři — recreate tabulky s novým schématem.
--
-- Původní partneri tabulka (001_init_schema) měla jiné sloupce:
--   typ IN ('dodavatel','odberatel','oboji','zamestnanec','urad')
--   ulice, mesto, psc, stat (rozbitá adresa)
--   chyběly: bankovni_ucet, email, telefon, poznamka, je_aktivni,
--            podil_procent, ucet_pohledavka, ucet_zavazek
--
-- Protože tabulka dosud neměla žádná data (Partneři entita neexistovala),
-- je bezpečné ji dropnout a vytvořit znovu.

-- Nejdřív odstraň FK constraint z doklady (SQLite neumí ALTER DROP CONSTRAINT,
-- ale partner_id sloupec zůstane — FK se jen nevynutí na staré tabulce).
-- Po recreate se FK obnoví na novou tabulku se stejným názvem.

DROP TABLE IF EXISTS partneri;

CREATE TABLE partneri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazev TEXT NOT NULL,
    kategorie TEXT NOT NULL
        CHECK (kategorie IN ('odberatel', 'dodavatel', 'spolecnik', 'kombinovany')),
    ico TEXT,
    dic TEXT,
    adresa TEXT,
    bankovni_ucet TEXT,
    email TEXT,
    telefon TEXT,
    poznamka TEXT,
    je_aktivni INTEGER NOT NULL DEFAULT 1 CHECK (je_aktivni IN (0, 1)),
    podil_procent REAL,
    ucet_pohledavka TEXT,
    ucet_zavazek TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_partneri_kategorie ON partneri(kategorie);
CREATE INDEX idx_partneri_ico ON partneri(ico) WHERE ico IS NOT NULL;
CREATE UNIQUE INDEX idx_partneri_ico_unique
    ON partneri(ico)
    WHERE ico IS NOT NULL AND je_aktivni = 1;
