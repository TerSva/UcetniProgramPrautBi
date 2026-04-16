"""DokladyRepository — abstraktní interface pro persistenci dokladů.

Definováno v doménové vrstvě. Implementaci dodá infrastruktura.
Žádný import z infrastructure/ — inverze závislostí.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from domain.doklady.doklad import Doklad
from domain.doklady.typy import StavDokladu, TypDokladu


class DokladyRepository(ABC):
    """Repository pro entitu Doklad.

    Pravidla mazání:
    - Mazat lze POUZE NOVY doklady bez účetních zápisů v deníku
      (koncept "koš na rozpracované" — doklad existuje v evidenci,
      ale ještě neprošel zaúčtováním, takže nemá daňový/auditovatelný
      dopad).
    - Zaúčtovaná účetní data se NIKDY nemažou. Pro zrušení dříve
      zaúčtovaného dokladu použij storno přes opravný doklad
      (UctovyPredpis s prohozenými MD/Dal).

    Toto pravidlo je vynucené na úrovni delete() metody a je železné —
    nedává se obejít ani při administrativních operacích.
    """

    @abstractmethod
    def add(self, doklad: Doklad) -> Doklad:
        """Uloží nový doklad. Vrátí Doklad s naplněným id.

        Raise ConflictError pokud cislo už existuje.
        Raise ValidationError pokud doklad už má id.
        """

    @abstractmethod
    def update(self, doklad: Doklad) -> None:
        """Aktualizuje existující doklad.

        Raise ValidationError pokud doklad nemá id.
        Raise NotFoundError pokud id neexistuje v DB.
        """

    @abstractmethod
    def get_by_id(self, doklad_id: int) -> Doklad:
        """Vrátí doklad. Raise NotFoundError pokud neexistuje."""

    @abstractmethod
    def get_by_cislo(self, cislo: str) -> Doklad:
        """Vrátí doklad podle čísla. Raise NotFoundError pokud neexistuje."""

    @abstractmethod
    def existuje_cislo(self, cislo: str) -> bool:
        """True pokud doklad s daným číslem už existuje."""

    @abstractmethod
    def list_by_typ(
        self, typ: TypDokladu, limit: int = 100, offset: int = 0
    ) -> list[Doklad]:
        """Seznam dokladů daného typu, sestupně podle datum_vystaveni."""

    @abstractmethod
    def list_by_stav(
        self, stav: StavDokladu, limit: int = 100, offset: int = 0
    ) -> list[Doklad]:
        """Seznam dokladů v daném stavu, sestupně podle datum_vystaveni."""

    @abstractmethod
    def list_by_obdobi(
        self, od: date, do: date, limit: int = 1000, offset: int = 0
    ) -> list[Doklad]:
        """Doklady s datum_vystaveni v intervalu [od, do], sestupně."""

    @abstractmethod
    def count_all(self) -> int:
        """Celkový počet všech dokladů v DB bez ohledu na stav/typ/flag.

        Použití: status bar „Zobrazeno X z Y dokladů" pod tabulkou Doklady.
        Triviální `SELECT COUNT(*)` — pro MVP škálu OK.
        """

    @abstractmethod
    def list_k_doreseni(
        self, limit: int = 100, offset: int = 0
    ) -> list[Doklad]:
        """Seznam dokladů s flagem k_doreseni=True.

        Seřazeno sestupně podle datum_vystaveni, pak DESC podle id.
        Vrací doklady v jakémkoli stavu (NOVY, ZAUCTOVANY, CASTECNE_UHRAZENY,
        UHRAZENY) — STORNOVANY se v seznamu nikdy neobjeví, protože storno
        flag auto-clearuje.
        """

    @abstractmethod
    def delete(self, doklad_id: int) -> None:
        """Fyzicky smaže doklad z DB.

        POVOLENO POUZE pro:
        - Doklad existuje
        - Stav == NOVY
        - Nemá žádné zápisy v ucetni_zaznamy (safety net pro inkonzistenci)

        Raises:
            NotFoundError: doklad s daným id neexistuje
            ValidationError: doklad není ve stavu NOVY
            ValidationError: doklad má účetní zápisy v deníku

        POZOR: jediná delete metoda v aplikaci. Pro zaúčtované doklady
        používej storno přes opravný doklad.
        """
