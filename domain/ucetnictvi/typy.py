"""Typy účtů — klasifikace účtové osnovy."""

from enum import Enum


class TypUctu(str, Enum):
    AKTIVA = "A"     # Majetkové účty (1xx, 2xx, 3xx debetní)
    PASIVA = "P"     # Zdrojové účty (3xx kreditní, 4xx)
    NAKLADY = "N"    # Nákladové účty (5xx)
    VYNOSY = "V"     # Výnosové účty (6xx)
