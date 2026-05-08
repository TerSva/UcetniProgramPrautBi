"""VykazyQuery — výkazy a sestavy pro roční účetní závěrku.

Rozvaha (zkrácený rozsah pro mikro ÚJ dle vyhlášky 500/2002 Sb. přílohy 1),
VZZ druhové členění (příloha 2), Předvaha, Hlavní kniha (syntetika
i analytika), Saldokonto, DPH přehled, Pokladní kniha.

Storno protizápisy (``je_storno = 1``) jsou součástí obratů — při stornu
se doklad neztratí, ale obě strany zápisu se vyrovnají (originál i jeho
opačný protizápis), takže netto efekt je 0. To zajišťuje, že rozvaha
po stornu bilancuje a předvaha sedí na nulu na dotčených účtech.

Počáteční stavy se berou z tabulky ``pocatecni_stavy`` (rok=N). Pro PRAUT
2025 = první rok, PS = 0 všude.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

from domain.shared.money import Money
from infrastructure.database.unit_of_work import SqliteUnitOfWork


# ────────────────────────────────────────────────────────────
# Definice řádků Rozvahy a VZZ (vyhláška 500/2002 Sb.)
# ────────────────────────────────────────────────────────────

# Tuple: (oznaceni, nazev, prefixes, level, kind)
#   prefixes: list[str] — účet patří do řádku, pokud začíná některým prefixem
#   level: 0 = top header (AKTIVA CELKEM, PASIVA CELKEM)
#          1 = pod-header (B. Stálá aktiva, C. Oběžná aktiva)
#          2 = běžný řádek (B.I., B.II., …)
#   kind: 'sum_top'    — celkový součet (AKTIVA CELKEM)
#         'sum_group'  — součet skupiny (B., C., A., B+C.)
#         'leaf'       — terminální řádek s prefixy
#         'leaf_vh'    — speciálně VH běžného období (z VZZ)

ROZVAHA_AKTIVA: tuple[tuple, ...] = (
    ("",       "AKTIVA CELKEM",                          (), 0, "sum_top"),
    ("A.",     "Pohledávky za upsaný základní kapitál",  ("353",), 2, "leaf"),
    ("B.",     "Stálá aktiva",                           (), 1, "sum_group"),
    ("B.I.",   "Dlouhodobý nehmotný majetek",            (), 2, "leaf"),
    ("B.II.",  "Dlouhodobý hmotný majetek",              ("022", "082"), 2, "leaf"),
    ("B.III.", "Dlouhodobý finanční majetek",            (), 2, "leaf"),
    ("C.",     "Oběžná aktiva",                          (), 1, "sum_group"),
    ("C.I.",   "Zásoby",                                 (), 2, "leaf"),
    ("C.II.",  "Pohledávky",                             ("311", "314", "355", "378", "343.100"), 2, "leaf"),
    ("C.III.", "Krátkodobý finanční majetek",            (), 2, "leaf"),
    ("C.IV.",  "Peněžní prostředky",                     ("211", "221", "261"), 2, "leaf"),
    ("D.",     "Časové rozlišení aktiv",                 ("381", "395"), 2, "leaf"),
)

ROZVAHA_PASIVA: tuple[tuple, ...] = (
    ("",       "PASIVA CELKEM",                          (), 0, "sum_top"),
    ("A.",     "Vlastní kapitál",                        (), 1, "sum_group"),
    ("A.I.",   "Základní kapitál",                       ("411",), 2, "leaf"),
    ("A.II.",  "Ážio a kapitálové fondy",                ("413",), 2, "leaf"),
    ("A.III.", "Fondy ze zisku",                         (), 2, "leaf"),
    ("A.IV.",  "VH minulých let",                        ("428", "429", "431"), 2, "leaf"),
    ("A.V.",   "VH běžného účetního období",             (), 2, "leaf_vh"),
    ("A.VI.",  "Rozhodnuto o zálohách na výplatu",       (), 2, "leaf"),
    ("B+C.",   "Cizí zdroje",                            (), 1, "sum_group"),
    ("B.",     "Rezervy",                                (), 2, "leaf"),
    ("C.",     "Závazky",                                ("321", "324", "331", "336", "341", "342", "343.200", "345", "365", "379", "479"), 2, "leaf"),
    ("D.",     "Časové rozlišení pasiv",                 (), 2, "leaf"),
)

# Mapování součtových skupin: parent oznaceni -> (řádky, které do něj patří).
# Plní se v _spocitej_rozvaha_radky.
ROZVAHA_AKTIVA_SUM_TOP_SOURCES = ("A.", "B.", "C.", "D.")
ROZVAHA_PASIVA_SUM_TOP_SOURCES = ("A.", "B+C.", "D.")
ROZVAHA_GROUPS = {
    "B.":   ("B.I.", "B.II.", "B.III."),
    "C.":   ("C.I.", "C.II.", "C.III.", "C.IV."),
    "A.":   ("A.I.", "A.II.", "A.III.", "A.IV.", "A.V.", "A.VI."),
    "B+C.": ("B.", "C."),
}


# Pro VZZ: (oznaceni, nazev, prefixes, druh, level)
#   druh:
#     'V'   — výnosy (sčítají se do součtu výnosů, +)
#     'N'   — náklady (sčítají se do součtu nákladů, -)
#     'sum' — součtový řádek (provozní VH, finanční VH, VH před/po zdanění)
#     'header' — jen text (např. ** VH celkem)
#   level: 1 = řádek (např. I., A.), 2 = sub-řádek (A.1., A.2.)
VZZ_RADKY: tuple[tuple, ...] = (
    ("I.",     "Tržby z prodeje výrobků a služeb",  ("601", "602"), "V", 1),
    ("II.",    "Tržby za zboží",                    ("604",), "V", 1),
    ("A.",     "Výkonová spotřeba",                 (), "N_group", 1),
    ("A.1.",   "  Náklady vynaložené na prodané zboží", ("504",), "N", 2),
    ("A.2.",   "  Spotřeba materiálu a energie",   ("501", "502"), "N", 2),
    ("A.3.",   "  Služby",                          ("511", "512", "513", "518"), "N", 2),
    ("B.",     "Změna stavu zásob vlastní činnosti", (), "N", 1),
    ("C.",     "Aktivace",                          (), "N", 1),
    ("D.",     "Osobní náklady",                    ("521", "524", "527"), "N", 1),
    ("E.",     "Úpravy hodnot v provozní oblasti",  ("551",), "N", 1),
    ("III.",   "Ostatní provozní výnosy",           ("644", "648"), "V", 1),
    ("F.",     "Ostatní provozní náklady",          ("538", "543", "544", "545", "548", "549"), "N", 1),
    ("*",      "Provozní výsledek hospodaření",     (), "sum_provozni", 1),
    ("IV.",    "Výnosy z dlouhodobého finančního majetku", (), "V", 1),
    ("G.",     "Náklady vynaložené na prodané podíly", (), "N", 1),
    ("V.",     "Výnosy z ostatního dlouhodobého finančního majetku", (), "V", 1),
    ("H.",     "Náklady související s ostatním DFM", (), "N", 1),
    ("VI.",    "Výnosové úroky a podobné výnosy",   ("662",), "V", 1),
    ("I.",     "Úpravy hodnot a rezervy ve fin. oblasti", (), "N", 1),
    ("J.",     "Nákladové úroky a podobné náklady", ("562",), "N", 1),
    ("VII.",   "Ostatní finanční výnosy",           ("663", "668"), "V", 1),
    ("K.",     "Ostatní finanční náklady",          ("563", "568"), "N", 1),
    ("**fin",  "Finanční výsledek hospodaření",     (), "sum_financni", 1),
    ("***pred", "Výsledek hospodaření před zdaněním", (), "sum_pred_dani", 1),
    ("L.",     "Daň z příjmů",                      ("591", "595"), "N", 1),
    ("**pod",  "Výsledek hospodaření po zdanění",   (), "sum_po_dani", 1),
    ("****",   "Výsledek hospodaření za účetní období", (), "sum_celkem", 1),
)


# ────────────────────────────────────────────────────────────
# DTO
# ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RozvahaRadek:
    """Jeden řádek rozvahy.

    `level` určuje vizuální odsazení:
        0 = AKTIVA/PASIVA CELKEM (tučně, top)
        1 = sub-header (B., C., A., B+C.)
        2 = běžný řádek
    `kind` rozlišuje součtový řádek od leaf řádku.
    """

    oznaceni: str
    nazev: str
    hodnota: Money       # netto za běžné období
    minule: Money        # za minulé období (pro 1. rok = 0)
    level: int
    kind: str            # 'sum_top', 'sum_group', 'leaf', 'leaf_vh'


@dataclass(frozen=True)
class VzzRadek:
    oznaceni: str
    nazev: str
    hodnota: Money
    minule: Money
    druh: str            # 'V', 'N', 'N_group', 'sum_*'
    level: int


@dataclass(frozen=True)
class PredvahaRadek:
    ucet: str
    nazev: str
    typ: str             # 'A','P','N','V','Z'
    ps_md: Money
    ps_dal: Money
    obrat_md: Money
    obrat_dal: Money

    @property
    def kz_md(self) -> Money:
        """Konečný zůstatek na MD straně (pro aktivní/nákladové účty kladný)."""
        delta = self.ps_md.to_halire() + self.obrat_md.to_halire() \
            - self.ps_dal.to_halire() - self.obrat_dal.to_halire()
        return Money(max(0, delta))

    @property
    def kz_dal(self) -> Money:
        delta = self.ps_dal.to_halire() + self.obrat_dal.to_halire() \
            - self.ps_md.to_halire() - self.obrat_md.to_halire()
        return Money(max(0, delta))


@dataclass(frozen=True)
class HlavniKnihaRadek:
    datum: date
    cislo_dokladu: str
    popis: str | None
    md: Money
    dal: Money
    zustatek: Money       # průběžný


@dataclass(frozen=True)
class DrilldownZapis:
    """Účetní zápis přispívající k částce v jednom řádku VZZ/rozvahy.

    `znamenko` říká jak zápis přispívá k saldu řádku:
      * +1 — částka se přičítá (např. MD na nákladovém účtu, Dal na výnosech)
      * -1 — částka se odečítá (opačná strana téhož účtu)

    Storno zápisy (`je_storno=True`) se zahrnují, aby drilldown souhlasil
    s celkovou hodnotou ve výkazu. V dialogu se vizuálně odlišují.
    """

    id: int                     # ucetni_zaznam.id (pro klik na detail)
    doklad_id: int
    datum: date
    cislo_dokladu: str
    md_ucet: str
    dal_ucet: str
    castka: Money
    popis: str | None
    znamenko: int               # +1 / -1
    je_storno: bool = False


@dataclass(frozen=True)
class HlavniKnihaUctu:
    ucet: str
    nazev: str
    typ: str
    pocatecni_stav: Money       # signed: + = MD strana, - = Dal strana
    radky: tuple[HlavniKnihaRadek, ...]
    obrat_md: Money
    obrat_dal: Money

    @property
    def koncovy_zustatek(self) -> Money:
        if self.radky:
            return self.radky[-1].zustatek
        return self.pocatecni_stav


@dataclass(frozen=True)
class SaldokontoRadek:
    cislo_dokladu: str
    typ: str                       # 'FP' / 'FV'
    partner_nazev: str | None
    datum: date
    castka: Money
    uhrazeno: Money
    zbyva: Money


@dataclass(frozen=True)
class SaldoUcetRadek:
    """Saldo na úrovni partnera/účetních zápisů — pro účty 355/365.

    Pro 311/321 se vyplňuje z FV/FP dokladů; pro 355/365 ze sumy
    účetních zápisů (MD − Dal nebo opačně) seskupených po analytice.
    """

    ucet: str                      # např. "355", "355.001"
    partner_nazev: str | None      # název analytického účtu / partnera
    saldo: Money                   # signed: + = pohledávka, − = závazek


@dataclass(frozen=True)
class SaldokontoUcetSekce:
    """Jedna sekce saldokonta podle účtu (311/321/355/365)."""

    ucet: str                      # "311", "321", "355", "365"
    nazev: str                     # popisek pro tisk
    je_pohledavka: bool            # True = aktivní účet, False = pasivní
    radky: tuple                    # tuple[SaldokontoRadek] nebo tuple[SaldoUcetRadek]
    celkem: Money                  # součet zbývajících částek / sald


@dataclass(frozen=True)
class DphDokladRadek:
    datum: date
    cislo_dokladu: str
    partner_nazev: str | None
    zaklad: Money
    dph: Money
    rezim: str


@dataclass(frozen=True)
class DphPrehled:
    rok: int
    obdobi_od: date
    obdobi_do: date
    vstup_celkem: Money            # 343.100 (saldo na MD)
    vstup_rc: Money                # z toho RC
    vystup_celkem: Money           # 343.200 (saldo na Dal)
    vystup_rc: Money               # z toho RC
    doklady: tuple[DphDokladRadek, ...]

    @property
    def k_uhrade(self) -> Money:
        """Výstup - vstup. Záporné = stát dluží firmě."""
        return Money(self.vystup_celkem.to_halire() - self.vstup_celkem.to_halire())


@dataclass(frozen=True)
class NedanovyUcetRadek:
    """Jeden účet s nenulovým nedaňovým obratem za rok."""

    ucet: str                    # např. "513" nebo "548.999"
    nazev: str
    popis: str | None
    castka: Money                # obrat MD − Dal (kladný = náklad)


@dataclass(frozen=True)
class NedanoveNaklady:
    """Souhrn nedaňových nákladů za rok pro DPPO řádek 40.

    Vrací jen účty třídy 5 s je_danovy=0 a nenulovým obratem.
    """

    rok: int
    radky: tuple                  # tuple[NedanovyUcetRadek]
    celkem: Money

    @property
    def je_prazdny(self) -> bool:
        return self.celkem.is_zero


@dataclass(frozen=True)
class MinimumPriloha:
    """Data pro minimální přílohu k účetní závěrce mikro ÚJ.

    Sestavuje se z entity Firma + Partneri (společníci) + zdraží
    (počet dokladů z roku — orientační počet zaměstnanců). Statutární
    orgán a předmět činnosti se berou z Firma textových polí.
    """

    # Obecné údaje (sekce a)
    nazev: str
    sidlo: str | None
    ico: str | None
    dic: str | None
    pravni_forma: str
    predmet_cinnosti: str | None
    rozvahovy_den: date            # 31.12.YYYY (uživatel zadává)
    datum_zalozeni: date | None
    datum_sestaveni: date          # uživatel zadává
    kategorie_uj: str
    statutarni_organ: str | None
    spolecnici: tuple              # tuple[(nazev, podil_procent)]
    zakladni_kapital: Money | None

    # Použité účetní metody (sekce b)
    zpusob_oceneni: str
    odpisovy_plan: str
    je_identifikovana_osoba_dph: bool
    je_platce_dph: bool

    # Doplňkové údaje (sekce c)
    prumerny_pocet_zamestnancu: int


@dataclass(frozen=True)
class PokladniKniha:
    rok: int
    pocatecni_stav: Money
    radky: tuple[HlavniKnihaRadek, ...]
    pouzita: bool                   # False → "pokladna nebyla v roce N používána"

    @property
    def koncovy_stav(self) -> Money:
        if self.radky:
            return self.radky[-1].zustatek
        return self.pocatecni_stav


# ────────────────────────────────────────────────────────────
# Hlavní query
# ────────────────────────────────────────────────────────────

class VykazyQuery:
    """Read-only query — výkazy a sestavy.

    Používá raw SQL nad ucetni_zaznamy + doklady + pocatecni_stavy.
    Storno zápisy (je_storno = 1) jsou ignorovány.
    """

    def __init__(self, uow_factory: Callable[[], SqliteUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    # ------------------------------------------------------------
    # 1. Rozvaha
    # ------------------------------------------------------------

    def get_rozvaha(
        self, rok: int,
    ) -> tuple[tuple[RozvahaRadek, ...], tuple[RozvahaRadek, ...]]:
        """Vrátí (aktiva, pasiva) jako tuple řádků rozvahy.

        Hodnoty jsou netto. A.V. (VH běžného období) se počítá z VZZ.
        """
        ucty = self._nacti_obraty_a_ps(rok)
        vh_bezne = self._spocitej_vh(ucty)

        aktiva = self._sestav_rozvaha_stranu(
            ROZVAHA_AKTIVA, ROZVAHA_AKTIVA_SUM_TOP_SOURCES, ucty,
            vh_bezne=None, je_aktiva=True,
        )
        pasiva = self._sestav_rozvaha_stranu(
            ROZVAHA_PASIVA, ROZVAHA_PASIVA_SUM_TOP_SOURCES, ucty,
            vh_bezne=vh_bezne, je_aktiva=False,
        )
        return aktiva, pasiva

    def get_bilancni_kontrola(self, rok: int) -> tuple[Money, Money]:
        """Vrátí (aktiva_celkem, pasiva_celkem) — musí být stejné."""
        aktiva, pasiva = self.get_rozvaha(rok)
        a_celkem = next((r.hodnota for r in aktiva if r.kind == "sum_top"), Money.zero())
        p_celkem = next((r.hodnota for r in pasiva if r.kind == "sum_top"), Money.zero())
        return a_celkem, p_celkem

    def get_zaverkove_saldo(self, rok: int) -> Money:
        """Vrátí součet sald závěrkových účtů (typ Z, např. 701, 702, 710).

        Pro běžné období musí být 0 — závěrkové účty se používají jen
        při otevření / uzavření roku. Nenulové saldo = nesprávné zaúčtování,
        které způsobí, že rozvaha nebilancuje.
        """
        ucty = self._nacti_obraty_a_ps(rok)
        total = 0
        for cislo, data in ucty.items():
            if data["typ"] != "Z":
                continue
            md = data["ps_md"] + data["obrat_md"]
            dal = data["ps_dal"] + data["obrat_dal"]
            total += md - dal
        return Money(total)

    # ------------------------------------------------------------
    # 2. VZZ
    # ------------------------------------------------------------

    def get_vzz(self, rok: int) -> tuple[VzzRadek, ...]:
        ucty = self._nacti_obraty_a_ps(rok)
        return self._sestav_vzz(ucty)

    # ------------------------------------------------------------
    # 3. Předvaha
    # ------------------------------------------------------------

    def get_predvaha(
        self, rok: int, jen_s_pohybem: bool = True,
    ) -> tuple[PredvahaRadek, ...]:
        """Obratová předvaha — všechny účty s PS, obraty, KZ."""
        ucty = self._nacti_obraty_a_ps(rok)
        vsechny = self._nacti_vsechny_ucty()

        radky: list[PredvahaRadek] = []
        for cislo in sorted(vsechny.keys()):
            data = ucty.get(cislo, {
                "ps_md": 0, "ps_dal": 0, "obrat_md": 0, "obrat_dal": 0,
            })
            ma_pohyb = (
                data["ps_md"] != 0 or data["ps_dal"] != 0
                or data["obrat_md"] != 0 or data["obrat_dal"] != 0
            )
            if jen_s_pohybem and not ma_pohyb:
                continue
            nazev, typ = vsechny[cislo]
            radky.append(PredvahaRadek(
                ucet=cislo,
                nazev=nazev,
                typ=typ,
                ps_md=Money(data["ps_md"]),
                ps_dal=Money(data["ps_dal"]),
                obrat_md=Money(data["obrat_md"]),
                obrat_dal=Money(data["obrat_dal"]),
            ))
        return tuple(radky)

    # ------------------------------------------------------------
    # 4. Hlavní kniha
    # ------------------------------------------------------------

    def get_hlavni_kniha(self, ucet: str, rok: int) -> HlavniKnihaUctu:
        """Hlavní kniha pro účet (syntetický nebo analytický).

        Pokud je `ucet` syntetický (např. '321' a v DB existují 321.001,
        321.002), zahrne pohyby na všech analytikách.
        """
        od = date(rok, 1, 1)
        do = date(rok, 12, 31)

        uow = self._uow_factory()
        with uow:
            conn = uow.connection

            row = conn.execute(
                "SELECT cislo, nazev, typ FROM uctova_osnova WHERE cislo = ?",
                (ucet,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Účet {ucet!r} neexistuje v osnově.")
            ucet_nazev = row["nazev"]
            ucet_typ = row["typ"]

            # Účty které matchují (syntetika + analytiky)
            match_pattern = f"{ucet}%" if "." not in ucet else ucet

            # Počáteční stav (z pocatecni_stavy)
            ps_rows = conn.execute(
                """
                SELECT strana, SUM(castka) AS suma
                FROM pocatecni_stavy
                WHERE rok = ? AND ucet_kod LIKE ?
                GROUP BY strana
                """,
                (rok, match_pattern),
            ).fetchall()
            ps_md = 0
            ps_dal = 0
            for r in ps_rows:
                if r["strana"] == "MD":
                    ps_md = r["suma"] or 0
                elif r["strana"] == "DAL":
                    ps_dal = r["suma"] or 0

            ps_signed = ps_md - ps_dal  # pozitivní = MD strana

            # Pohyby — vč. storno protizápisů, ať jsou v auditu vidět.
            zaznamy = conn.execute(
                """
                SELECT uz.datum, uz.castka, uz.popis,
                       uz.md_ucet, uz.dal_ucet, uz.je_storno,
                       d.cislo AS doklad_cislo
                FROM ucetni_zaznamy uz
                JOIN doklady d ON d.id = uz.doklad_id
                WHERE uz.datum >= ? AND uz.datum <= ?
                  AND (uz.md_ucet LIKE ? OR uz.dal_ucet LIKE ?)
                ORDER BY uz.datum, uz.id
                """,
                (od.isoformat(), do.isoformat(), match_pattern, match_pattern),
            ).fetchall()

        zustatek = ps_signed
        radky: list[HlavniKnihaRadek] = []
        obrat_md_total = 0
        obrat_dal_total = 0
        for r in zaznamy:
            md_match = self._matches(r["md_ucet"], ucet)
            dal_match = self._matches(r["dal_ucet"], ucet)
            castka = r["castka"]
            md = 0
            dal = 0
            if md_match:
                md = castka
                zustatek += castka
                obrat_md_total += castka
            if dal_match:
                dal = castka
                zustatek -= castka
                obrat_dal_total += castka

            radky.append(HlavniKnihaRadek(
                datum=date.fromisoformat(r["datum"]),
                cislo_dokladu=r["doklad_cislo"],
                popis=r["popis"],
                md=Money(md),
                dal=Money(dal),
                zustatek=Money(zustatek),
            ))

        return HlavniKnihaUctu(
            ucet=ucet,
            nazev=ucet_nazev,
            typ=ucet_typ,
            pocatecni_stav=Money(ps_signed),
            radky=tuple(radky),
            obrat_md=Money(obrat_md_total),
            obrat_dal=Money(obrat_dal_total),
        )

    def get_ucty_s_pohybem(self, rok: int) -> tuple[tuple[str, str], ...]:
        """Vrátí (cislo, nazev) účtů které mají v daném roce zápis nebo PS."""
        od = date(rok, 1, 1)
        do = date(rok, 12, 31)

        uow = self._uow_factory()
        with uow:
            conn = uow.connection
            rows = conn.execute(
                """
                SELECT DISTINCT u.cislo, u.nazev
                FROM uctova_osnova u
                WHERE u.cislo IN (
                    SELECT md_ucet FROM ucetni_zaznamy
                    WHERE datum >= ? AND datum <= ?
                    UNION
                    SELECT dal_ucet FROM ucetni_zaznamy
                    WHERE datum >= ? AND datum <= ?
                    UNION
                    SELECT ucet_kod FROM pocatecni_stavy WHERE rok = ?
                )
                ORDER BY u.cislo
                """,
                (od.isoformat(), do.isoformat(),
                 od.isoformat(), do.isoformat(), rok),
            ).fetchall()
        return tuple((r["cislo"], r["nazev"]) for r in rows)

    # ------------------------------------------------------------
    # 5. Saldokonto
    # ------------------------------------------------------------

    def get_saldokonto(
        self, rok: int,
    ) -> tuple[tuple[SaldokontoRadek, ...], tuple[SaldokontoRadek, ...]]:
        """Vrátí (zavazky_FP, pohledavky_FV) — neuhrazené nebo částečně uhrazené."""
        od = date(rok, 1, 1)
        do = date(rok, 12, 31)

        uow = self._uow_factory()
        with uow:
            conn = uow.connection
            rows = conn.execute(
                """
                SELECT d.id, d.cislo, d.typ, d.datum_vystaveni,
                       d.castka_celkem, p.nazev AS partner_nazev
                FROM doklady d
                LEFT JOIN partneri p ON p.id = d.partner_id
                WHERE d.typ IN ('FP', 'FV')
                  AND d.stav IN ('zauctovany', 'castecne_uhrazeny')
                  AND d.datum_vystaveni >= ? AND d.datum_vystaveni <= ?
                ORDER BY d.datum_vystaveni, d.cislo
                """,
                (od.isoformat(), do.isoformat()),
            ).fetchall()

            zavazky: list[SaldokontoRadek] = []
            pohledavky: list[SaldokontoRadek] = []
            for r in rows:
                doklad_id = r["id"]
                typ = r["typ"]
                castka = Money(r["castka_celkem"])
                uhrazeno = self._spocitej_uhrazeno(conn, doklad_id, typ, r["cislo"])
                zbyva = Money(castka.to_halire() - uhrazeno.to_halire())

                radek = SaldokontoRadek(
                    cislo_dokladu=r["cislo"],
                    typ=typ,
                    partner_nazev=r["partner_nazev"],
                    datum=date.fromisoformat(r["datum_vystaveni"]),
                    castka=castka,
                    uhrazeno=uhrazeno,
                    zbyva=zbyva,
                )
                if typ == "FP":
                    zavazky.append(radek)
                else:
                    pohledavky.append(radek)

        return tuple(zavazky), tuple(pohledavky)

    # ------------------------------------------------------------
    # 5a0. Nedaňové náklady (DPPO řádek 40)
    # ------------------------------------------------------------

    def get_nedanove_naklady(self, rok: int) -> "NedanoveNaklady":
        """Souhrn nedaňových nákladů za rok.

        Vrací účty s typem 'N' a je_danovy=0, které mají nenulový obrat
        (MD − Dal) za daný rok. Storno zápisy se nezohledňují (filtr
        je_storno = 0). Hodnota = obrat MD − obrat Dal (čistý náklad).

        Tento součet se použije pro daňové přiznání PO (formulář 25 5404),
        řádek 40 — Výdaje neuznané za výdaje vynaložené k dosažení příjmů.
        """
        od = date(rok, 1, 1).isoformat()
        do = date(rok, 12, 31).isoformat()

        uow = self._uow_factory()
        with uow:
            conn = uow.connection
            # Načti všechny nedaňové N účty
            ucty_rows = conn.execute(
                """
                SELECT cislo, nazev, popis FROM uctova_osnova
                WHERE typ = 'N' AND je_danovy = 0
                ORDER BY cislo
                """,
            ).fetchall()
            if not ucty_rows:
                return NedanoveNaklady(
                    rok=rok, radky=(), celkem=Money.zero(),
                )

            radky: list[NedanovyUcetRadek] = []
            celkem_hal = 0
            for u in ucty_rows:
                cislo = u["cislo"]
                # Obrat MD na účtu (vč. analytik pokud je syntetický)
                # Pro syntetiku '513' vezmi i '513.xxx'; pro analytiku
                # '548.999' vezmi přesnou shodu.
                if "." in cislo:
                    md_pattern = cislo
                    use_like = False
                else:
                    md_pattern = f"{cislo}.%"
                    use_like = True
                # Obrat MD
                if use_like:
                    md_row = conn.execute(
                        """
                        SELECT COALESCE(SUM(castka), 0) AS s
                        FROM ucetni_zaznamy
                        WHERE datum >= ? AND datum <= ?
                          AND je_storno = 0
                          AND (md_ucet = ? OR md_ucet LIKE ?)
                        """,
                        (od, do, cislo, md_pattern),
                    ).fetchone()
                    dal_row = conn.execute(
                        """
                        SELECT COALESCE(SUM(castka), 0) AS s
                        FROM ucetni_zaznamy
                        WHERE datum >= ? AND datum <= ?
                          AND je_storno = 0
                          AND (dal_ucet = ? OR dal_ucet LIKE ?)
                        """,
                        (od, do, cislo, md_pattern),
                    ).fetchone()
                else:
                    md_row = conn.execute(
                        """
                        SELECT COALESCE(SUM(castka), 0) AS s
                        FROM ucetni_zaznamy
                        WHERE datum >= ? AND datum <= ?
                          AND je_storno = 0
                          AND md_ucet = ?
                        """,
                        (od, do, cislo),
                    ).fetchone()
                    dal_row = conn.execute(
                        """
                        SELECT COALESCE(SUM(castka), 0) AS s
                        FROM ucetni_zaznamy
                        WHERE datum >= ? AND datum <= ?
                          AND je_storno = 0
                          AND dal_ucet = ?
                        """,
                        (od, do, cislo),
                    ).fetchone()

                obrat_md = md_row["s"] or 0
                obrat_dal = dal_row["s"] or 0
                # Pro nákladový účet: kladný náklad = MD > Dal
                netto = obrat_md - obrat_dal
                if netto == 0:
                    continue

                # Pro syntetiku nezdvojovat — pokud má aktivní analytiky
                # se je_danovy=0, syntetický by načetl jejich obrat znovu.
                # Vyřešíme tak, že syntetický se ZAHRNE jen pokud nejsou
                # nedaňové analytiky (jinak by sčítání bylo dvojí).
                if not "." in cislo:
                    has_analytic_nedanove = conn.execute(
                        """
                        SELECT 1 FROM uctova_osnova
                        WHERE parent_kod = ? AND je_danovy = 0
                          AND je_aktivni = 1
                        LIMIT 1
                        """,
                        (cislo,),
                    ).fetchone()
                    if has_analytic_nedanove is not None:
                        # Syntetický má analytiky → použijeme jen analytiky,
                        # syntetické zápisy přímo na 'cislo' bez tečky.
                        md_only_synt = conn.execute(
                            """
                            SELECT COALESCE(SUM(castka), 0) AS s
                            FROM ucetni_zaznamy
                            WHERE datum >= ? AND datum <= ?
                              AND je_storno = 0
                              AND md_ucet = ?
                            """,
                            (od, do, cislo),
                        ).fetchone()
                        dal_only_synt = conn.execute(
                            """
                            SELECT COALESCE(SUM(castka), 0) AS s
                            FROM ucetni_zaznamy
                            WHERE datum >= ? AND datum <= ?
                              AND je_storno = 0
                              AND dal_ucet = ?
                            """,
                            (od, do, cislo),
                        ).fetchone()
                        netto = (md_only_synt["s"] or 0) - (dal_only_synt["s"] or 0)
                        if netto == 0:
                            continue

                radky.append(NedanovyUcetRadek(
                    ucet=cislo,
                    nazev=u["nazev"],
                    popis=u["popis"],
                    castka=Money(netto),
                ))
                celkem_hal += netto

        return NedanoveNaklady(
            rok=rok, radky=tuple(radky), celkem=Money(celkem_hal),
        )

    # ------------------------------------------------------------
    # 5a1. Minimum příloha (vyhláška 500/2002 Sb., §39)
    # ------------------------------------------------------------

    def get_minimum_priloha(
        self,
        rok: int,
        rozvahovy_den: date,
        datum_sestaveni: date,
    ) -> "MinimumPriloha":
        """Sestaví minimum přílohu z Firma + Partneri (společníci).

        Společníci se načtou z partneri kategorie='spolecnik' aktivních.
        Pokud Firma neexistuje, vrátí přílohu s minimálními daty
        (nazev = "—") aby PDF nepadalo.
        """
        from infrastructure.database.repositories.firma_repository import (
            SqliteFirmaRepository,
        )
        uow = self._uow_factory()
        with uow:
            firma_repo = SqliteFirmaRepository(uow)
            firma = firma_repo.get()
            conn = uow.connection
            spolecnici_rows = conn.execute(
                """
                SELECT nazev, podil_procent
                FROM partneri
                WHERE kategorie = 'spolecnik'
                  AND je_aktivni = 1
                ORDER BY podil_procent DESC NULLS LAST, nazev
                """,
            ).fetchall()
            spolecnici = tuple(
                (r["nazev"], r["podil_procent"])
                for r in spolecnici_rows
            )

        if firma is None:
            return MinimumPriloha(
                nazev="—",
                sidlo=None, ico=None, dic=None,
                pravni_forma="—",
                predmet_cinnosti=None,
                rozvahovy_den=rozvahovy_den,
                datum_zalozeni=None,
                datum_sestaveni=datum_sestaveni,
                kategorie_uj="mikro",
                statutarni_organ=None,
                spolecnici=spolecnici,
                zakladni_kapital=None,
                zpusob_oceneni="pořizovacími cenami",
                odpisovy_plan="lineární",
                je_identifikovana_osoba_dph=False,
                je_platce_dph=False,
                prumerny_pocet_zamestnancu=0,
            )

        return MinimumPriloha(
            nazev=firma.nazev,
            sidlo=firma.sidlo,
            ico=firma.ico,
            dic=firma.dic,
            pravni_forma=firma.pravni_forma,
            predmet_cinnosti=firma.predmet_cinnosti,
            rozvahovy_den=rozvahovy_den,
            datum_zalozeni=firma.datum_zalozeni,
            datum_sestaveni=datum_sestaveni,
            kategorie_uj=firma.kategorie_uj,
            statutarni_organ=firma.statutarni_organ,
            spolecnici=spolecnici,
            zakladni_kapital=firma.zakladni_kapital,
            zpusob_oceneni=firma.zpusob_oceneni,
            odpisovy_plan=firma.odpisovy_plan,
            je_identifikovana_osoba_dph=firma.je_identifikovana_osoba_dph,
            je_platce_dph=firma.je_platce_dph,
            prumerny_pocet_zamestnancu=firma.prumerny_pocet_zamestnancu,
        )

    # ------------------------------------------------------------
    # 5b. Saldokonto po účtech (311 / 321 / 355 / 365)
    # ------------------------------------------------------------

    def get_saldokonto_per_ucet(
        self, rok: int,
    ) -> tuple[SaldokontoUcetSekce, ...]:
        """Vrátí 4 sekce saldokonta — pro účty 311, 321, 355, 365.

        311 (odběratelé) a 321 (dodavatelé) se sestaví z neuhrazených
        FV/FP dokladů (jako get_saldokonto). 355 a 365 (společníci)
        se sestaví ze sumy účetních zápisů per analytika, protože tam
        nejsou doklady FV/FP.
        """
        zavazky_fp, pohledavky_fv = self.get_saldokonto(rok)

        celkem_fv = Money(sum(r.zbyva.to_halire() for r in pohledavky_fv))
        celkem_fp = Money(sum(r.zbyva.to_halire() for r in zavazky_fp))

        sekce_311 = SaldokontoUcetSekce(
            ucet="311",
            nazev="Pohledávky z obchodního styku (311)",
            je_pohledavka=True,
            radky=pohledavky_fv,
            celkem=celkem_fv,
        )
        sekce_321 = SaldokontoUcetSekce(
            ucet="321",
            nazev="Závazky z obchodního styku (321)",
            je_pohledavka=False,
            radky=zavazky_fp,
            celkem=celkem_fp,
        )

        # 355 / 365 — saldo z účetních zápisů (společníci)
        sekce_355 = self._saldo_zaznamu_per_ucet(
            rok, prefix="355",
            nazev="Pohledávky za společníky (355)",
            je_pohledavka=True,
        )
        sekce_365 = self._saldo_zaznamu_per_ucet(
            rok, prefix="365",
            nazev="Závazky vůči společníkům (365)",
            je_pohledavka=False,
        )

        # 314 / 324 — zálohy z účetních zápisů
        sekce_314 = self._saldo_zaznamu_per_ucet(
            rok, prefix="314",
            nazev="Poskytnuté zálohy (314)",
            je_pohledavka=True,
        )
        sekce_324 = self._saldo_zaznamu_per_ucet(
            rok, prefix="324",
            nazev="Přijaté zálohy od odběratelů (324)",
            je_pohledavka=False,
        )

        return (
            sekce_311, sekce_321, sekce_314, sekce_324,
            sekce_355, sekce_365,
        )

    def _saldo_zaznamu_per_ucet(
        self,
        rok: int,
        prefix: str,
        nazev: str,
        je_pohledavka: bool,
    ) -> SaldokontoUcetSekce:
        """Saldo MD−Dal (nebo Dal−MD) per analytika pro daný prefix.

        Sčítá počáteční stavy + obraty za rok a vrací jen nenulová salda.
        """
        od = date(rok, 1, 1).isoformat()
        do = date(rok, 12, 31).isoformat()
        uow = self._uow_factory()
        with uow:
            conn = uow.connection
            ucty_rows = conn.execute(
                """
                SELECT cislo, nazev FROM uctova_osnova
                WHERE cislo = ? OR cislo LIKE ?
                ORDER BY cislo
                """,
                (prefix, f"{prefix}.%"),
            ).fetchall()

            saldo_per_ucet: dict[str, dict] = {}
            for r in ucty_rows:
                saldo_per_ucet[r["cislo"]] = {
                    "nazev": r["nazev"],
                    "md": 0,
                    "dal": 0,
                }

            # Počáteční stavy
            ps_rows = conn.execute(
                """
                SELECT ucet_kod, strana, SUM(castka) AS suma
                FROM pocatecni_stavy
                WHERE rok = ? AND (ucet_kod = ? OR ucet_kod LIKE ?)
                GROUP BY ucet_kod, strana
                """,
                (rok, prefix, f"{prefix}.%"),
            ).fetchall()
            for r in ps_rows:
                if r["ucet_kod"] not in saldo_per_ucet:
                    saldo_per_ucet[r["ucet_kod"]] = {
                        "nazev": r["ucet_kod"], "md": 0, "dal": 0,
                    }
                if r["strana"] == "MD":
                    saldo_per_ucet[r["ucet_kod"]]["md"] += r["suma"] or 0
                else:
                    saldo_per_ucet[r["ucet_kod"]]["dal"] += r["suma"] or 0

            # Obraty MD
            md_rows = conn.execute(
                """
                SELECT md_ucet, SUM(castka) AS suma
                FROM ucetni_zaznamy
                WHERE datum >= ? AND datum <= ?
                  AND je_storno = 0
                  AND (md_ucet = ? OR md_ucet LIKE ?)
                GROUP BY md_ucet
                """,
                (od, do, prefix, f"{prefix}.%"),
            ).fetchall()
            for r in md_rows:
                if r["md_ucet"] not in saldo_per_ucet:
                    saldo_per_ucet[r["md_ucet"]] = {
                        "nazev": r["md_ucet"], "md": 0, "dal": 0,
                    }
                saldo_per_ucet[r["md_ucet"]]["md"] += r["suma"] or 0

            # Obraty Dal
            dal_rows = conn.execute(
                """
                SELECT dal_ucet, SUM(castka) AS suma
                FROM ucetni_zaznamy
                WHERE datum >= ? AND datum <= ?
                  AND je_storno = 0
                  AND (dal_ucet = ? OR dal_ucet LIKE ?)
                GROUP BY dal_ucet
                """,
                (od, do, prefix, f"{prefix}.%"),
            ).fetchall()
            for r in dal_rows:
                if r["dal_ucet"] not in saldo_per_ucet:
                    saldo_per_ucet[r["dal_ucet"]] = {
                        "nazev": r["dal_ucet"], "md": 0, "dal": 0,
                    }
                saldo_per_ucet[r["dal_ucet"]]["dal"] += r["suma"] or 0

        # Sestav řádky — jen nenulová salda
        radky: list[SaldoUcetRadek] = []
        celkem = 0
        for ucet, data in sorted(saldo_per_ucet.items()):
            saldo = data["md"] - data["dal"]
            if not je_pohledavka:
                saldo = -saldo  # pasivní účet: kladné saldo = závazek
            if saldo == 0:
                continue
            radky.append(SaldoUcetRadek(
                ucet=ucet,
                partner_nazev=data["nazev"],
                saldo=Money(saldo),
            ))
            celkem += saldo

        return SaldokontoUcetSekce(
            ucet=prefix,
            nazev=nazev,
            je_pohledavka=je_pohledavka,
            radky=tuple(radky),
            celkem=Money(celkem),
        )

    # ------------------------------------------------------------
    # 6. DPH přehled
    # ------------------------------------------------------------

    def get_dph_prehled(
        self, rok: int, mesic: int | None = None, ctvrtleti: int | None = None,
    ) -> DphPrehled:
        """DPH přehled za rok / měsíc / čtvrtletí.

        Pro identifikovanou osobu: vstup = 343.100 (MD), výstup = 343.200 (Dal).
        U RC: vstup = výstup → vzájemně se vynuluje.
        """
        if mesic is not None:
            od = date(rok, mesic, 1)
            if mesic == 12:
                do = date(rok, 12, 31)
            else:
                do = date(rok, mesic + 1, 1) - timedelta(days=1)
        elif ctvrtleti is not None:
            zacatek = (ctvrtleti - 1) * 3 + 1
            od = date(rok, zacatek, 1)
            konec_mesic = zacatek + 2
            if konec_mesic == 12:
                do = date(rok, 12, 31)
            else:
                do = date(rok, konec_mesic + 1, 1) - timedelta(days=1)
        else:
            od = date(rok, 1, 1)
            do = date(rok, 12, 31)

        uow = self._uow_factory()
        with uow:
            conn = uow.connection

            # Vstup: záznamy s MD ucet LIKE '343.1%' nebo md_ucet = '343.100'
            vstup_total = conn.execute(
                """
                SELECT COALESCE(SUM(castka), 0) AS s
                FROM ucetni_zaznamy
                WHERE je_storno = 0
                  AND datum >= ? AND datum <= ?
                  AND md_ucet LIKE '343.1%'
                """,
                (od.isoformat(), do.isoformat()),
            ).fetchone()["s"]

            vstup_rc = conn.execute(
                """
                SELECT COALESCE(SUM(uz.castka), 0) AS s
                FROM ucetni_zaznamy uz
                JOIN doklady d ON d.id = uz.doklad_id
                WHERE uz.je_storno = 0
                  AND uz.datum >= ? AND uz.datum <= ?
                  AND uz.md_ucet LIKE '343.1%'
                  AND d.dph_rezim = 'REVERSE_CHARGE'
                """,
                (od.isoformat(), do.isoformat()),
            ).fetchone()["s"]

            # Výstup: záznamy s Dal ucet LIKE '343.2%'
            vystup_total = conn.execute(
                """
                SELECT COALESCE(SUM(castka), 0) AS s
                FROM ucetni_zaznamy
                WHERE je_storno = 0
                  AND datum >= ? AND datum <= ?
                  AND dal_ucet LIKE '343.2%'
                """,
                (od.isoformat(), do.isoformat()),
            ).fetchone()["s"]

            vystup_rc = conn.execute(
                """
                SELECT COALESCE(SUM(uz.castka), 0) AS s
                FROM ucetni_zaznamy uz
                JOIN doklady d ON d.id = uz.doklad_id
                WHERE uz.je_storno = 0
                  AND uz.datum >= ? AND uz.datum <= ?
                  AND uz.dal_ucet LIKE '343.2%'
                  AND d.dph_rezim = 'REVERSE_CHARGE'
                """,
                (od.isoformat(), do.isoformat()),
            ).fetchone()["s"]

            # Detail dokladů s DPH
            doklad_rows = conn.execute(
                """
                SELECT d.id, d.cislo, d.datum_vystaveni, d.castka_celkem,
                       COALESCE(d.dph_rezim, 'TUZEMSKO') AS rezim,
                       p.nazev AS partner_nazev
                FROM doklady d
                LEFT JOIN partneri p ON p.id = d.partner_id
                WHERE d.id IN (
                    SELECT DISTINCT doklad_id FROM ucetni_zaznamy
                    WHERE je_storno = 0
                      AND datum >= ? AND datum <= ?
                      AND (md_ucet LIKE '343%' OR dal_ucet LIKE '343%')
                )
                ORDER BY d.datum_vystaveni, d.cislo
                """,
                (od.isoformat(), do.isoformat()),
            ).fetchall()

            doklady: list[DphDokladRadek] = []
            for d_row in doklad_rows:
                # Pro každý doklad: zaklad = sum castka záznamů kde nejde
                # o DPH řádek (ani MD ani Dal není 343)
                base_row = conn.execute(
                    """
                    SELECT COALESCE(SUM(castka), 0) AS s
                    FROM ucetni_zaznamy
                    WHERE doklad_id = ? AND je_storno = 0
                      AND md_ucet NOT LIKE '343%'
                      AND dal_ucet NOT LIKE '343%'
                    """,
                    (d_row["id"],),
                ).fetchone()
                # DPH = sum z 343 řádků (každý se počítá jednou)
                dph_row = conn.execute(
                    """
                    SELECT COALESCE(SUM(castka), 0) AS s
                    FROM ucetni_zaznamy
                    WHERE doklad_id = ? AND je_storno = 0
                      AND md_ucet LIKE '343.1%'
                    """,
                    (d_row["id"],),
                ).fetchone()
                doklady.append(DphDokladRadek(
                    datum=date.fromisoformat(d_row["datum_vystaveni"]),
                    cislo_dokladu=d_row["cislo"],
                    partner_nazev=d_row["partner_nazev"],
                    zaklad=Money(base_row["s"]),
                    dph=Money(dph_row["s"]),
                    rezim=d_row["rezim"],
                ))

        return DphPrehled(
            rok=rok,
            obdobi_od=od,
            obdobi_do=do,
            vstup_celkem=Money(vstup_total),
            vstup_rc=Money(vstup_rc),
            vystup_celkem=Money(vystup_total),
            vystup_rc=Money(vystup_rc),
            doklady=tuple(doklady),
        )

    # ------------------------------------------------------------
    # 7. Drilldown — zápisy přispívající k řádku VZZ/rozvahy
    # ------------------------------------------------------------

    def get_vzz_drilldown(
        self, rok: int, oznaceni: str,
    ) -> tuple[DrilldownZapis, ...]:
        """Zápisy tvořící částku konkrétního řádku VZZ.

        Pro `sum_*` řádky agreguje prefixy všech podřízených leaf řádků.
        """
        prefixy, druhy = self._najdi_prefixy_vzz(oznaceni)
        if not prefixy:
            return tuple()
        return self._nacti_zapisy_pro_prefixy(
            rok=rok, prefixy=prefixy, druhy=druhy, je_aktiva=None,
        )

    def get_rozvaha_drilldown(
        self, rok: int, je_aktiva: bool, oznaceni: str,
    ) -> tuple[DrilldownZapis, ...]:
        """Zápisy tvořící částku konkrétního řádku rozvahy.

        Pro `sum_top` / `sum_group` agreguje prefixy podřízených.
        """
        prefixy = self._najdi_prefixy_rozvaha(oznaceni, je_aktiva)
        if not prefixy:
            return tuple()
        return self._nacti_zapisy_pro_prefixy(
            rok=rok, prefixy=prefixy, druhy=None, je_aktiva=je_aktiva,
        )

    def _najdi_prefixy_vzz(
        self, oznaceni: str,
    ) -> tuple[tuple[str, ...], dict[str, str]]:
        """Vrátí (prefixy, druhy_pre_ucet) pro řádek VZZ.

        Pro sum_* řádky agreguje prefixy všech leaf řádků (`druh`
        in {'V', 'N', 'N_group'}). `druhy` mapuje prefix → 'V'/'N',
        aby drilldown věděl znaménko.
        """
        # Najdi řádek
        row = next(
            (r for r in VZZ_RADKY if r[0] == oznaceni), None,
        )
        if row is None:
            return tuple(), {}
        oz, _, prefixy, druh, _ = row

        if druh in ("V", "N", "N_group") and prefixy:
            return prefixy, {p: druh for p in prefixy}

        # Sumové řádky — agregace všech VZZ leaf řádků
        # (zjednodušené: zahrnujeme všechny řádky s prefixy)
        if druh.startswith("sum"):
            agreg: list[str] = []
            druhy: dict[str, str] = {}
            for r in VZZ_RADKY:
                d = r[3]
                if d in ("V", "N", "N_group") and r[2]:
                    for p in r[2]:
                        if p not in druhy:
                            agreg.append(p)
                            druhy[p] = d
            return tuple(agreg), druhy

        return prefixy, {p: druh for p in prefixy}

    def _najdi_prefixy_rozvaha(
        self, oznaceni: str, je_aktiva: bool,
    ) -> tuple[str, ...]:
        rows = ROZVAHA_AKTIVA if je_aktiva else ROZVAHA_PASIVA
        row = next((r for r in rows if r[0] == oznaceni), None)
        if row is None:
            return tuple()
        _, _, prefixy, _, kind = row

        if kind == "leaf":
            return prefixy

        # sum_top / sum_group → agregovat všechny leaf řádky strany
        if kind in ("sum_top", "sum_group"):
            agreg: list[str] = []
            for r in rows:
                if r[4] == "leaf" and r[2]:
                    for p in r[2]:
                        if p not in agreg:
                            agreg.append(p)
            return tuple(agreg)

        return prefixy

    def _nacti_zapisy_pro_prefixy(
        self,
        rok: int,
        prefixy: tuple[str, ...],
        druhy: dict[str, str] | None,
        je_aktiva: bool | None,
    ) -> tuple[DrilldownZapis, ...]:
        """Načte zápisy z deníku, kde MD nebo Dal matchuje některý prefix.

        Znaménko (+1/-1) určuje, jak zápis přispívá k saldu řádku:
          * Pro VZZ:
              - druh='V' (výnosy): Dal strana = +, MD strana = -
              - druh='N' (náklady): MD strana = +, Dal strana = -
          * Pro rozvahu:
              - aktiva: MD = +, Dal = -
              - pasiva: Dal = +, MD = -
        """
        od = date(rok, 1, 1)
        do = date(rok, 12, 31)

        uow = self._uow_factory()
        with uow:
            # Zahrnujeme i storno zápisy — originál + protizápis se ruší
            # (netto = 0), ale jejich součet musí souhlasit s celkovou
            # hodnotou ve výkazu (která taky storno započítává).
            zaznamy = uow.connection.execute(
                """
                SELECT uz.id, uz.doklad_id, uz.datum, uz.md_ucet, uz.dal_ucet,
                       uz.castka, uz.popis, uz.je_storno,
                       d.cislo AS doklad_cislo
                FROM ucetni_zaznamy uz
                JOIN doklady d ON d.id = uz.doklad_id
                WHERE uz.datum >= ? AND uz.datum <= ?
                ORDER BY uz.datum, uz.id
                """,
                (od.isoformat(), do.isoformat()),
            ).fetchall()

        result: list[DrilldownZapis] = []
        seen: set[int] = set()
        for r in zaznamy:
            if r["id"] in seen:
                continue
            md = r["md_ucet"]
            dal = r["dal_ucet"]
            md_match = next(
                (p for p in prefixy if self._matches(md, p)), None,
            )
            dal_match = next(
                (p for p in prefixy if self._matches(dal, p)), None,
            )
            if md_match is None and dal_match is None:
                continue

            znamenko = self._spocitej_znamenko(
                md_match, dal_match, druhy, je_aktiva,
            )
            if znamenko == 0:
                continue

            seen.add(r["id"])
            result.append(DrilldownZapis(
                id=r["id"],
                doklad_id=r["doklad_id"],
                datum=date.fromisoformat(r["datum"]),
                cislo_dokladu=r["doklad_cislo"],
                md_ucet=md,
                dal_ucet=dal,
                castka=Money(r["castka"]),
                popis=r["popis"],
                znamenko=znamenko,
                je_storno=bool(r["je_storno"]),
            ))
        return tuple(result)

    @staticmethod
    def _spocitej_znamenko(
        md_match: str | None,
        dal_match: str | None,
        druhy: dict[str, str] | None,
        je_aktiva: bool | None,
    ) -> int:
        """Vrátí +1, -1 nebo 0 (nematch / nejednoznačné)."""
        if druhy is not None:
            # VZZ
            if md_match is not None:
                d = druhy.get(md_match, "")
                if d in ("N", "N_group"):
                    return +1
                if d == "V":
                    return -1
            if dal_match is not None:
                d = druhy.get(dal_match, "")
                if d == "V":
                    return +1
                if d in ("N", "N_group"):
                    return -1
            return 0

        # Rozvaha
        if je_aktiva:
            if md_match is not None and dal_match is None:
                return +1
            if dal_match is not None and md_match is None:
                return -1
        else:
            if dal_match is not None and md_match is None:
                return +1
            if md_match is not None and dal_match is None:
                return -1
        # Oboustranný match (převod uvnitř stejné strany) → ignoruj
        return 0

    # ------------------------------------------------------------
    # 8. Pokladní kniha
    # ------------------------------------------------------------

    def get_pokladni_kniha(self, rok: int) -> PokladniKniha:
        """Pokladní kniha = hlavní kniha účtu 211."""
        try:
            kniha = self.get_hlavni_kniha("211", rok)
        except ValueError:
            return PokladniKniha(
                rok=rok, pocatecni_stav=Money.zero(),
                radky=tuple(), pouzita=False,
            )

        return PokladniKniha(
            rok=rok,
            pocatecni_stav=kniha.pocatecni_stav,
            radky=kniha.radky,
            pouzita=bool(kniha.radky),
        )

    # ────────────────────────────────────────────────────────
    # Interní helpers
    # ────────────────────────────────────────────────────────

    def _matches(self, ucet: str, prefix: str) -> bool:
        """Účet matchuje prefix pokud == prefix nebo začíná prefix + '.'.

        Boundary na tečce zaručí, že prefix '343.100' nematchuje '343.200'
        a prefix '321' matchuje syntetiku i všechny analytiky '321.xxx'.
        """
        if ucet == prefix:
            return True
        return ucet.startswith(prefix + ".")

    def _nacti_vsechny_ucty(self) -> dict[str, tuple[str, str]]:
        """Načte všechny aktivní účty: cislo -> (nazev, typ)."""
        uow = self._uow_factory()
        with uow:
            rows = uow.connection.execute(
                "SELECT cislo, nazev, typ FROM uctova_osnova WHERE je_aktivni = 1",
            ).fetchall()
        return {r["cislo"]: (r["nazev"], r["typ"]) for r in rows}

    def _nacti_obraty_a_ps(self, rok: int) -> dict[str, dict]:
        """Vrátí mapping cislo_uctu -> {ps_md, ps_dal, obrat_md, obrat_dal, typ, nazev}.

        Hodnoty v haléřích (int). Storno zápisy ignorovány.
        """
        od = date(rok, 1, 1)
        do = date(rok, 12, 31)

        uow = self._uow_factory()
        with uow:
            conn = uow.connection

            # Všechny účty (potřebujeme typ a název)
            ucty_rows = conn.execute(
                "SELECT cislo, nazev, typ FROM uctova_osnova",
            ).fetchall()
            data: dict[str, dict] = {}
            for r in ucty_rows:
                data[r["cislo"]] = {
                    "nazev": r["nazev"],
                    "typ": r["typ"],
                    "ps_md": 0,
                    "ps_dal": 0,
                    "obrat_md": 0,
                    "obrat_dal": 0,
                }

            # Počáteční stavy
            ps_rows = conn.execute(
                """
                SELECT ucet_kod, strana, SUM(castka) AS s
                FROM pocatecni_stavy
                WHERE rok = ?
                GROUP BY ucet_kod, strana
                """,
                (rok,),
            ).fetchall()
            for r in ps_rows:
                if r["ucet_kod"] not in data:
                    continue
                if r["strana"] == "MD":
                    data[r["ucet_kod"]]["ps_md"] = r["s"] or 0
                else:
                    data[r["ucet_kod"]]["ps_dal"] = r["s"] or 0

            # Obraty — vč. storno protizápisů (originál + protizápis se
            # navzájem ruší, netto = 0, ale obraty na obou stranách jsou
            # potřeba pro správný součet a bilancování rozvahy).
            obraty_md = conn.execute(
                """
                SELECT md_ucet, SUM(castka) AS s
                FROM ucetni_zaznamy
                WHERE datum >= ? AND datum <= ?
                GROUP BY md_ucet
                """,
                (od.isoformat(), do.isoformat()),
            ).fetchall()
            for r in obraty_md:
                if r["md_ucet"] not in data:
                    continue
                data[r["md_ucet"]]["obrat_md"] = r["s"] or 0

            obraty_dal = conn.execute(
                """
                SELECT dal_ucet, SUM(castka) AS s
                FROM ucetni_zaznamy
                WHERE datum >= ? AND datum <= ?
                GROUP BY dal_ucet
                """,
                (od.isoformat(), do.isoformat()),
            ).fetchall()
            for r in obraty_dal:
                if r["dal_ucet"] not in data:
                    continue
                data[r["dal_ucet"]]["obrat_dal"] = r["s"] or 0

        return data

    def _saldo_uctu(self, ucet_data: dict, je_aktiva: bool) -> int:
        """Vrátí saldo účtu v haléřích — vždy kladné na vlastní straně.

        Aktiva: PS_md + obrat_md - PS_dal - obrat_dal
        Pasiva: PS_dal + obrat_dal - PS_md - obrat_md
        """
        md = ucet_data["ps_md"] + ucet_data["obrat_md"]
        dal = ucet_data["ps_dal"] + ucet_data["obrat_dal"]
        return (md - dal) if je_aktiva else (dal - md)

    def _sum_obrat_signed(
        self, ucty: dict, prefixes: tuple[str, ...], je_vynosovy: bool,
    ) -> Money:
        """Sečte obraty účtů s daným prefixem.

        Výnosy: Dal - MD (kladný = výnos)
        Náklady: MD - Dal (kladný = náklad)
        """
        if not prefixes:
            return Money.zero()

        total = 0
        for cislo, data in ucty.items():
            if not any(self._matches(cislo, pfx) for pfx in prefixes):
                continue
            md = data["obrat_md"]
            dal = data["obrat_dal"]
            if je_vynosovy:
                total += dal - md
            else:
                total += md - dal
        return Money(total)

    def _spocitej_vh(self, ucty: dict) -> Money:
        """VH = výnosy - náklady = sum(V účtů: Dal-MD) - sum(N účtů: MD-Dal).

        Tj. VH = sum(V: Dal-MD) + sum(N: Dal-MD) = sum(N+V: Dal-MD)
        ekvivalentně VH = sum(N+V: Dal) - sum(N+V: MD)
        """
        vynosy = 0
        naklady = 0
        for _cislo, data in ucty.items():
            md = data["obrat_md"]
            dal = data["obrat_dal"]
            typ = data["typ"]
            if typ == "V":
                vynosy += dal - md
            elif typ == "N":
                naklady += md - dal
        return Money(vynosy - naklady)

    def _sestav_rozvaha_stranu(
        self,
        layout: tuple[tuple, ...],
        sum_top_sources: tuple[str, ...],
        ucty: dict,
        vh_bezne: Money | None,
        je_aktiva: bool,
    ) -> tuple[RozvahaRadek, ...]:
        """Sestaví řádky rozvahy včetně součtů."""
        # 1. Spočítej leaf řádky
        leaf_hodnoty: dict[str, Money] = {}
        for oznaceni, _nazev, prefixes, _level, kind in layout:
            if kind == "leaf":
                hodnota = 0
                for cislo, data in ucty.items():
                    if not any(self._matches(cislo, pfx) for pfx in prefixes):
                        continue
                    hodnota += self._saldo_uctu(data, je_aktiva)
                leaf_hodnoty[oznaceni] = Money(hodnota)
            elif kind == "leaf_vh":
                # A.V. — vh běžného období (na pasivách)
                leaf_hodnoty[oznaceni] = vh_bezne if vh_bezne is not None else Money.zero()

        # 2. Spočítej skupinové součty
        sum_hodnoty: dict[str, Money] = {}
        for oznaceni, _nazev, _prefixes, _level, kind in layout:
            if kind == "sum_group":
                source = ROZVAHA_GROUPS.get(oznaceni, ())
                hodnota = 0
                for src in source:
                    if src in leaf_hodnoty:
                        hodnota += leaf_hodnoty[src].to_halire()
                    elif src in sum_hodnoty:
                        hodnota += sum_hodnoty[src].to_halire()
                sum_hodnoty[oznaceni] = Money(hodnota)

        # 3. Spočítej top součet (AKTIVA CELKEM / PASIVA CELKEM)
        top_hodnota = 0
        for src in sum_top_sources:
            if src in leaf_hodnoty:
                top_hodnota += leaf_hodnoty[src].to_halire()
            elif src in sum_hodnoty:
                top_hodnota += sum_hodnoty[src].to_halire()

        # 4. Sestav výsledné řádky
        radky: list[RozvahaRadek] = []
        for oznaceni, nazev, _prefixes, level, kind in layout:
            if kind == "sum_top":
                hodnota = Money(top_hodnota)
            elif kind == "sum_group":
                hodnota = sum_hodnoty.get(oznaceni, Money.zero())
            else:
                hodnota = leaf_hodnoty.get(oznaceni, Money.zero())
            radky.append(RozvahaRadek(
                oznaceni=oznaceni,
                nazev=nazev,
                hodnota=hodnota,
                minule=Money.zero(),
                level=level,
                kind=kind,
            ))
        return tuple(radky)

    def _sestav_vzz(self, ucty: dict) -> tuple[VzzRadek, ...]:
        """Sestaví řádky VZZ. Klíčuje podle (oznaceni, druh) protože
        oznaceni 'I.' je v VZZ duplicitní (výnos i náklad)."""
        # Rozdělíme druhy
        # Pro každý leaf řádek vypočítej hodnotu
        per_klic: dict[tuple[str, str], Money] = {}
        for oznaceni, _nazev, prefixes, druh, _lvl in VZZ_RADKY:
            if druh == "V":
                hodnota = self._sum_obrat_signed(ucty, prefixes, je_vynosovy=True)
            elif druh == "N":
                hodnota = self._sum_obrat_signed(ucty, prefixes, je_vynosovy=False)
            else:
                hodnota = Money.zero()
            per_klic[(oznaceni, druh)] = hodnota

        # Provozní VH
        provozni = (
            per_klic[("I.", "V")] + per_klic[("II.", "V")] + per_klic[("III.", "V")]
            - per_klic[("A.1.", "N")] - per_klic[("A.2.", "N")] - per_klic[("A.3.", "N")]
            - per_klic[("B.", "N")] - per_klic[("C.", "N")] - per_klic[("D.", "N")]
            - per_klic[("E.", "N")] - per_klic[("F.", "N")]
        )
        # A. (výkonová spotřeba součet) = A.1 + A.2 + A.3
        a_group = (
            per_klic[("A.1.", "N")] + per_klic[("A.2.", "N")] + per_klic[("A.3.", "N")]
        )
        per_klic[("A.", "N_group")] = a_group

        # Finanční VH
        financni = (
            per_klic[("IV.", "V")] + per_klic[("V.", "V")]
            + per_klic[("VI.", "V")] + per_klic[("VII.", "V")]
            - per_klic[("G.", "N")] - per_klic[("H.", "N")]
            - per_klic[("I.", "N")] - per_klic[("J.", "N")] - per_klic[("K.", "N")]
        )
        pred_dani = provozni + financni
        po_dani = pred_dani - per_klic[("L.", "N")]

        per_klic[("*", "sum_provozni")] = provozni
        per_klic[("**fin", "sum_financni")] = financni
        per_klic[("***pred", "sum_pred_dani")] = pred_dani
        per_klic[("**pod", "sum_po_dani")] = po_dani
        per_klic[("****", "sum_celkem")] = po_dani

        radky: list[VzzRadek] = []
        for oznaceni, nazev, _prefixes, druh, level in VZZ_RADKY:
            hodnota = per_klic.get((oznaceni, druh), Money.zero())
            radky.append(VzzRadek(
                oznaceni=oznaceni,
                nazev=nazev,
                hodnota=hodnota,
                minule=Money.zero(),
                druh=druh,
                level=level,
            ))
        return tuple(radky)

    def _spocitej_uhrazeno(
        self, conn, doklad_id: int, typ: str, cislo: str,
    ) -> Money:
        """Spočítá uhrazenou částku pro FP/FV.

        FP (závazek): úhrady = MD '321%' nebo '365%' v jiných dokladech
                      spárovaných přes bankovni_transakce nebo přes popis.
        FV (pohledávka): úhrady = Dal '311%' v jiných dokladech.
        """
        if typ == "FP":
            md_dal_clause = "(uz.md_ucet LIKE '321%' OR uz.md_ucet LIKE '365%')"
        else:  # FV
            md_dal_clause = "uz.dal_ucet LIKE '311%'"

        # Source 1: bankovní transakce spárované s tímto dokladem
        rows = conn.execute(
            f"""
            SELECT uz.id, uz.castka
            FROM ucetni_zaznamy uz
            JOIN bankovni_transakce bt ON bt.ucetni_zapis_id = uz.id
            WHERE bt.sparovany_doklad_id = ?
              AND uz.je_storno = 0
              AND uz.doklad_id != ?
              AND {md_dal_clause}
            UNION
            SELECT uz.id, uz.castka
            FROM ucetni_zaznamy uz
            JOIN doklady d ON d.id = uz.doklad_id
            WHERE uz.popis LIKE ?
              AND uz.je_storno = 0
              AND uz.doklad_id != ?
              AND d.typ IN ('PD', 'ID')
              AND {md_dal_clause}
            """,
            (doklad_id, doklad_id, f"%{cislo}%", doklad_id),
        ).fetchall()

        seen_ids: set[int] = set()
        total = 0
        for r in rows:
            if r["id"] in seen_ids:
                continue
            seen_ids.add(r["id"])
            total += r["castka"]
        return Money(total)
