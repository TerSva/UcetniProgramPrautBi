"""QSS stylesheet builder — jediné místo, kde se sestavuje Qt stylesheet.

Všechny hodnoty pocházejí z ui.design_tokens. Žádné hex literály zde
nesmějí být — pokud chybí token, přidej ho do design_tokens.py a použij odtud.

Stylesheet se aplikuje globálně v ui.app.run() přes QApplication.setStyleSheet().
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ui.design_tokens import (
    Borders,
    Colors,
    Fonts,
    Radius,
    Spacing,
    Surfaces,
)

_ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


def _materialize_colored_icon(name: str, color: str) -> str:
    """Přebarvi Lucide SVG ikonu (currentColor → hex) a vrať posix path.

    Qt stylesheet `image: url(...)` neumí `currentColor`, takže si
    colored variantu vyrenderujeme do tempfile při buildu stylesheetu.
    """
    svg_text = (_ICONS_DIR / f"{name}.svg").read_text(encoding="utf-8")
    svg_text = svg_text.replace("currentColor", color)

    cache_dir = Path(tempfile.gettempdir()) / "ucetni-program-qss-icons"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{name}_{color.lstrip('#')}.svg"
    out.write_text(svg_text, encoding="utf-8")
    return out.as_posix()


def build_stylesheet() -> str:
    """Sestav kompletní QSS řetězec z design tokenů.

    Návratová hodnota je připravena k předání do QApplication.setStyleSheet().
    """
    chevron_path = _materialize_colored_icon("chevron-down", Colors.GRAY_500)
    return f"""
/* ═══════════════════════════════════════════════════════════
   GLOBAL — base typografie a barvy
   ═══════════════════════════════════════════════════════════ */

QWidget {{
    background: {Surfaces.PAGE};
    color: {Colors.GRAY_900};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_BASE}px;
}}

/* ═══════════════════════════════════════════════════════════
   MAIN WINDOW — root kontejner
   ═══════════════════════════════════════════════════════════ */

QMainWindow {{
    background: {Surfaces.PAGE};
}}

/* ═══════════════════════════════════════════════════════════
   SIDEBAR — tmavě teal navigační panel vlevo
   ═══════════════════════════════════════════════════════════ */

QWidget#Sidebar {{
    background: {Surfaces.SIDEBAR};
    border: none;
}}

QLabel#SidebarLogo {{
    color: {Colors.WHITE};
    font-family: {Fonts.HEADING_STACK};
    font-size: {Fonts.SIZE_XL}px;
    font-weight: {Fonts.WEIGHT_BOLD};
    padding: {Spacing.S6}px {Spacing.S5}px {Spacing.S4}px {Spacing.S5}px;
    background: transparent;
}}

QLabel[class="sidebar-section"] {{
    color: rgba(255, 255, 255, 0.5);
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_XS}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    padding: {Spacing.S4}px {Spacing.S5}px {Spacing.S1}px {Spacing.S5}px;
    background: transparent;
}}

QPushButton[class="sidebar-item"] {{
    color: rgba(255, 255, 255, 0.85);
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    padding: {Spacing.S2}px {Spacing.S4}px {Spacing.S2}px {Spacing.S4}px;
    text-align: left;
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_BASE}px;
    font-weight: {Fonts.WEIGHT_MEDIUM};
    min-height: 32px;
}}

QPushButton[class="sidebar-item"]:hover {{
    background: {Surfaces.SIDEBAR_HOVER};
    color: {Colors.WHITE};
}}

QPushButton[class="sidebar-item"]:disabled {{
    color: rgba(255, 255, 255, 0.35);
    background: transparent;
}}

QPushButton[class="sidebar-item"][active="true"] {{
    border-left: 3px solid {Colors.ACCENT_400};
    background: rgba(255, 255, 255, 0.12);
    color: {Colors.WHITE};
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
}}

/* ═══════════════════════════════════════════════════════════
   PAGES — placeholder stránky (dashboard, doklady, nastavení)
   ═══════════════════════════════════════════════════════════ */

QWidget[class="page"] {{
    background: {Surfaces.PAGE};
}}

QLabel[class="page-title"] {{
    color: {Colors.BRAND};
    font-family: {Fonts.HEADING_STACK};
    font-size: {Fonts.SIZE_3XL}px;
    font-weight: {Fonts.WEIGHT_BOLD};
    background: transparent;
    padding: 0;
}}

