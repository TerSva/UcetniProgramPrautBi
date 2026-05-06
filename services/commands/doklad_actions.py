"""DokladActionsCommand — sada akcí nad existujícím dokladem.

Jedna třída sdružuje mutace, které UI volá z detailu nebo kontextového menu:

* ``stornovat(doklad_id)`` — doménové ``Doklad.stornuj()``.
* ``smazat(doklad_id)`` — repository ``delete()`` (jen NOVY + bez zápisů).
* ``oznac_k_doreseni(doklad_id, poznamka)`` — ``Doklad.oznac_k_doreseni``.
* ``dores(doklad_id)`` — ``Doklad.dores()``.
* ``upravit_popis_a_splatnost(doklad_id, popis, splatnost)`` —
  atomická úprava dvou polí, která entita povoluje (popis kdykoli
  kromě STORNOVANY, splatnost jen NOVY).
* ``upravit_pole_novy_dokladu(doklad_id, popis, splatnost, k_doreseni,
  poznamka_doreseni)`` — kompletní edit NOVY dokladu (popis + splatnost
  + flag k dořešení + poznámka) v jedné transakci. Slouží detail
  dialogu v edit mode.

Každá metoda běží v jedné transakci. Vrací ``DokladyListItem`` DTO
(kromě ``smazat``, které vrací ``None``).
"""

from __future__ import annotations

from datetime import date
from typing import Callable

from domain.doklady.repository import DokladyRepository
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.doklady_list import DokladyListItem
from services.zauctovani_service import ZauctovaniDokladuService


