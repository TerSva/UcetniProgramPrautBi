"""PDF export — všechny výkazy do jednoho PDF souboru.

Používá weasyprint (HTML/CSS → PDF). Generuje:
  - Titulní strana (firma, IČO, rok)
  - Rozvaha (aktiva + pasiva)
  - VZZ (druhové členění)
  - Předvaha
  - Hlavní kniha (jen účty s pohybem)
  - Saldokonto
  - DPH přehled
  - Pokladní kniha (jen pokud má pohyb)

Brand teal #134E4A v hlavičkách. Záporné hodnoty červeně.
Zápatí: 'PRAUT s.r.o. | IČO: 22545107 | Vygenerováno DD.MM.YYYY | Strana X/Y'.
"""

from __future__ import annotations

from datetime import date, datetime
from html import escape
from pathlib import Path

from domain.shared.money import Money
from services.queries.vykazy_query import (
    DphPrehled,
    HlavniKnihaUctu,
    PokladniKniha,
    PredvahaRadek,
    RozvahaRadek,
    SaldokontoRadek,
    VykazyQuery,
    VzzRadek,
)


BRAND_TEAL = "#134E4A"
ERROR_RED = "#B91C1C"
GRAY_TEXT = "#374151"
GRAY_BORDER = "#E5E7EB"
GRAY_LIGHT_BG = "#F9FAFB"


CSS = f"""
@page {{
    size: A4;
    margin: 18mm 14mm 22mm 14mm;
    @bottom-center {{
        content: "PRAUT s.r.o. | IČO: 22545107 | Vygenerováno {{date}} | Strana " counter(page) " / " counter(pages);
        font-family: Arial, Helvetica, sans-serif;
        font-size: 9pt;
        color: #6B7280;
    }}
}}

body {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: 10pt;
    color: {GRAY_TEXT};
    line-height: 1.4;
}}

h1.cover-title {{
    font-size: 32pt;
    color: {BRAND_TEAL};
    margin: 0;
    letter-spacing: -0.02em;
}}

.cover {{
    page-break-after: always;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
}}

.cover .firma {{
    font-size: 22pt;
    color: {BRAND_TEAL};
    font-weight: 700;
    margin: 16pt 0 8pt 0;
}}

.cover .meta {{
    font-size: 12pt;
    color: {GRAY_TEXT};
    margin: 4pt 0;
}}

.cover .rok {{
    font-size: 48pt;
    color: {BRAND_TEAL};
    font-weight: 700;
    margin: 32pt 0 8pt 0;
    letter-spacing: -0.04em;
}}

h2.report-title {{
    color: {BRAND_TEAL};
    font-size: 20pt;
    margin: 0 0 6pt 0;
    border-bottom: 2pt solid {BRAND_TEAL};
    padding-bottom: 4pt;
    letter-spacing: -0.01em;
}}

h3.section-title {{
    color: {BRAND_TEAL};
    font-size: 13pt;
    margin: 16pt 0 8pt 0;
}}

.report {{
    page-break-before: always;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin: 6pt 0;
}}

th, td {{
    padding: 4pt 6pt;
    border-bottom: 0.5pt solid {GRAY_BORDER};
    vertical-align: top;
}}

th {{
    background-color: {GRAY_LIGHT_BG};
    color: {BRAND_TEAL};
    font-weight: 600;
    text-align: left;
    font-size: 9.5pt;
}}

td.num, th.num {{
    text-align: right;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}}

tr.bold td, tr.bold th {{
    font-weight: 700;
    background-color: {GRAY_LIGHT_BG};
}}

tr.subheader td {{
    font-weight: 600;
    color: {BRAND_TEAL};
}}

td.negative {{
    color: {ERROR_RED};
}}

.indent-1 {{ padding-left: 16pt; }}
.indent-2 {{ padding-left: 32pt; }}

.summary-box {{
    margin: 12pt 0;
    padding: 8pt 12pt;
    background: {GRAY_LIGHT_BG};
    border-left: 3pt solid {BRAND_TEAL};
    font-size: 10pt;
}}

.empty-note {{
    font-style: italic;
    color: #6B7280;
    margin: 12pt 0;
}}
"""


# ────────────────────────────────────────────────────────────
# Helpers — money formatting
# ────────────────────────────────────────────────────────────