QLabel[class="page-subtitle"] {{
    color: {Colors.GRAY_500};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_BASE}px;
    font-weight: {Fonts.WEIGHT_REGULAR};
    background: transparent;
    padding: 0;
}}

QLabel[class="page-date"] {{
    color: {Colors.GRAY_500};
    font-family: "{Fonts.BODY}";
    font-size: {Fonts.SIZE_BASE}px;
    font-weight: {Fonts.WEIGHT_MEDIUM};
    background: transparent;
    padding-top: 8px;
}}

/* ═══════════════════════════════════════════════════════════
   KPI CARD — kartička pro KPI hodnotu na Dashboardu
   ═══════════════════════════════════════════════════════════ */

QFrame[class="kpi-card"] {{
    background: {Surfaces.CARD};
    border: 1px solid {Borders.DEFAULT};
    border-radius: {Radius.LG}px;
}}

QFrame[class="kpi-card"][positive="true"] {{
    border: 1px solid {Colors.PRIMARY_200};
    background: {Colors.PRIMARY_25};
}}

QFrame[class="kpi-card"][clickable="true"]:hover {{
    border: 1px solid {Colors.BRAND};
    background: {Surfaces.HOVER};
}}

QLabel[class="kpi-label"] {{
    color: {Colors.GRAY_500};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_XS}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    background: transparent;
    padding: 0;
}}

QLabel[class="kpi-value"] {{
    color: {Colors.BRAND};
    font-family: {Fonts.HEADING_STACK};
    font-size: {Fonts.SIZE_2XL}px;
    font-weight: {Fonts.WEIGHT_BOLD};
    background: transparent;
    padding: 0;
}}

QLabel[class="kpi-value"][positive="true"] {{
    color: {Colors.SUCCESS_700};
}}

QLabel[class="kpi-subtitle"] {{
    color: {Colors.GRAY_500};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_REGULAR};
    background: transparent;
    padding: 0;
}}

QLabel[class="kpi-subtitle"][clickable="true"] {{
    color: {Colors.BRAND};
    font-weight: {Fonts.WEIGHT_MEDIUM};
    text-decoration: underline;
}}

/* ═══════════════════════════════════════════════════════════
   ERROR TEXT — chybové hlášení (např. načítání Dashboard)
   ═══════════════════════════════════════════════════════════ */

QLabel[class="error-text"] {{
    color: {Colors.ERROR_700};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_BASE}px;
    font-weight: {Fonts.WEIGHT_MEDIUM};
    background: {Colors.ERROR_50};
    border: 1px solid {Colors.ERROR_500};
    border-radius: {Radius.MD}px;
    padding: {Spacing.S3}px {Spacing.S4}px;
}}

/* ═══════════════════════════════════════════════════════════
   BADGES — barevný pill (Typ, Stav, atd.)
   ═══════════════════════════════════════════════════════════ */

QLabel[class="badge"] {{
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_XS}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    border-radius: {Radius.SM}px;
    padding: 2px 8px;
    min-height: 18px;
}}

QLabel[class="badge"][variant="neutral"] {{
    background: {Colors.GRAY_100};
    color: {Colors.GRAY_700};
}}

QLabel[class="badge"][variant="primary"] {{
    background: {Colors.PRIMARY_50};
    color: {Colors.PRIMARY_700};
}}

QLabel[class="badge"][variant="success"] {{
    background: {Colors.SUCCESS_50};
    color: {Colors.SUCCESS_700};
}}

QLabel[class="badge"][variant="warning"] {{
    background: {Colors.WARNING_50};
    color: {Colors.WARNING_700};
}}

QLabel[class="badge"][variant="error"] {{
    background: {Colors.ERROR_50};
    color: {Colors.ERROR_700};
}}

QLabel[class="badge"][variant="info"] {{
    background: {Colors.INFO_50};
    color: {Colors.INFO_700};
}}

/* ═══════════════════════════════════════════════════════════
   FILTER BAR — řádek s dropdowny nad tabulkou dokladů
   ═══════════════════════════════════════════════════════════ */

QWidget#FilterBar {{
    background: {Surfaces.CARD};
    border: 1px solid {Borders.DEFAULT};
    border-radius: {Radius.MD}px;
}}

QWidget#FilterBar[active="true"] {{
    border: 1px solid {Colors.INFO_700};
    background: {Colors.INFO_50};
}}

