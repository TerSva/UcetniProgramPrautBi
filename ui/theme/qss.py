"""QSS stylesheet builder — jediné místo, kde se sestavuje Qt stylesheet.

Všechny hodnoty pocházejí z ui.design_tokens. Žádné hex literály zde
nesmějí být — pokud chybí token, přidej ho do design_tokens.py a použij odtud.

Stylesheet se aplikuje globálně v ui.app.run() přes QApplication.setStyleSheet().
"""

from __future__ import annotations

from ui.design_tokens import (
    Borders,
    Colors,
    Fonts,
    Radius,
    Spacing,
    Surfaces,
)


def build_stylesheet() -> str:
    """Sestav kompletní QSS řetězec z design tokenů.

    Návratová hodnota je připravena k předání do QApplication.setStyleSheet().
    """
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
"""
