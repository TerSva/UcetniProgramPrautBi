-- Příznak uzavíracího (závěrkového) dokladu.
-- Doklady s je_zaverka=1 (např. ID-{rok}-Z1, Z2, Z3) jsou součástí roční
-- uzávěrky, ne běžných obratů. VykazyQuery je defaultně vynechává
-- (Rozvaha, VZZ, Předvaha, Nedaňové, DPH přehled) a zahrnuje pouze
-- v Hlavní knize a v drilldownech pro audit.

ALTER TABLE doklady ADD COLUMN je_zaverka INTEGER NOT NULL DEFAULT 0;
