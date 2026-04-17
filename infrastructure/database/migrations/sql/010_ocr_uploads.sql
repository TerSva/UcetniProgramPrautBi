-- 010_ocr_uploads.sql
-- OCR inbox: upload + parsing + schválení dokladu.

CREATE TABLE ocr_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    stav TEXT NOT NULL CHECK (stav IN ('nahrany', 'zpracovany', 'schvaleny', 'zamitnuty')),
    ocr_text TEXT,
    ocr_method TEXT,
    ocr_confidence INTEGER,
    parsed_data TEXT,
    vytvoreny_doklad_id INTEGER REFERENCES doklady(id),
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_ocr_stav ON ocr_uploads(stav);
CREATE UNIQUE INDEX idx_ocr_hash ON ocr_uploads(file_hash);
