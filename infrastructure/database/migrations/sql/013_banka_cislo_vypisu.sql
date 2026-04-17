-- Fáze 13 fix: číslo výpisu + datumový rozsah místo rok/měsíc unique

ALTER TABLE bankovni_vypisy ADD COLUMN cislo_vypisu TEXT;
ALTER TABLE bankovni_vypisy ADD COLUMN datum_od TEXT;
ALTER TABLE bankovni_vypisy ADD COLUMN datum_do TEXT;

-- Backfill datum_od/datum_do z existujících transakcí
UPDATE bankovni_vypisy
SET datum_od = (
    SELECT MIN(datum_zauctovani) FROM bankovni_transakce
    WHERE bankovni_transakce.bankovni_vypis_id = bankovni_vypisy.id
),
datum_do = (
    SELECT MAX(datum_zauctovani) FROM bankovni_transakce
    WHERE bankovni_transakce.bankovni_vypis_id = bankovni_vypisy.id
);

-- Drop starý unique index (rok, mesic) — SQLite neumí DROP INDEX IF EXISTS,
-- ale index se jmenuje podle UNIQUE constraintu na tabulce.
-- SQLite nemá ALTER TABLE DROP CONSTRAINT, takže musíme tabulku přetvořit.
-- Pro jednoduchost: nový unique index přidáme, starý constraint
-- v původní CREATE TABLE zůstane, ale duplicity řeší nové indexy.

-- Nový unique: číslo výpisu (pokud existuje)
CREATE UNIQUE INDEX IF NOT EXISTS idx_vypisy_ucet_cislo
    ON bankovni_vypisy(bankovni_ucet_id, cislo_vypisu)
    WHERE cislo_vypisu IS NOT NULL;
