"""UctovyPredpis — sada účetních zápisů jednoho dokladu.

Podvojnost je inherentně zaručena strukturou (každý UcetniZaznam má MD+Dal+castka).
Validuje konzistenci: stejný doklad_id, stejné datum, žádné duplicity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from domain.shared.errors import ValidationError
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam


@dataclass(frozen=True)
class UctovyPredpis:
    """Sada účetních zápisů jednoho dokladu — validuje konzistenci."""

    doklad_id: int
    zaznamy: tuple[UcetniZaznam, ...]

    def __post_init__(self) -> None:
        # 1. Alespoň jeden záznam
        if not self.zaznamy:
            raise ValidationError(
                "Účetní předpis musí obsahovat alespoň jeden zápis"
            )

        # 2. Všechny záznamy mají stejný doklad_id
        for z in self.zaznamy:
            if z.doklad_id != self.doklad_id:
                raise ValidationError(
                    f"Záznam má doklad_id={z.doklad_id}, "
                    f"očekáváno {self.doklad_id}"
                )

        # 3. Všechny záznamy mají stejné datum
        data = {z.datum for z in self.zaznamy}
        if len(data) > 1:
            raise ValidationError(
                f"Záznamy předpisu mají různá data: {sorted(data)}. "
                f"Jeden účetní předpis = jeden den."
            )

        # 4. Žádné duplicitní zápisy (stejné MD, Dal, castka, popis)
        seen: set[tuple[str, str, int, str | None]] = set()
        for z in self.zaznamy:
            key = (z.md_ucet, z.dal_ucet, z.castka.to_halire(), z.popis)
            if key in seen:
                raise ValidationError("Duplicitní účetní zápis v předpisu")
            seen.add(key)

    @classmethod
    def jednoduchy(
        cls,
        doklad_id: int,
        datum: date,
        md_ucet: str,
        dal_ucet: str,
        castka: Money,
        popis: str | None = None,
    ) -> UctovyPredpis:
        """Factory pro nejčastější případ — jeden zápis MD/Dal."""
        zaznam = UcetniZaznam(
            doklad_id=doklad_id,
            datum=datum,
            md_ucet=md_ucet,
            dal_ucet=dal_ucet,
            castka=castka,
            popis=popis,
        )
        return cls(doklad_id=doklad_id, zaznamy=(zaznam,))

    @classmethod
    def storno_z_zaznamu(
        cls,
        originaly: tuple[UcetniZaznam, ...],
        datum: date,
        popis_override: str | None = None,
    ) -> UctovyPredpis:
        """Factory pro opravný (storno) předpis.

        Pro každý ``originaly[i]`` vytvoří protizápis s:
          * prohozenými MD ↔ Dal,
          * shodnou kladnou částkou (Varianta A — ne červený zápis),
          * ``je_storno=True`` + ``stornuje_zaznam_id = originaly[i].id``,
          * datum = ``datum``.

        Args:
            popis_override: pokud je vyplněn, použije se jako popis storno
                zápisů (např. uživatelská poznámka "Duplicitní zaúčtování").
                Bez něj popis = "Storno: {orig.popis}" / "Storno".

        Pre-condition: všechny originály musí mít stejný ``doklad_id``
        a musí být už persistované (``id is not None``). Originály smí být
        jen „čisté" zápisy — nelze stornovat už jednou stornovaný zápis
        (``originaly[i].je_storno`` musí být False).

        Raises:
            ValidationError: originály prázdné / různý doklad_id / bez id /
                už stornované.
        """
        if not originaly:
            raise ValidationError(
                "storno_z_zaznamu: seznam originálů je prázdný."
            )

        doklad_ids = {z.doklad_id for z in originaly}
        if len(doklad_ids) > 1:
            raise ValidationError(
                f"storno_z_zaznamu: originály mají různý doklad_id: "
                f"{sorted(doklad_ids)}"
            )

        for z in originaly:
            if z.id is None:
                raise ValidationError(
                    "storno_z_zaznamu: originál musí být persistovaný "
                    "(id is None)."
                )
            if z.je_storno:
                raise ValidationError(
                    "storno_z_zaznamu: nelze stornovat už stornovaný "
                    "záznam."
                )

        doklad_id = originaly[0].doklad_id

        def _popis_for(orig: UcetniZaznam) -> str:
            if popis_override is not None and popis_override.strip():
                return f"Storno: {popis_override.strip()}"
            return f"Storno: {orig.popis}" if orig.popis else "Storno"

        storno_zaznamy = tuple(
            UcetniZaznam(
                doklad_id=z.doklad_id,
                datum=datum,
                md_ucet=z.dal_ucet,   # prohozené strany
                dal_ucet=z.md_ucet,
                castka=z.castka,
                popis=_popis_for(z),
                je_storno=True,
                stornuje_zaznam_id=z.id,
            )
            for z in originaly
        )
        return cls(doklad_id=doklad_id, zaznamy=storno_zaznamy)

    @property
    def soucet_md(self) -> dict[str, Money]:
        """Součty po účtech na straně MD: {ucet_cislo: Money}."""
        result: dict[str, Money] = {}
        for z in self.zaznamy:
            result[z.md_ucet] = result.get(z.md_ucet, Money.zero()) + z.castka
        return result

    @property
    def soucet_dal(self) -> dict[str, Money]:
        """Součty po účtech na straně Dal: {ucet_cislo: Money}."""
        result: dict[str, Money] = {}
        for z in self.zaznamy:
            result[z.dal_ucet] = result.get(z.dal_ucet, Money.zero()) + z.castka
        return result

    @property
    def celkova_castka(self) -> Money:
        """Suma všech zápisů (MD = Dal díky struktuře)."""
        total = Money.zero()
        for z in self.zaznamy:
            total = total + z.castka
        return total
