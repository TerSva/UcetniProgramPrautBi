"""OcrInboxViewModel — stránka Nahrát doklady."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable

from domain.doklady.typy import DphRezim, Mena, TypDokladu
from domain.ocr.ocr_upload import StavUploadu
from domain.shared.money import Money
from services.commands.ocr_upload import OcrUploadCommand
from services.queries.ocr_inbox import OcrInboxItem, OcrInboxQuery


class OcrInboxViewModel:
    """ViewModel pro OCR inbox stránku."""

    def __init__(
        self,
        upload_cmd: OcrUploadCommand,
        inbox_query: OcrInboxQuery,
    ) -> None:
        self._upload_cmd = upload_cmd
        self._inbox_query = inbox_query

        self._items: list[OcrInboxItem] = []
        self._error: str | None = None

    @property
    def items(self) -> list[OcrInboxItem]:
        return self._items

    @property
    def zpracovane_items(self) -> list[OcrInboxItem]:
        return [i for i in self._items if i.stav == "zpracovany"]

    @property
    def schvalene_items(self) -> list[OcrInboxItem]:
        return [i for i in self._items if i.stav == "schvaleny"]

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def pocet_nezpracovanych(self) -> int:
        return len(self.zpracovane_items)

    def load(self) -> None:
        """Načte všechny položky inboxu."""
        try:
            self._items = self._inbox_query.execute()
            self._error = None
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__

    def upload_files(self, paths: list[Path]) -> list[int]:
        """Nahraje a zpracuje soubory. Vrátí upload_ids."""
        ids: list[int] = []
        for p in paths:
            try:
                uid = self._upload_cmd.upload_and_process(p)
                ids.append(uid)
            except Exception as exc:  # noqa: BLE001
                self._error = f"Chyba při nahrávání {p.name}: {exc}"
        self.load()
        return ids

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
        is_reverse_charge: bool = False,
    ) -> int | None:
        """Schválí upload a vytvoří doklad."""
        dph_rezim = (
            DphRezim.REVERSE_CHARGE if is_reverse_charge
            else DphRezim.TUZEMSKO
        )
        try:
            doklad_id = self._upload_cmd.approve(
                upload_id=upload_id,
                typ=typ,
                cislo=cislo,
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
            self._error = None
            self.load()
            return doklad_id
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
            return None

    def reject(self, upload_id: int) -> None:
        """Zamítne upload."""
        try:
            self._upload_cmd.reject(upload_id)
            self._error = None
            self.load()
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__

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
        """Hromadné schválení."""
        try:
            ids = self._upload_cmd.batch_approve(
                upload_ids=upload_ids,
                typ=typ,
                cislo_prefix=cislo_prefix,
                datum_vystaveni=datum_vystaveni,
                partner_id=partner_id,
                popis_prefix=popis_prefix,
                k_doreseni=k_doreseni,
            )
            self._error = None
            self.load()
            return ids
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
            return []

    def can_batch_approve(self) -> bool:
        """True pokud existují zpracované položky."""
        return len(self.zpracovane_items) > 0
