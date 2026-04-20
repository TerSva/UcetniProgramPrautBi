"""UcetniDenikViewModel — ViewModel pro stránku Účetní deník."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from domain.shared.money import Money
from infrastructure.database.unit_of_work import SqliteUnitOfWork


@dataclass(frozen=True)
class UcetniDenikRow:
    """Jeden řádek účetního deníku pro UI."""

    id: int
    datum: date
    doklad_id: int
    doklad_cislo: str
    md_ucet: str
    dal_ucet: str
    castka: Money
    popis: str | None
    je_storno: bool


class UcetniDenikViewModel:
    """ViewModel pro stránku Účetní deník."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        ucetni_rok: int | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._ucetni_rok = ucetni_rok
        self._items: list[UcetniDenikRow] = []
        self._error: str | None = None

    @property
    def ucetni_rok(self) -> int:
        """Aktuální účetní rok (fallback na aktuální kalendářní rok)."""
        return self._ucetni_rok if self._ucetni_rok is not None else date.today().year

    @property
    def items(self) -> list[UcetniDenikRow]:
        return list(self._items)

    @property
    def error(self) -> str | None:
        return self._error

    def load(self, od: date, do: date) -> None:
        """Načte záznamy účetního deníku za období."""
        self._error = None
        try:
            uow = self._uow_factory()
            with uow:
                rows = uow.connection.execute(
                    "SELECT z.id, z.datum, z.doklad_id, d.cislo AS doklad_cislo, "
                    "z.md_ucet, z.dal_ucet, z.castka, z.popis, z.je_storno "
                    "FROM ucetni_zaznamy z "
                    "JOIN doklady d ON d.id = z.doklad_id "
                    "WHERE z.datum >= ? AND z.datum <= ? "
                    "ORDER BY z.datum DESC, z.id DESC "
                    "LIMIT 5000",
                    (od.isoformat(), do.isoformat()),
                ).fetchall()
                self._items = [
                    UcetniDenikRow(
                        id=r["id"],
                        datum=date.fromisoformat(r["datum"]),
                        doklad_id=r["doklad_id"],
                        doklad_cislo=r["doklad_cislo"],
                        md_ucet=r["md_ucet"],
                        dal_ucet=r["dal_ucet"],
                        castka=Money(r["castka"]),
                        popis=r["popis"],
                        je_storno=bool(r["je_storno"]),
                    )
                    for r in rows
                ]
        except Exception as e:
            self._error = str(e)
            self._items = []
