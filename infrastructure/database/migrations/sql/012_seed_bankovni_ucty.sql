-- Fáze 13: Seed data — bankovní účty + chybějící účty osnovy pro bankovní modul

-- Analytické účty 221.xxx (parent_kod = '221')
INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni, parent_kod) VALUES
    ('221.001', 'Bankovní účet — MONETA Money Bank', 'A', 1, '221'),
    ('221.002', 'Bankovní účet — Česká spořitelna', 'A', 1, '221'),
    ('221.003', 'Bankovní účet — Obecný', 'A', 1, '221');

-- Účty potřebné pro auto-zaúčtování bankovních transakcí
INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES
    ('568', 'Ostatní finanční náklady', 'N', 1),
    ('591', 'Daň z příjmů z běžné činnosti — splatná', 'N', 1),
    ('662', 'Úroky', 'V', 1),
    ('261', 'Peníze na cestě', 'A', 1);

-- Bankovní účty se zakládají uživatelem přes UI.
