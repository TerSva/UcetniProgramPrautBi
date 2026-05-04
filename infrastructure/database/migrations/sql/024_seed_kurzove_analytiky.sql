-- 024_seed_kurzove_analytiky.sql
-- Pre-seed analytik pro kurzové rozdíly (563.100, 663.100).
-- Tyto analytiky používá SparovatPlatbuDoklademCommand když existují
-- (preference analytika nad syntetickým 563/663) — zajistí se tak
-- konzistentní účtování napříč instalacemi.
--
-- INSERT OR IGNORE: pokud Tereza už má v DB ručně vytvořené, nepřepisuje.

INSERT OR IGNORE INTO uctova_osnova
    (cislo, nazev, typ, je_aktivni, parent_kod, je_danovy, popis)
VALUES
    ('563.100', 'Kurzové ztráty bankovní', 'N', 1, '563', 1, NULL),
    ('663.100', 'Kurzové zisky bankovní', 'V', 1, '663', 1, NULL);