def _money(m: Money) -> str:
    text = escape(m.format_cz())
    cls = "num negative" if m.is_negative else "num"
    return f'<td class="{cls}">{text}</td>'


def _money_bold(m: Money) -> str:
    text = escape(m.format_cz())
    cls = "num negative" if m.is_negative else "num"
    return f'<td class="{cls}"><strong>{text}</strong></td>'


def _format_date(d: date) -> str:
    return f"{d.day:02d}. {d.month:02d}. {d.year}"


# ────────────────────────────────────────────────────────────
# Renderery jednotlivých výkazů
# ────────────────────────────────────────────────────────────

def _render_cover(rok: int, firma_nazev: str, firma_ico: str) -> str:
    today = _format_date(date.today())
    return f"""
    <div class="cover">
        <h1 class="cover-title">Účetní závěrka</h1>
        <div class="firma">{escape(firma_nazev)}</div>
        <div class="meta">IČO: {escape(firma_ico)}</div>
        <div class="rok">{rok}</div>
        <div class="meta">Mikro účetní jednotka</div>
        <div class="meta">Vygenerováno: {today}</div>
    </div>
    """


def _render_rozvaha(
    aktiva: tuple[RozvahaRadek, ...],
    pasiva: tuple[RozvahaRadek, ...],
) -> str:
    a_celkem = next((r.hodnota for r in aktiva if r.kind == "sum_top"), Money.zero())
    p_celkem = next((r.hodnota for r in pasiva if r.kind == "sum_top"), Money.zero())
    bilancuje = a_celkem == p_celkem

    rows_a = _rozvaha_rows_html(aktiva)
    rows_p = _rozvaha_rows_html(pasiva)

    bilance_warning = ""
    if not bilancuje:
        bilance_warning = (
            f'<div class="summary-box" style="border-left-color: {ERROR_RED};">'
            f'<strong>⚠ Rozvaha nebilancuje:</strong> '
            f'Aktiva {escape(a_celkem.format_cz())} ≠ Pasiva {escape(p_celkem.format_cz())}'
            f'</div>'
        )

    return f"""
    <div class="report">
        <h2 class="report-title">Rozvaha</h2>
        <p>Zkrácený rozsah pro mikro účetní jednotku (vyhláška 500/2002 Sb., příloha 1).</p>
        {bilance_warning}

        <h3 class="section-title">Aktiva</h3>
        <table>
            <thead><tr>
                <th style="width: 60pt;">Označení</th>
                <th>Název</th>
                <th class="num" style="width: 90pt;">Běžné období</th>
                <th class="num" style="width: 90pt;">Minulé období</th>
            </tr></thead>
            <tbody>{rows_a}</tbody>
        </table>

        <h3 class="section-title">Pasiva</h3>
        <table>
            <thead><tr>
                <th style="width: 60pt;">Označení</th>
                <th>Název</th>
                <th class="num" style="width: 90pt;">Běžné období</th>
                <th class="num" style="width: 90pt;">Minulé období</th>
            </tr></thead>
            <tbody>{rows_p}</tbody>
        </table>
    </div>
    """


def _rozvaha_rows_html(radky: tuple[RozvahaRadek, ...]) -> str:
    out: list[str] = []
    for r in radky:
        is_sum = r.kind in ("sum_top", "sum_group")
        is_subheader = r.kind == "sum_group"
        cls = ""
        if is_sum:
            cls = "bold"
        elif is_subheader:
            cls = "subheader"

        nazev_cls = ""
        if r.level == 2:
            nazev_cls = "indent-1"

        money_fn = _money_bold if is_sum else _money
        out.append(
            f'<tr class="{cls}">'
            f'<td>{escape(r.oznaceni)}</td>'
            f'<td class="{nazev_cls}">{escape(r.nazev)}</td>'
            f'{money_fn(r.hodnota)}'
            f'{money_fn(r.minule)}'
            f'</tr>'
        )
    return "\n".join(out)