class DokladActionsCommand:
    """Sada write operací nad existujícím dokladem."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
        zauctovani_service: ZauctovaniDokladuService,
    ) -> None:
        self._uow_factory = uow_factory
        self._doklady_repo_factory = doklady_repo_factory
        self._zauctovani_service = zauctovani_service

    # ── State transitions ──────────────────────────────────────────────

    def stornovat(
        self,
        doklad_id: int,
        datum: date | None = None,
        poznamka: str | None = None,
    ) -> DokladyListItem:
        """Stornuje doklad přes opravný účetní předpis.

        Deleguje na ``ZauctovaniDokladuService.stornuj_doklad``, který
        v jedné UoW vytvoří protizápisy + změní stav. Auto-clear ``k_doreseni``
        řeší ``Doklad.stornuj()`` uvnitř service transakce.

        Args:
            datum: Datum storna; default = ``doklad.datum_vystaveni``.
            poznamka: Volitelná poznámka uložená do popisu storno zápisů.

        Vrácený DTO nese ``datum_storna`` (datum prvního protizápisu) —
        aby UI po stornu mohlo okamžitě zobrazit „Stornováno: {datum}"
        bez re-fetche.

        Raises:
            ValidationError — NOVY (použij Smazat), UHRAZENY (nelze).
            NotFoundError — doklad neexistuje.
        """
        doklad, protizapisy = self._zauctovani_service.stornuj_doklad(
            doklad_id, datum=datum, poznamka=poznamka,
        )
        datum_storna = protizapisy[0].datum if protizapisy else None
        return DokladyListItem.from_domain(doklad, datum_storna=datum_storna)

    def smazat(self, doklad_id: int) -> None:
        """Smaže doklad (jen NOVY + bez zápisů). Raises ValidationError."""
        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            repo.delete(doklad_id)
            uow.commit()

    # ── Flag "k dořešení" ──────────────────────────────────────────────

    def oznac_k_doreseni(
        self, doklad_id: int, poznamka: str | None = None
    ) -> DokladyListItem:
        """Nastaví flag k_doreseni=True + volitelnou poznámku."""
        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            doklad = repo.get_by_id(doklad_id)
            doklad.oznac_k_doreseni(poznamka)
            repo.update(doklad)
            uow.commit()
        return DokladyListItem.from_domain(doklad)

    def dores(self, doklad_id: int) -> DokladyListItem:
        """Odznačí flag. Idempotentní."""
        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            doklad = repo.get_by_id(doklad_id)
            doklad.dores()
            repo.update(doklad)
            uow.commit()
        return DokladyListItem.from_domain(doklad)

    # ── Editace ────────────────────────────────────────────────────────

    def upravit_popis_a_splatnost(
        self,
        doklad_id: int,
        popis: str | None,
        splatnost: date | None,
        partner_id: object = ...,
        datum_vystaveni: date | None = None,
    ) -> DokladyListItem:
        """Atomicky upraví popis + splatnost (+ volitelně datum vystavení).

        Popis — povoleno kdykoli kromě STORNOVANY.
        Splatnost — povoleno jen ve stavu NOVY.
        Datum vystavení — povoleno krom UHRAZENY/STORNOVANY. Pokud se mění,
            propíše se i do účetních zápisů (zápisy musí mít stejné datum
            jako doklad). Vše v jedné UoW transakci.

        Když je splatnost stejná jako stávající, ``uprav_splatnost`` se
        nezavolá — editovatelné pole u jiného než NOVY stavu je tak bezpečné
        (UI dialog splatnost disabluje, ale double-check je levný).

        Raises:
            ValidationError: popis přes limit, splatnost < datum vystavení,
                doklad STORNOVANY, splatnost měněna ne-NOVY dokladu,
                datum_vystaveni měněno na UHRAZENY/STORNOVANY.
            NotFoundError: doklad neexistuje.
        """
        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            doklad = repo.get_by_id(doklad_id)

            # Datum vystavení — aplikovat jako PRVNÍ, protože může uvolnit
            # pozdější validace splatnosti (např. zvětšení data vystavení
            # přes hranici stávající splatnosti).
            if (
                datum_vystaveni is not None
                and datum_vystaveni != doklad.datum_vystaveni
            ):
                doklad.uprav_datum_vystaveni(datum_vystaveni)
                # Atomicky propsat do účetních zápisů (datum řádků = datum dokladu)
                uow.connection.execute(
                    "UPDATE ucetni_zaznamy SET datum = ? WHERE doklad_id = ?",
                    (datum_vystaveni.isoformat(), doklad_id),
                )

            # Popis — vždy aplikuj, entita si hlídá STORNOVANY a délku.
            doklad.uprav_popis(popis)

            # Splatnost — přeskočit no-op, jinak entita zkusí změnit i na
            # stejnou hodnotu a u ne-NOVY dokladu by vyhodila.
            if splatnost != doklad.datum_splatnosti:
                doklad.uprav_splatnost(splatnost)

            # Partner — sentinel ... = nezměněno
            if partner_id is not ...:
                doklad.uprav_partner(partner_id)

            repo.update(doklad)
            uow.commit()
        return DokladyListItem.from_domain(doklad)

    def upravit_pole_novy_dokladu(
        self,
        doklad_id: int,
        popis: str | None,
        splatnost: date | None,
        k_doreseni: bool,
        poznamka_doreseni: str | None,
        partner_id: object = ...,
        datum_vystaveni: date | None = None,
        castka_celkem: object = ...,
        castka_mena: object = ...,
        kurz: object = ...,
        mena: object = ...,
    ) -> DokladyListItem:
        """Atomicky upraví všechna editovatelná pole NOVY dokladu.

        Slouží detail dialogu v edit mode, kde uživatelka může zároveň
        upravit popis, splatnost a flag k_doreseni + poznámku. Všechno
        v jedné transakci — buď se povede všechno, nebo nic.

        Flag/poznámka:
        - ``k_doreseni=True``  → zavolá ``oznac_k_doreseni(poznamka)``
          (idempotentní — funguje i jako update poznámky, když už flag byl).
        - ``k_doreseni=False`` → zavolá ``dores()`` (idempotentní).

        Splatnost se aplikuje jen pokud se liší (stejná logika jako
        ``upravit_popis_a_splatnost`` — entita u ne-NOVY vyhodí).

        Raises:
            ValidationError: popis přes limit, splatnost < datum vystavení,
                doklad není NOVY (splatnost), STORNOVANY, poznámka přes limit.
            NotFoundError: doklad neexistuje.
        """
        uow = self._uow_factory()
        with uow:
            repo = self._doklady_repo_factory(uow)
            doklad = repo.get_by_id(doklad_id)

            # Datum vystavení nejdřív (uvolní pozdější validace splatnosti
            # a propíše se i do účetních zápisů, pokud nějaké jsou).
            if (
                datum_vystaveni is not None
                and datum_vystaveni != doklad.datum_vystaveni
            ):
                doklad.uprav_datum_vystaveni(datum_vystaveni)
                uow.connection.execute(
                    "UPDATE ucetni_zaznamy SET datum = ? WHERE doklad_id = ?",
                    (datum_vystaveni.isoformat(), doklad_id),
                )

            doklad.uprav_popis(popis)

            if splatnost != doklad.datum_splatnosti:
                doklad.uprav_splatnost(splatnost)

            if k_doreseni:
                doklad.oznac_k_doreseni(poznamka_doreseni)
            else:
                doklad.dores()

            # Partner — sentinel ... = nezměněno
            if partner_id is not ...:
                doklad.uprav_partner(partner_id)

            # Částka — sentinel ... = nezměněno (jen pro NOVY doklady).
            # Pokud se mění měna (mena!=...), zavolá se uprav_castku i kdyby
            # samotná castka byla stejná — měna potřebuje validaci kurz/cm.
            if castka_celkem is not ... or mena is not ...:
                if castka_celkem is not ...:
                    nova_castka = castka_celkem
                else:
                    nova_castka = doklad.castka_celkem
                cm = castka_mena if castka_mena is not ... else None
                k = kurz if kurz is not ... else None
                m = mena if mena is not ... else None
                doklad.uprav_castku(
                    nova_castka, castka_mena=cm, kurz=k, nova_mena=m,
                )

            repo.update(doklad)
            uow.commit()
        return DokladyListItem.from_domain(doklad)
