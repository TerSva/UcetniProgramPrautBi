"""Typy a stavy dokladů — enumy pro typovou bezpečnost."""

from enum import Enum


class TypDokladu(str, Enum):
    FAKTURA_VYDANA = "FV"
    FAKTURA_PRIJATA = "FP"
    ZALOHA_FAKTURA = "ZF"
    BANKOVNI_VYPIS = "BV"
    POKLADNI_DOKLAD = "PD"
    INTERNI_DOKLAD = "ID"
    OPRAVNY_DOKLAD = "OD"


class StavDokladu(str, Enum):
    NOVY = "novy"
    ZAUCTOVANY = "zauctovany"
    UHRAZENY = "uhrazeny"
    CASTECNE_UHRAZENY = "castecne_uhrazeny"
    STORNOVANY = "stornovany"


class Mena(str, Enum):
    CZK = "CZK"
    EUR = "EUR"
    USD = "USD"


class DphRezim(str, Enum):
    TUZEMSKO = "TUZEMSKO"
    REVERSE_CHARGE = "REVERSE_CHARGE"
    OSVOBOZENO = "OSVOBOZENO"
    MIMO_DPH = "MIMO_DPH"
