"""Money value object — základ celého účetního systému.

Vnitřní reprezentace: int v haléřích. Money(12345) = 123,45 Kč.
Žádný Decimal, žádný float, žádný str pro peněžní částky v doméně.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, localcontext


# Regex pro from_koruny string parsing.
# Akceptuje: "123,45", "123.45", "1 234,56", "1234", "-123,45"
# NEakceptuje: "1,234.56" (anglický formát), prázdný string, písmena
_PATTERN = re.compile(
    r"^\s*(?P<sign>-?)\s*(?P<whole>[\d \u00a0]+)(?:[,.](?P<frac>\d{1,2}))?\s*$"
)


@dataclass(frozen=True)
class Money:
    """Immutable value object pro peněžní částky v CZK.

    Interně INTEGER v haléřích. Money(12345) = 123,45 Kč.
    DB sloupce: castka_hal INTEGER NOT NULL DEFAULT 0
    SQL agregace: SUM(castka_hal) — žádný CAST.
    """

    halire: int

    def __post_init__(self) -> None:
        if not isinstance(self.halire, int):
            raise TypeError(
                f"Money očekává int (haléře), dostal {type(self.halire).__name__}"
            )

    # --- Factory metody ---

    @classmethod
    def from_koruny(cls, koruny: Decimal | str | int) -> Money:
        """Vytvoří Money z korun.

        Akceptuje:
          - Decimal("123.45")
          - "123,45" (česká čárka)
          - "123.45" (tečka — pro CSV importy)
          - "1 234,56" (mezera jako tisícový oddělovač)
          - "1234" (celé číslo)
          - "-123,45" (záporné)
          - int (celé koruny)

        Float → TypeError. Neplatný formát → ValueError.
        """
        if isinstance(koruny, float):
            raise TypeError(
                "Money.from_koruny() nepřijímá float — použij Decimal nebo str. "
                f"Dostal: {koruny!r}"
            )

        if isinstance(koruny, int):
            return cls(halire=koruny * 100)

        if isinstance(koruny, Decimal):
            with localcontext() as ctx:
                ctx.rounding = ROUND_HALF_UP
                halire = int(koruny.quantize(Decimal("0.01")) * 100)
            return cls(halire=halire)

        if isinstance(koruny, str):
            return cls._parse_string(koruny)

        raise TypeError(
            f"Money.from_koruny() očekává Decimal, str nebo int, "
            f"dostal {type(koruny).__name__}"
        )

    @classmethod
    def _parse_string(cls, text: str) -> Money:
        """Parsuje český/standardní formát částky ze stringu."""
        # Odmítnout anglický formát "1,234.56" — čárka před tečkou = katastrofa
        if "," in text and "." in text:
            raise ValueError(
                f"Neplatný formát částky: {text!r}. "
                "Smíšení čárky a tečky není podporováno — "
                "použij buď českou čárku (123,45) nebo tečku (123.45)."
            )

        match = _PATTERN.match(text)
        if not match:
            raise ValueError(
                f"Neplatný formát částky: {text!r}. "
                "Akceptované formáty: '123,45', '123.45', '1 234,56', '1234', '-123,45'."
            )

        sign = -1 if match.group("sign") == "-" else 1
        whole_str = match.group("whole").replace(" ", "").replace("\u00a0", "")
        frac_str = match.group("frac") or "0"

        if not whole_str:
            raise ValueError(f"Neplatný formát částky: {text!r}.")

        # Doplnit na 2 desetinná místa: "5" → "50", "05" → "05"
        if len(frac_str) == 1:
            frac_str += "0"

        whole = int(whole_str)
        frac = int(frac_str)
        halire = sign * (whole * 100 + frac)
        return cls(halire=halire)

    @classmethod
    def zero(cls) -> Money:
        """Nulová částka."""
        return cls(halire=0)

    # --- Aritmetika ---

    def __add__(self, other: object) -> Money:
        if not isinstance(other, Money):
            raise TypeError(
                f"Nelze sčítat Money s {type(other).__name__}. "
                "Použij Money + Money."
            )
        return Money(self.halire + other.halire)

    def __sub__(self, other: object) -> Money:
        if not isinstance(other, Money):
            raise TypeError(
                f"Nelze odčítat {type(other).__name__} od Money. "
                "Použij Money - Money."
            )
        return Money(self.halire - other.halire)

    def __mul__(self, scalar: object) -> Money:
        if isinstance(scalar, Money):
            raise TypeError(
                "Nelze násobit Money × Money (Kč × Kč nedává smysl). "
                "Použij Money * int nebo Money * Decimal."
            )
        if isinstance(scalar, float):
            raise TypeError(
                "Nelze násobit Money s float — použij Decimal pro přesnost. "
                f"Dostal: {scalar!r}"
            )
        if isinstance(scalar, int):
            return Money(self.halire * scalar)
        if isinstance(scalar, Decimal):
            with localcontext() as ctx:
                ctx.rounding = ROUND_HALF_UP
                result = (Decimal(self.halire) * scalar).quantize(Decimal("1"))
            return Money(int(result))
        raise TypeError(f"Nelze násobit Money s {type(scalar).__name__}.")

    def __rmul__(self, scalar: object) -> Money:
        return self.__mul__(scalar)

    def __truediv__(self, scalar: object) -> Money:
        if isinstance(scalar, Money):
            raise TypeError(
                "Nelze dělit Money / Money (výsledek by nebyly Kč). "
                "Pro poměr dvou částek použij a.to_halire() / b.to_halire()."
            )
        if isinstance(scalar, float):
            raise TypeError(
                "Nelze dělit Money s float — použij Decimal pro přesnost. "
                f"Dostal: {scalar!r}"
            )
        if isinstance(scalar, int):
            if scalar == 0:
                raise ZeroDivisionError("Dělení Money nulou.")
            with localcontext() as ctx:
                ctx.rounding = ROUND_HALF_UP
                result = (Decimal(self.halire) / Decimal(scalar)).quantize(
                    Decimal("1")
                )
            return Money(int(result))
        if isinstance(scalar, Decimal):
            if scalar == 0:
                raise ZeroDivisionError("Dělení Money nulou.")
            with localcontext() as ctx:
                ctx.rounding = ROUND_HALF_UP
                result = (Decimal(self.halire) / scalar).quantize(Decimal("1"))
            return Money(int(result))
        raise TypeError(f"Nelze dělit Money s {type(scalar).__name__}.")

    # --- Porovnání (jen mezi Money) ---

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.halire == other.halire

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.halire < other.halire

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.halire <= other.halire

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.halire > other.halire

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.halire >= other.halire

    # --- Vlastnosti ---

    @property
    def is_zero(self) -> bool:
        return self.halire == 0

    @property
    def is_positive(self) -> bool:
        return self.halire > 0

    @property
    def is_negative(self) -> bool:
        return self.halire < 0

    def __abs__(self) -> Money:
        return Money(abs(self.halire))

    def negate(self) -> Money:
        """Vrátí Money s opačným znaménkem. Pro storno operace."""
        return Money(-self.halire)

    # --- Konverze ven ---

    def to_koruny(self) -> Decimal:
        """Decimal('123.45') — pro export, výpočty mimo doménu."""
        return Decimal(self.halire) / Decimal(100)

    def to_halire(self) -> int:
        """Int v haléřích — pro DB perzistenci (INTEGER sloupec)."""
        return self.halire

    def format_cz(self) -> str:
        """České formátování: '1\u00a0234,56 Kč' (non-breaking space jako tisícový oddělovač)."""
        sign = "-" if self.halire < 0 else ""
        abs_hal = abs(self.halire)
        cela = abs_hal // 100
        des = abs_hal % 100
        cela_str = f"{cela:,}".replace(",", "\u00a0")
        return f"{sign}{cela_str},{des:02d}\u00a0Kč"

    # --- Reprezentace ---

    def __repr__(self) -> str:
        """Money(12345)"""
        return f"Money({self.halire})"

    def __str__(self) -> str:
        """České formátování — alias pro format_cz()."""
        return self.format_cz()
