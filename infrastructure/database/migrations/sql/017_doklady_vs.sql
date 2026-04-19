-- 017_doklady_vs.sql
-- Variabilní symbol jako prvotřídní pole na dokladu.

ALTER TABLE doklady ADD COLUMN variabilni_symbol TEXT;
CREATE INDEX idx_doklady_vs ON doklady(variabilni_symbol);
