"""PartneriViewModel — prezentační stav pro stránku Partneři.

Pure Python, žádný Qt import.
"""

from __future__ import annotations

from typing import Protocol

from domain.partneri.partner import KategoriePartnera
from services.queries.partneri_list import PartneriListItem
from ui.dialogs.partner_dialog import PartnerDialogResult


class _ListQuery(Protocol):
    def execute(
        self,
        kategorie: KategoriePartnera | None = None,
        jen_aktivni: bool = True,
    ) -> list[PartneriListItem]: ...


class _ManageCommand(Protocol):
    def create(self, **kwargs) -> object: ...
    def update(self, partner_id: int, **kwargs) -> None: ...
    def deactivate(self, partner_id: int) -> None: ...


class PartneriViewModel:
    """ViewModel pro stránku Partneři."""

    def __init__(
        self,
        query: _ListQuery,
        command: _ManageCommand,
    ) -> None:
        self._query = query
        self._command = command
        self._items: list[PartneriListItem] = []
        self._error: str | None = None

    @property
    def items(self) -> list[PartneriListItem]:
        return self._items

    @property
    def error(self) -> str | None:
        return self._error

    def load(
        self, kategorie: KategoriePartnera | None = None,
    ) -> None:
        try:
            self._items = self._query.execute(kategorie=kategorie)
            self._error = None
        except Exception as exc:
            self._items = []
            self._error = str(exc) or exc.__class__.__name__

    def create(self, data: PartnerDialogResult) -> bool:
        try:
            self._command.create(
                nazev=data.nazev,
                kategorie=data.kategorie,
                ico=data.ico,
                dic=data.dic,
                adresa=data.adresa,
                bankovni_ucet=data.bankovni_ucet,
                email=data.email,
                telefon=data.telefon,
                poznamka=data.poznamka,
                podil_procent=data.podil_procent,
                ucet_pohledavka=data.ucet_pohledavka,
                ucet_zavazek=data.ucet_zavazek,
            )
            self._error = None
            return True
        except Exception as exc:
            self._error = str(exc) or exc.__class__.__name__
            return False

    def update(self, partner_id: int, data: PartnerDialogResult) -> bool:
        try:
            self._command.update(
                partner_id,
                nazev=data.nazev,
                kategorie=data.kategorie,
                ico=data.ico,
                dic=data.dic,
                adresa=data.adresa,
                bankovni_ucet=data.bankovni_ucet,
                email=data.email,
                telefon=data.telefon,
                poznamka=data.poznamka,
                podil_procent=data.podil_procent,
                ucet_pohledavka=data.ucet_pohledavka,
                ucet_zavazek=data.ucet_zavazek,
            )
            self._error = None
            return True
        except Exception as exc:
            self._error = str(exc) or exc.__class__.__name__
            return False

    def deactivate(self, partner_id: int) -> bool:
        try:
            self._command.deactivate(partner_id)
            self._error = None
            return True
        except Exception as exc:
            self._error = str(exc) or exc.__class__.__name__
            return False
