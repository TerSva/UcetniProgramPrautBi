"""Testy pro VykazyQuery — Rozvaha, VZZ, Předvaha, Hlavní kniha,
Saldokonto, DPH přehled, Pokladní kniha.

Kontrolní pravidla:
  - Rozvaha bilancuje (aktiva == pasiva)
  - VZZ.VH == Rozvaha A.V.
  - Předvaha vyvážená (MD obraty == Dal obraty)
  - U RC: DPH vstup == DPH výstup
"""

from __future__ import annotations

from datetime import date

import pytest

from domain.doklady.doklad import Doklad
from domain.doklady.typy import DphRezim, StavDokladu, TypDokladu
from domain.shared.money import Money
from domain.ucetnictvi.ucetni_zaznam import UcetniZaznam
from domain.ucetnictvi.uctovy_predpis import UctovyPredpis
from infrastructure.database.repositories.doklady_repository import (
    SqliteDokladyRepository,
)
from services.queries.vykazy_query import VykazyQuery
from services.zauctovani_service import ZauctovaniDokladuService


# ────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────

@pytest.fixture
def vykazy_query(service_factories) -> VykazyQuery:
    return VykazyQuery(uow_factory=service_factories["uow"])


@pytest.fixture
def zauctovani(service_factories) -> ZauctovaniDokladuService:
    return ZauctovaniDokladuService(
        uow_factory=service_factories["uow"],
        doklady_repo_factory=service_factories["doklady"],
        denik_repo_factory=service_factories["denik"],
    )


def _vytvor_doklad(
    service_factories, cislo, typ, datum, castka_kc,
    dph_rezim=DphRezim.TUZEMSKO,
):
    uow = service_factories["uow"]()
    with uow:
        repo = SqliteDokladyRepository(uow)
        d = repo.add(Doklad(
            cislo=cislo, typ=typ, datum_vystaveni=datum,
            castka_celkem=Money.from_koruny(castka_kc),
            dph_rezim=dph_rezim,
        ))
        uow.commit()
    return d.id


def _set_stav(service_factories, doklad_id: int, stav: StavDokladu) -> None:
    """Pomocný helper — přepsat stav dokladu (testy saldokonta)."""
    uow = service_factories["uow"]()
    with uow:
        uow.connection.execute(
            "UPDATE doklady SET stav = ? WHERE id = ?",
            (stav.value, doklad_id),
        )
        uow.commit()


