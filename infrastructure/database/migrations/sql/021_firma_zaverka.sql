-- 021_firma_zaverka.sql
-- Rozšíření firma tabulky o pole pro účetní závěrku (minimální příloha
-- + cover formulář 25 5404).

ALTER TABLE firma ADD COLUMN predmet_cinnosti TEXT;
ALTER TABLE firma ADD COLUMN prumerny_pocet_zamestnancu INTEGER NOT NULL DEFAULT 0;
ALTER TABLE firma ADD COLUMN zpusob_oceneni TEXT NOT NULL DEFAULT 'pořizovacími cenami';
ALTER TABLE firma ADD COLUMN odpisovy_plan TEXT NOT NULL DEFAULT 'lineární';
ALTER TABLE firma ADD COLUMN statutarni_organ TEXT;
