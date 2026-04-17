"""SqliteOcrUploadRepository — CRUD pro OCR uploads."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from domain.ocr.ocr_upload import OcrUpload, StavUploadu
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class SqliteOcrUploadRepository:
    """Repository pro OCR uploads."""

    def __init__(self, uow: SqliteUnitOfWork) -> None:
        self._uow = uow

    @property
    def _conn(self) -> sqlite3.Connection:
        return self._uow.connection

    def add(self, upload: OcrUpload) -> OcrUpload:
        parsed_json = (
            json.dumps(upload.parsed_data, ensure_ascii=False)
            if upload.parsed_data else None
        )
        cursor = self._conn.execute(
            """INSERT INTO ocr_uploads
               (file_path, file_name, file_hash, mime_type, stav,
                ocr_text, ocr_method, ocr_confidence, parsed_data,
                vytvoreny_doklad_id, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                upload.file_path,
                upload.file_name,
                upload.file_hash,
                upload.mime_type,
                upload.stav.value,
                upload.ocr_text,
                upload.ocr_method,
                upload.ocr_confidence,
                parsed_json,
                upload.vytvoreny_doklad_id,
                upload.error,
            ),
        )
        upload.id = cursor.lastrowid
        return upload

    def get(self, upload_id: int) -> OcrUpload | None:
        row = self._conn.execute(
            "SELECT * FROM ocr_uploads WHERE id = ?", (upload_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_upload(row)

    def get_by_hash(self, file_hash: str) -> OcrUpload | None:
        row = self._conn.execute(
            "SELECT * FROM ocr_uploads WHERE file_hash = ?", (file_hash,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_upload(row)

    def update(self, upload: OcrUpload) -> None:
        parsed_json = (
            json.dumps(upload.parsed_data, ensure_ascii=False)
            if upload.parsed_data else None
        )
        self._conn.execute(
            """UPDATE ocr_uploads SET
                stav = ?, ocr_text = ?, ocr_method = ?,
                ocr_confidence = ?, parsed_data = ?,
                vytvoreny_doklad_id = ?, error = ?
               WHERE id = ?""",
            (
                upload.stav.value,
                upload.ocr_text,
                upload.ocr_method,
                upload.ocr_confidence,
                parsed_json,
                upload.vytvoreny_doklad_id,
                upload.error,
                upload.id,
            ),
        )

    def delete(self, upload_id: int) -> None:
        self._conn.execute(
            "DELETE FROM ocr_uploads WHERE id = ?", (upload_id,),
        )

    def list_by_stav(
        self, stav: StavUploadu | None = None,
    ) -> list[OcrUpload]:
        if stav is not None:
            rows = self._conn.execute(
                "SELECT * FROM ocr_uploads WHERE stav = ? ORDER BY id DESC",
                (stav.value,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM ocr_uploads ORDER BY id DESC",
            ).fetchall()
        return [self._row_to_upload(r) for r in rows]

    def count_by_stav(self, stav: StavUploadu) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM ocr_uploads WHERE stav = ?",
            (stav.value,),
        ).fetchone()
        return row[0] if row else 0

    def _row_to_upload(self, row: sqlite3.Row) -> OcrUpload:
        parsed_data = None
        if row["parsed_data"]:
            try:
                parsed_data = json.loads(row["parsed_data"])
            except json.JSONDecodeError:
                pass

        created_at = None
        if row["created_at"]:
            try:
                created_at = datetime.fromisoformat(row["created_at"])
            except ValueError:
                pass

        return OcrUpload(
            id=row["id"],
            file_path=row["file_path"],
            file_name=row["file_name"],
            file_hash=row["file_hash"],
            mime_type=row["mime_type"],
            stav=StavUploadu(row["stav"]),
            ocr_text=row["ocr_text"],
            ocr_method=row["ocr_method"],
            ocr_confidence=row["ocr_confidence"],
            parsed_data=parsed_data,
            vytvoreny_doklad_id=row["vytvoreny_doklad_id"],
            error=row["error"],
            created_at=created_at,
        )
