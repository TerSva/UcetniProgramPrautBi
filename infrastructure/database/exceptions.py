"""Výjimky pro databázovou vrstvu."""


class DatabaseError(Exception):
    """Základní výjimka pro databázové operace."""


class MigrationError(DatabaseError):
    """Chyba při migraci schématu (nevalidní SQL, gap v sekvenci, ...)."""


class UnitOfWorkError(DatabaseError):
    """Chyba při práci s Unit of Work (přístup mimo with, opakovaný commit, ...)."""
