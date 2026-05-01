-- 022_je_danovy.sql
-- Sloupec je_danovy pro účty třídy 5 (náklady) a 6 (výnosy).
-- 1 = daňově uznatelný, 0 = nedaňový, NULL = irrelevantní (A/P/Z účty).
-- Default 1 (daňový) — nedaňové se označí explicitně.

ALTER TABLE uctova_osnova ADD COLUMN je_danovy INTEGER;

-- ═══════════════════════════════════════
-- Označit existující N/V účty jako daňové (default)
-- ═══════════════════════════════════════
UPDATE uctova_osnova SET je_danovy = 1 WHERE typ IN ('N', 'V');

-- ═══════════════════════════════════════
-- Označit nedaňové účty + naplnit popis odkazem na § ZDP
-- ═══════════════════════════════════════
UPDATE uctova_osnova SET je_danovy = 0, popis = 'Nedaňový (§25/1/t ZDP)'
WHERE cislo = '513';

-- 543 (syntetický) zůstává jako parent — daňovost se řeší na analytikách
-- 544 (syntetický) zůstává jako parent — daňovost se řeší na analytikách
-- 548 (syntetický) zůstává jako parent — daňovost se řeší na analytikách
-- 549 (syntetický) zůstává jako parent — daňovost se řeší na analytikách

-- Pokud Tereza už má v DB 548.999 (ad-hoc nedaňový), označit jako nedaňový.
-- INSERT OR IGNORE neudělá nic; UPDATE pokud existuje.
UPDATE uctova_osnova SET je_danovy = 0, popis = 'Nedaňový'
WHERE cislo = '548.999';

-- ═══════════════════════════════════════
-- Nové analytiky pro 543/544/548/549 + nový 545
-- (INSERT OR IGNORE — Tereziny existující analytiky nepřepíše)
-- ═══════════════════════════════════════

-- 543 Dary
INSERT OR IGNORE INTO uctova_osnova
    (cislo, nazev, typ, je_aktivni, parent_kod, popis, je_danovy)
VALUES
    ('543.100', 'Dary daňově uznatelné', 'N', 1, '543',
     'Dary §20/8 ZDP — odčitatelná položka', 1),
    ('543.200', 'Dary daňově neuznatelné', 'N', 1, '543',
     'Nedaňový (§25/1/t ZDP)', 0);

-- 544 Smluvní pokuty a úroky z prodlení
INSERT OR IGNORE INTO uctova_osnova
    (cislo, nazev, typ, je_aktivni, parent_kod, popis, je_danovy)
VALUES
    ('544.100', 'Smluvní pokuty daňové (zaplacené)', 'N', 1, '544',
     'Daňové pouze pokud byly skutečně zaplaceny (§24/2/zi ZDP)', 1),
    ('544.200', 'Smluvní pokuty nedaňové (nezaplacené)', 'N', 1, '544',
     'Nedaňový — neuhrazené smluvní pokuty', 0);

-- 545 Ostatní pokuty a penále (nový syntetický účet)
INSERT OR IGNORE INTO uctova_osnova
    (cislo, nazev, typ, je_aktivni, popis, je_danovy)
VALUES
    ('545', 'Ostatní pokuty a penále', 'N', 1,
     'Nedaňový (§25/1/f ZDP) — sankce, úroky penále, pokuty FÚ', 0);

-- 548 Ostatní provozní náklady — analytiky
INSERT OR IGNORE INTO uctova_osnova
    (cislo, nazev, typ, je_aktivni, parent_kod, popis, je_danovy)
VALUES
    ('548.100', 'Ostatní provozní náklady daňové', 'N', 1, '548', NULL, 1),
    ('548.200', 'Ostatní provozní náklady nedaňové', 'N', 1, '548',
     'Nedaňový', 0);

-- 549 Manka a škody — analytiky
INSERT OR IGNORE INTO uctova_osnova
    (cislo, nazev, typ, je_aktivni, parent_kod, popis, je_danovy)
VALUES
    ('549.100', 'Manka a škody daňové (do výše náhrady)', 'N', 1, '549',
     'Daňové do výše náhrady (§24/2/l ZDP)', 1),
    ('549.200', 'Manka a škody nedaňové (nad náhradu)', 'N', 1, '549',
     'Nedaňový — část nad přijatou náhradu', 0);
