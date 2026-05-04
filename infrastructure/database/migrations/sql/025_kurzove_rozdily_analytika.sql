-- 024_kurzove_rozdily_analytika.sql
-- Převede existující kurzové zápisy ze syntetických účtů 563/663 na
-- analytiky (563.x / 663.x), pokud v osnově existují aktivní analytiky.
-- Idempotentní: pokud analytika neexistuje, zápis zůstane na syntetickém.
-- Pokud byl zápis už dříve na analytice, neměníme.
--
-- Důvod: před opravou v sparovat_platbu_dokladem.py (commit d823d53)
-- se kurzové ztráty/zisky účtovaly hardcoded na "563"/"663" místo
-- na uživatelovu analytiku (např. "563.100"). Tím se rozbila analytická
-- evidence v hlavní knize a předvaze.

-- 563 → první aktivní analytika 563.x (kurzová ztráta)
UPDATE ucetni_zaznamy
SET md_ucet = (
    SELECT cislo FROM uctova_osnova
    WHERE parent_kod = '563' AND je_aktivni = 1
    ORDER BY cislo ASC LIMIT 1
)
WHERE md_ucet = '563'
  AND popis LIKE 'Kurzov%'
  AND EXISTS (
      SELECT 1 FROM uctova_osnova
      WHERE parent_kod = '563' AND je_aktivni = 1
  );

-- 663 → první aktivní analytika 663.x (kurzový zisk)
UPDATE ucetni_zaznamy
SET dal_ucet = (
    SELECT cislo FROM uctova_osnova
    WHERE parent_kod = '663' AND je_aktivni = 1
    ORDER BY cislo ASC LIMIT 1
)
WHERE dal_ucet = '663'
  AND popis LIKE 'Kurzov%'
  AND EXISTS (
      SELECT 1 FROM uctova_osnova
      WHERE parent_kod = '663' AND je_aktivni = 1
  );
