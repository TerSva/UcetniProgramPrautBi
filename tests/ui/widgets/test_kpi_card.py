"""Testy pro KpiCard widget."""

from __future__ import annotations

import pytest

from ui.widgets.kpi_card import KpiCard


@pytest.fixture
def card(qtbot):
    w = KpiCard(label="Doklady", value="42", subtitle="celkem letos")
    qtbot.addWidget(w)
    return w


# ──────────────────────────────────────────────────────────────────────
# Konstrukce
# ──────────────────────────────────────────────────────────────────────


class TestKonstrukce:

    def test_label_se_zobrazi(self, card):
        assert card.label_widget.text() == "Doklady"

    def test_value_se_zobrazi(self, card):
        assert card.value_widget.text() == "42"

    def test_subtitle_se_zobrazi(self, card):
        assert card.subtitle_widget.text() == "celkem letos"
        assert card.subtitle_widget.isVisibleTo(card)

    def test_property_class_je_kpi_card(self, card):
        assert card.property("class") == "kpi-card"

    def test_label_class(self, card):
        assert card.label_widget.property("class") == "kpi-label"

    def test_value_class(self, card):
        assert card.value_widget.property("class") == "kpi-value"


# ──────────────────────────────────────────────────────────────────────
# Subtitle: vždy vytvořený, viditelnost přes setVisible
# ──────────────────────────────────────────────────────────────────────


class TestSubtitle:

    def test_bez_subtitle_je_skryty_ale_existuje(self, qtbot):
        w = KpiCard(label="X", value="1", subtitle=None)
        qtbot.addWidget(w)
        assert w.subtitle_widget is not None
        assert w.subtitle_widget.isVisibleTo(w) is False

    def test_set_subtitle_zviditelni(self, qtbot):
        w = KpiCard(label="X", value="1", subtitle=None)
        qtbot.addWidget(w)
        w.show()
        w.set_subtitle("nový popisek")
        assert w.subtitle_widget.text() == "nový popisek"
        assert w.subtitle_widget.isVisibleTo(w) is True

    def test_set_subtitle_none_skryje(self, card, qtbot):
        card.show()
        card.set_subtitle(None)
        assert card.subtitle_widget.isVisibleTo(card) is False


# ──────────────────────────────────────────────────────────────────────
# Mutátory hodnot
# ──────────────────────────────────────────────────────────────────────


class TestMutatory:

    def test_set_value(self, card):
        card.set_value("100")
        assert card.value_widget.text() == "100"

    def test_set_positive_true(self, card):
        card.set_positive(True)
        assert card.property("positive") == "true"
        assert card.value_widget.property("positive") == "true"

    def test_set_positive_false(self, qtbot):
        w = KpiCard(label="X", value="1", positive=True)
        qtbot.addWidget(w)
        w.set_positive(False)
        assert w.property("positive") == "false"
        assert w.value_widget.property("positive") == "false"


# ──────────────────────────────────────────────────────────────────────
# Konstruktorové varianty
# ──────────────────────────────────────────────────────────────────────


class TestVarianty:

    def test_positive_v_konstruktoru(self, qtbot):
        w = KpiCard(label="Zisk", value="10 000 Kč", positive=True)
        qtbot.addWidget(w)
        assert w.property("positive") == "true"
        assert w.value_widget.property("positive") == "true"

    def test_default_neni_positive(self, qtbot):
        w = KpiCard(label="X", value="1")
        qtbot.addWidget(w)
        assert w.property("positive") == "false"


# ──────────────────────────────────────────────────────────────────────
# Subtitle clickable (nové v Kroku 3)
# ──────────────────────────────────────────────────────────────────────


class TestSubtitleClickable:

    def test_default_neni_clickable(self, qtbot):
        w = KpiCard(label="X", value="1", subtitle="s")
        qtbot.addWidget(w)
        assert w.subtitle_widget.property("clickable") == "false"

    def test_konstruktor_clickable_nastavi_property(self, qtbot):
        w = KpiCard(
            label="X", value="1", subtitle="s", subtitle_clickable=True,
        )
        qtbot.addWidget(w)
        assert w.subtitle_widget.property("clickable") == "true"

    def test_set_subtitle_clickable_prepne_property(self, qtbot):
        w = KpiCard(label="X", value="1", subtitle="s")
        qtbot.addWidget(w)
        w.set_subtitle_clickable(True)
        assert w.subtitle_widget.property("clickable") == "true"
        w.set_subtitle_clickable(False)
        assert w.subtitle_widget.property("clickable") == "false"

    def test_klik_na_clickable_subtitle_emituje_signal(self, qtbot):
        from PyQt6.QtCore import QPointF, Qt
        from PyQt6.QtGui import QMouseEvent
        w = KpiCard(
            label="X", value="1", subtitle="s", subtitle_clickable=True,
        )
        qtbot.addWidget(w)
        received = []
        w.subtitle_clicked.connect(lambda: received.append(True))

        # Simulace mousePressEvent přímo na subtitle labelu
        ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(5, 5),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        w.subtitle_widget.mousePressEvent(ev)
        assert received == [True]

    def test_klik_na_nclickable_subtitle_neemituje(self, qtbot):
        from PyQt6.QtCore import QPointF, Qt
        from PyQt6.QtGui import QMouseEvent
        w = KpiCard(label="X", value="1", subtitle="s")
        qtbot.addWidget(w)
        received = []
        w.subtitle_clicked.connect(lambda: received.append(True))

        ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(5, 5),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        w.subtitle_widget.mousePressEvent(ev)
        assert received == []
