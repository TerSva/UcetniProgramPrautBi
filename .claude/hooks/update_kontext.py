"""update_kontext.py — auto-update PRAUT_kontext.md po každém git commitu.

Aktualizuje JEN sekce mezi <!-- AUTO_START:nazev --> a <!-- AUTO_END:nazev -->.
Manuální sekce <!-- MANUAL_START:nazev --> ... <!-- MANUAL_END:nazev --> NIKDY
nepřepíše.

Spouští se z .git/hooks/post-commit, lze spustit i ručně:

    .venv/bin/python .claude/hooks/update_kontext.py

Pravidla:
- Schema: ucetni_zaznamy(md_ucet, dal_ucet, castka), doklady.datum_vystaveni
- Pokud VykazyQuery selže → ⚠️ hláška v sekci, ostatní sekce pokračují
- Filter uncommitted změn: jen *.py, *.md, *.sql, *.html, *.css, *.js
- TODO se extrahuje z ROADMAP.md (- [ ] items) + funkční mezery z §9.1
  v PRAUT_program.md
"""

from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "ucetni.db"
KONTEXT_PATH = REPO_ROOT / "PRAUT_kontext.md"
ROADMAP_PATH = REPO_ROOT / "ROADMAP.md"
PROGRAM_PATH = REPO_ROOT / "PRAUT_program.md"

# Aktuální účetní rok (pro výpočty Rozvahy / VZZ / DPH zůstatků)
ROK_BEZNY = 2026
ROK_MINULY = 2025

# Filter relevantních přípon pro uncommitted změny
REL_EXTS = {".py", ".md", ".sql", ".html", ".css", ".js"}


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(
        cmd, cwd=str(REPO_ROOT), stderr=subprocess.DEVNULL,
    ).decode().strip()


def get_git_info() -> dict:
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    last_commit = _run(["git", "log", "-1", "--format=%h %s"])
    commits_7d = _run(["git", "rev-list", "--count", "--since=7.days", "HEAD"])
    last_5 = _run([
        "git", "log", "-5", "--format=- %h (%ad) %s", "--date=short",
    ])

    status = _run(["git", "status", "--porcelain"])
    uncommitted_rel = 0
    if status:
        for line in status.splitlines():
            # Format: "XY filename"
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                fname = parts[1]
                if Path(fname).suffix in REL_EXTS:
                    uncommitted_rel += 1

    return {
        "branch": branch,
        "last_commit": last_commit,
        "commits_7d": commits_7d,
        "last_5": last_5,
        "uncommitted_rel": uncommitted_rel,
    }


