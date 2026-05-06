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

            # Detekce speciálních řádků v předpisu — vylučují se z porovnání
            # se castka_celkem dokladu, protože nejsou součástí "základu":
            #   * RC DPH řádky (343/343) — průtokové (přenos daňové povinnosti)
            #   * Odečet zálohy (popis "Odečet zálohy …") — zúčtování proti
            #     pohledávce/závazku, netto efekt na castka_celkem je 0
            ma_dph_radek = any(
                z.md_ucet.startswith("343") and z.dal_ucet.startswith("343")
                for z in predpis.zaznamy
            )
            je_rc = (
                doklad.dph_rezim == DphRezim.REVERSE_CHARGE or ma_dph_radek
            )

            def _je_dph(z: UcetniZaznam) -> bool:
                return (
                    z.md_ucet.startswith("343")
                    and z.dal_ucet.startswith("343")
                )

            def _je_odecet_zalohy(z: UcetniZaznam) -> bool:
                return bool(z.popis and z.popis.startswith("Odečet zálohy"))

            zaklad = Money.zero()
            for z in predpis.zaznamy:
                if _je_dph(z) or _je_odecet_zalohy(z):
                    continue
                zaklad = zaklad + z.castka

            if doklad.castka_celkem != zaklad:
                raise PodvojnostError(
                    f"Základ předpisu ({zaklad}) nesouhlasí "
                    f"s celkovou částkou dokladu ({doklad.castka_celkem})"
                )

            # Pokud doklad neměl dph_rezim=RC ale předpis obsahuje 343/343,
            # dorovnáme dph_rezim na REVERSE_CHARGE.
            if je_rc and doklad.dph_rezim != DphRezim.REVERSE_CHARGE:
                doklad.nastav_dph_rezim(DphRezim.REVERSE_CHARGE)

            # Detekce zúčtování zálohy v předpisu — pokud existuje řádek
            # odečtu zálohy a součet odečtů >= castka_celkem, doklad je
            # de facto plně uhrazený (záloha pokryla vše). Po zaúčtování
            # ho označíme UHRAZENY místo ZAUCTOVANY.
            suma_odpoctu = Money.zero()
            zalohy_cisla: list[str] = []
            for z in predpis.zaznamy:
                if _je_odecet_zalohy(z):
                    suma_odpoctu = suma_odpoctu + z.castka
                    # Vyzískat cislo zálohy z popisu "Odečet zálohy ZF-..."
                    if z.popis:
                        cislo_zalohy = z.popis.replace(
                            "Odečet zálohy", "",
                        ).strip()
                        if cislo_zalohy:
                            zalohy_cisla.append(cislo_zalohy)

            doklad.zauctuj()

            # Auto-UHRAZENÍ: pokud zálohy pokrývají celou pohledávku/závazek
            if (
                suma_odpoctu.to_halire() > 0
                and suma_odpoctu.to_halire() >= doklad.castka_celkem.to_halire()
            ):
                doklad.oznac_uhrazeny()

            ulozene = denik_repo.zauctuj(predpis)
            doklady_repo.update(doklad)

            # Označ zúčtované ZF dokladu poznámkou
            if zalohy_cisla:
                self._oznac_zalohy_zuctovane(
                    doklady_repo, zalohy_cisla, doklad.cislo,
                )

            uow.commit()

        return doklad, ulozene

    def _oznac_zalohy_zuctovane(
        self,
        doklady_repo,
        zalohy_cisla: list[str],
        finalni_doklad_cislo: str,
    ) -> None:
        """Označí ZF doklady poznámkou „Zúčtováno s {finalni}".

        Volá se po úspěšném zaúčtování finální FV/FP, která obsahuje
        odečetní řádky zálohy. Pokud ZF už má poznámku, přepíše ji
        — záloha může být zúčtována jen jednou.

        Pokud ZF neexistuje (popis byl ručně napsán bez existující ZF),
        ignoruje (best-effort).
        """
        for cislo_zf in zalohy_cisla:
            try:
                zf = doklady_repo.get_by_cislo(cislo_zf)
            except Exception:  # noqa: BLE001
                continue
            if zf is None:
                continue
            poznamka = (
                f"Zúčtováno s {finalni_doklad_cislo}"
            )
            puvodni = zf.popis or ""
            if poznamka not in puvodni:
                novy_popis = (
                    f"{puvodni} | {poznamka}".strip(" |")
                    if puvodni else poznamka
                )
                zf.uprav_popis(novy_popis)
                doklady_repo.update(zf)

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
