-- Analytika 701.100 — Počáteční účet rozvažný.
-- Používá se při generování otevíracího dokladu ID-{rok}-PS.

INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, parent_kod, je_aktivni)
VALUES ('701.100', 'Počáteční účet rozvažný', 'Z', '701', 1);