def get_ucetni_stav_via_vykazy() -> str:
    """Spočítá účetní stav přes VykazyQuery. Při chybě vrátí ⚠️ hlášku."""
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from infrastructure.database.connection import ConnectionFactory
        from infrastructure.database.unit_of_work import SqliteUnitOfWork
        from services.queries.vykazy_query import VykazyQuery

        factory = ConnectionFactory(DB_PATH)
        vq = VykazyQuery(lambda: SqliteUnitOfWork(factory))

        # Rok minulý — uzavřeno?
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM doklady "
            "WHERE cislo IN (?, ?, ?)",
            (f"ID-{ROK_MINULY}-Z1", f"ID-{ROK_MINULY}-Z2", f"ID-{ROK_MINULY}-Z3"),
        )
        uzavreno = cur.fetchone()[0] == 3

        cur.execute(
            "SELECT COUNT(*) FROM doklady WHERE datum_vystaveni LIKE ?",
            (f"{ROK_MINULY}%",),
        )
        d_minuly = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM doklady WHERE datum_vystaveni LIKE ?",
            (f"{ROK_BEZNY}%",),
        )
        d_bezny = cur.fetchone()[0]
        conn.close()

        # VH minulého roku z VZZ (před uzávěrkou — default vcetne_zaverky=False)
        data_minuly = vq._nacti_obraty_a_ps(ROK_MINULY, vcetne_zaverky=False)
        vh_minuly = sum(
            d["obrat_dal"] - d["obrat_md"]
            for d in data_minuly.values() if d["typ"] == "V"
        ) - sum(
            d["obrat_md"] - d["obrat_dal"]
            for d in data_minuly.values() if d["typ"] == "N"
        )

        # Bilance běžného roku
        a_bezny, p_bezny = vq.get_bilancni_kontrola(ROK_BEZNY)
        bilance_ok = a_bezny == p_bezny

        # Saldo 343.200 a 426.100 v běžném roce
        def _saldo(ucet: str, typ: str) -> int:
            d = vq._nacti_obraty_a_ps(ROK_BEZNY).get(ucet, {})
            md = d.get("ps_md", 0) + d.get("obrat_md", 0)
            dal = d.get("ps_dal", 0) + d.get("obrat_dal", 0)
            return (dal - md) if typ == "P" else (md - dal)

        s_343 = _saldo("343.200", "P")
        s_426 = _saldo("426.100", "P")

        # VH minulých let (saldo 431.100 v rozvaze 2026 jako pasivum)
        s_431 = _saldo("431.100", "P")

        def _kc(halire: int) -> str:
            """Formát Kč po česku: '-415 626,75 Kč'."""
            znak = "-" if halire < 0 else ""
            abs_h = abs(halire)
            kc = abs_h // 100
            hal = abs_h % 100
            # tisíce s mezerou
            kc_str = f"{kc:,}".replace(",", " ")
            return f"{znak}{kc_str},{hal:02d} Kč"

        sekce = [
            f"### Rok {ROK_MINULY}",
            f"- Doklady: **{d_minuly}**",
            f"- Účetně uzavřen (Z1/Z2/Z3): **{'ANO' if uzavreno else 'NE'}**",
            f"- VH: **{_kc(vh_minuly)}**",
            "",
            f"### Rok {ROK_BEZNY}",
            f"- Doklady: **{d_bezny}**",
            f"- Bilance: A={a_bezny.format_cz()}, P={p_bezny.format_cz()}"
            f"  {'✅' if bilance_ok else '⚠️ NEBILANCUJE'}",
            f"- VH minulých let (431.100 saldo): **{_kc(s_431)}**",
            f"- 343.200 (DPH závazek): **{_kc(s_343)}**",
            f"- 426.100 (oprava chyb min. let): **{_kc(s_426)}**",
        ]
        return "\n".join(sekce)
    except Exception as exc:  # noqa: BLE001
        return (
            f"⚠️ VykazyQuery selhala: `{type(exc).__name__}: {exc}`\n\n"
            f"K doplnění ručně z `VykazyQuery.get_rozvaha({ROK_BEZNY})` a "
            f"`get_vzz({ROK_MINULY})`."
        )


def get_todo() -> str:
    """Funkční mezery z PRAUT_program.md §9.1 + architektonické - [ ] z ROADMAP.md."""
    parts: list[str] = []

    # Funkční mezery — pevný seznam z PRAUT_program.md §9.1 (statický
    # protože sekce 9.1 nemá strojově čitelný formát; aktualizovat ručně
    # pokud se §9.1 změní)
    parts.append("### Funkční mezery (z PRAUT_program.md §9.1)")
    parts.append("- Mzdový modul — placeholder bez logiky (firma nemá zaměstnance)")
    parts.append("- Majetek + odpisy — placeholder (firma nemá DHM)")
    parts.append("- Kontrolní hlášení (KH) — info-only (identif. osoba ho nepodává)")
    parts.append("- EPO XML export — pouze textový clipboard")
    parts.append("- DPH dodatečná přiznání + dph_podani tabulka prázdná")
    parts.append("- Opravné položky, rezervy, časové rozlišení")
    parts.append("- ARES integrace — entity existuje, klient k ověření")
    parts.append("")

    # Architektonické TODO — extrakce - [ ] z ROADMAP.md
    parts.append("### Architektonické (- [ ] z ROADMAP.md)")
    if ROADMAP_PATH.exists():
        roadmap = ROADMAP_PATH.read_text(encoding="utf-8").splitlines()
        items = [line for line in roadmap if re.match(r"^\s*- \[ \]", line)]
        if items:
            parts.extend(items)
        else:
            parts.append("(žádné - [ ] položky v ROADMAP.md)")
    else:
        parts.append("(ROADMAP.md nenalezen)")

    return "\n".join(parts)


