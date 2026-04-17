-- Fáze 10: Cizoměnové doklady — castka_mena + kurz na dokladu.
-- Sloupec mena už existuje v 001_init_schema.sql (DEFAULT 'CZK').

ALTER TABLE doklady ADD COLUMN castka_mena INTEGER;  -- haléře cizí měny (NULL pro CZK)
ALTER TABLE doklady ADD COLUMN kurz TEXT;             -- Decimal jako text pro přesnost (NULL pro CZK)