def _render_vzz(radky: tuple[VzzRadek, ...]) -> str:
    oznaceni_map = {
        "*":       "*",
        "**fin":   "*",
        "***pred": "**",
        "**pod":   "**",
        "****":    "***",
    }

    out: list[str] = []
    for r in radky:
        is_sum = r.druh.startswith("sum") or r.druh == "N_group"
        cls = "bold" if is_sum else ""
        display_oznaceni = oznaceni_map.get(r.oznaceni, r.oznaceni)
        nazev_cls = "indent-1" if r.level == 2 else ""
        money_fn = _money_bold if is_sum else _money
        out.append(
            f'<tr class="{cls}">'
            f'<td>{escape(display_oznaceni)}</td>'
            f'<td class="{nazev_cls}">{escape(r.nazev)}</td>'
            f'{money_fn(r.hodnota)}'
            f'{money_fn(r.minule)}'
            f'</tr>'
        )
    rows = "\n".join(out)

    return f"""
    <div class="report">
        <h2 class="report-title">Výkaz zisku a ztráty</h2>
        <p>Druhové členění (vyhláška 500/2002 Sb., příloha 2).</p>
        <table>
            <thead><tr>
                <th style="width: 60pt;">Označení</th>
                <th>Název</th>
                <th class="num" style="width: 90pt;">Běžné období</th>
                <th class="num" style="width: 90pt;">Minulé období</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    """


def _render_predvaha(radky: tuple[PredvahaRadek, ...]) -> str:
    celkem_md = 0
    celkem_dal = 0
    out: list[str] = []
    for r in radky:
        out.append(
            f'<tr>'
            f'<td>{escape(r.ucet)}</td>'
            f'<td>{escape(r.nazev)}</td>'
            f'{_money(r.ps_md)}'
            f'{_money(r.ps_dal)}'
            f'{_money(r.obrat_md)}'
            f'{_money(r.obrat_dal)}'
            f'{_money(r.kz_md)}'
            f'{_money(r.kz_dal)}'
            f'</tr>'
        )
        celkem_md += r.obrat_md.to_halire()
        celkem_dal += r.obrat_dal.to_halire()

    md_total = Money(celkem_md)
    dal_total = Money(celkem_dal)
    bilancuje = celkem_md == celkem_dal
    warning = ""
    if not bilancuje:
        warning = (
            f'<div class="summary-box" style="border-left-color: {ERROR_RED};">'
            f'<strong>⚠ Předvaha nesouhlasí:</strong> MD {escape(md_total.format_cz())} '
            f'≠ Dal {escape(dal_total.format_cz())}'
            f'</div>'
        )

    out.append(
        f'<tr class="bold">'
        f'<td></td><td><strong>CELKEM</strong></td>'
        f'<td></td><td></td>'
        f'{_money_bold(md_total)}{_money_bold(dal_total)}'
        f'<td></td><td></td>'
        f'</tr>'
    )

    rows = "\n".join(out)

    return f"""
    <div class="report">
        <h2 class="report-title">Předvaha</h2>
        <p>Obratová předvaha — všechny účty s pohybem.</p>
        {warning}
        <table>
            <thead><tr>
                <th>Účet</th>
                <th>Název</th>
                <th class="num">PS MD</th>
                <th class="num">PS Dal</th>
                <th class="num">Obrat MD</th>
                <th class="num">Obrat Dal</th>
                <th class="num">KZ MD</th>
                <th class="num">KZ Dal</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    """


def _render_hlavni_kniha(knihy: tuple[HlavniKnihaUctu, ...]) -> str:
    """Vrátí HTML s hlavní knihou — každý účet má vlastní sekci."""
    if not knihy:
        return f"""
        <div class="report">
            <h2 class="report-title">Hlavní kniha</h2>
            <p class="empty-note">Žádné účty s pohybem v daném roce.</p>
        </div>
        """

    sections: list[str] = []
    for k in knihy:
        rows: list[str] = []
        for r in k.radky:
            md_html = _money(r.md) if r.md.is_positive else '<td class="num"></td>'
            dal_html = _money(r.dal) if r.dal.is_positive else '<td class="num"></td>'
            rows.append(
                f'<tr>'
                f'<td>{_format_date(r.datum)}</td>'
                f'<td>{escape(r.cislo_dokladu)}</td>'
                f'<td>{escape(r.popis or "")}</td>'
                f'{md_html}{dal_html}'
                f'{_money(r.zustatek)}'
                f'</tr>'
            )
        rows.append(
            f'<tr class="bold">'
            f'<td></td><td></td><td><strong>CELKEM</strong></td>'
            f'{_money_bold(k.obrat_md)}{_money_bold(k.obrat_dal)}'
            f'{_money_bold(k.koncovy_zustatek)}'
            f'</tr>'
        )
        rows_html = "\n".join(rows)

        sections.append(f"""
            <h3 class="section-title">{escape(k.ucet)} — {escape(k.nazev)}</h3>
            <div class="summary-box">
                Počáteční stav: <strong>{escape(k.pocatecni_stav.format_cz())}</strong>
                &nbsp;&nbsp; Konečný zůstatek: <strong>{escape(k.koncovy_zustatek.format_cz())}</strong>
            </div>
            <table>
                <thead><tr>
                    <th style="width: 60pt;">Datum</th>
                    <th style="width: 80pt;">Doklad</th>
                    <th>Popis</th>
                    <th class="num" style="width: 70pt;">MD</th>
                    <th class="num" style="width: 70pt;">Dal</th>
                    <th class="num" style="width: 80pt;">Zůstatek</th>
                </tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
        """)

    return f"""
    <div class="report">
        <h2 class="report-title">Hlavní kniha</h2>
        {''.join(sections)}
    </div>
    """