@pytest.fixture
def scenar_2025(service_factories, zauctovani):
    """Reálný scénář PRAUT 2025 (zjednodušený):

    1. FV-001: 12 100 Kč (10 000 + 21% DPH 2 100)
       MD 311 / Dal 601: 10 000
       MD 311 / Dal 343.200: 2 100
       → ZAUCTOVANY

    2. FP-001 RC (Meta-like): 100 Kč (RC 21%)
       MD 518.200 / Dal 321.002: 100
       MD 343.100 / Dal 343.200: 21
       → ZAUCTOVANY

    3. Vklad ZK 10 Kč:
       MD 221.001 / Dal 411: 10
       → ZAUCTOVANY (jako ID)

    4. Úhrada FV-001 přes BV:
       MD 221.001 / Dal 311: 12 100
       → BV doklad, ovlivní stav FV-001 → UHRAZENY
    """
    # 1. FV
    fv_id = _vytvor_doklad(
        service_factories, "FV-001", TypDokladu.FAKTURA_VYDANA,
        date(2025, 4, 1), "12100",
    )
    zauctovani.zauctuj_doklad(fv_id, UctovyPredpis(
        doklad_id=fv_id,
        zaznamy=(
            UcetniZaznam(
                doklad_id=fv_id, datum=date(2025, 4, 1),
                md_ucet="311", dal_ucet="601",
                castka=Money.from_koruny("10000"),
                popis="Tržba",
            ),
            UcetniZaznam(
                doklad_id=fv_id, datum=date(2025, 4, 1),
                md_ucet="311", dal_ucet="343.200",
                castka=Money.from_koruny("2100"),
                popis="DPH 21%",
            ),
        ),
    ))

    # 2. FP RC
    fp_id = _vytvor_doklad(
        service_factories, "FP-001", TypDokladu.FAKTURA_PRIJATA,
        date(2025, 4, 10), "100",
        dph_rezim=DphRezim.REVERSE_CHARGE,
    )
    zauctovani.zauctuj_doklad(fp_id, UctovyPredpis(
        doklad_id=fp_id,
        zaznamy=(
            UcetniZaznam(
                doklad_id=fp_id, datum=date(2025, 4, 10),
                md_ucet="518.200", dal_ucet="321.002",
                castka=Money.from_koruny("100"),
                popis="Meta služby",
            ),
            UcetniZaznam(
                doklad_id=fp_id, datum=date(2025, 4, 10),
                md_ucet="343.100", dal_ucet="343.200",
                castka=Money.from_koruny("21"),
                popis="DPH RC 21%",
            ),
        ),
    ))

    # 3. Vklad ZK
    id_id = _vytvor_doklad(
        service_factories, "ID-001", TypDokladu.INTERNI_DOKLAD,
        date(2025, 2, 3), "10",
    )
    zauctovani.zauctuj_doklad(id_id, UctovyPredpis(
        doklad_id=id_id,
        zaznamy=(
            UcetniZaznam(
                doklad_id=id_id, datum=date(2025, 2, 3),
                md_ucet="221.001", dal_ucet="411",
                castka=Money.from_koruny("10"),
                popis="Vklad ZK",
            ),
        ),
    ))

    # 4. Úhrada FV — BV doklad
    bv_id = _vytvor_doklad(
        service_factories, "BV-2025-04", TypDokladu.BANKOVNI_VYPIS,
        date(2025, 4, 15), "12100",
    )
    zauctovani.zauctuj_doklad(bv_id, UctovyPredpis(
        doklad_id=bv_id,
        zaznamy=(
            UcetniZaznam(
                doklad_id=bv_id, datum=date(2025, 4, 15),
                md_ucet="221.001", dal_ucet="311",
                castka=Money.from_koruny("12100"),
                popis="Úhrada FV-001",
            ),
        ),
    ))
    _set_stav(service_factories, fv_id, StavDokladu.UHRAZENY)

    return {
        "fv_id": fv_id,
        "fp_id": fp_id,
        "id_id": id_id,
        "bv_id": bv_id,
    }


# ────────────────────────────────────────────────────────────
# Rozvaha
# ────────────────────────────────────────────────────────────

class TestRozvaha:

    def test_prazdny_rok_vse_nuly(self, vykazy_query):
        aktiva, pasiva = vykazy_query.get_rozvaha(2025)
        # Existuje řádek "AKTIVA CELKEM" / "PASIVA CELKEM" s hodnotou 0
        a_total = next(r for r in aktiva if r.kind == "sum_top")
        p_total = next(r for r in pasiva if r.kind == "sum_top")
        assert a_total.hodnota == Money.zero()
        assert p_total.hodnota == Money.zero()

    def test_rozvaha_bilancuje(self, vykazy_query, scenar_2025):
        a_celkem, p_celkem = vykazy_query.get_bilancni_kontrola(2025)
        assert a_celkem == p_celkem, (
            f"Rozvaha nebilancuje: aktiva={a_celkem}, pasiva={p_celkem}"
        )

    def test_rozvaha_obsahuje_vsechny_radky(self, vykazy_query):
        """První rok = vše 0, ale řádky musí být všechny."""
        aktiva, pasiva = vykazy_query.get_rozvaha(2025)
        a_oznaceni = [r.oznaceni for r in aktiva]
        # Aspoň hlavní řádky aktiv
        for ozn in ("", "A.", "B.", "C.II.", "C.IV.", "D."):
            assert ozn in a_oznaceni, f"Chybí řádek aktiv: {ozn!r}"
        p_oznaceni = [r.oznaceni for r in pasiva]
        for ozn in ("", "A.", "A.I.", "A.V.", "B+C.", "C."):
            assert ozn in p_oznaceni, f"Chybí řádek pasiv: {ozn!r}"

    def test_penize_221(self, vykazy_query, scenar_2025):
        """Po úhradě FV: 221.001 = 10 (vklad) + 12 100 (úhrada) = 12 110."""
        aktiva, _ = vykazy_query.get_rozvaha(2025)
        c_iv = next(r for r in aktiva if r.oznaceni == "C.IV.")
        assert c_iv.hodnota == Money.from_koruny("12110")

    def test_zk_411(self, vykazy_query, scenar_2025):
        """Základní kapitál (411) = 10 Kč."""
        _, pasiva = vykazy_query.get_rozvaha(2025)
        a_i = next(r for r in pasiva if r.oznaceni == "A.I.")
        assert a_i.hodnota == Money.from_koruny("10")

    def test_zavazek_321_002(self, vykazy_query, scenar_2025):
        """Závazek z RC FP: 321.002 = 100 (neuhrazený)."""
        _, pasiva = vykazy_query.get_rozvaha(2025)
        c = next(r for r in pasiva if r.oznaceni == "C.")
        # 321.002 = 100. 343.100 vstup = -21 jako pasivum (záporné).
        # 343.200 výstup = 2 100 + 21 = 2 121.
        # Σ = 100 + 2121 = 2 221 (343.100 v aktivech, ne pasivech)
        assert c.hodnota == Money.from_koruny("2221"), (
            f"Závazky C. = {c.hodnota}"
        )

    def test_343_100_v_pohledavkach(self, vykazy_query, scenar_2025):
        """343.100 (vstup DPH) je v C.II. Pohledávky pro identifikovanou osobu.

        Po RC: MD 343.100 = 21, Dal 343.100 = 0 → saldo aktiv +21.
        Po FV: 311 cyklus (12100 dovnitř, 12100 ven) → 0.
        C.II. = 0 + 21 = 21.
        """
        aktiva, _ = vykazy_query.get_rozvaha(2025)
        c_ii = next(r for r in aktiva if r.oznaceni == "C.II.")
        assert c_ii.hodnota == Money.from_koruny("21")


