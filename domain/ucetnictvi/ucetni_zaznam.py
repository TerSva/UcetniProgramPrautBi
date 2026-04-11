"""UcetniZaznam — immutable entita jednoho řádku účetního deníku.

Jeden záznam = MD účet / Dal účet / částka. Jednou zapsaný se NIKDY nemění.
Storno přes nový záznam s prohozenými stranami (opravný doklad).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from domain.shared.errors import ValidationError
from domain.shared.money import Money

_UCET_RE = re.compile(r"^\d{3,6}$")


@dataclass(frozen=True)
class UcetniZaznam:
    """Jeden řádek účetního deníku — immutable."""

    doklad_id: int
    datum: date
    md_ucet: str
    dal_ucet: str
    castka: Money
    popis: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        # doklad_id — kladný int, ne bool
        if (
            not isinstance(self.doklad_id, int)
            or isinstance(self.doklad_id, bool)
            or self.doklad_id <= 0
        ):
            raise ValidationError("doklad_id musí být kladný int")

        # md_ucet
        if not isinstance(self.md_ucet, str) or not _UCET_RE.match(self.md_ucet):
            raise ValidationError(
                f"md_ucet musí být 3-6 číslic, got: {self.md_ucet!r}"
            )

        # dal_ucet
        if not isinstance(self.dal_ucet, str) or not _UCET_RE.match(self.dal_ucet):
            raise ValidationError(
                f"dal_ucet musí být 3-6 číslic, got: {self.dal_ucet!r}"
            )

        # md_ucet != dal_ucet
        if self.md_ucet == self.dal_ucet:
            raise ValidationError(
                f"Nelze účtovat účet sám na sebe: {self.md_ucet}"
            )

        # castka — Money, striktně kladná
        if not isinstance(self.castka, Money):
            raise TypeError("castka musí být Money")
        if not self.castka.is_positive:
            raise ValidationError(
                "castka musí být kladná (storno = prohozené MD/Dal)"
            )

        # popis — max 500 znaků
        if self.popis is not None and len(self.popis) > 500:
            raise ValidationError("popis max 500 znaků")

        # id — pokud zadáno, kladný int
        if self.id is not None:
            if (
                not isinstance(self.id, int)
                or isinstance(self.id, bool)
                or self.id <= 0
            ):
                raise ValidationError("id musí být kladný int nebo None")

    def with_id(self, new_id: int) -> UcetniZaznam:
        """Vrátí novou instanci s naplněným id (po uložení do DB)."""
        return UcetniZaznam(
            doklad_id=self.doklad_id,
            datum=self.datum,
            md_ucet=self.md_ucet,
            dal_ucet=self.dal_ucet,
            castka=self.castka,
            popis=self.popis,
            id=new_id,
        )