QLabel[class="filter-active-indicator"] {{
    color: {Colors.INFO_700};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_XS}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    background: {Colors.INFO_50};
    border: 1px solid {Colors.INFO_700};
    border-radius: {Radius.SM}px;
    padding: 2px 8px;
}}

QLabel[class="filter-label"] {{
    color: {Colors.GRAY_500};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_XS}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    background: transparent;
    padding: 0;
}}

QWidget#FilterBar QComboBox {{
    background: {Surfaces.CARD};
    color: {Colors.GRAY_900};
    border: 1px solid {Borders.DEFAULT};
    border-radius: {Radius.SM}px;
    padding: 4px 28px 4px 8px;
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    min-height: 28px;
    min-width: 140px;
}}

QWidget#FilterBar QComboBox:hover {{
    border: 1px solid {Borders.STRONG};
}}

QWidget#FilterBar QComboBox:focus {{
    border: 1px solid {Borders.FOCUS};
}}

QWidget#FilterBar QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    border: none;
    background: transparent;
    width: 24px;
}}

QWidget#FilterBar QComboBox::down-arrow {{
    image: url({chevron_path});
    width: 14px;
    height: 14px;
}}

QComboBox QAbstractItemView {{
    background: {Surfaces.CARD};
    border: 1px solid {Borders.DEFAULT};
    border-radius: {Radius.MD}px;
    selection-background-color: {Surfaces.SELECTED};
    selection-color: {Colors.BRAND};
    padding: 4px;
    outline: 0;
}}

/* ═══════════════════════════════════════════════════════════
   PRIMARY / SECONDARY BUTTON
   ═══════════════════════════════════════════════════════════ */

QPushButton[class="primary"] {{
    background: {Colors.BRAND};
    color: {Colors.WHITE};
    border: none;
    border-radius: {Radius.SM}px;
    padding: 8px 16px;
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    min-height: 32px;
}}

QPushButton[class="primary"]:hover {{
    background: {Colors.BRAND_HOVER};
}}

QPushButton[class="primary"]:disabled {{
    background: {Colors.GRAY_200};
    color: {Colors.GRAY_500};
}}

QPushButton[class="secondary"] {{
    background: {Surfaces.CARD};
    color: {Colors.BRAND};
    border: 1px solid {Borders.DEFAULT};
    border-radius: {Radius.SM}px;
    padding: 6px 12px;
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_MEDIUM};
    min-height: 28px;
}}

QPushButton[class="secondary"]:hover {{
    background: {Surfaces.HOVER};
    border: 1px solid {Borders.STRONG};
}}

QPushButton[class="secondary"]:disabled {{
    background: {Colors.GRAY_200};
    color: {Colors.GRAY_500};
    border: 1px solid {Borders.SUBTLE};
}}

/* ═══════════════════════════════════════════════════════════
   DOKLADY TABLE — read-only seznam dokladů
   ═══════════════════════════════════════════════════════════ */

QTableView[class="doklady-table"] {{
    background: {Surfaces.CARD};
    alternate-background-color: {Colors.GRAY_50};
    border: 1px solid {Borders.DEFAULT};
    border-radius: {Radius.MD}px;
    gridline-color: transparent;
    selection-background-color: {Surfaces.SELECTED};
    selection-color: {Colors.BRAND};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    color: {Colors.GRAY_900};
}}

QTableView[class="doklady-table"]::item {{
    padding: 6px 8px;
    border: none;
}}

QTableView[class="doklady-table"] QHeaderView::section {{
    background: {Colors.GRAY_50};
    color: {Colors.GRAY_500};
    border: none;
    border-bottom: 1px solid {Borders.DEFAULT};
    padding: 8px 8px;
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_XS}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    text-transform: uppercase;
}}

QTableView[class="doklady-table"] QHeaderView {{
    background: {Colors.GRAY_50};
}}

/* ═══════════════════════════════════════════════════════════
   EMPTY STATE — Doklady stránka bez dat
   ═══════════════════════════════════════════════════════════ */

QWidget[class="empty-state"] {{
    background: {Surfaces.CARD};
    border: 1px dashed {Borders.STRONG};
    border-radius: {Radius.MD}px;
}}

QLabel[class="empty-state-text"] {{
    color: {Colors.GRAY_500};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_BASE}px;
    font-weight: {Fonts.WEIGHT_REGULAR};
    background: transparent;
}}

