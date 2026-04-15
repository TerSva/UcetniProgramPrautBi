"""Testy pro Labeled* input widgety."""

from __future__ import annotations

from datetime import date

from domain.shared.money import Money
from ui.widgets.labeled_inputs import (
    LabeledComboBox,
    LabeledDateEdit,
    LabeledLineEdit,
    LabeledMoneyEdit,
    LabeledTextEdit,
)


class TestLabeledLineEdit:

    def test_value_a_set_value(self, qtbot):
        w = LabeledLineEdit("Popis")
        qtbot.addWidget(w)
        w.set_value("ahoj")
        assert w.value() == "ahoj"

    def test_text_changed_signal(self, qtbot):
        w = LabeledLineEdit("Popis")
        qtbot.addWidget(w)
        events: list[str] = []
        w.text_changed.connect(events.append)
        w.set_value("xy")
        assert events == ["xy"]

    def test_max_length(self, qtbot):
        w = LabeledLineEdit("Popis", max_length=3)
        qtbot.addWidget(w)
        w.line_widget.setText("abcdef")
        assert len(w.value()) == 3

    def test_set_error_ukaze_hlasku_a_prepne_class(self, qtbot):
        w = LabeledLineEdit("Popis")
        qtbot.addWidget(w)
        w.set_error("chybí")
        assert w.error_widget.isHidden() is False
        assert w.error_widget.text() == "chybí"
        assert w.inner_widget.property("class") == "input-error"

    def test_set_error_none_schova(self, qtbot):
        w = LabeledLineEdit("Popis")
        qtbot.addWidget(w)
        w.set_error("x")
        w.set_error(None)
        assert w.error_widget.isHidden() is True
        assert w.inner_widget.property("class") == ""


class TestLabeledTextEdit:

    def test_value_a_set_value(self, qtbot):
        w = LabeledTextEdit("Poznámka")
        qtbot.addWidget(w)
        w.set_value("víceřádkový\ntext")
        assert w.value() == "víceřádkový\ntext"

    def test_placeholder(self, qtbot):
        w = LabeledTextEdit("Poznámka", placeholder="zde")
        qtbot.addWidget(w)
        assert w.edit_widget.placeholderText() == "zde"


class TestLabeledDateEdit:

    def test_default_value_je_dnes(self, qtbot):
        w = LabeledDateEdit("Datum")
        qtbot.addWidget(w)
        assert w.value() == date.today()

    def test_set_value_a_value(self, qtbot):
        w = LabeledDateEdit("Datum")
        qtbot.addWidget(w)
        w.set_value(date(2026, 3, 1))
        assert w.value() == date(2026, 3, 1)

    def test_clearable_vraci_none(self, qtbot):
        w = LabeledDateEdit("Datum", clearable=True)
        qtbot.addWidget(w)
        w.set_value(None)
        assert w.value() is None

    def test_clearable_po_nastaveni_date_vraci_date(self, qtbot):
        w = LabeledDateEdit("Datum", clearable=True)
        qtbot.addWidget(w)
        w.set_value(date(2026, 5, 1))
        assert w.value() == date(2026, 5, 1)

    def test_non_clearable_none_fallback_na_dnes(self, qtbot):
        w = LabeledDateEdit("Datum")
        qtbot.addWidget(w)
        w.set_value(None)
        assert w.value() == date.today()


class TestLabeledMoneyEdit:

    def test_prazdny_vstup_vraci_none(self, qtbot):
        w = LabeledMoneyEdit("Částka")
        qtbot.addWidget(w)
        assert w.value() is None

    def test_integer_ciselny(self, qtbot):
        w = LabeledMoneyEdit("Částka")
        qtbot.addWidget(w)
        w.line_widget.setText("12100")
        assert w.value() == Money.from_koruny("12100")

    def test_carka_desetinna(self, qtbot):
        w = LabeledMoneyEdit("Částka")
        qtbot.addWidget(w)
        w.line_widget.setText("12100,50")
        assert w.value() == Money.from_koruny("12100.50")

    def test_mezery_jako_tisicove(self, qtbot):
        w = LabeledMoneyEdit("Částka")
        qtbot.addWidget(w)
        w.line_widget.setText("12 100,50")
        assert w.value() == Money.from_koruny("12100.50")

    def test_nbsp_jako_tisicove(self, qtbot):
        w = LabeledMoneyEdit("Částka")
        qtbot.addWidget(w)
        w.line_widget.setText("12\u00a0100,50")
        assert w.value() == Money.from_koruny("12100.50")

    def test_nevalidni_vraci_none(self, qtbot):
        w = LabeledMoneyEdit("Částka")
        qtbot.addWidget(w)
        w.line_widget.setText("abc")
        assert w.value() is None

    def test_set_value_formatuje(self, qtbot):
        w = LabeledMoneyEdit("Částka")
        qtbot.addWidget(w)
        w.set_value(Money.from_koruny("12100.50"))
        assert w.line_widget.text() == "12100,50"

    def test_set_value_none_clear(self, qtbot):
        w = LabeledMoneyEdit("Částka")
        qtbot.addWidget(w)
        w.line_widget.setText("1")
        w.set_value(None)
        assert w.line_widget.text() == ""


class TestLabeledComboBox:

    def test_add_item_a_value(self, qtbot):
        w: LabeledComboBox[str] = LabeledComboBox("Typ")
        qtbot.addWidget(w)
        w.add_item("A", "a")
        w.add_item("B", "b")
        w.combo_widget.setCurrentIndex(1)
        assert w.value() == "b"

    def test_set_value_nastaví_správný_index(self, qtbot):
        w: LabeledComboBox[str] = LabeledComboBox("Typ")
        qtbot.addWidget(w)
        w.add_item("A", "a")
        w.add_item("B", "b")
        w.set_value("b")
        assert w.combo_widget.currentIndex() == 1

    def test_set_value_neexistujici_resetuje_na_minus_jedna(self, qtbot):
        w: LabeledComboBox[str] = LabeledComboBox("Typ")
        qtbot.addWidget(w)
        w.add_item("A", "a")
        w.set_value("neexistuje")
        assert w.combo_widget.currentIndex() == -1

    def test_current_value_changed_signal(self, qtbot):
        w: LabeledComboBox[str] = LabeledComboBox("Typ")
        qtbot.addWidget(w)
        w.add_item("A", "a")
        w.add_item("B", "b")
        received: list[object] = []
        w.current_value_changed.connect(received.append)
        w.combo_widget.setCurrentIndex(1)
        assert received == ["b"]
