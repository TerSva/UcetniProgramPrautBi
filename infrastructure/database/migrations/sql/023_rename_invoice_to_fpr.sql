-- 023_rename_invoice_to_fpr.sql
-- Přejmenuj doklad s názvem "Invoice" (importovaný EU faktura) na novou
-- číselnou řadu FPR — reverse charge faktury.
-- Bezpečné: pokud doklad neexistuje, UPDATE nic neudělá; pokud už má
-- FPR-… cislo, ponechá ho beze změny.

UPDATE doklady
SET cislo = 'FPR-' || strftime('%Y', datum_vystaveni) || '-001'
WHERE LOWER(cislo) = 'invoice'
  AND typ = 'FP'
  AND dph_rezim = 'REVERSE_CHARGE'
  AND NOT EXISTS (
      SELECT 1 FROM doklady d2
      WHERE d2.cislo = 'FPR-' || strftime('%Y', doklady.datum_vystaveni) || '-001'
        AND d2.id != doklady.id
  );
