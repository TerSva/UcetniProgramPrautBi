-- 026_zalohove_faktury.sql
-- Podpora zálohových faktur (ZF):
--   1) Účet 324 — Přijaté zálohy od odběratelů (pasiva)
--   2) Analytiky 314.001 a 324.001 (aby ZF nešly na syntetiku)
--   3) Sloupec doklady.je_vystavena (1 = vystavená pro odběratele,
--      0 = přijatá od dodavatele, NULL = irrelevant pro non-ZF typy)

-- Účet 324 — pasivní účet pro vystavené zálohy
INSERT OR IGNORE INTO uctova_osnova
    (cislo, nazev, typ, je_aktivni)
VALUES
    ('324', 'Přijaté zálohy od odběratelů', 'P', 1);

-- Analytiky pro 314 a 324 — ZF se účtují na analytiky, ne syntetiku
INSERT OR IGNORE INTO uctova_osnova
    (cislo, nazev, typ, je_aktivni, parent_kod, popis)
VALUES
    ('314.001', 'Poskytnuté zálohy CZK', 'A', 1, '314',
     'Záloha zaplacená dodavateli (přijatá ZF)'),
    ('324.001', 'Přijaté zálohy CZK', 'P', 1, '324',
     'Záloha přijatá od odběratele (vystavená ZF)');

-- Sloupec doklady.je_vystavena — pro ZF nutné rozlišit směr.
-- NULL pro non-ZF typy (FV/FP/PD/ID/OD/BV — směr derivovatelný z typu).
ALTER TABLE doklady ADD COLUMN je_vystavena INTEGER;
