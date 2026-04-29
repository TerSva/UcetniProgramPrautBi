"""Doklad — doménová entita s identitou, stavovým strojem a invarianty.

Pure Python + Money + stdlib. Žádný import z infrastructure/, services/, ui/.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal

from domain.doklady.typy import DphRezim, Mena, StavDokladu, TypDokladu
from domain.shared.errors import ValidationError
from domain.shared.money import Money

# Povolené znaky v čísle dokladu: alfanumerické + -, /, _
_CISLO_PATTERN = re.compile(r"^[A-Za-z0-9\-/_]+$")

# Maximální délky
_CISLO_MAX = 50
_POPIS_MAX = 500
_POZNAMKA_DORESENI_MAX = 500
_VS_MAX = 10

# Variabilní symbol: jen číslice
_VS_PATTERN = re.compile(r"^\d+$")

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
        k_doreseni: bool = False,
        poznamka_doreseni: str | None = None,
        mena: Mena = Mena.CZK,
        castka_mena: Money | None = None,
        kurz: Decimal | None = None,
        variabilni_symbol: str | None = None,
        dph_rezim: DphRezim = DphRezim.TUZEMSKO,
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

        # Validace k_doreseni — strict bool (isinstance propustí int, musíme type())
        if type(k_doreseni) is not bool:
            raise TypeError(
                f"k_doreseni musí být bool, "
                f"dostal {type(k_doreseni).__name__}."
            )

        # Validace poznamka_doreseni
        if poznamka_doreseni is not None:
            if len(poznamka_doreseni) > _POZNAMKA_DORESENI_MAX:
                raise ValidationError(
                    f"Poznámka k dořešení max {_POZNAMKA_DORESENI_MAX} znaků, "
                    f"dostal {len(poznamka_doreseni)}."
                )

        # Invariant: poznámka může existovat jen s flagem
        if not k_doreseni and poznamka_doreseni is not None:
            raise ValidationError(
                "Poznámka k dořešení může existovat jen když k_doreseni=True."
            )

        # Invariant: stornovaný doklad nesmí být flagnutý
        if stav == StavDokladu.STORNOVANY and k_doreseni:
            raise ValidationError(
                "Stornované doklady nelze flagovat k dořešení."
            )

        # Validace cizoměnových polí
        if mena != Mena.CZK:
            if kurz is None or kurz <= 0:
                raise ValidationError(
                    f"Pro měnu {mena.value} je kurz povinný a musí být kladný."
                )
            if castka_mena is None:
                raise ValidationError(
                    f"Pro měnu {mena.value} je částka v cizí měně povinná."
                )
        else:
            if kurz is not None or castka_mena is not None:
                raise ValidationError(
                    "Pro CZK nelze zadávat kurz ani částku v cizí měně."
                )

        # Validace variabilni_symbol
        if variabilni_symbol is not None:
            if not _VS_PATTERN.match(variabilni_symbol):
                raise ValidationError(
                    f"Variabilní symbol smí obsahovat pouze číslice, "
                    f"dostal {variabilni_symbol!r}."
                )
            if len(variabilni_symbol) > _VS_MAX:
                raise ValidationError(
                    f"Variabilní symbol max {_VS_MAX} znaků, "
                    f"dostal {len(variabilni_symbol)}."
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
        self._k_doreseni = k_doreseni
        self._poznamka_doreseni = poznamka_doreseni
        self._mena = mena
        self._castka_mena = castka_mena
        self._kurz = kurz
        self._variabilni_symbol = variabilni_symbol
        self._dph_rezim = dph_rezim

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

    @property
    def k_doreseni(self) -> bool:
        return self._k_doreseni

    @property
    def poznamka_doreseni(self) -> str | None:
        return self._poznamka_doreseni

    @property
    def mena(self) -> Mena:
        return self._mena

    @property
    def castka_mena(self) -> Money | None:
        return self._castka_mena

    @property
    def kurz(self) -> Decimal | None:
        return self._kurz

    @property
    def variabilni_symbol(self) -> str | None:
        return self._variabilni_symbol

    @property
    def dph_rezim(self) -> DphRezim:
        return self._dph_rezim

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

    def zrus_uhradu(self) -> None:
        """UHRAZENY → ZAUCTOVANY (reverz při smazání výpisu / odpárování)."""
        self._prechod(
            povolene_z={StavDokladu.UHRAZENY},
            cilovy=StavDokladu.ZAUCTOVANY,
            akce="zrušit úhradu",
        )

    def oznac_castecne_uhrazeny(self) -> None:
        """ZAUCTOVANY → CASTECNE_UHRAZENY."""
        self._prechod(
            povolene_z={StavDokladu.ZAUCTOVANY},
            cilovy=StavDokladu.CASTECNE_UHRAZENY,
            akce="označit jako částečně uhrazený",
        )

    def stornuj(self) -> None:
        """Cokoliv kromě STORNOVANY a UHRAZENY → STORNOVANY.

        Navíc: pokud má doklad k_doreseni=True, flag a poznámka se
        automaticky vymažou (storno uzavírá workflow — není co "dořešit").
        Clear flagu proběhne AŽ po úspěšné validaci stavu, takže při
        selhání (např. UHRAZENY) zůstávají flag i poznámka beze změny.
        """
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
        # Auto-clear flagu — až po úspěšném přechodu stavu
        self._k_doreseni = False
        self._poznamka_doreseni = None

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

    def uprav_partner(self, partner_id: int | None) -> None:
        """Partner lze měnit kdykoli kromě STORNOVANY."""
        if self._stav == StavDokladu.STORNOVANY:
            raise ValidationError(
                "Nelze upravovat stornovaný doklad."
            )
        if partner_id is not None:
            if not isinstance(partner_id, int) or partner_id <= 0:
                raise ValidationError(
                    f"partner_id musí být kladný int nebo None, dostal {partner_id}."
                )
        self._partner_id = partner_id

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

    # --- Flag "k dořešení" (ortogonální k stavu) ---

    def oznac_k_doreseni(self, poznamka: str | None = None) -> None:
        """Označí doklad, že vyžaduje pozornost uživatelky.

        Povoleno v jakémkoli stavu KROMĚ STORNOVANY.
        Idempotentní: pokud už k_doreseni=True, funguje jako update poznámky
        (vědomá výjimka z pravidla "žádná idempotence" — flag je checkbox,
        ne stavový přechod workflow).

        Args:
            poznamka: volitelný text max 500 znaků. None = flag bez poznámky.

        Raises:
            ValidationError: stav == STORNOVANY
            ValidationError: poznamka delší než 500 znaků
        """
        if self._stav == StavDokladu.STORNOVANY:
            raise ValidationError(
                "Stornované doklady nelze flagovat k dořešení."
            )
        if poznamka is not None and len(poznamka) > _POZNAMKA_DORESENI_MAX:
            raise ValidationError(
                f"Poznámka k dořešení max {_POZNAMKA_DORESENI_MAX} znaků, "
                f"dostal {len(poznamka)}."
            )
        self._k_doreseni = True
        self._poznamka_doreseni = poznamka

    def dores(self) -> None:
        """Odznačí flag + vymaže poznámku. Povoleno v jakémkoli stavu.

        Idempotentní — volání na doklad s k_doreseni=False je no-op,
        ne chyba (často se volá jako součást jiných operací, např. storno).
        """
        self._k_doreseni = False
        self._poznamka_doreseni = None

    def uprav_poznamku_doreseni(self, nova: str | None) -> None:
        """Změní jen poznámku, flag zůstává True.

        Args:
            nova: nový text (max 500 znaků) nebo None pro vymazání.
                 Flag zůstává True i po nastavení None.

        Raises:
            ValidationError: k_doreseni == False (nedává smysl měnit poznámku
                na nefragnutém dokladu — použij oznac_k_doreseni)
            ValidationError: nova delší než 500 znaků
        """
        if not self._k_doreseni:
            raise ValidationError(
                "Nelze upravovat poznámku k dořešení na nefragnutém dokladu. "
                "Použij oznac_k_doreseni() pro nastavení flagu i poznámky."
            )
        if nova is not None and len(nova) > _POZNAMKA_DORESENI_MAX:
            raise ValidationError(
                f"Poznámka k dořešení max {_POZNAMKA_DORESENI_MAX} znaků, "
                f"dostal {len(nova)}."
            )
        self._poznamka_doreseni = nova

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

    def uprav_datum_vystaveni(self, nove_datum: date) -> None:
        """Datum vystavení lze měnit ve všech stavech kromě STORNOVANY.

        Pro zaúčtované doklady to volá service vrstva atomicky spolu
        s UPDATE účetních zápisů (zápis musí mít stejné datum jako doklad).
        Použití: oprava chyby v zaúčtování (datum mimo účetní období).

        Pro UHRAZENY je povoleno — úhrada (BV doklad) je samostatný
        účetní doklad s vlastním datem; oprava data faktury úhradu
        neovlivní.

        Raises:
            ValidationError: stav je STORNOVANY; nové datum je za
                splatností; DUZP > rok po novém datu.
        """
        if self._stav == StavDokladu.STORNOVANY:
            raise ValidationError(
                f"Datum vystavení nelze měnit ve stavu {self._stav.value}."
            )
        if not isinstance(nove_datum, date):
            raise TypeError(
                f"nove_datum musí být date, dostal {type(nove_datum).__name__}."
            )
        if (
            self._datum_splatnosti is not None
            and self._datum_splatnosti < nove_datum
        ):
            raise ValidationError(
                f"Datum vystavení ({nove_datum}) by bylo po splatnosti "
                f"({self._datum_splatnosti}). Nejdřív uprav splatnost."
            )
        if (
            self._datum_zdanitelneho_plneni is not None
            and self._datum_zdanitelneho_plneni > nove_datum + _MAX_ZP_OFFSET
        ):
            raise ValidationError(
                f"Datum zdanitelného plnění ({self._datum_zdanitelneho_plneni}) "
                f"by bylo víc než rok po novém datu vystavení ({nove_datum})."
            )
        self._datum_vystaveni = nove_datum

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
