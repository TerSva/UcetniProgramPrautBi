"""ZauctovaniDokladuService — orchestrace zaúčtování dokladu.

Tenká service vrstva: ví JAK věci skládat dohromady.
Doménové entity ví JAK věci BÝT (validace, stav, invarianty).
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Tuple

from domain.doklady.doklad import Doklad
from domain.doklady.repository import DokladyRepository
from domain.doklady.typy import DphRezim, StavDokladu
from domain.shared.errors import PodvojnostError, ValidationError
from domain.shared.money import Money
from domain.ucetnictvi.repository import UcetniDenikRepository
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class ZauctovaniDokladuService:
    """Atomické zaúčtování dokladu — jedna transakce, vše nebo nic."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        doklady_repo_factory: Callable[[SqliteUnitOfWork], DokladyRepository],
        denik_repo_factory: Callable[[SqliteUnitOfWork], UcetniDenikRepository],
    ) -> None:
        self._uow_factory = uow_factory
        self._doklady_repo_factory = doklady_repo_factory
        self._denik_repo_factory = denik_repo_factory

    def zauctuj_doklad(
        self,
        doklad_id: int,
        predpis: UctovyPredpis,
    ) -> Tuple[Doklad, tuple[UcetniZaznam, ...]]:
        """Atomicky zaúčtuje doklad.

        Raises:
            ValidationError — predpis.doklad_id != doklad_id, nebo špatný stav
            NotFoundError — doklad/účet neexistuje
            PodvojnostError — celková částka předpisu != castka_celkem dokladu
        """
        if predpis.doklad_id != doklad_id:
            raise ValidationError(
                f"Předpis odkazuje na doklad {predpis.doklad_id}, "
                f"ale zaúčtováváme {doklad_id}"
            )

        uow = self._uow_factory()
        with uow:
            doklady_repo = self._doklady_repo_factory(uow)
            denik_repo = self._denik_repo_factory(uow)

            doklad = doklady_repo.get_by_id(doklad_id)

            # U reverse charge: DPH řádky (343/343) jsou průtokové —
            # porovnáváme jen základ (ne-DPH řádky) s částkou dokladu.
            if doklad.dph_rezim == DphRezim.REVERSE_CHARGE:
                zaklad = Money.zero()
                for z in predpis.zaznamy:
                    if not (z.md_ucet.startswith("343") and z.dal_ucet.startswith("343")):
                        zaklad = zaklad + z.castka
                if doklad.castka_celkem != zaklad:
                    raise PodvojnostError(
                        f"Základ předpisu ({zaklad}) nesouhlasí "
                        f"s celkovou částkou dokladu ({doklad.castka_celkem})"
                    )
            elif doklad.castka_celkem != predpis.celkova_castka:
                raise PodvojnostError(
                    f"Předpis ({predpis.celkova_castka}) nesouhlasí "
                    f"s celkovou částkou dokladu ({doklad.castka_celkem})"
                )

            doklad.zauctuj()

            ulozene = denik_repo.zauctuj(predpis)
            doklady_repo.update(doklad)

            uow.commit()

        return doklad, ulozene

    def stornuj_doklad(
        self,
        doklad_id: int,
        datum: date | None = None,
        poznamka: str | None = None,
    ) -> Tuple[Doklad, tuple[UcetniZaznam, ...]]:
        """Atomicky stornuje doklad: protizápis + změna stavu.

        Pro zaúčtovaný (nebo částečně uhrazený) doklad:
          1. Načte všechny „čisté" původní zápisy z deníku.
          2. Vytvoří opravný předpis (MD ↔ Dal prohozené, kladná částka,
             ``je_storno=True``, ``stornuje_zaznam_id`` na originál).
          3. Uloží protizápisy do deníku.
          4. Změní stav dokladu na STORNOVANY (+ vyčistí k_doreseni).

        Vše v jedné UoW transakci — selhání kteréhokoli kroku → rollback.

        Args:
            doklad_id: ID dokladu ke stornu.
            datum: Datum storna. Pokud None, použije se ``datum_vystaveni``
                originálního dokladu — storno tak zůstává ve stejném účetním
                období jako původní doklad.
            poznamka: Volitelná uživatelská poznámka. Pokud je vyplněna,
                uloží se do popisu storno protizápisů ve formátu
                "Storno: {poznamka}".

        Returns:
            ``(Doklad, protizápisy)`` — aktualizovaný doklad a uložené
            protizápisy (s naplněnými id z DB).

        Raises:
            NotFoundError: doklad neexistuje.
            ValidationError: NOVY (použít Smazat), UHRAZENY (nelze),
                STORNOVANY (už stornovaný — idempotence řešena checkem níže).
        """
        uow = self._uow_factory()
        with uow:
            doklady_repo = self._doklady_repo_factory(uow)
            denik_repo = self._denik_repo_factory(uow)

            doklad = doklady_repo.get_by_id(doklad_id)

            # Default datum = datum vystavení originálu (stejné účetní období).
            storno_datum = datum or doklad.datum_vystaveni

            # Idempotence: už stornovaný → vrať stav beze změny.
            if doklad.stav == StavDokladu.STORNOVANY:
                zaznamy = denik_repo.list_by_doklad(doklad_id)
                protizapisy = tuple(z for z in zaznamy if z.je_storno)
                return doklad, protizapisy

            # Validace: jen ZAUCTOVANY / CASTECNE_UHRAZENY potřebují protizápis.
            if doklad.stav == StavDokladu.NOVY:
                raise ValidationError(
                    "NOVY doklad nelze stornovat — použij Smazat "
                    "(nemá účetní zápisy, které by bylo třeba reversovat)."
                )
            if doklad.stav == StavDokladu.UHRAZENY:
                raise ValidationError(
                    "Doklad ve stavu UHRAZENY nelze stornovat — "
                    "nejdřív je potřeba vrátit peníze."
                )

            # Načti „čisté" originály (ne storno, bez existujícího protizápisu).
            zaznamy = denik_repo.list_by_doklad(doklad_id)
            already_stornuje: set[int] = {
                z.stornuje_zaznam_id
                for z in zaznamy
                if z.je_storno and z.stornuje_zaznam_id is not None
            }
            originaly = tuple(
                z for z in zaznamy
                if not z.je_storno and z.id not in already_stornuje
            )
            if not originaly:
                raise ValidationError(
                    f"Doklad {doklad_id} ve stavu {doklad.stav.value} "
                    f"nemá žádné zápisy ke stornu."
                )

            storno_predpis = UctovyPredpis.storno_z_zaznamu(
                originaly, datum=storno_datum, popis_override=poznamka,
            )
            protizapisy = denik_repo.zauctuj(storno_predpis)

            doklad.stornuj()
            doklady_repo.update(doklad)

            uow.commit()

        return doklad, protizapisy
