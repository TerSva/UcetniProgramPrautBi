"""ManageChartOfAccountsCommand — správa účtové osnovy.

Operace: aktivace/deaktivace syntetických účtů, přidání/úprava analytik.
Každá operace běží v samostatné UoW transakci.
"""

from __future__ import annotations

from typing import Callable

from domain.shared.errors import ConflictError, NotFoundError, ValidationError
from domain.ucetnictvi.repository import UctovaOsnovaRepository
from domain.ucetnictvi.ucet import Ucet
from infrastructure.database.unit_of_work import SqliteUnitOfWork


class ManageChartOfAccountsCommand:
    """Command pro správu účtové osnovy."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        osnova_repo_factory: Callable[
            [SqliteUnitOfWork], UctovaOsnovaRepository
        ],
    ) -> None:
        self._uow_factory = uow_factory
        self._osnova_repo_factory = osnova_repo_factory

    def activate_ucet(self, cislo: str) -> None:
        """Aktivuje účet. Raise NotFoundError pokud neexistuje."""
        uow = self._uow_factory()
        with uow:
            repo = self._osnova_repo_factory(uow)
            ucet = repo.get_by_cislo(cislo)
            ucet.aktivuj()
            repo.update(ucet)
            uow.commit()

    def deactivate_ucet(self, cislo: str) -> None:
        """Deaktivuje účet.

        Raise ValidationError pokud má aktivní analytiky.
        Raise NotFoundError pokud neexistuje.
        """
        uow = self._uow_factory()
        with uow:
            repo = self._osnova_repo_factory(uow)
            ucet = repo.get_by_cislo(cislo)

            # Nelze deaktivovat syntetiku s aktivními analytikami
            if not ucet.is_analytic:
                analytiky = repo.get_analytiky(ucet.cislo)
                active_analytiky = [a for a in analytiky if a.je_aktivni]
                if active_analytiky:
                    codes = ", ".join(a.cislo for a in active_analytiky)
                    raise ValidationError(
                        f"Účet {cislo} nelze deaktivovat — má aktivní "
                        f"analytiky: {codes}. Nejdřív deaktivujte analytiky."
                    )

            ucet.deaktivuj()
            repo.update(ucet)
            uow.commit()

    def add_analytika(
        self,
        syntetic_kod: str,
        analytika_suffix: str,
        nazev: str,
        popis: str | None = None,
    ) -> Ucet:
        """Přidá novou analytiku k syntetickému účtu.

        Args:
            syntetic_kod: Kód syntetického účtu (např. "518").
            analytika_suffix: Suffix za tečkou (např. "100").
            nazev: Název analytiky.
            popis: Volitelný popis.

        Returns:
            Nově vytvořený Ucet.

        Raises:
            NotFoundError: syntetický účet neexistuje.
            ConflictError: analytika s tímto kódem již existuje.
            ValidationError: neplatný formát.
        """
        full_kod = f"{syntetic_kod}.{analytika_suffix}"

        uow = self._uow_factory()
        with uow:
            repo = self._osnova_repo_factory(uow)

            # Ověř, že parent existuje
            parent = repo.get_by_cislo(syntetic_kod)

            # Vytvoř analytiku (validace formátu v Ucet konstruktoru)
            analytika = Ucet(
                cislo=full_kod,
                nazev=nazev,
                typ=parent.typ,
                je_aktivni=True,
                parent_kod=syntetic_kod,
                popis=popis,
            )
            repo.add(analytika)

            # Automaticky aktivuj parent pokud není aktivní
            if not parent.je_aktivni:
                parent.aktivuj()
                repo.update(parent)

            uow.commit()

        return analytika

    def update_analytika(
        self,
        cislo: str,
        nazev: str,
        popis: str | None = None,
    ) -> None:
        """Změní název a popis analytiky.

        Raises:
            NotFoundError: účet neexistuje.
            ValidationError: účet není analytika.
        """
        uow = self._uow_factory()
        with uow:
            repo = self._osnova_repo_factory(uow)
            ucet = repo.get_by_cislo(cislo)
            if not ucet.is_analytic:
                raise ValidationError(
                    f"Účet {cislo} není analytika — nelze upravit název."
                )
            ucet.uprav_nazev(nazev)
            ucet.uprav_popis(popis)
            repo.update(ucet)
            uow.commit()

    def delete_analytika(self, cislo: str) -> None:
        """Smaže analytiku. Nelze smazat syntetický účet.

        Raises:
            NotFoundError: účet neexistuje.
            ValidationError: účet není analytika nebo má účetní zápisy.
        """
        uow = self._uow_factory()
        with uow:
            repo = self._osnova_repo_factory(uow)
            ucet = repo.get_by_cislo(cislo)
            if not ucet.is_analytic:
                raise ValidationError(
                    f"Účet {cislo} není analytika — syntetické účty nelze mazat."
                )
            # Check for journal entries referencing this account
            count = uow.connection.execute(
                "SELECT COUNT(*) FROM ucetni_zaznamy "
                "WHERE md_ucet = ? OR dal_ucet = ?",
                (cislo, cislo),
            ).fetchone()[0]
            if count > 0:
                raise ValidationError(
                    f"Účet {cislo} nelze smazat — má {count} účetních zápisů."
                )
            repo.delete(cislo)
            uow.commit()

    def rename_analytika(
        self, old_cislo: str, new_suffix: str,
        nazev: str, popis: str | None = None,
    ) -> Ucet:
        """Přejmenuje analytiku (změní suffix). Vytvoří novou, smaže starou.

        Raises:
            NotFoundError: účet neexistuje.
            ValidationError: účet není analytika nebo má účetní zápisy.
            ConflictError: nový kód už existuje.
        """
        uow = self._uow_factory()
        with uow:
            repo = self._osnova_repo_factory(uow)
            old = repo.get_by_cislo(old_cislo)
            if not old.is_analytic:
                raise ValidationError(
                    f"Účet {old_cislo} není analytika."
                )
            new_cislo = f"{old.parent_kod}.{new_suffix}"
            if new_cislo == old_cislo:
                # Suffix se nezměnil — jen update název/popis
                old.uprav_nazev(nazev)
                old.uprav_popis(popis)
                repo.update(old)
                uow.commit()
                return old
            # Check for journal entries on old account
            count = uow.connection.execute(
                "SELECT COUNT(*) FROM ucetni_zaznamy "
                "WHERE md_ucet = ? OR dal_ucet = ?",
                (old_cislo, old_cislo),
            ).fetchone()[0]
            if count > 0:
                raise ValidationError(
                    f"Účet {old_cislo} nelze přejmenovat — má {count} účetních zápisů."
                )
            # Create new, delete old
            new_ucet = Ucet(
                cislo=new_cislo,
                nazev=nazev,
                typ=old.typ,
                je_aktivni=old.je_aktivni,
                parent_kod=old.parent_kod,
                popis=popis,
            )
            repo.add(new_ucet)
            repo.delete(old_cislo)
            uow.commit()
        return new_ucet

    def update_ucet(
        self,
        cislo: str,
        nazev: str,
        popis: str | None = None,
    ) -> None:
        """Změní název a popis účtu (syntetického i analytického).

        Raises:
            NotFoundError: účet neexistuje.
        """
        uow = self._uow_factory()
        with uow:
            repo = self._osnova_repo_factory(uow)
            ucet = repo.get_by_cislo(cislo)
            ucet.uprav_nazev(nazev)
            ucet.uprav_popis(popis)
            repo.update(ucet)
            uow.commit()