def get_db_info() -> str:
    size_kb = DB_PATH.stat().st_size // 1024

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    try:
        cur.execute("SELECT MAX(version) FROM schema_migrations")
        last_migration = cur.fetchone()[0] or "neznámá"
    except sqlite3.OperationalError:
        last_migration = "tabulka neexistuje"

    cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
    tables_count = cur.fetchone()[0]
    conn.close()

    backups = sorted(
        REPO_ROOT.glob("ucetni.db.backup_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:3]
    backup_lines = (
        "\n".join(f"- {b.name} ({b.stat().st_size // 1024} KB)" for b in backups)
        if backups else "- žádné zálohy"
    )

    return (
        f"**Cesta:** ucetni.db\n"
        f"**Velikost:** {size_kb} KB\n"
        f"**Poslední migrace:** {last_migration}\n"
        f"**Tabulek:** {tables_count}\n\n"
        f"### Poslední 3 zálohy\n{backup_lines}"
    )


def get_tests_info() -> str:
    """Statický placeholder — auto-spouštět testy by trvalo desítky vteřin."""
    return (
        "**Poslední run:** auto-nepouštěno (commit hook)\n"
        "**Pro nový run:** `.venv/bin/python -m pytest --ignore=tests/ui -q`\n"
        "**Známé failures:** `tests/services/banka/test_validator.py::"
        "TestCsvPdfValidator::test_pdf_errors_propagated` (pre-existing, "
        "commit 43c1933 — viz ROADMAP TODO)"
    )


# ───────────────────────────────────────────────────────────
# I/O — render + replace
# ───────────────────────────────────────────────────────────

def update_section(text: str, name: str, new_content: str) -> str:
    """Nahradí obsah mezi AUTO_START:name a AUTO_END:name."""
    pattern = (
        rf"(<!-- AUTO_START:{re.escape(name)} -->\n).*?"
        rf"(\n<!-- AUTO_END:{re.escape(name)} -->)"
    )
    replacement = rf"\g<1>{new_content}\g<2>"
    return re.sub(pattern, replacement, text, flags=re.DOTALL)


def main() -> int:
    if not KONTEXT_PATH.exists():
        print(f"❌ {KONTEXT_PATH} neexistuje. Vytvoř ho ručně z template.")
        return 1

    text = KONTEXT_PATH.read_text(encoding="utf-8")

    # git
    git = get_git_info()
    git_section = (
        f"**Branch:** {git['branch']}\n"
        f"**Poslední commit:** {git['last_commit']}\n"
        f"**Commitů za posledních 7 dní:** {git['commits_7d']}\n"
        f"**Uncommitted relevantní soubory** (.py/.md/.sql/...): "
        f"{git['uncommitted_rel']}\n\n"
        f"### Posledních 5 commitů\n{git['last_5']}"
    )
    text = update_section(text, "git", git_section)

    # ucetni_stav (přes VykazyQuery)
    ucetni = get_ucetni_stav_via_vykazy()
    text = update_section(text, "ucetni_stav", ucetni)

    # todo
    text = update_section(text, "todo", get_todo())

    # db
    text = update_section(text, "db", get_db_info())

    # tests
    text = update_section(text, "tests", get_tests_info())

    # timestamp v záhlaví
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    last_hash = git["last_commit"].split()[0]
    text = re.sub(
        r"Naposledy aktualizováno: .+",
        f"Naposledy aktualizováno: {now} (commit {last_hash})",
        text,
        count=1,
    )

    KONTEXT_PATH.write_text(text, encoding="utf-8")
    print(f"✅ PRAUT_kontext.md aktualizován ({now}, commit {last_hash})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