# ────────────────────────────────────────────────────────────
# VZZ
# ────────────────────────────────────────────────────────────

class TestVZZ:

    def test_vzz_prazdny_rok(self, vykazy_query):
        radky = vykazy_query.get_vzz(2025)
        assert len(radky) > 0
        # Všechny hodnoty = 0
        for r in radky:
            assert r.hodnota == Money.zero(), f"{r.oznaceni}: {r.hodnota}"

    def test_vzz_vh_odpovida_rozvaze(self, vykazy_query, scenar_2025):
        """A.V. v Rozvaze = výsledek hospodaření z VZZ."""
        radky = vykazy_query.get_vzz(2025)
        vh_vzz = next(r for r in radky if r.druh == "sum_celkem")

        _, pasiva = vykazy_query.get_rozvaha(2025)
        a_v = next(r for r in pasiva if r.oznaceni == "A.V.")

        assert vh_vzz.hodnota == a_v.hodnota

    def test_vzz_vynosy(self, vykazy_query, scenar_2025):
        """I. Tržby = 10 000 Kč (Dal 601)."""
        radky = vykazy_query.get_vzz(2025)
        i = next(r for r in radky if r.oznaceni == "I." and r.druh == "V")
        assert i.hodnota == Money.from_koruny("10000")

    def test_vzz_naklady_sluzby(self, vykazy_query, scenar_2025):
        """A.3. Služby = 100 Kč (518.200 RC)."""
        radky = vykazy_query.get_vzz(2025)
        a_3 = next(r for r in radky if r.oznaceni == "A.3.")
        assert a_3.hodnota == Money.from_koruny("100")


# ────────────────────────────────────────────────────────────
# Předvaha
# ────────────────────────────────────────────────────────────