/* ═══════════════════════════════════════════════════════════
   DETAIL DIALOG — Doklad detail (read-only)
   ═══════════════════════════════════════════════════════════ */

QDialog[class="doklad-detail"] {{
    background: {Surfaces.CARD};
}}

QLabel[class="dialog-title"] {{
    color: {Colors.BRAND};
    font-family: {Fonts.HEADING_STACK};
    font-size: {Fonts.SIZE_XL}px;
    font-weight: {Fonts.WEIGHT_BOLD};
    background: transparent;
}}

QLabel[class="dialog-label"] {{
    color: {Colors.GRAY_500};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_MEDIUM};
    background: transparent;
}}

QLabel[class="dialog-value"] {{
    color: {Colors.GRAY_900};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_BASE}px;
    font-weight: {Fonts.WEIGHT_REGULAR};
    background: transparent;
}}

QLabel[class="dialog-value-strong"] {{
    color: {Colors.BRAND};
    font-family: {Fonts.HEADING_STACK};
    font-size: {Fonts.SIZE_LG}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    background: transparent;
}}

QWidget[class="doreseni-box"] {{
    background: {Colors.WARNING_50};
    border: 1px solid {Colors.WARNING_500};
    border-left: 3px solid {Colors.WARNING_600};
    border-radius: {Radius.SM}px;
}}

QLabel[class="doreseni-header"] {{
    color: {Colors.WARNING_700};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    background: transparent;
}}

QLabel[class="doreseni-note"] {{
    color: {Colors.GRAY_700};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_REGULAR};
    background: transparent;
}}

QLabel[class="doreseni-note"][empty="true"] {{
    color: {Colors.GRAY_400};
    font-style: italic;
}}

QCheckBox[class="form-check"] {{
    color: {Colors.GRAY_900};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_MEDIUM};
    background: transparent;
    spacing: {Spacing.S2}px;
    padding: 2px 0;
}}

QCheckBox[class="form-check"]::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {Borders.STRONG};
    border-radius: {Radius.SM}px;
    background: {Surfaces.CARD};
}}

QCheckBox[class="form-check"]::indicator:checked {{
    background: {Colors.BRAND};
    border: 1px solid {Colors.BRAND};
}}

QCheckBox[class="form-check"]::indicator:hover {{
    border: 1px solid {Colors.BRAND};
}}

QLabel[class="doklady-status-bar"] {{
    color: {Colors.GRAY_500};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_XS}px;
    font-weight: {Fonts.WEIGHT_MEDIUM};
    background: transparent;
    padding: {Spacing.S2}px {Spacing.S1}px 0 {Spacing.S1}px;
}}

/* ═══════════════════════════════════════════════════════════
   STACKED WIDGET — kontejner stránek
   ═══════════════════════════════════════════════════════════ */

QStackedWidget {{
    background: {Surfaces.PAGE};
    border: none;
}}

/* ═══════════════════════════════════════════════════════════
   SCROLLBARS — minimalistické, v barvě borders
   ═══════════════════════════════════════════════════════════ */

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {Borders.STRONG};
    border-radius: {Radius.SM}px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: {Colors.GRAY_400};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
    background: transparent;
}}

/* ═══════════════════════════════════════════════════════════
   FORM INPUTS — QLineEdit / QPlainTextEdit / QDateEdit / QComboBox
   (globální styl; filter bar má vlastní override výše)
   ═══════════════════════════════════════════════════════════ */

QLineEdit, QPlainTextEdit, QDateEdit, QComboBox {{
    background: {Surfaces.CARD};
    color: {Colors.GRAY_900};
    border: 1px solid {Borders.DEFAULT};
    border-radius: {Radius.SM}px;
    padding: 6px 10px;
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_BASE}px;
    min-height: 30px;
    selection-background-color: {Surfaces.SELECTED};
    selection-color: {Colors.BRAND};
}}

QLineEdit:hover, QPlainTextEdit:hover, QDateEdit:hover, QComboBox:hover {{
    border: 1px solid {Borders.STRONG};
}}

QLineEdit:focus, QPlainTextEdit:focus, QDateEdit:focus, QComboBox:focus {{
    border: 1px solid {Borders.FOCUS};
}}

QLineEdit:disabled, QPlainTextEdit:disabled,
QDateEdit:disabled, QComboBox:disabled {{
    background: {Colors.GRAY_50};
    color: {Colors.GRAY_400};
    border: 1px solid {Borders.SUBTLE};
}}

