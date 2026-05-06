"""DokladDetailViewModel — prezentační stav pro detail dialog.

Pure Python, žádný Qt import. Drží aktuální DTO dokladu a modální „režim"
(read-only vs. editace). Vystavuje computed properties typu ``can_edit``,
``can_storno`` atd., aby dialog zapínal/vypínal tlačítka jednotně.

Akce:
    * ``enter_edit()`` / ``cancel_edit()`` — přepíná edit mode, drží draft
      hodnoty popisu + splatnosti, které uživatelka může kdykoli zrušit.
    * ``save_edit()`` — posle draft do ``DokladActionsCommand``.
    * ``stornovat() / smazat() / oznac_k_doreseni() / dores()`` — deleguje
      na actions command; při úspěchu refreshne ``doklad`` z návratového DTO.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol

from domain.doklady.typy import Mena, StavDokladu
from domain.shared.money import Money
from services.queries.doklady_list import DokladyListItem


class _DokladActionsCommand(Protocol):
    def stornovat(
        self,
        doklad_id: int,
        datum: date | None = None,
        poznamka: str | None = None,
    ) -> DokladyListItem: ...
    def smazat(self, doklad_id: int) -> None: ...
    def oznac_k_doreseni(
        self, doklad_id: int, poznamka: str | None = None,
    ) -> DokladyListItem: ...
    def dores(self, doklad_id: int) -> DokladyListItem: ...
    def upravit_popis_a_splatnost(
        self,
        doklad_id: int,
        popis: str | None,
        splatnost: date | None,
        partner_id: object = ...,
        datum_vystaveni: date | None = None,
    ) -> DokladyListItem: ...
    def upravit_pole_novy_dokladu(
        self,
        doklad_id: int,
        popis: str | None,
        splatnost: date | None,
        k_doreseni: bool,
        poznamka_doreseni: str | None,
        partner_id: object = ...,
        datum_vystaveni: date | None = None,
    ) -> DokladyListItem: ...


class DokladDetailViewModel:
    """ViewModel pro detail dokladu."""

    def __init__(
        self,
        doklad: DokladyListItem,
        actions_command: _DokladActionsCommand,
    ) -> None:
        self._doklad = doklad
        self._actions = actions_command
        self._edit_mode: bool = False
        self._draft_popis: str | None = doklad.popis
        self._draft_splatnost: date | None = doklad.datum_splatnosti
        self._draft_k_doreseni: bool = doklad.k_doreseni
        self._draft_poznamka_doreseni: str | None = doklad.poznamka_doreseni
        self._draft_partner_id: int | None = doklad.partner_id
        self._draft_datum_vystaveni: date = doklad.datum_vystaveni
        self._draft_castka_celkem: Money = doklad.castka_celkem
        self._draft_castka_mena: Money | None = doklad.castka_mena
        self._draft_kurz: Decimal | None = doklad.kurz
        self._draft_mena: Mena = doklad.mena
        self._error: str | None = None
        self._deleted: bool = False

    # ─── Read-only state ──────────────────────────────────────────────

    @property
    def doklad(self) -> DokladyListItem:
        return self._doklad

    @property
    def edit_mode(self) -> bool:
        return self._edit_mode

    @property
    def draft_popis(self) -> str | None:
        return self._draft_popis

    @property
    def draft_splatnost(self) -> date | None:
        return self._draft_splatnost

    @property
    def draft_k_doreseni(self) -> bool:
        return self._draft_k_doreseni

    @property
    def draft_poznamka_doreseni(self) -> str | None:
        return self._draft_poznamka_doreseni

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def is_deleted(self) -> bool:
        """True po úspěšném smazání — dialog se má zavřít."""
        return self._deleted

    # ─── Computed: co lze s dokladem dělat ───────────────────────────

    @property
    def can_edit(self) -> bool:
        """Edit mode — popis + splatnost — povolen kromě STORNOVANY."""
        return self._doklad.stav != StavDokladu.STORNOVANY

    @property
    def can_edit_splatnost(self) -> bool:
        """Splatnost editovatelná jen ve stavu NOVY."""
        return self._doklad.stav == StavDokladu.NOVY

    @property
    def can_edit_castka(self) -> bool:
        """Částka editovatelná jen ve stavu NOVY.

        Pro zaúčtovaný doklad částku měnit nelze, protože by to rozbilo
        účetní zápisy. Pro úpravu po zaúčtování je nutné stornovat
        a vytvořit nový.
        """
        return self._doklad.stav == StavDokladu.NOVY

    @property
    def can_edit_datum_vystaveni(self) -> bool:
        """Datum vystavení editovatelné ve všech stavech kromě STORNOVANY.

        Změna se atomicky propíše i do účetních zápisů. Pro UHRAZENY
        povoleno — úhrada (BV) je samostatný doklad s vlastním datem,
        oprava data faktury úhradu neovlivní.
        """
        return self._doklad.stav != StavDokladu.STORNOVANY

    @property
    def can_storno(self) -> bool:
        """Stornovat NOVY/ZAUCTOVANY/CASTECNE_UHRAZENY. Ne UHRAZENY/STORNOVANY."""
        return self._doklad.stav in (
            StavDokladu.NOVY,
            StavDokladu.ZAUCTOVANY,
            StavDokladu.CASTECNE_UHRAZENY,
        )

    @property
    def can_smazat(self) -> bool:
        """Smazat jen NOVY (bez zápisů)."""
        return self._doklad.stav == StavDokladu.NOVY

    @property
    def can_toggle_flag(self) -> bool:
        """Flag k_doreseni — povoleno kromě STORNOVANY."""
        return self._doklad.stav != StavDokladu.STORNOVANY

    @property
    def can_zauctovat(self) -> bool:
        """Zaúčtovat jen NOVY doklady."""
        return self._doklad.stav == StavDokladu.NOVY

    # ─── Edit mode ────────────────────────────────────────────────────

    def enter_edit(self) -> None:
        """Přepne do edit módu. Draft se nastaví ze stávajícího DTO."""
        if not self.can_edit:
            self._error = "Tento doklad nelze upravovat."
            return
        self._edit_mode = True
        self._draft_popis = self._doklad.popis
        self._draft_splatnost = self._doklad.datum_splatnosti
        self._draft_k_doreseni = self._doklad.k_doreseni
        self._draft_poznamka_doreseni = self._doklad.poznamka_doreseni
        self._draft_partner_id = self._doklad.partner_id
        self._draft_datum_vystaveni = self._doklad.datum_vystaveni
        self._draft_castka_celkem = self._doklad.castka_celkem
        self._draft_castka_mena = self._doklad.castka_mena
        self._draft_kurz = self._doklad.kurz
        self._draft_mena = self._doklad.mena
        self._error = None

    def cancel_edit(self) -> None:
        """Zahodí draft a vrátí se do read-only."""
        self._edit_mode = False
        self._draft_popis = self._doklad.popis
        self._draft_splatnost = self._doklad.datum_splatnosti
        self._draft_k_doreseni = self._doklad.k_doreseni
        self._draft_poznamka_doreseni = self._doklad.poznamka_doreseni
        self._draft_partner_id = self._doklad.partner_id
        self._draft_datum_vystaveni = self._doklad.datum_vystaveni
        self._draft_castka_celkem = self._doklad.castka_celkem
        self._draft_castka_mena = self._doklad.castka_mena
        self._draft_kurz = self._doklad.kurz
        self._draft_mena = self._doklad.mena
        self._error = None

    def set_draft_popis(self, popis: str | None) -> None:
        self._draft_popis = popis

    def set_draft_splatnost(self, splatnost: date | None) -> None:
        self._draft_splatnost = splatnost

    def set_draft_k_doreseni(self, flag: bool) -> None:
        self._draft_k_doreseni = flag

    def set_draft_poznamka_doreseni(self, poznamka: str | None) -> None:
        self._draft_poznamka_doreseni = poznamka

    @property
    def draft_partner_id(self) -> int | None:
        return self._draft_partner_id

    def set_draft_partner_id(self, partner_id: int | None) -> None:
        self._draft_partner_id = partner_id

    @property
    def draft_datum_vystaveni(self) -> date:
        return self._draft_datum_vystaveni

    def set_draft_datum_vystaveni(self, datum: date) -> None:
        self._draft_datum_vystaveni = datum

    @property
    def draft_castka_celkem(self) -> Money:
        return self._draft_castka_celkem

    def set_draft_castka_celkem(self, castka: Money) -> None:
        """Pro CZK doklad: přímo. Pro EUR/USD: setter castka_mena
        + kurz se použije pro přepočet (volá se z dialogu zvlášť)."""
        self._draft_castka_celkem = castka

    @property
    def draft_castka_mena(self) -> Money | None:
        return self._draft_castka_mena

    def set_draft_castka_mena(self, castka: Money | None) -> None:
        self._draft_castka_mena = castka

    @property
    def draft_kurz(self) -> Decimal | None:
        return self._draft_kurz

    def set_draft_kurz(self, kurz: Decimal | None) -> None:
        self._draft_kurz = kurz

    @property
    def draft_mena(self) -> Mena:
        return self._draft_mena

    def set_draft_mena(self, mena: Mena) -> None:
        """Změna měny — pokud se přechází na CZK, vyčistí EUR/kurz draft."""
        self._draft_mena = mena
        if mena == Mena.CZK:
            self._draft_castka_mena = None
            self._draft_kurz = None

    def save_edit(self) -> DokladyListItem | None:
        """Uloží draft přes DokladActionsCommand.

        NOVY doklad → ``upravit_pole_novy_dokladu`` (popis + splatnost +
        flag + poznámka).
        Jiný stav → ``upravit_popis_a_splatnost`` (jen popis, splatnost
        je stejná jako stávající).
        """
        try:
            # Partner — jen pokud se změnil
            _partner_arg = (
                self._draft_partner_id
                if self._draft_partner_id != self._doklad.partner_id
                else ...
            )
            # Datum vystavení — None pokud se nezměnilo (action command
            # to ponechá beze změny + zápisy se neaktualizují)
            _datum_arg = (
                self._draft_datum_vystaveni
                if self._draft_datum_vystaveni != self._doklad.datum_vystaveni
                else None
            )
            if self._doklad.stav == StavDokladu.NOVY:
                # Castka/měna/kurz — argumenty jen pokud se něco změnilo.
                # Pokud uživatel změnil měnu, posíláme všechno (i castku),
                # protože domain potřebuje konzistentní set kurz/cm/mena.
                castka_changed = (
                    self._draft_castka_celkem != self._doklad.castka_celkem
                )
                mena_changed = self._draft_mena != self._doklad.mena
                if castka_changed or mena_changed:
                    _castka_arg = self._draft_castka_celkem
                    _castka_mena_arg = self._draft_castka_mena
                    _kurz_arg = self._draft_kurz
                    _mena_arg = (
                        self._draft_mena if mena_changed else ...
                    )
                else:
                    _castka_arg = ...
                    _castka_mena_arg = ...
                    _kurz_arg = ...
                    _mena_arg = ...
                item = self._actions.upravit_pole_novy_dokladu(
                    self._doklad.id,
                    popis=self._draft_popis,
                    splatnost=self._draft_splatnost,
                    k_doreseni=self._draft_k_doreseni,
                    poznamka_doreseni=self._draft_poznamka_doreseni,
                    partner_id=_partner_arg,
                    datum_vystaveni=_datum_arg,
                    castka_celkem=_castka_arg,
                    castka_mena=_castka_mena_arg,
                    kurz=_kurz_arg,
                    mena=_mena_arg,
                )
            else:
                item = self._actions.upravit_popis_a_splatnost(
                    self._doklad.id,
                    popis=self._draft_popis,
                    splatnost=self._draft_splatnost,
                    partner_id=_partner_arg,
                    datum_vystaveni=_datum_arg,
                )
            self._doklad = item
            self._edit_mode = False
            self._error = None
            return item
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
            return None

    # ─── Akce (state transitions + flag) ──────────────────────────────

    def stornovat(
        self,
        datum: date | None = None,
        poznamka: str | None = None,
    ) -> DokladyListItem | None:
        """Stornuje doklad. Default datum = datum_vystaveni originálu.

        Args:
            datum: Datum storna (None → datum_vystaveni originálu).
            poznamka: Volitelná poznámka pro popis storno zápisů.
        """
        try:
            item = self._actions.stornovat(
                self._doklad.id, datum=datum, poznamka=poznamka,
            )
            self._doklad = item
            self._edit_mode = False
            self._error = None
            return item
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
            return None

    def smazat(self) -> bool:
        """Smaže doklad. Vrátí True při úspěchu, nastaví ``is_deleted``."""
        try:
            self._actions.smazat(self._doklad.id)
            self._deleted = True
            self._error = None
            return True
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
            return False

    def oznac_k_doreseni(
        self, poznamka: str | None = None,
    ) -> DokladyListItem | None:
        try:
            item = self._actions.oznac_k_doreseni(
                self._doklad.id, poznamka=poznamka,
            )
            self._doklad = item
            self._error = None
            return item
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
            return None

    def dores(self) -> DokladyListItem | None:
        try:
            item = self._actions.dores(self._doklad.id)
            self._doklad = item
            self._error = None
            return item
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc) or exc.__class__.__name__
            return None

    def refresh_from(self, doklad: DokladyListItem) -> None:
        """External refresh (např. po zaúčtování v jiném dialogu)."""
        self._doklad = doklad
        self._draft_popis = doklad.popis
        self._draft_splatnost = doklad.datum_splatnosti
        self._draft_k_doreseni = doklad.k_doreseni
        self._draft_poznamka_doreseni = doklad.poznamka_doreseni
        self._edit_mode = False
        self._error = None
