-- 020_seed_osnova_praut_2025.sql
-- Kompletní účtová osnova pro PRAUT s.r.o. (mikro ÚJ, IČO 22545107).
-- Identifikovaná osoba DPH, 2 společníci (Martin 90%, Tomáš 10%).
-- INSERT OR IGNORE = přidá jen chybějící, stávající účty nezmění.

-- ═══════════════════════════════════════
-- Třída 0 — Dlouhodobý majetek
-- ═══════════════════════════════════════
INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES
    ('022', 'Hmotné movité věci', 'A', 1),
    ('082', 'Oprávky k hmotným movitým věcem', 'A', 1);

-- ═══════════════════════════════════════
-- Třída 3 — Pohledávky a závazky
-- ═══════════════════════════════════════
INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES
    ('314', 'Poskytnuté zálohy', 'A', 1);

INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni, parent_kod) VALUES
    ('321.001', 'Závazky CZK tuzemsko', 'P', 1, '321');

INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES
    ('331', 'Zaměstnanci', 'P', 1),
    ('336', 'Zúčtování se SP a ZP', 'P', 1),
    ('341', 'Daň z příjmů', 'P', 1),
    ('342', 'Ostatní přímé daně', 'P', 1),
    ('345', 'Ostatní daně a poplatky', 'P', 1);

INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES
    ('355', 'Ostatní pohledávky za společníky', 'A', 1);
INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni, parent_kod) VALUES
    ('355.001', 'Pohledávky za společníkem Martin Švanda', 'A', 1, '355'),
    ('355.002', 'Pohledávky za společníkem Tomáš Hůf', 'A', 1, '355');

INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES
    ('365', 'Ostatní závazky ke společníkům', 'P', 1);
INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni, parent_kod) VALUES
    ('365.001', 'Závazky ke společníkovi Martin Švanda', 'P', 1, '365'),
    ('365.002', 'Závazky ke společníkovi Tomáš Hůf', 'P', 1, '365');

INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES
    ('379', 'Jiné závazky', 'P', 1),
    ('381', 'Náklady příštích období', 'A', 1),
    ('395', 'Vnitřní zúčtování', 'A', 1);

-- ═══════════════════════════════════════
-- Třída 4 — Kapitálové účty
-- ═══════════════════════════════════════
INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES
    ('411', 'Základní kapitál', 'P', 1),
    ('413', 'Ostatní kapitálové fondy', 'P', 1),
    ('428', 'Nerozdělený zisk minulých let', 'P', 1),
    ('429', 'Neuhrazená ztráta minulých let', 'A', 1),
    ('431', 'Výsledek hospodaření ve schvalovacím řízení', 'P', 1);

-- ═══════════════════════════════════════
-- Třída 7 — Závěrkové účty
-- ═══════════════════════════════════════
INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES
    ('701', 'Počáteční účet rozvažný', 'Z', 1),
    ('702', 'Konečný účet rozvažný', 'Z', 1),
    ('710', 'Účet zisku a ztráty', 'Z', 1);

-- ═══════════════════════════════════════
-- Třída 5 — Náklady
-- ═══════════════════════════════════════
INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni, parent_kod) VALUES
    ('501.100', 'Drobný DHM do 80 000 Kč', 'N', 1, '501');

INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES
    ('502', 'Spotřeba energie', 'N', 1),
    ('504', 'Prodané zboží', 'N', 1),
    ('511', 'Opravy a udržování', 'N', 1),
    ('512', 'Cestovné', 'N', 1),
    ('513', 'Náklady na reprezentaci', 'N', 1);

INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni, parent_kod) VALUES
    ('518.300', 'Software a SaaS tuzemsko', 'N', 1, '518'),
    ('518.400', 'Ostatní služby tuzemsko', 'N', 1, '518');

INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES
    ('521', 'Mzdové náklady', 'N', 1),
    ('524', 'Zákonné sociální pojištění', 'N', 1),
    ('527', 'Zákonné sociální náklady', 'N', 1),
    ('538', 'Ostatní daně a poplatky', 'N', 1),
    ('543', 'Dary', 'N', 1),
    ('544', 'Smluvní pokuty a úroky z prodlení', 'N', 1),
    ('548', 'Ostatní provozní náklady', 'N', 1),
    ('549', 'Manka a škody', 'N', 1),
    ('563', 'Kurzové ztráty', 'N', 1);

-- ═══════════════════════════════════════
-- Třída 6 — Výnosy
-- ═══════════════════════════════════════
INSERT OR IGNORE INTO uctova_osnova (cislo, nazev, typ, je_aktivni) VALUES
    ('648', 'Ostatní provozní výnosy', 'V', 1),
    ('663', 'Kurzové zisky', 'V', 1),
    ('668', 'Ostatní finanční výnosy', 'V', 1);
