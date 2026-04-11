"""Doklad — doménová entita s identitou, stavovým strojem a invarianty.

Pure Python + Money + stdlib. Žádný import z infrastructure/, services/, ui/.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from domain.doklady.typy import StavDokladu, TypDokladu
from domain.shared.errors import ValidationError
from domain.shared.money import Money

# Povolené znaky v čísle dokladu: alfanumerické + -, /, _
_CISLO_PATTERN = re.compile(r"^[A-Za-z0-9\-/_]+$")

# Maximální délky
_CISLO_MAX = 50
_POPIS_MAX = 500

# Sanity check: DUZP nesmí být víc než rok po vystavení
_MAX_ZP_OFFSET = timedelta(days=366)


class Doklad:
    """Doménová entita Doklad.

    Má identitu (id), životní cyklus (stavový stroj), a obsahuje invarianty.
    Mutace jen přes metody, nikdy přímý setattr na business polích.
    """

    def __init__(
        self,
        cislo: str,
        typ: TypDokladu,
        datum_vystaveni: date,
        castka_celkem: Money,
        partner_id: int | None = None,
        datum_zdanitelneho_plneni: date | None = None,
        datum_splatnosti: date | None = None,
        popis: str | None = None,
        stav: StavDokladu = StavDokladu.NOVY,
        id: int | None = None,
    ) -> None:
        # Validace cislo
        if not cislo or not cislo.strip():
            raise ValidationError("Číslo dokladu nesmí být prázdné.")
        if len(cislo) > _CISLO_MAX:
            raise ValidationError(
                f"Číslo dokladu max {_CISLO_MAX} znaků, dostal {len(cislo)}."
            )
        if not _CISLO_PATTERN.match(cislo):
            raise ValidationError(
                f"Číslo dokladu obsahuje neplatné znaky: {cislo!r}. "
                "Povolené: alfanumerické, -, /, _."
            )

        # Validace castka_celkem
        if not isinstance(castka_celkem, Money):
            raise TypeError(
                f"castka_celkem musí být Money, dostal {type(castka_celkem).__name__}."
            )

        # Validace partner_id
        if partner_id is not None:
            if not isinstance(partner_id, int):
                raise TypeError(
                    f"partner_id musí být int nebo None, dostal {type(partner_id).__name__}."
                )
            if partner_id <= 0:
                raise ValidationError(
                    f"partner_id musí být kladný, dostal {partner_id}."
                )

        # Validace datum_splatnosti
        if datum_splatnosti is not None and datum_splatnosti < datum_vystaveni:
            raise ValidationError(
                f"Datum splatnosti ({datum_splatnosti}) nesmí být před "
                f"datem vystavení ({datum_vystaveni})."
            )

        # Validace datum_zdanitelneho_plneni
        if datum_zdanitelneho_plneni is not None:
            if datum_zdanitelneho_plneni > datum_vystaveni + _MAX_ZP_OFFSET:
                raise ValidationError(
                    f"Datum zdanitelného plnění ({datum_zdanitelneho_plneni}) "
                    f"je víc než rok po vystavení ({datum_vystaveni})."
                )

        # Validace popis
        if popis is not None and len(popis) > _POPIS_MAX:
            raise ValidationError(
                f"Popis max {_POPIS_MAX} znaků, dostal {len(popis)}."
            )

        self._id = id
        self._cislo = cislo
        self._typ = typ
        self._datum_vystaveni = datum_vystaveni
        self._datum_zdanitelneho_plneni = datum_zdanitelneho_plneni
        self._datum_splatnosti = datum_splatnosti
        self._partner_id = partner_id
        self._castka_celkem = castka_celkem
        self._popis = popis
        self._stav = stav

    # --- Properties ---

    @property
    def id(self) -> int | None:
        return self._id

    @property
    def cislo(self) -> str:
        return self._cislo

    @property
    def typ(self) -> TypDokladu:
        return self._typ

    @property
    def datum_vystaveni(self) -> date:
        return self._datum_vystaveni

    @property
    def datum_zdanitelneho_plneni(self) -> date | None:
        return self._datum_zdanitelneho_plneni

    @property
    def datum_splatnosti(self) -> date | None:
        return self._datum_splatnosti

    @property
    def partner_id(self) -> int | None:
        return self._partner_id

    @property
    def castka_celkem(self) -> Money:
        return self._castka_celkem

    @property
    def popis(self) -> str | None:
        return self._popis

    @property
    def stav(self) -> StavDokladu:
        return self._stav

    # --- Stavový stroj ---

    def zauctuj(self) -> None:
        """NOVY → ZAUCTOVANY. Jiný výchozí stav → ValidationError."""
        self._prechod(
            povolene_z={StavDokladu.NOVY},
            cilovy=StavDokladu.ZAUCTOVANY,
            akce="zaúčtovat",
        )

    def oznac_uhrazeny(self) -> None:
        """ZAUCTOVANY/CASTECNE_UHRAZENY → UHRAZENY."""
        self._prechod(
            povolene_z={StavDokladu.ZAUCTOVANY, StavDokladu.CASTECNE_UHRAZENY},
            cilovy=StavDokladu.UHRAZENY,
            akce="označit jako uhrazený",
        )

    def oznac_castecne_uhrazeny(self) -> None:
        """ZAUCTOVANY → CASTECNE_UHRAZENY."""
        self._prechod(
            povolene_z={StavDokladu.ZAUCTOVANY},
            cilovy=StavDokladu.CASTECNE_UHRAZENY,
            akce="označit jako částečně uhrazený",
        )

    def stornuj(self) -> None:
        """Cokoliv kromě STORNOVANY a UHRAZENY → STORNOVANY."""
        if self._stav == StavDokladu.UHRAZENY:
            raise ValidationError(
                "Doklad ve stavu UHRAZENY nelze stornovat."
            )
        self._prechod(
            povolene_z={
                StavDokladu.NOVY,
                StavDokladu.ZAUCTOVANY,
                StavDokladu.CASTECNE_UHRAZENY,
            },
            cilovy=StavDokladu.STORNOVANY,
            akce="stornovat",
        )

    def _prechod(
        self,
        povolene_z: set[StavDokladu],
        cilovy: StavDokladu,
        akce: str,
    ) -> None:
        """Provede stavový přechod nebo vyhodí ValidationError."""
        if self._stav not in povolene_z:
            raise ValidationError(
                f"Nelze {akce} doklad ve stavu {self._stav.value}. "
                f"Povoleno z: {', '.join(s.value for s in povolene_z)}."
            )
        self._stav = cilovy

    # --- Editace (omezená dle stavu) ---

    def uprav_popis(self, novy_popis: str | None) -> None:
        """Popis lze měnit kdykoli kromě STORNOVANY."""
        if self._stav == StavDokladu.STORNOVANY:
            raise ValidationError(
                "Nelze upravovat stornovaný doklad."
            )
        if novy_popis is not None and len(novy_popis) > _POPIS_MAX:
            raise ValidationError(
                f"Popis max {_POPIS_MAX} znaků, dostal {len(novy_popis)}."
            )
        self._popis = novy_popis

    def uprav_splatnost(self, nova_splatnost: date | None) -> None:
        """Splatnost lze měnit jen ve stavu NOVY."""
        if self._stav != StavDokladu.NOVY:
            raise ValidationError(
                f"Splatnost lze měnit jen ve stavu NOVY, "
                f"aktuální stav: {self._stav.value}."
            )
        if nova_splatnost is not None and nova_splatnost < self._datum_vystaveni:
            raise ValidationError(
                f"Datum splatnosti ({nova_splatnost}) nesmí být před "
                f"datem vystavení ({self._datum_vystaveni})."
            )
        self._datum_splatnosti = nova_splatnost

    # --- Equality / Hash ---

    def __eq__(self, other: object) -> bool:
        """Doklady se stejným id jsou si rovny. Bez id jen identity."""
        if not isinstance(other, Doklad):
            return NotImplemented
        if self._id is not None and other._id is not None:
            return self._id == other._id
        return self is other

    def __hash__(self) -> int:
        if self._id is not None:
            return hash(self._id)
        return hash(id(self))

    def __repr__(self) -> str:
        return (
            f"Doklad(id={self._id}, cislo={self._cislo!r}, "
            f"typ={self._typ.value}, stav={self._stav.value}, "
            f"castka={self._castka_celkem.format_cz()})"
        )