QPlainTextEdit {{
    padding: 8px 10px;
}}

QDateEdit::drop-down, QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    border: none;
    background: transparent;
    width: 24px;
}}

QDateEdit::down-arrow, QComboBox::down-arrow {{
    image: url({chevron_path});
    width: 14px;
    height: 14px;
}}

QCalendarWidget QToolButton {{
    color: {Colors.BRAND};
    background: transparent;
    font-family: {Fonts.BODY_STACK};
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
}}

QCalendarWidget QAbstractItemView {{
    selection-background-color: {Surfaces.SELECTED};
    selection-color: {Colors.BRAND};
}}

/* Chybový stav — input po client-side validaci */
QLineEdit[class="input-error"],
QPlainTextEdit[class="input-error"],
QDateEdit[class="input-error"],
QComboBox[class="input-error"] {{
    border: 1px solid {Borders.ERROR};
    background: {Colors.ERROR_50};
}}

QLabel[class="input-label"] {{
    color: {Colors.GRAY_700};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    background: transparent;
    padding: 0;
}}

QLabel[class="input-error-text"] {{
    color: {Colors.ERROR_700};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_XS}px;
    font-weight: {Fonts.WEIGHT_MEDIUM};
    background: transparent;
    padding: 0;
}}

/* ═══════════════════════════════════════════════════════════
   DESTRUCTIVE BUTTON — červené akce (storno, smazat, potvrzení)
   ═══════════════════════════════════════════════════════════ */

QPushButton[class="destructive"] {{
    background: {Colors.ERROR_600};
    color: {Colors.WHITE};
    border: none;
    border-radius: {Radius.SM}px;
    padding: 8px 16px;
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    min-height: 32px;
}}

QPushButton[class="destructive"]:hover {{
    background: {Colors.ERROR_700};
}}

QPushButton[class="destructive"]:disabled {{
    background: {Colors.GRAY_200};
    color: {Colors.GRAY_500};
}}

/* Malé × tlačítko pro odstranění řádku v tabulce záznamů */
QPushButton[class="row-remove"] {{
    background: transparent;
    color: {Colors.GRAY_500};
    border: 1px solid {Borders.DEFAULT};
    border-radius: {Radius.SM}px;
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_LG}px;
    font-weight: {Fonts.WEIGHT_MEDIUM};
    padding: 0;
}}

QPushButton[class="row-remove"]:hover {{
    background: {Colors.ERROR_50};
    color: {Colors.ERROR_700};
    border: 1px solid {Colors.ERROR_500};
}}

/* ═══════════════════════════════════════════════════════════
   DIALOGY — confirm / form / zauctovani (sdílený background)
   ═══════════════════════════════════════════════════════════ */

QDialog[class="confirm-dialog"],
QDialog[class="doklad-form"],
QDialog[class="zauctovani-dialog"] {{
    background: {Surfaces.CARD};
}}

QLabel[class="dialog-subtitle"] {{
    color: {Colors.GRAY_500};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_MEDIUM};
    background: transparent;
}}

QLabel[class="dialog-message"] {{
    color: {Colors.GRAY_900};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_BASE}px;
    font-weight: {Fonts.WEIGHT_REGULAR};
    background: transparent;
}}

QLabel[class="dialog-error"] {{
    color: {Colors.ERROR_700};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_MEDIUM};
    background: {Colors.ERROR_50};
    border: 1px solid {Colors.ERROR_500};
    border-radius: {Radius.SM}px;
    padding: {Spacing.S2}px {Spacing.S3}px;
}}

QLabel[class="section-title"] {{
    color: {Colors.BRAND};
    font-family: {Fonts.HEADING_STACK};
    font-size: {Fonts.SIZE_BASE}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    background: transparent;
}}

QLabel[class="sum-label"] {{
    color: {Colors.GRAY_700};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    background: transparent;
}}

QLabel[class="rozdil-label"] {{
    color: {Colors.GRAY_700};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    background: transparent;
}}

QLabel[class="status-ok"] {{
    color: {Colors.SUCCESS_700};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    background: transparent;
}}

QLabel[class="status-error"] {{
    color: {Colors.ERROR_700};
    font-family: {Fonts.BODY_STACK};
    font-size: {Fonts.SIZE_SM}px;
    font-weight: {Fonts.WEIGHT_SEMIBOLD};
    background: transparent;
}}
"""
