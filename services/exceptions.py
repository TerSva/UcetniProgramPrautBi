"""Výjimky service vrstvy."""


class ServiceError(Exception):
    """Bázová třída pro chyby service vrstvy."""


class ZauctovaniError(ServiceError):
    """Chyba při zaúčtování dokladu — souhrnná."""