class TestPredvaha:

    def test_predvaha_md_eq_dal(self, vykazy_query, scenar_2025):
        """MD obraty CELKEM == Dal obraty CELKEM."""
        radky = vykazy_query.get_predvaha(2025)
        celkem_md = sum(r.obrat_md.to_halire() for r in radky)
        celkem_dal = sum(r.obrat_dal.to_halire() for r in radky)
        assert celkem_md == celkem_dal, f"MD={celkem_md}, Dal={celkem_dal}"

    def test_predvaha_jen_ucty_s_pohybem(self, vykazy_query, scenar_2025):
        """Default: jen účty s pohybem."""
        radky = vykazy_query.get_predvaha(2025, jen_s_pohybem=True)
        cisla = {r.ucet for r in radky}
        # Účty bez pohybu nesmí být
        assert "504" not in cisla     # Prodané zboží
        assert "521" not in cisla     # Mzdové náklady
        # Účty s pohybem musí být
        assert "311" in cisla
        assert "411" in cisla
        assert "601" in cisla

    def test_predvaha_obraty_311(self, vykazy_query, scenar_2025):
        """311: MD 12 100 (FV), Dal 12 100 (úhrada)."""
        radky = vykazy_query.get_predvaha(2025)
        r_311 = next(r for r in radky if r.ucet == "311")
        assert r_311.obrat_md == Money.from_koruny("12100")
        assert r_311.obrat_dal == Money.from_koruny("12100")
        # KZ = 0
        assert r_311.kz_md == Money.zero()
        assert r_311.kz_dal == Money.zero()


# ────────────────────────────────────────────────────────────
# Hlavní kniha
# ────────────────────────────────────────────────────────────

class TestHlavniKniha:

    def test_hlavni_kniha_311(self, vykazy_query, scenar_2025):
        """311: dva pohyby (zaúčtování FV + úhrada)."""
        kniha = vykazy_query.get_hlavni_kniha("311", 2025)
        # Dva pohyby z FV-001 (Tržba + DPH = 2 řádky), úhrada (1 řádek) = 3
        # Pozn.: oba řádky FV-001 jsou na MD 311.
        assert len(kniha.radky) == 3
        # Konečný zůstatek = 0 (všechno uhrazeno)
        assert kniha.koncovy_zustatek == Money.zero()
        assert kniha.obrat_md == Money.from_koruny("12100")
        assert kniha.obrat_dal == Money.from_koruny("12100")

    def test_hlavni_kniha_321_synteticky(self, vykazy_query, scenar_2025):
        """Syntetický 321 zachytí pohyby na 321.002 (RC analytika)."""
        kniha = vykazy_query.get_hlavni_kniha("321", 2025)
        assert len(kniha.radky) == 1
        assert kniha.radky[0].dal == Money.from_koruny("100")
        assert kniha.koncovy_zustatek == Money.from_koruny("-100")  # Dal strana

    def test_hlavni_kniha_zustatky_prubezne(self, vykazy_query, scenar_2025):
        """Zůstatek po každém řádku = PS + cumsum(MD-Dal)."""
        kniha = vykazy_query.get_hlavni_kniha("311", 2025)
        # Pohyby chronologicky:
        # 2025-04-01: MD 10000 → +10000
        # 2025-04-01: MD 2100  → +12100
        # 2025-04-15: Dal 12100 → 0
        zustatky = [r.zustatek for r in kniha.radky]
        assert zustatky[0] == Money.from_koruny("10000")
        assert zustatky[1] == Money.from_koruny("12100")
        assert zustatky[2] == Money.zero()

    def test_hlavni_kniha_neexistujici_ucet(self, vykazy_query):
        with pytest.raises(ValueError):
            vykazy_query.get_hlavni_kniha("999", 2025)


# ────────────────────────────────────────────────────────────
# Saldokonto
# ────────────────────────────────────────────────────────────

class TestSaldokonto:

    def test_saldokonto_jen_neuhrazene(self, vykazy_query, scenar_2025):
        """FV-001 je UHRAZENY → není v saldokontu.
        FP-001 je ZAUCTOVANY → je v saldokontu."""
        zavazky, pohledavky = vykazy_query.get_saldokonto(2025)
        zavazky_cisla = {r.cislo_dokladu for r in zavazky}
        pohledavky_cisla = {r.cislo_dokladu for r in pohledavky}
        assert "FP-001" in zavazky_cisla
        assert "FV-001" not in pohledavky_cisla   # uhrazeny

    def test_saldokonto_zbyva_neuhrazene_fp(self, vykazy_query, scenar_2025):
        """FP-001 (100 Kč) bez úhrady → zbyva = 100, uhrazeno = 0."""
        zavazky, _ = vykazy_query.get_saldokonto(2025)
        fp = next(r for r in zavazky if r.cislo_dokladu == "FP-001")
        assert fp.uhrazeno == Money.zero()
        assert fp.zbyva == Money.from_koruny("100")
        assert fp.castka == Money.from_koruny("100")


