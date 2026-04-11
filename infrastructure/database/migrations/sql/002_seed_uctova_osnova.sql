-- 002_seed_uctova_osnova.sql
-- Minimální seed účtové osnovy pro MVP.
-- 9 účtů: dost na FV, FP, hotovostní/bankovní úhrady.

INSERT INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES
    -- Aktiva
    ('211', 'Pokladna', 'A', 1),
    ('221', 'Bankovní účty', 'A', 1),
    ('311', 'Pohledávky z obchodních vztahů', 'A', 1),
    -- Pasiva
    ('321', 'Závazky z obchodních vztahů', 'P', 1),
    ('343', 'Daň z přidané hodnoty', 'P', 1),
    -- Náklady
    ('501', 'Spotřeba materiálu', 'N', 1),
    ('518', 'Ostatní služby', 'N', 1),
    -- Výnosy
    ('601', 'Tržby za vlastní výrobky', 'V', 1),
    ('602', 'Tržby z prodeje služeb', 'V', 1);
