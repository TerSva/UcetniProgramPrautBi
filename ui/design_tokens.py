"""Design tokens — 1:1 přepis z visual-book-ucetni-program.html (:root).

Zdroj pravdy: visual-book-ucetni-program.html, sekce `:root { ... }` (řádky 12–178).

Převody:
  * Barvy: hex 1:1 z CSS proměnných.
  * rem → px při 16px base (např. 0.9375rem × 16 = 15px).
  * em → Qt percentage spacing: -0.02em = -2% (QFont.setLetterSpacing).
  * rgba() řetězce zůstávají jako str (Qt QSS je přijímá doslovně).

Žádné alternativní hodnoty, žádné „vylepšení".
"""

from __future__ import annotations

from typing import Final


# ══════════════════════════════════════════════
# COLORS
# ══════════════════════════════════════════════

class Colors:
    """Barevné tokeny (hex). Alfa kanály jako rgba řetězce (pro QSS)."""

    # ── Primary Palette: Deep Teal ──
    PRIMARY_900: Final[str] = "#022C22"
    PRIMARY_800: Final[str] = "#064E3B"
    PRIMARY_700: Final[str] = "#065F46"
    PRIMARY_600: Final[str] = "#047857"
    PRIMARY_500: Final[str] = "#059669"
    PRIMARY_400: Final[str] = "#10B981"
    PRIMARY_300: Final[str] = "#34D399"
    PRIMARY_200: Final[str] = "#6EE7B7"
    PRIMARY_100: Final[str] = "#A7F3D0"
    PRIMARY_50: Final[str] = "#D1FAE5"
    PRIMARY_25: Final[str] = "#ECFDF5"

    # ── Semantic: Brand ──
    BRAND: Final[str] = "#134E4A"
    BRAND_HOVER: Final[str] = "#0F766E"
    BRAND_ACTIVE: Final[str] = "#0D6B63"
    BRAND_SUBTLE: Final[str] = "#F0FDFA"

    # ── Accent: Gold ──
    ACCENT_700: Final[str] = "#92400E"
    ACCENT_600: Final[str] = "#A16207"
    ACCENT_500: Final[str] = "#B47D04"  # adjusted z #CA8A04 pro WCAG 3:1 na bílé
    ACCENT_400: Final[str] = "#EAB308"
    ACCENT_300: Final[str] = "#FDE047"
    ACCENT_200: Final[str] = "#FEF08A"
    ACCENT_100: Final[str] = "#FEF9C3"
    ACCENT_50: Final[str] = "#FEFCE8"

    # ── Neutrals ──
    GRAY_950: Final[str] = "#0A0F0D"
    GRAY_900: Final[str] = "#111827"
    GRAY_800: Final[str] = "#1F2937"
    GRAY_700: Final[str] = "#374151"
    GRAY_600: Final[str] = "#4B5563"
    GRAY_500: Final[str] = "#6B7280"
    GRAY_400: Final[str] = "#9CA3AF"
    GRAY_300: Final[str] = "#D1D5DB"
    GRAY_200: Final[str] = "#E5E7EB"
    GRAY_100: Final[str] = "#F3F4F6"
    GRAY_50: Final[str] = "#F9FAFB"
    WHITE: Final[str] = "#FFFFFF"

    # ── Semantic: Success ──
    SUCCESS_700: Final[str] = "#15803D"
    SUCCESS_600: Final[str] = "#16A34A"
    SUCCESS_500: Final[str] = "#22C55E"
    SUCCESS_100: Final[str] = "#DCFCE7"
    SUCCESS_50: Final[str] = "#F0FDF4"

    # ── Semantic: Warning ──
    WARNING_700: Final[str] = "#A16207"
    WARNING_600: Final[str] = "#CA8A04"
    WARNING_500: Final[str] = "#EAB308"
    WARNING_100: Final[str] = "#FEF9C3"
    WARNING_50: Final[str] = "#FEFCE8"

    # ── Semantic: Error ──
    ERROR_700: Final[str] = "#B91C1C"
    ERROR_600: Final[str] = "#DC2626"
    ERROR_500: Final[str] = "#EF4444"
    ERROR_100: Final[str] = "#FEE2E2"
    ERROR_50: Final[str] = "#FEF2F2"

    # ── Semantic: Info ──
    INFO_700: Final[str] = "#1D4ED8"
    INFO_600: Final[str] = "#0284C7"
    INFO_500: Final[str] = "#0EA5E9"
    INFO_100: Final[str] = "#E0F2FE"
    INFO_50: Final[str] = "#F0F9FF"

    # ── Financial: Debit / Kredit / Zero ──
    DEBIT: Final[str] = "#DC2626"
    DEBIT_BG: Final[str] = "#FEF2F2"
    CREDIT: Final[str] = "#15803D"
    CREDIT_BG: Final[str] = "#F0FDF4"
    ZERO: Final[str] = "#6B7280"


