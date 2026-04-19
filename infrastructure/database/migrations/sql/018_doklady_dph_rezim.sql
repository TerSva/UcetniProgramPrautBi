-- Přidání sloupce dph_rezim na doklady.
-- Default TUZEMSKO — stávající doklady jsou tuzemské.
ALTER TABLE doklady ADD COLUMN dph_rezim TEXT DEFAULT 'TUZEMSKO';
