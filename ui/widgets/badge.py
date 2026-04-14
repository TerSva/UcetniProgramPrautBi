"""Badge — malý barevný pill pro tagy (typ dokladu, stav, atd.).

Property-based styling: `class="badge"` + `variant="neutral|primary|success|
warning|error|info"`. Barvy definuje globální QSS, widget sám neobsahuje
žádný setStyleSheet.
"""

from __future__ import annotations

from enum import Enum

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QWidget

from domain.doklady.typy import StavDokladu, TypDokladu


class BadgeVariant(Enum):
    """Vizuální varianta badge — určuje barvu pozadí + textu."""

    NEUTRAL = "neutral"
    PRIMARY = "primary"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


class Badge(QLabel):
    """Barevný pill s textem — neutral/primary/success/warning/error/info."""

    def __init__(
        self,
        text: str,
        variant: BadgeVariant = BadgeVariant.NEUTRAL,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setProperty("class", "badge")
        self.setProperty("variant", variant.value)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._variant = variant

    # ────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────

    def set_text(self, text: str) -> None:
        self.setText(text)

    def set_variant(self, variant: BadgeVariant) -> None:
        """Změní variantu + vynutí refresh QSS (property-based selector)."""
        self._variant = variant
        self.setProperty("variant", variant.value)
        self.style().unpolish(self)
        self.style().polish(self)

    @property
    def variant(self) -> BadgeVariant:
        return self._variant


# ══════════════════════════════════════════════
# Helpers — mapování domény na vizuál
# ══════════════════════════════════════════════


def badge_variant_for_typ(typ: TypDokladu) -> BadgeVariant:
    """Vrátí vizuální variantu pro TypDokladu."""
    return _TYP_VARIANTS.get(typ, BadgeVariant.NEUTRAL)


def badge_variant_for_stav(stav: StavDokladu) -> BadgeVariant:
    """Vrátí vizuální variantu pro StavDokladu."""
    return _STAV_VARIANTS.get(stav, BadgeVariant.NEUTRAL)


def typ_display_text(typ: TypDokladu) -> str:
    """České zkratky pro typ dokladu v tabulce."""
    return _TYP_LABELS.get(typ, typ.value)


def stav_display_text(stav: StavDokladu) -> str:
    """České popisky stavu pro zobrazení v UI."""
    return _STAV_LABELS.get(stav, stav.value)


_TYP_VARIANTS: dict[TypDokladu, BadgeVariant] = {
    TypDokladu.FAKTURA_VYDANA: BadgeVariant.PRIMARY,
    TypDokladu.FAKTURA_PRIJATA: BadgeVariant.INFO,
    TypDokladu.ZALOHA_FAKTURA: BadgeVariant.WARNING,
    TypDokladu.BANKOVNI_VYPIS: BadgeVariant.NEUTRAL,
    TypDokladu.POKLADNI_DOKLAD: BadgeVariant.NEUTRAL,
    TypDokladu.INTERNI_DOKLAD: BadgeVariant.NEUTRAL,
    TypDokladu.OPRAVNY_DOKLAD: BadgeVariant.ERROR,
}


_STAV_VARIANTS: dict[StavDokladu, BadgeVariant] = {
    StavDokladu.NOVY: BadgeVariant.WARNING,
    StavDokladu.ZAUCTOVANY: BadgeVariant.INFO,
    StavDokladu.CASTECNE_UHRAZENY: BadgeVariant.PRIMARY,
    StavDokladu.UHRAZENY: BadgeVariant.SUCCESS,
    StavDokladu.STORNOVANY: BadgeVariant.NEUTRAL,
}


_TYP_LABELS: dict[TypDokladu, str] = {
    TypDokladu.FAKTURA_VYDANA: "FV",
    TypDokladu.FAKTURA_PRIJATA: "FP",
    TypDokladu.ZALOHA_FAKTURA: "ZF",
    TypDokladu.BANKOVNI_VYPIS: "BV",
    TypDokladu.POKLADNI_DOKLAD: "PD",
    TypDokladu.INTERNI_DOKLAD: "ID",
    TypDokladu.OPRAVNY_DOKLAD: "OD",
}


_STAV_LABELS: dict[StavDokladu, str] = {
    StavDokladu.NOVY: "Nový",
    StavDokladu.ZAUCTOVANY: "Zaúčtovaný",
    StavDokladu.CASTECNE_UHRAZENY: "Částečně uhrazený",
    StavDokladu.UHRAZENY: "Uhrazený",
    StavDokladu.STORNOVANY: "Stornovaný",
}
