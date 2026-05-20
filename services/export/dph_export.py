"""Export DPH přiznání za rozsah měsíců do PDF.

WeasyPrint (HTML+CSS → PDF). Per měsíc: hlavička firma + období + stav,
tabulka 11 řádků EPO formuláře, tabulka RC transakcí. Měsíce bez RC
plnění se vynechají.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from domain.firma.firma import Firma
from domain.shared.money import Money
from infrastructure.database.repositories.firma_repository import (
    SqliteFirmaRepository,
)
from infrastructure.database.unit_of_work import SqliteUnitOfWork
from services.queries.dph_prehled import (
    DphMesicDetailQuery,
    DphMesicItem,
    DphPrehledQuery,
    DphPriznaniRadky,
    DphTransakceItem,
)


_MESICE_CZ = [
    "", "Leden", "Únor", "Březen", "Duben", "Květen", "Červen",
    "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec",
]


@dataclass(frozen=True)
class DphExportRozsah:
    """Rozsah měsíců k exportu (včetně obou krajů)."""

    od_rok: int
    od_mesic: int
    do_rok: int
    do_mesic: int

    def iter_mesice(self) -> list[tuple[int, int]]:
        out = []
        rok, mesic = self.od_rok, self.od_mesic
        while (rok, mesic) <= (self.do_rok, self.do_mesic):
            out.append((rok, mesic))
            mesic += 1
            if mesic > 12:
                mesic = 1
                rok += 1
        return out


_CSS = """
@page {
    size: A4;
    margin: 18mm 16mm 18mm 16mm;
    @bottom-right {
        content: "Strana " counter(page) " / " counter(pages);
        font-size: 9pt;
        color: #666;
    }
}
body {
    font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
    font-size: 10pt;
    color: #1a1a1a;
}
.mesic { page-break-after: always; }
.mesic:last-child { page-break-after: auto; }
h1 {
    font-size: 16pt;
    margin: 0 0 4pt 0;
    border-bottom: 2pt solid #2c5f4f;
    padding-bottom: 4pt;
}
.subtitle {
    color: #666;
    font-size: 10pt;
    margin-bottom: 12pt;
}
.metadata {
    margin: 8pt 0 14pt 0;
    padding: 6pt 8pt;
    background: #f4f7f5;
    border-left: 3pt solid #2c5f4f;
    font-size: 9.5pt;
}
.metadata div { margin: 2pt 0; }
.metadata .label { display: inline-block; min-width: 110pt; color: #555; }
.status-podano { color: #1f7a3a; font-weight: 600; }
.status-k-podani { color: #b8500c; font-weight: 600; }
h2 {
    font-size: 11pt;
    margin: 14pt 0 6pt 0;
    color: #2c5f4f;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 8pt;
    font-size: 9.5pt;
}
th, td {
    border: 0.5pt solid #d0d0d0;
    padding: 4pt 6pt;
    text-align: left;
    vertical-align: top;
}
th {
    background: #eef2f0;
    font-weight: 600;
    font-size: 9pt;
}
td.right { text-align: right; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
tr.row-66 td { font-weight: 700; background: #f9f6e8; }
tr.celkem td { font-weight: 700; border-top: 1pt solid #888; }
.firma-header {
    font-size: 9pt;
    color: #666;
    text-align: right;
    margin-bottom: 4pt;
}
"""


def _fmt_kc(money: Money) -> str:
    return money.format_cz()


def _kc_celé(money: Money) -> int:
    from decimal import Decimal as _D, ROUND_HALF_UP, localcontext
    with localcontext() as ctx:
        ctx.rounding = ROUND_HALF_UP
        return int(_D(money.to_halire()).scaleb(-2).quantize(_D("1")))


def _format_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _termin_podani(rok: int, mesic: int) -> date:
    if mesic == 12:
        return date(rok + 1, 1, 25)
    return date(rok, mesic + 1, 25)


def _render_firma_header(firma: Firma | None) -> str:
    if firma is None:
        return ""
    parts = [firma.nazev]
    if firma.ico:
        parts.append(f"IČO {firma.ico}")
    if firma.dic:
        parts.append(f"DIČ {firma.dic}")
    return f'<div class="firma-header">{" · ".join(parts)}</div>'


def _render_metadata(
    rok: int,
    mesic: int,
    mesic_item: DphMesicItem,
    datum_sestaveni: date,
) -> str:
    termin = _termin_podani(rok, mesic)
    if mesic_item.je_podane:
        status = '<span class="status-podano">Podáno</span>'
    else:
        status = (
            f'<span class="status-k-podani">K podání '
            f'(termín {_format_date(termin)})</span>'
        )
    return f"""
    <div class="metadata">
        <div><span class="label">Období:</span>
             {_MESICE_CZ[mesic]} {rok}</div>
        <div><span class="label">Termín podání:</span>
             {_format_date(termin)}</div>
        <div><span class="label">Stav:</span> {status}</div>
        <div><span class="label">Datum sestavení:</span>
             {_format_date(datum_sestaveni)}</div>
        <div><span class="label">Počet RC dokladů:</span>
             {mesic_item.pocet_transakci}</div>
    </div>
    """


_EPO_LABELS: list[tuple[str, str, bool, bool]] = [
    ("Řádek 7", "Pořízení zboží z JČS (§16)", False, False),
    ("Řádek 9", "Přijetí služby z JČS (§24)", False, False),
    ("Řádek 10", "Přijetí služby (21 %) – základ", False, False),
    ("Řádek 11", "Přijetí služby (12 %) – základ", False, False),
    ("Řádek 43", "DPH základ (21 %)", False, False),
    ("Řádek 44", "DPH (21 % z ř. 43)", False, False),
    ("Řádek 47", "DPH základ (12 %)", False, False),
    ("Řádek 48", "DPH (12 % z ř. 47)", False, False),
    ("Řádek 62", "Celková daň", True, False),
    ("Řádek 64", "Odpočet (identifikovaná osoba = 0)", True, False),
    ("Řádek 66", "Vlastní daňová povinnost", True, True),
]

_EPO_ATTRS = [
    "radek_7_zbozi_jcs",
    "radek_9_sluzby_jcs",
    "radek_10_sluzby_21",
    "radek_11_sluzby_12",
    "radek_43_zaklad_21",
    "radek_44_dph_21",
    "radek_47_zaklad_12",
    "radek_48_dph_12",
    "radek_62_celkova_dan",
    "radek_64_odpocet",
    "radek_66_dan_povinnost",
]


def _render_epo_table(priznani: DphPriznaniRadky) -> str:
    rows = []
    for (cislo, popis, vzdy_zobrazit, je_66), attr in zip(
        _EPO_LABELS, _EPO_ATTRS, strict=True,
    ):
        money = getattr(priznani, attr)
        if not vzdy_zobrazit and money.is_zero:
            continue
        cls = ' class="row-66"' if je_66 else ""
        rows.append(
            f"<tr{cls}><td>{cislo}</td><td>{popis}</td>"
            f"<td class='num'>{_fmt_kc(money)}</td>"
            f"<td class='num'>{_kc_celé(money)}</td></tr>"
        )
    return f"""
    <h2>Řádky přiznání (formulář EPO)</h2>
    <table>
        <thead>
            <tr>
                <th style="width: 12%">Řádek</th>
                <th>Popis</th>
                <th style="width: 18%; text-align: right">Částka (Kč)</th>
                <th style="width: 12%; text-align: right">Celé Kč</th>
            </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
    </table>
    """


def _render_transakce_table(transakce: list[DphTransakceItem]) -> str:
    if not transakce:
        return ""
    rows = []
    zaklad_total = Money.zero()
    dph_total = Money.zero()
    for t in transakce:
        sazba_str = f"{int(t.sazba)} %"
        rows.append(
            f"<tr>"
            f"<td>{_format_date(t.doklad_datum)}</td>"
            f"<td>{t.doklad_cislo}</td>"
            f"<td>{(t.partner_nazev or '—')}</td>"
            f"<td class='num'>{_fmt_kc(t.zaklad)}</td>"
            f"<td class='num'>{_fmt_kc(t.dph)}</td>"
            f"<td class='right'>{sazba_str}</td>"
            f"</tr>"
        )
        zaklad_total = zaklad_total + t.zaklad
        dph_total = dph_total + t.dph
    rows.append(
        f"<tr class='celkem'>"
        f"<td colspan='3'>CELKEM</td>"
        f"<td class='num'>{_fmt_kc(zaklad_total)}</td>"
        f"<td class='num'>{_fmt_kc(dph_total)}</td>"
        f"<td></td>"
        f"</tr>"
    )
    return f"""
    <h2>Reverse charge transakce</h2>
    <table>
        <thead>
            <tr>
                <th style="width: 12%">Datum</th>
                <th style="width: 16%">Doklad</th>
                <th>Partner</th>
                <th style="width: 14%; text-align: right">Základ</th>
                <th style="width: 14%; text-align: right">DPH</th>
                <th style="width: 8%">Sazba</th>
            </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
    </table>
    """


def _render_mesic(
    firma: Firma | None,
    rok: int,
    mesic: int,
    mesic_item: DphMesicItem,
    transakce: list[DphTransakceItem],
    priznani: DphPriznaniRadky,
    datum_sestaveni: date,
) -> str:
    return f"""
    <section class="mesic">
        {_render_firma_header(firma)}
        <h1>DPH přiznání — {_MESICE_CZ[mesic]} {rok}</h1>
        <div class="subtitle">
            Identifikovaná osoba dle §6g zákona o DPH — reverse charge
        </div>
        {_render_metadata(rok, mesic, mesic_item, datum_sestaveni)}
        {_render_epo_table(priznani)}
        {_render_transakce_table(transakce)}
    </section>
    """


class DphExportService:
    """Export DPH přehledu za rozsah měsíců do PDF."""

    def __init__(
        self,
        uow_factory: Callable[[], SqliteUnitOfWork],
        prehled_query: DphPrehledQuery,
        detail_query: DphMesicDetailQuery,
    ) -> None:
        self._uow_factory = uow_factory
        self._prehled = prehled_query
        self._detail = detail_query

    def render_html(
        self,
        rozsah: DphExportRozsah,
        datum_sestaveni: date | None = None,
    ) -> tuple[str, list[tuple[int, int]]]:
        """Sestaví HTML dokument a vrátí ho spolu se seznamem zahrnutých
        (rok, mesic) — měsíce bez RC se vynechají."""
        if datum_sestaveni is None:
            datum_sestaveni = date.today()

        firma = self._load_firma()

        # Cache měsíčních přehledů per rok
        prehled_cache: dict[int, list[DphMesicItem]] = {}
        zahrnute: list[tuple[int, int]] = []
        sections: list[str] = []

        for rok, mesic in rozsah.iter_mesice():
            if rok not in prehled_cache:
                prehled_cache[rok] = self._prehled.execute(rok)
            mesic_item = prehled_cache[rok][mesic - 1]
            if mesic_item.pocet_transakci == 0:
                continue
            transakce = self._detail.execute(rok, mesic)
            priznani = DphPriznaniRadky.from_transakce(rok, mesic, transakce)
            sections.append(_render_mesic(
                firma=firma,
                rok=rok,
                mesic=mesic,
                mesic_item=mesic_item,
                transakce=transakce,
                priznani=priznani,
                datum_sestaveni=datum_sestaveni,
            ))
            zahrnute.append((rok, mesic))

        body = "".join(sections) if sections else (
            '<p style="margin: 80pt 40pt; font-size: 12pt; color: #666;">'
            'V zadaném rozsahu nebyly nalezeny žádné měsíce s reverse '
            'charge plněním.</p>'
        )

        html = f"""<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="utf-8">
    <title>DPH přehled — {rozsah.od_rok}/{rozsah.od_mesic:02d} – {rozsah.do_rok}/{rozsah.do_mesic:02d}</title>
</head>
<body>
{body}
</body>
</html>
"""
        return html, zahrnute

    def export_pdf(
        self,
        rozsah: DphExportRozsah,
        output_path: Path,
        datum_sestaveni: date | None = None,
    ) -> tuple[Path, list[tuple[int, int]]]:
        """Vygeneruje PDF na output_path. Vrátí cestu a zahrnuté měsíce."""
        from weasyprint import CSS as WeasyCSS, HTML

        html, zahrnute = self.render_html(rozsah, datum_sestaveni)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        HTML(string=html).write_pdf(
            target=str(output_path),
            stylesheets=[WeasyCSS(string=_CSS)],
        )
        return output_path, zahrnute

    def _load_firma(self) -> Firma | None:
        try:
            uow = self._uow_factory()
            with uow:
                return SqliteFirmaRepository(uow).get()
        except Exception:  # noqa: BLE001
            return None