class Surfaces:
    """Surface tokeny."""

    PAGE: Final[str] = "#F8FAFB"
    CARD: Final[str] = "#FFFFFF"
    SIDEBAR: Final[str] = "#134E4A"
    SIDEBAR_HOVER: Final[str] = "rgba(255, 255, 255, 0.08)"
    HEADER: Final[str] = "#FFFFFF"
    MODAL_OVERLAY: Final[str] = "rgba(10, 15, 13, 0.5)"
    TOOLTIP: Final[str] = "#1F2937"
    SELECTED: Final[str] = "#F0FDFA"
    HOVER: Final[str] = "#F3F4F6"


class Borders:
    """Border tokeny."""

    DEFAULT: Final[str] = "#E5E7EB"
    SUBTLE: Final[str] = "#F3F4F6"
    STRONG: Final[str] = "#D1D5DB"
    FOCUS: Final[str] = "#0F766E"
    ERROR: Final[str] = "#EF4444"
    SUCCESS: Final[str] = "#22C55E"
    DIVIDER: Final[str] = "#E5E7EB"
    TABLE: Final[str] = "#F3F4F6"


# ══════════════════════════════════════════════
# TYPOGRAPHY
# ══════════════════════════════════════════════

class Fonts:
    """Font families + velikosti (px) + leading + tracking.

    Velikosti přepočteny z rem při 16px base:
        0.6875rem × 16 = 11px
        0.8125rem × 16 = 13px
        0.9375rem × 16 = 15px
        1.125rem  × 16 = 18px
        1.25rem   × 16 = 20px
        1.5rem    × 16 = 24px
        1.875rem  × 16 = 30px
        2.25rem   × 16 = 36px

    Tracking přepočten z em na procenta (pro QFont.setLetterSpacing):
        -0.02em = -2.0 %
        0em     =  0.0 %
        0.025em =  2.5 %
        -0.01em = -1.0 %
    """

    # Families (primární + fallbacky; použitelné v QSS `font-family` i QFont)
    HEADING: Final[str] = "Space Grotesk"
    BODY: Final[str] = "DM Sans"
    MONO: Final[str] = "SF Mono"

    # Fallback řetězce pro QSS (když preferovaný font není registrován)
    HEADING_STACK: Final[str] = "'Space Grotesk', system-ui, sans-serif"
    BODY_STACK: Final[str] = "'DM Sans', system-ui, sans-serif"
    MONO_STACK: Final[str] = "'SF Mono', 'Fira Code', 'Consolas', monospace"

    # Weights (odpovídá staženým řezům: 300, 400, 500, 600, 700)
    WEIGHT_LIGHT: Final[int] = 300
    WEIGHT_REGULAR: Final[int] = 400
    WEIGHT_MEDIUM: Final[int] = 500
    WEIGHT_SEMIBOLD: Final[int] = 600
    WEIGHT_BOLD: Final[int] = 700

    # Sizes (px)
    SIZE_XS: Final[int] = 11
    SIZE_SM: Final[int] = 13
    SIZE_BASE: Final[int] = 15
    SIZE_LG: Final[int] = 18
    SIZE_XL: Final[int] = 20
    SIZE_2XL: Final[int] = 24
    SIZE_3XL: Final[int] = 30
    SIZE_4XL: Final[int] = 36

    # Leading (line-height multiplikátor)
    LEADING_TIGHT: Final[float] = 1.2
    LEADING_SNUG: Final[float] = 1.35
    LEADING_NORMAL: Final[float] = 1.5
    LEADING_RELAXED: Final[float] = 1.6

    # Tracking (procenta pro QFont.setLetterSpacing s PercentageSpacing)
    TRACKING_TIGHT: Final[float] = -2.0
    TRACKING_NORMAL: Final[float] = 0.0
    TRACKING_WIDE: Final[float] = 2.5
    TRACKING_TABULAR: Final[float] = -1.0


