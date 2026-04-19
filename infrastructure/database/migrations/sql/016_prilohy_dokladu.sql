-- 016_prilohy_dokladu.sql
-- Přílohy (PDF soubory) připojené k dokladům. Vztah 1:N.

CREATE TABLE prilohy_dokladu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doklad_id INTEGER NOT NULL,
    nazev_souboru TEXT NOT NULL,
    relativni_cesta TEXT NOT NULL,
    velikost_bytes INTEGER NOT NULL,
    mime_type TEXT NOT NULL,
    vytvoreno TIMESTAMP NOT NULL,

    FOREIGN KEY (doklad_id) REFERENCES doklady(id) ON DELETE CASCADE
);

CREATE INDEX idx_prilohy_doklad ON prilohy_dokladu(doklad_id);
