from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import ClassVar


@dataclass(frozen=True)
class Money:
    """Immutable value object pro peněžní částky.

    Interně ukládá haléře (int) pro bezeztrátové SQL operace.
    DB sloupce: INTEGER NOT NULL DEFAULT 0
    SQL agregace: SUM(castka_hal) — žádný CAST.
    """

    _halere: int
    mena: str = "CZK"

    @classmethod
    def koruny(cls, castka: Decimal | str | int | float, mena: str = "CZK") -> Money:
        """Vytvoří Money z částky v korunách: Money.koruny("1234.50")"""
        d = Decimal(str(castka)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return cls(_halere=int(d * 100), mena=mena)

    @classmethod
    def halere(cls, hal: int, mena: str = "CZK") -> Money:
        """Vytvoří Money z haléřů (pro načtení z DB): Money.halere(123450)"""
        if not isinstance(hal, int):
            raise TypeError(f"halere() očekává int, dostal {type(hal).__name__}")
        return cls(_halere=hal, mena=mena)

    @classmethod
    def nula(cls, mena: str = "CZK") -> Money:
        """Money.nula() — nulová částka."""
        return cls(_halere=0, mena=mena)

    @property
    def castka(self) -> Decimal:
        """Vrátí částku jako Decimal: Decimal('1234.50')"""
        return Decimal(self._halere) / Decimal(100)

    @property
    def halere_int(self) -> int:
        """Pro uložení do DB: 123450"""
        return self._halere

    def _kontrola_meny(self, other: Money) -> None:
        if not isinstance(other, Money):
            raise TypeError(f"Nelze operovat s {type(other).__name__}")
        if self.mena != other.mena:
            raise ValueError(f"Nelze míchat měny: {self.mena} a {other.mena}")

    def __add__(self, other: Money) -> Money:
        self._kontrola_meny(other)
        return Money(self._halere + other._halere, self.mena)

    def __sub__(self, other: Money) -> Money:
        self._kontrola_meny(other)
        return Money(self._halere - other._halere, self.mena)

    def __neg__(self) -> Money:
        return Money(-self._halere, self.mena)

    def __abs__(self) -> Money:
        return Money(abs(self._halere), self.mena)

    def __mul__(self, factor: int | Decimal) -> Money:
        if isinstance(factor, int):
            return Money(self._halere * factor, self.mena)
        if isinstance(factor, Decimal):
            result = (Decimal(self._halere) * factor).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
            return Money(int(result), self.mena)
        raise TypeError(f"Nelze násobit Money s {type(factor).__name__}")

    def __gt__(self, other: object) -> bool:
        if isinstance(other, Money):
            self._kontrola_meny(other)
            return self._halere > other._halere
        if other == 0:
            return self._halere > 0
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Money):
            self._kontrola_meny(other)
            return self._halere < other._halere
        if other == 0:
            return self._halere < 0
        return NotImplemented

    def __ge__(self, other: object) -> bool:
        if isinstance(other, Money):
            self._kontrola_meny(other)
            return self._halere >= other._halere
        if other == 0:
            return self._halere >= 0
        return NotImplemented

    def __le__(self, other: object) -> bool:
        if isinstance(other, Money):
            self._kontrola_meny(other)
            return self._halere <= other._halere
        if other == 0:
            return self._halere <= 0
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._halere == other._halere and self.mena == other.mena

    def __hash__(self) -> int:
        return hash((self._halere, self.mena))

    def __bool__(self) -> bool:
        return self._halere != 0

    def __repr__(self) -> str:
        return f"Money({self.castka:.2f}, '{self.mena}')"

    def format_cz(self) -> str:
        """Formát pro české UI: '1 234,50 Kč' (nbsp jako oddělovač tisíců)."""
        sign = "-" if self._halere < 0 else ""
        abs_hal = abs(self._halere)
        cela = abs_hal // 100
        des = abs_hal % 100
        cela_str = f"{cela:,}".replace(",", "\u00a0")
        symbol = {"CZK": "Kč", "EUR": "€", "USD": "$"}.get(self.mena, self.mena)
        return f"{sign}{cela_str},{des:02d} {symbol}"

    ZERO_CZK: ClassVar[Money]


Money.ZERO_CZK = Money(0, "CZK")  # type: ignore[misc]