def _render_saldokonto(
    zavazky: tuple[SaldokontoRadek, ...],
    pohledavky: tuple[SaldokontoRadek, ...],
) -> str:
    def _rows(radky: tuple[SaldokontoRadek, ...]) -> str:
        if not radky:
            return f'<tr><td colspan="6" class="empty-note">Žádné neuhrazené doklady.</td></tr>'
        out: list[str] = []
        celkem = 0
        for r in radky:
            out.append(
                f'<tr>'
                f'<td>{escape(r.cislo_dokladu)}</td>'
                f'<td>{escape(r.partner_nazev or "—")}</td>'
                f'<td>{_format_date(r.datum)}</td>'
                f'{_money(r.castka)}'
                f'{_money(r.uhrazeno)}'
                f'{_money(r.zbyva)}'
                f'</tr>'
            )
            celkem += r.zbyva.to_halire()
        out.append(
            f'<tr class="bold"><td colspan="5"><strong>CELKEM</strong></td>'
            f'{_money_bold(Money(celkem))}</tr>'
        )
        return "\n".join(out)

    headers = """
        <tr>
            <th>Doklad</th>
            <th>Partner</th>
            <th>Datum</th>
            <th class="num">Částka</th>
            <th class="num">Uhrazeno</th>
            <th class="num">Zbývá</th>
        </tr>
    """

    return f"""
    <div class="report">
        <h2 class="report-title">Saldokonto</h2>
        <p>Neuhrazené nebo částečně uhrazené pohledávky a závazky.</p>

        <h3 class="section-title">Závazky (FP)</h3>
        <table>
            <thead>{headers}</thead>
            <tbody>{_rows(zavazky)}</tbody>
        </table>

        <h3 class="section-title">Pohledávky (FV)</h3>
        <table>
            <thead>{headers}</thead>
            <tbody>{_rows(pohledavky)}</tbody>
        </table>
    </div>
    """


def _render_dph(prehled: DphPrehled) -> str:
    summary = f"""
    <table>
        <tbody>
            <tr><td>DPH na vstupu (343.100)</td>{_money(prehled.vstup_celkem)}</tr>
            <tr><td class="indent-1">z toho reverse charge</td>{_money(prehled.vstup_rc)}</tr>
            <tr><td>DPH na výstupu (343.200)</td>{_money(prehled.vystup_celkem)}</tr>
            <tr><td class="indent-1">z toho reverse charge</td>{_money(prehled.vystup_rc)}</tr>
            <tr class="bold"><td><strong>DPH k úhradě (výstup − vstup)</strong></td>{_money_bold(prehled.k_uhrade)}</tr>
        </tbody>
    </table>
    """

    if prehled.doklady:
        rows: list[str] = []
        for d in prehled.doklady:
            rezim = "RC" if d.rezim == "REVERSE_CHARGE" else "Tuzemsko"
            rows.append(
                f'<tr>'
                f'<td>{_format_date(d.datum)}</td>'
                f'<td>{escape(d.cislo_dokladu)}</td>'
                f'<td>{escape(d.partner_nazev or "—")}</td>'
                f'{_money(d.zaklad)}'
                f'{_money(d.dph)}'
                f'<td>{rezim}</td>'
                f'</tr>'
            )
        doklady_html = f"""
        <h3 class="section-title">Detail dokladů s DPH</h3>
        <table>
            <thead><tr>
                <th>Datum</th>
                <th>Doklad</th>
                <th>Partner</th>
                <th class="num">Základ</th>
                <th class="num">DPH</th>
                <th>Režim</th>
            </tr></thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
        """
    else:
        doklady_html = '<p class="empty-note">Žádné doklady s DPH za zvolené období.</p>'

    obdobi = f"{_format_date(prehled.obdobi_od)} – {_format_date(prehled.obdobi_do)}"

    return f"""
    <div class="report">
        <h2 class="report-title">DPH přehled</h2>
        <p>Období: {obdobi}</p>
        {summary}
        {doklady_html}
    </div>
    """