# ────────────────────────────────────────────────────────────
# DPH přehled
# ────────────────────────────────────────────────────────────

class TestDphPrehled:

    def test_dph_rc_vstup_eq_vystup(self, vykazy_query, scenar_2025):
        """U RC: DPH vstup == DPH výstup."""
        prehled = vykazy_query.get_dph_prehled(2025)
        assert prehled.vstup_rc == prehled.vystup_rc

    def test_dph_celkove_vystup(self, vykazy_query, scenar_2025):
        """Výstup celkem = 2 100 (FV) + 21 (RC) = 2 121."""
        prehled = vykazy_query.get_dph_prehled(2025)
        assert prehled.vystup_celkem == Money.from_koruny("2121")

    def test_dph_celkove_vstup(self, vykazy_query, scenar_2025):
        """Vstup celkem = 21 (RC)."""
        prehled = vykazy_query.get_dph_prehled(2025)
        assert prehled.vstup_celkem == Money.from_koruny("21")

    def test_dph_doklady_obsahuje_fp_a_fv(self, vykazy_query, scenar_2025):
        prehled = vykazy_query.get_dph_prehled(2025)
        cisla = {d.cislo_dokladu for d in prehled.doklady}
        assert "FV-001" in cisla
        assert "FP-001" in cisla

    def test_dph_obdobi_q1_prazdne(self, vykazy_query, scenar_2025):
        """Q1 2025 (leden-březen) — žádné DPH doklady, jen ID-001 vklad."""
        prehled = vykazy_query.get_dph_prehled(2025, ctvrtleti=1)
        assert prehled.vstup_celkem == Money.zero()
        assert prehled.vystup_celkem == Money.zero()


# ────────────────────────────────────────────────────────────
# Pokladní kniha
# ────────────────────────────────────────────────────────────

class TestPokladniKniha:

    def test_pokladna_neaktivni(self, vykazy_query, scenar_2025):
        """211 nemá pohyb → pouzita = False."""
        kniha = vykazy_query.get_pokladni_kniha(2025)
        assert kniha.pouzita is False
        assert kniha.koncovy_stav == Money.zero()

    def test_pokladna_aktivni(self, service_factories, vykazy_query, zauctovani):
        """Vytvoříme pohyb na 211 → pouzita = True."""
        pd = _vytvor_doklad(
            service_factories, "PD-001", TypDokladu.POKLADNI_DOKLAD,
            date(2025, 5, 1), "500",
        )
        zauctovani.zauctuj_doklad(pd, UctovyPredpis(
            doklad_id=pd,
            zaznamy=(
                UcetniZaznam(
                    doklad_id=pd, datum=date(2025, 5, 1),
                    md_ucet="211", dal_ucet="221.001",
                    castka=Money.from_koruny("500"),
                    popis="Výběr z banky",
                ),
            ),
        ))
        kniha = vykazy_query.get_pokladni_kniha(2025)
        assert kniha.pouzita is True
        assert kniha.koncovy_stav == Money.from_koruny("500")
        assert len(kniha.radky) == 1


# ────────────────────────────────────────────────────────────
# PDF Export
# ────────────────────────────────────────────────────────────

class TestPdfExport:

    def test_pdf_export_vytvori_soubor(
        self, vykazy_query, scenar_2025, tmp_path,
    ):
        """Export do PDF vytvoří soubor s plausibilní velikostí."""
        from services.export.pdf_export import export_vykazy_pdf

        output = tmp_path / "vykazy.pdf"
        result = export_vykazy_pdf(
            vykazy_query=vykazy_query,
            rok=2025,
            output_path=output,
        )
        assert result == output
        assert output.exists()
        assert output.stat().st_size > 5000  # netriviálně velký
        # PDF magic header
        assert output.read_bytes()[:4] == b"%PDF"

    def test_pdf_export_prazdny_rok(self, vykazy_query, tmp_path):
        """Export i bez dat se nesmí rozbít — minimum titul + prázdné výkazy."""
        from services.export.pdf_export import export_vykazy_pdf

        output = tmp_path / "prazdny.pdf"
        export_vykazy_pdf(
            vykazy_query=vykazy_query,
            rok=2025,
            output_path=output,
        )
        assert output.exists()
        assert output.stat().st_size > 1000
