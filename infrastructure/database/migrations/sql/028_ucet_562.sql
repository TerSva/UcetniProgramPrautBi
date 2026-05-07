-- Účet 562 — Úroky (placené úroky z půjček apod.).
-- Synteticky účet, analytiky 562.xxx si uživatel vytvoří dle potřeby.

INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni)
VALUES ('562', 'Úroky', 'N', 1);
