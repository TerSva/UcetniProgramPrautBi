"""OcrUploadCommand — upload, OCR zpracování, schválení/zamítnutí."""

from __future__ import annotations

import hashlib
import shutil
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

from domain.doklady.doklad import Doklad
from domain.doklady.typy import DphRezim, Mena, TypDokladu
from domain.ocr.ocr_upload import OcrUpload, StavUploadu
from domain.shared.money import Money
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from infrastructure.database.repositories.ocr_upload_repository import (
    SqliteOcrUploadRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from infrastructure.ocr.invoice_parser import InvoiceParser, ParsedInvoice
from infrastructure.ocr.ocr_engine import OcrEngine


#: Adresář pro uložení nahraných souborů.
_DEFAULT_UPLOAD_DIR = Path("uploads") / "ocr_inbox"


class OcrUploadCommand:
    """Správa OCR uploadů — nahrání, zpracování, schválení."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        upload_dir: Path | None = None,
        ocr_engine: OcrEngine | None = None,
        parser: InvoiceParser | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._upload_dir = upload_dir or _DEFAULT_UPLOAD_DIR
        self._ocr = ocr_engine or OcrEngine()
        self._parser = parser or InvoiceParser()

    def upload_file(self, source_path: Path) -> int:
        """Nahraje soubor, spočítá hash, vytvoří OcrUpload záznam.

        Returns:
            ID nového uploadu.
        """
        # Compute hash
        file_hash = self._compute_hash(source_path)

        # Check duplicate
        uow = self._uow_factory()
        with uow:
            repo = SqliteOcrUploadRepository(uow)
            existing = repo.get_by_hash(file_hash)
            if existing is not None:
                return existing.id

            # Copy file to upload dir
            self._upload_dir.mkdir(parents=True, exist_ok=True)
            suffix = source_path.suffix.lower()
            dest = self._upload_dir / f"{file_hash}{suffix}"
            shutil.copy2(source_path, dest)

            # Detect mime type
            mime = self._detect_mime(suffix)

            upload = OcrUpload(
                file_path=str(dest),
                file_name=source_path.name,
                file_hash=file_hash,
                mime_type=mime,
                stav=StavUploadu.NAHRANY,
            )
            repo.add(upload)
            uow.commit()
            return upload.id

    def process_ocr(self, upload_id: int) -> None:
        """Spustí OCR + parsing na nahraném souboru."""
        uow = self._uow_factory()
        with uow:
            repo = SqliteOcrUploadRepository(uow)
            upload = repo.get(upload_id)
            if upload is None:
                return
            if upload.stav != StavUploadu.NAHRANY:
                return

            file_path = Path(upload.file_path)
            if not file_path.exists():
                upload.oznac_chybu(f"Soubor nenalezen: {file_path}")
                repo.update(upload)
                uow.commit()
                return

            # Run OCR
            result = self._ocr.extract_text(file_path)

            if result.method == "failed" or not result.text.strip():
                upload.oznac_chybu("OCR nepodařilo extrahovat text.")
                repo.update(upload)
                uow.commit()
                return

            # Parse invoice
            parsed = self._parser.parse(result.text)
            upload.zpracuj(
                ocr_text=result.text,
                ocr_method=result.method,
                ocr_confidence=result.confidence,
                parsed_data=parsed.to_dict(),
            )
            repo.update(upload)
            uow.commit()

    def upload_and_process(self, source_path: Path) -> int:
        """Nahraje a ihned zpracuje soubor. Vrátí upload_id."""
        upload_id = self.upload_file(source_path)
        self.process_ocr(upload_id)
        return upload_id

    def approve(
        self,
        upload_id: int,
        typ: TypDokladu,
        cislo: str,
        datum_vystaveni: date,
        castka_celkem: Money,
        partner_id: int | None = None,
        popis: str | None = None,
        datum_splatnosti: date | None = None,
        mena: Mena = Mena.CZK,
        castka_mena: Money | None = None,
        kurz: Decimal | None = None,
        k_doreseni: bool = False,
        variabilni_symbol: str | None = None,
        dph_rezim: DphRezim = DphRezim.TUZEMSKO,
    ) -> int:
        """Vytvoří doklad z uploadu. Vrátí doklad_id."""
        uow = self._uow_factory()
        with uow:
            repo = SqliteOcrUploadRepository(uow)
            drepo = SqliteDokladyRepository(uow)

            upload = repo.get(upload_id)
            if upload is None:
                raise ValueError(f"Upload {upload_id} neexistuje.")

            doklad = Doklad(
                cislo=cislo,
                typ=typ,
                datum_vystaveni=datum_vystaveni,
                castka_celkem=castka_celkem,
                partner_id=partner_id,
                popis=popis,
                datum_splatnosti=datum_splatnosti,
                mena=mena,
                castka_mena=castka_mena,
                kurz=kurz,
                k_doreseni=k_doreseni,
                variabilni_symbol=variabilni_symbol,
                dph_rezim=dph_rezim,
            )
            drepo.add(doklad)
            loaded = drepo.get_by_cislo(cislo)

            upload.schval(loaded.id)
            repo.update(upload)
            uow.commit()
            return loaded.id

    def reject(self, upload_id: int) -> None:
        """Zamítne upload."""
        uow = self._uow_factory()
        with uow:
            repo = SqliteOcrUploadRepository(uow)
            upload = repo.get(upload_id)
            if upload is None:
                return
            upload.zamitni()
            repo.update(upload)
            uow.commit()

    def batch_approve(
        self,
        upload_ids: list[int],
        typ: TypDokladu,
        cislo_prefix: str,
        datum_vystaveni: date,
        partner_id: int | None = None,
        popis_prefix: str = "",
        k_doreseni: bool = False,
    ) -> list[int]:
        """Hromadné schválení více uploadů. Vrátí seznam doklad_ids."""
        created: list[int] = []
        for i, uid in enumerate(upload_ids, start=1):
            uow = self._uow_factory()
            with uow:
                repo = SqliteOcrUploadRepository(uow)
                drepo = SqliteDokladyRepository(uow)

                upload = repo.get(uid)
                if upload is None or upload.stav != StavUploadu.ZPRACOVANY:
                    continue

                # Částka, datum, popis z parsed_data
                castka = Money(100)  # default
                parsed_datum = datum_vystaveni
                popis = popis_prefix
                vs: str | None = None
                dph_r = DphRezim.TUZEMSKO
                if upload.parsed_data:
                    parsed = ParsedInvoice.from_dict(upload.parsed_data)
                    if parsed.castka_celkem:
                        castka = parsed.castka_celkem
                    if parsed.datum_vystaveni:
                        parsed_datum = parsed.datum_vystaveni
                    if parsed.dodavatel_nazev and parsed.cislo_dokladu:
                        popis = f"{parsed.dodavatel_nazev} \u2013 {parsed.cislo_dokladu}"
                    elif parsed.cislo_dokladu:
                        popis = f"{popis_prefix} {parsed.cislo_dokladu}".strip()
                    vs = parsed.variabilni_symbol
                    if parsed.is_reverse_charge:
                        dph_r = DphRezim.REVERSE_CHARGE

                rok = parsed_datum.year
                cislo = f"{cislo_prefix.replace(str(datum_vystaveni.year), str(rok))}-{i:03d}"
                if drepo.existuje_cislo(cislo):
                    continue

                doklad = Doklad(
                    cislo=cislo,
                    typ=typ,
                    datum_vystaveni=parsed_datum,
                    castka_celkem=castka,
                    partner_id=partner_id,
                    popis=popis or None,
                    k_doreseni=k_doreseni,
                    variabilni_symbol=vs,
                    dph_rezim=dph_r,
                )
                drepo.add(doklad)
                loaded = drepo.get_by_cislo(cislo)

                upload.schval(loaded.id)
                repo.update(upload)
                uow.commit()
                created.append(loaded.id)

        return created

    @staticmethod
    def _compute_hash(path: Path) -> str:
        """SHA-256 hash souboru."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _detect_mime(suffix: str) -> str:
        """Detekce MIME typu podle přípony."""
        return {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
        }.get(suffix, "application/octet-stream")
