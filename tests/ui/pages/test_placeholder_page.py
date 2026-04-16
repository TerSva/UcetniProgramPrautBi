"""Testy pro PlaceholderPage — Fáze 8."""

from ui.pages.placeholder_page import PlaceholderPage


class TestPlaceholderPage:

    def test_shows_title(self, qtbot):
        page = PlaceholderPage(
            title="Partneři",
            subtitle="Evidence odběratelů a dodavatelů.",
            phase_number=9,
            phase_name="Partneři + Společníci",
        )
        qtbot.addWidget(page)
        assert page.title_label.text() == "Partneři"

    def test_shows_phase_number_in_badge(self, qtbot):
        page = PlaceholderPage(
            title="Banka",
            subtitle="CSV import bankovních výpisů.",
            phase_number=13,
            phase_name="Banka + CSV Import + Párování",
        )
        qtbot.addWidget(page)
        assert "Fáze 13" in page.phase_badge.text()
        assert "Banka + CSV Import + Párování" in page.phase_badge.text()

    def test_badge_without_phase_number(self, qtbot):
        page = PlaceholderPage(
            title="Nastavení",
            subtitle="Firemní údaje.",
            phase_number=None,
            phase_name="Obecná nastavení aplikace",
        )
        qtbot.addWidget(page)
        assert "Fáze" not in page.phase_badge.text()
        assert "Obecná nastavení" in page.phase_badge.text()

    def test_has_page_class(self, qtbot):
        page = PlaceholderPage(
            title="DPH", subtitle="DPH výpočet.",
            phase_number=11, phase_name="DPH",
        )
        qtbot.addWidget(page)
        assert page.property("class") == "page"
