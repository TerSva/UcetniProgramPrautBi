"""Testy ZauctovatUhraduDialog — fokus na výpočet _rozdil."""

from datetime import date
from decimal import Decimal

from domain.banka.bankovni_transakce import StavTransakce
from domain.doklady.typy import TypDokladu
from domain.shared.money import Money
from domain.ucetnictvi.typy import TypUctu
from services.queries.banka import TransakceListItem
from services.queries.uctova_osnova import UcetItem
from ui.dialogs.zauctovat_uhradu_dialog import ZauctovatUhraduDialog


def _tx(castka_hal: int) -> TransakceListItem:
    return TransakceListItem(
        id=1,
        datum_transakce=date(2025, 5, 5),
        datum_zauctovani=date(2025, 5, 5),
        castka=Money(-castka_hal),
        smer="V",
        variabilni_symbol=None,
        protiucet=None,
        popis="Platba",
        stav=StavTransakce.NESPAROVANO,
    )


def _ucty():
    return [
        UcetItem(cislo="221.001", nazev="Banka", typ=TypUctu.AKTIVA),
        UcetItem(cislo="321", nazev="Dodavatelé", typ=TypUctu.PASIVA),
    ]


class TestRozdilVypocet:

    def test_plna_uhrada_bez_predchozich_je_rozdil_nula(self, qtbot):
        """Faktura 5000, tx 5000, žádné předchozí úhrady → rozdíl 0."""
        d = ZauctovatUhraduDialog(
            doklad_cislo="FP-1",
            doklad_typ=TypDokladu.FAKTURA_PRIJATA,
            doklad_castka=Money(500000),
            transakce=_tx(500000),
            ucty=_ucty(),
            ucet_protistrany="321",
            ucet_221="221.001",
        )
        qtbot.addWidget(d)
        assert d._rozdil == Money.zero()

    def test_castecna_uhrada_doplatek_zbytku_je_rozdil_nula(self, qtbot):
        """Faktura 6100, předchozí úhrada 4000 (zbývá 2100), tx 2100 → rozdíl 0."""
        d = ZauctovatUhraduDialog(
            doklad_cislo="FP-1",
            doklad_typ=TypDokladu.FAKTURA_PRIJATA,
            doklad_castka=Money(610000),
            transakce=_tx(210000),
            ucty=_ucty(),
            ucet_protistrany="321",
            ucet_221="221.001",
            zbyva_uhradit=Money(210000),
        )
        qtbot.addWidget(d)
        # Bez fixu by bylo rozdíl 210000 - 610000 = -400000
        # Po fixu: 210000 - 210000 = 0
        assert d._rozdil == Money.zero()

    def test_castecna_uhrada_zbytek_se_zobrazuje_v_info(self, qtbot):
        """Header info ukazuje 'celkem X, zbývá Y' když má dílčí úhrady."""
        d = ZauctovatUhraduDialog(
            doklad_cislo="FP-1",
            doklad_typ=TypDokladu.FAKTURA_PRIJATA,
            doklad_castka=Money(610000),
            transakce=_tx(210000),
            ucty=_ucty(),
            ucet_protistrany="321",
            ucet_221="221.001",
            zbyva_uhradit=Money(210000),
        )
        qtbot.addWidget(d)
        # Najdi info label v dětských widgetech
        from PyQt6.QtWidgets import QLabel
        labels = d.findChildren(QLabel)
        text = " ".join(lbl.text() for lbl in labels)
        assert "celkem" in text
        assert "zbývá uhradit" in text

    def test_uhrada_vetsi_nez_zbytek_ma_kladny_rozdil(self, qtbot):
        """Tx 3000 ale zbývá jen 2100 → kladný rozdíl 900."""
        d = ZauctovatUhraduDialog(
            doklad_cislo="FP-1",
            doklad_typ=TypDokladu.FAKTURA_PRIJATA,
            doklad_castka=Money(610000),
            transakce=_tx(300000),
            ucty=_ucty(),
            ucet_protistrany="321",
            ucet_221="221.001",
            zbyva_uhradit=Money(210000),
        )
        qtbot.addWidget(d)
        assert d._rozdil == Money(90000)
