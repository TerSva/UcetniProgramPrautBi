"""PrenosZustatkuCommand — přenos KZ rozvahových účtů jako PS následujícího roku.

Rozvahové účty (typ A, P): KZ → PS následujícího roku
Výsledkové účty (typ N, V): se NEPŘENÁŠEJÍ, VH se převede na 431
Závěrkové účty (typ Z, 7xx): se NEPŘENÁŠEJÍ
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from domain.firma.pocatecni_stav import PocatecniStav
from domain.shared.errors import ValidationError
from domain.shared.money import Money
from domain.ucetnictvi.typy import TypUctu
from infrastructure.database.repositories.pocatecni_stavy_repository import (
    SqlitePocatecniStavyRepository,
)
from infrastructure.database.repositories.ucetni_denik_repository import (
    SqliteUcetniDenikRepository,
)
from infrastructure.database.repositories.uctova_osnova_repository import (
    SqliteUctovaOsnovaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork


UCET_VH_VE_SCHVALENI = "431.100"
"""Účet 431.100 — Výsledek hospodaření ve schvalovacím řízení (analytika)."""


@dataclass(frozen=True)
class PrenosZustatkuVysledek:
    """Výsledek přenosu KZ → PS."""

    rok_zdroj: int
    rok_cil: int
    pocet_zaznamu: int
    soucet_md: Money
    soucet_dal: Money
    vh: Money
    """Hospodářský výsledek roku zdroje. Kladný = zisk, záporný = ztráta."""

    @property
    def bilancuje(self) -> bool:
        return self.soucet_md == self.soucet_dal


class PrenosZustatkuCommand:
    """Přenos konečných zůstatků z roku N jako počátečních stavů roku N+1."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def prenest(self, z_roku: int, do_roku: int) -> PrenosZustatkuVysledek:
        """Spočítá KZ rozvahových účtů za z_roku a uloží jako PS do_roku.

        - Rozvahové účty (A, P): kladný zůstatek na své přirozené straně,
          záporný zůstatek (anomálie) na opačné straně.
        - Výsledkové účty (N, V): nepřenášejí se, VH se převede na 431.
        - Závěrkové účty (Z): nepřenášejí se.

        Idempotence: pokud do_roku už má jakékoli PS, raise ValidationError.
        """
        if do_roku != z_roku + 1:
            raise ValidationError(
                "Přenos je možný jen do následujícího roku "
                f"({z_roku} → {z_roku + 1})."
            )

        od = date(z_roku, 1, 1)
        do = date(z_roku, 12, 31)

        uow = self._uow_factory()
        with uow:
            ps_repo = SqlitePocatecniStavyRepository(uow)
            existing = ps_repo.list_by_rok(do_roku)
            if existing:
                raise ValidationError(
                    f"Pro rok {do_roku} už existují počáteční stavy "
                    f"({len(existing)} záznamů). Smažte je nejdřív."
                )

            denik = SqliteUcetniDenikRepository(uow)
            osnova = SqliteUctovaOsnovaRepository(uow)

            zaznamy = denik.list_by_obdobi(od, do, limit=1_000_000)

            obrat_md: dict[str, Money] = {}
            obrat_dal: dict[str, Money] = {}
            for z in zaznamy:
                obrat_md[z.md_ucet] = (
                    obrat_md.get(z.md_ucet, Money.zero()) + z.castka
                )
                obrat_dal[z.dal_ucet] = (
                    obrat_dal.get(z.dal_ucet, Money.zero()) + z.castka
                )

            dotcene = set(obrat_md.keys()) | set(obrat_dal.keys())
            ucty = {c: osnova.get_by_cislo(c) for c in dotcene}

            naklady_celkem = Money.zero()
            vynosy_celkem = Money.zero()
            ps_zaznamy: list[PocatecniStav] = []

            for cislo in sorted(ucty.keys()):
                ucet = ucty[cislo]
                md = obrat_md.get(cislo, Money.zero())
                dal = obrat_dal.get(cislo, Money.zero())

                if ucet.typ == TypUctu.NAKLADY:
                    naklady_celkem = naklady_celkem + (md - dal)
                    continue
                if ucet.typ == TypUctu.VYNOSY:
                    vynosy_celkem = vynosy_celkem + (dal - md)
                    continue
                if ucet.typ == TypUctu.VYPOCTOVY:
                    continue

                if ucet.typ == TypUctu.AKTIVA:
                    zustatek = md - dal
                    if zustatek.is_zero:
                        continue
                    strana = "MD" if zustatek.is_positive else "DAL"
                    ps_zaznamy.append(PocatecniStav(
                        ucet_kod=cislo,
                        castka=abs(zustatek),
                        strana=strana,
                        rok=do_roku,
                        poznamka=f"Přenos KZ z roku {z_roku}",
                    ))
                elif ucet.typ == TypUctu.PASIVA:
                    zustatek = dal - md
                    if zustatek.is_zero:
                        continue
                    strana = "DAL" if zustatek.is_positive else "MD"
                    ps_zaznamy.append(PocatecniStav(
                        ucet_kod=cislo,
                        castka=abs(zustatek),
                        strana=strana,
                        rok=do_roku,
                        poznamka=f"Přenos KZ z roku {z_roku}",
                    ))

            vh = vynosy_celkem - naklady_celkem
            if not vh.is_zero:
                strana_vh = "DAL" if vh.is_positive else "MD"
                ps_zaznamy.append(PocatecniStav(
                    ucet_kod=UCET_VH_VE_SCHVALENI,
                    castka=abs(vh),
                    strana=strana_vh,
                    rok=do_roku,
                    poznamka=f"VH za rok {z_roku} ({'zisk' if vh.is_positive else 'ztráta'})",
                ))

            for ps in ps_zaznamy:
                ps_repo.add(ps)

            soucet_md = Money.zero()
            soucet_dal = Money.zero()
            for ps in ps_zaznamy:
                if ps.strana == "MD":
                    soucet_md = soucet_md + ps.castka
                else:
                    soucet_dal = soucet_dal + ps.castka

            if soucet_md != soucet_dal:
                raise ValidationError(
                    f"Přenos nebilancuje: MD {soucet_md.format_cz()} "
                    f"≠ DAL {soucet_dal.format_cz()}. "
                    f"Rozdíl: {(soucet_md - soucet_dal).format_cz()}."
                )

            uow.commit()

            return PrenosZustatkuVysledek(
                rok_zdroj=z_roku,
                rok_cil=do_roku,
                pocet_zaznamu=len(ps_zaznamy),
                soucet_md=soucet_md,
                soucet_dal=soucet_dal,
                vh=vh,
            )
