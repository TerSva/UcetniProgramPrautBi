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
    ("C.II.",  "Pohledávky",                             ("311", "314", "355", "343.100"), 2, "leaf"),
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
    ("C.",     "Závazky",                                ("321", "331", "336", "341", "342", "343.200", "345", "365", "379"), 2, "leaf"),
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
    ("F.",     "Ostatní provozní náklady",          ("538", "543", "544", "548", "549"), "N", 1),
    ("*",      "Provozní výsledek hospodaření",     (), "sum_provozni", 1),
    ("IV.",    "Výnosy z dlouhodobého finančního majetku", (), "V", 1),
    ("G.",     "Náklady vynaložené na prodané podíly", (), "N", 1),
    ("V.",     "Výnosy z ostatního dlouhodobého finančního majetku", (), "V", 1),
    ("H.",     "Náklady související s ostatním DFM", (), "N", 1),
    ("VI.",    "Výnosové úroky a podobné výnosy",   ("662",), "V", 1),
    ("I.",     "Úpravy hodnot a rezervy ve fin. oblasti", (), "N", 1),
    ("J.",     "Nákladové úroky a podobné náklady", (), "N", 1),
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
    # 7. Pokladní kniha
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