def _render_pokladna(kniha: PokladniKniha) -> str:
    if not kniha.pouzita:
        return f"""
        <div class="report">
            <h2 class="report-title">Pokladní kniha</h2>
            <p class="empty-note">Pokladna nebyla v roce {kniha.rok} používána.</p>
        </div>
        """

    rows: list[str] = []
    for r in kniha.radky:
        prijem = _money(r.md) if r.md.is_positive else '<td class="num"></td>'
        vydaj = _money(r.dal) if r.dal.is_positive else '<td class="num"></td>'
        rows.append(
            f'<tr>'
            f'<td>{_format_date(r.datum)}</td>'
            f'<td>{escape(r.cislo_dokladu)}</td>'
            f'<td>{escape(r.popis or "")}</td>'
            f'{prijem}{vydaj}'
            f'{_money(r.zustatek)}'
            f'</tr>'
        )
    rows_html = "\n".join(rows)

    return f"""
    <div class="report">
        <h2 class="report-title">Pokladní kniha</h2>
        <div class="summary-box">
            Počáteční stav: <strong>{escape(kniha.pocatecni_stav.format_cz())}</strong>
            &nbsp;&nbsp; Konečný stav: <strong>{escape(kniha.koncovy_stav.format_cz())}</strong>
        </div>
        <table>
            <thead><tr>
                <th style="width: 60pt;">Datum</th>
                <th style="width: 80pt;">Doklad</th>
                <th>Popis</th>
                <th class="num" style="width: 70pt;">Příjem</th>
                <th class="num" style="width: 70pt;">Výdaj</th>
                <th class="num" style="width: 80pt;">Zůstatek</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """


# ────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────

def export_vykazy_pdf(
    vykazy_query: VykazyQuery,
    rok: int,
    output_path: Path,
    firma_nazev: str = "PRAUT s.r.o.",
    firma_ico: str = "22545107",
) -> Path:
    """Vygeneruje kompletní PDF se všemi výkazy.

    Args:
        vykazy_query: query služba
        rok: účetní rok
        output_path: cílová cesta (přepíše existující)
        firma_nazev: název firmy do hlavičky
        firma_ico: IČO do zápatí

    Returns:
        Cesta k vytvořenému PDF.
    """
    from weasyprint import CSS as WeasyCSS, HTML

    aktiva, pasiva = vykazy_query.get_rozvaha(rok)
    vzz = vykazy_query.get_vzz(rok)
    predvaha = vykazy_query.get_predvaha(rok, jen_s_pohybem=True)
    saldo_zavazky, saldo_pohledavky = vykazy_query.get_saldokonto(rok)
    dph = vykazy_query.get_dph_prehled(rok)
    pokladna = vykazy_query.get_pokladni_kniha(rok)

    ucty_s_pohybem = vykazy_query.get_ucty_s_pohybem(rok)
    knihy = tuple(
        vykazy_query.get_hlavni_kniha(cislo, rok) for cislo, _nazev in ucty_s_pohybem
    )

    body_parts = [
        _render_cover(rok, firma_nazev, firma_ico),
        _render_rozvaha(aktiva, pasiva),
        _render_vzz(vzz),
        _render_predvaha(predvaha),
        _render_hlavni_kniha(knihy),
        _render_saldokonto(saldo_zavazky, saldo_pohledavky),
        _render_dph(dph),
        _render_pokladna(pokladna),
    ]

    today_str = _format_date(date.today())
    css_text = CSS.replace("{date}", today_str)

    html_doc = f"""<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="utf-8">
    <title>Účetní závěrka {rok}</title>
</head>
<body>
    {''.join(body_parts)}
</body>
</html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_doc).write_pdf(
        target=str(output_path),
        stylesheets=[WeasyCSS(string=css_text)],
    )
    return output_path
