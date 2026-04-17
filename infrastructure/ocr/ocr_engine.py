"""OcrEngine — extrakce textu z PDF a obrázků.

Preferuje text-layer (pdfplumber), fallback na Tesseract OCR.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OcrResult:
    """Výsledek OCR extrakce."""

    text: str
    method: Literal["pdf_text", "tesseract", "failed"]
    confidence: int  # 0-100


class OcrEngine:
    """Extrahuje text z PDF/obrázku."""

    #: Minimální délka textu pro uznání PDF text-layer.
    MIN_TEXT_LENGTH = 50

    def extract_text(self, file_path: Path) -> OcrResult:
        """Extrahuje text ze souboru."""
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            text = self._try_pdf_text(file_path)
            if text and len(text.strip()) >= self.MIN_TEXT_LENGTH:
                return OcrResult(
                    text=text.strip(), method="pdf_text", confidence=100,
                )
            return self._tesseract_pdf(file_path)
        elif suffix in (".jpg", ".jpeg", ".png"):
            return self._tesseract_image(file_path)
        return OcrResult(text="", method="failed", confidence=0)

    def _try_pdf_text(self, path: Path) -> str:
        """Extrakce textu přes pdfplumber (digital-born PDFs)."""
        try:
            import pdfplumber
            texts: list[str] = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        texts.append(page_text)
            return "\n".join(texts)
        except Exception as exc:
            logger.warning("pdfplumber failed for %s: %s", path, exc)
            return ""

    def _tesseract_pdf(self, path: Path) -> OcrResult:
        """PDF → rasterize → Tesseract OCR."""
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(str(path), dpi=300, first_page=1, last_page=5)
            texts: list[str] = []
            total_conf = 0
            for img in images:
                result = self._run_tesseract(img)
                texts.append(result.text)
                total_conf += result.confidence
            avg_conf = total_conf // max(len(images), 1)
            return OcrResult(
                text="\n".join(texts).strip(),
                method="tesseract",
                confidence=avg_conf,
            )
        except Exception as exc:
            logger.warning("Tesseract PDF failed for %s: %s", path, exc)
            return OcrResult(text="", method="failed", confidence=0)

    def _tesseract_image(self, path: Path) -> OcrResult:
        """Obrázek → Tesseract OCR."""
        try:
            from PIL import Image
            img = Image.open(path)
            return self._run_tesseract(img)
        except Exception as exc:
            logger.warning("Tesseract image failed for %s: %s", path, exc)
            return OcrResult(text="", method="failed", confidence=0)

    def _run_tesseract(self, image: object) -> OcrResult:
        """Spustí Tesseract na PIL Image."""
        try:
            import pytesseract
            # Extrakce s confidence daty
            data = pytesseract.image_to_data(
                image, lang="ces+eng", output_type=pytesseract.Output.DICT,
            )
            # Confidence průměr (přes slova s konf. > 0)
            confs = [
                int(c) for c in data.get("conf", [])
                if str(c).lstrip("-").isdigit() and int(c) > 0
            ]
            avg_conf = sum(confs) // max(len(confs), 1) if confs else 0

            text = pytesseract.image_to_string(image, lang="ces+eng")
            return OcrResult(
                text=text.strip(), method="tesseract", confidence=avg_conf,
            )
        except Exception as exc:
            logger.warning("Tesseract run failed: %s", exc)
            return OcrResult(text="", method="failed", confidence=0)
