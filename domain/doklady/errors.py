"""Doménové chyby specifické pro doklady."""

from domain.shared.errors import ConflictError


class CisloDokladuJizExistujeError(ConflictError):
    """Číslo dokladu už v daném typu a roce existuje."""
