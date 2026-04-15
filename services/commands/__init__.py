"""Commands — write-side operations nad doménou.

Commands oproti services:
    * Command = jedna konkrétní uživatelská akce (vytvořit, stornovat, ...).
    * Vrací DTO snapshot, ne doménovou entitu.
    * Drží si UoW + repo factories pro atomicitu.

Queries viz ``services.queries``.
"""