# ══════════════════════════════════════════════
# SPACING (4px grid)
# ══════════════════════════════════════════════

class Spacing:
    """Spacing tokeny v px (4px base grid)."""

    S0: Final[int] = 0
    S1: Final[int] = 4
    S2: Final[int] = 8
    S3: Final[int] = 12
    S4: Final[int] = 16
    S5: Final[int] = 20
    S6: Final[int] = 24
    S7: Final[int] = 28
    S8: Final[int] = 32
    S10: Final[int] = 40
    S12: Final[int] = 48
    S16: Final[int] = 64
    S20: Final[int] = 80


# ══════════════════════════════════════════════
# RADIUS
# ══════════════════════════════════════════════

class Radius:
    """Border radius tokeny v px."""

    NONE: Final[int] = 0
    SM: Final[int] = 4
    MD: Final[int] = 6
    LG: Final[int] = 8
    XL: Final[int] = 12
    XL2: Final[int] = 16
    FULL: Final[int] = 9999


# ══════════════════════════════════════════════
# SHADOWS (použitelné v QSS nebo jako dropshadow params)
# ══════════════════════════════════════════════

class Shadows:
    """Shadow tokeny jako CSS řetězce (Qt QSS je nepodporuje u všech widgetů,
    ale necháváme je pro dokumentaci a případné QGraphicsDropShadowEffect)."""

    XS: Final[str] = "0 1px 2px rgba(0,0,0,0.04)"
    SM: Final[str] = "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)"
    MD: Final[str] = "0 4px 6px -1px rgba(0,0,0,0.06), 0 2px 4px -2px rgba(0,0,0,0.04)"
    LG: Final[str] = "0 10px 15px -3px rgba(0,0,0,0.06), 0 4px 6px -4px rgba(0,0,0,0.04)"
    XL: Final[str] = "0 20px 25px -5px rgba(0,0,0,0.08), 0 8px 10px -6px rgba(0,0,0,0.04)"
    FOCUS: Final[str] = "0 0 0 3px rgba(15,118,110,0.2)"
    ERROR: Final[str] = "0 0 0 3px rgba(239,68,68,0.15)"


# ══════════════════════════════════════════════
# TRANSITIONS
# ══════════════════════════════════════════════

class Transitions:
    """Délky animací v ms (Qt používá QPropertyAnimation.setDuration(ms))."""

    FAST_MS: Final[int] = 150
    BASE_MS: Final[int] = 200
    SLOW_MS: Final[int] = 300


# ══════════════════════════════════════════════
# Z-INDEX (Qt používá QWidget.raise_() / stacking; tokeny kvůli konzistenci)
# ══════════════════════════════════════════════

class ZIndex:
    """Z-index tokeny (informativní — Qt řídí stacking přes raise_()/lower())."""

    DROPDOWN: Final[int] = 10
    STICKY: Final[int] = 20
    OVERLAY: Final[int] = 30
    MODAL: Final[int] = 40
    TOOLTIP: Final[int] = 50
    TOAST: Final[int] = 60
