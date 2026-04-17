-- 008_dph_podani.sql
-- Stav podání DPH přiznání za měsíc.

CREATE TABLE dph_podani (
    rok INTEGER NOT NULL,
    mesic INTEGER NOT NULL CHECK (mesic BETWEEN 1 AND 12),
    podano INTEGER NOT NULL DEFAULT 0 CHECK (podano IN (0, 1)),
    datum_podani TEXT,
    poznamka TEXT,
    PRIMARY KEY (rok, mesic)
);
