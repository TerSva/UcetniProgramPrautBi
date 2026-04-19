-- Analytické účty pro reverse charge zaúčtování.
INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni, parent_kod, popis)
VALUES
    ('518.200', 'Služby z EU (reverse charge)', 'N', 1, '518', 'Náklady za služby přijaté z EU – přenesení daňové povinnosti'),
    ('321.002', 'Závazky z obch. vztahů – EU', 'P', 1, '321', 'Závazky za služby z EU (reverse charge)'),
    ('343.100', 'DPH na vstupu', 'A', 1, '343', 'DPH na vstupu – nárok na odpočet'),
    ('343.200', 'DPH na výstupu', 'P', 1, '343', 'DPH na výstupu – povinnost odvodu');
