"""Doménové výjimky — hierarchie chyb pro business logiku."""


class DomainError(Exception):
    """Bázová třída pro všechny doménové chyby."""


class ValidationError(DomainError):
    """Validační chyba — neplatný stav entity nebo vstupních dat."""


class NotFoundError(DomainError):
    """Entita nebyla nalezena."""


class ConflictError(DomainError):
    """Konflikt — např. duplicitní číslo dokladu."""
