-- Fáze 15: Drop UNIQUE constraint on row_hash — allow legitimate duplicates.
-- Banks produce identical transactions (e.g., two ATM withdrawals same amount/day/VS).
-- row_hash retained as non-unique index for debug/audit.

DROP INDEX IF EXISTS idx_transakce_hash;
CREATE INDEX idx_transakce_hash ON bankovni_transakce(row_hash);
