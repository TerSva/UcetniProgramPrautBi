"""Test render všech vah Space Grotesk (variable) + DM Sans (static).

Potvrzuje, že Qt správně renderuje oba přístupy ke stejnému vizuálnímu cíli.
Diagnostic tool — necháváme v scripts/ pro budoucí ověření fontů.

Spuštění:
    python scripts/test_fonts.py
"""

import argparse
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QWidget


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--save",
        metavar="PATH",
        help="Po render+show ulož screenshot do PATH a ukonči (headless mód).",
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)

    fonts_dir = Path("ui/assets/fonts").resolve()
    print(f"Loading fonts from {fonts_dir}")

    # Načti všechny TTF soubory (absolutní cesty — Qt 6.11 na macOS je vyžaduje)
    loaded_families: set[str] = set()
    for font_path in sorted(fonts_dir.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id == -1:
            print(f"  ✗ FAILED: {font_path.name}")
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        print(f"  ✓ {font_path.name:45} → families: {families}")
        loaded_families.update(families)

    print(f"\nTotal loaded families: {sorted(loaded_families)}")

    # Hlavní okno s test textem
    w = QWidget()
    w.setWindowTitle("Font render test — Space Grotesk variable + DM Sans static")
    w.resize(700, 700)
    w.setStyleSheet(
        "QWidget { background: white; } "
        "QLabel { color: #134E4A; padding: 2px 10px; }"
    )

    layout = QVBoxLayout(w)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(4)

    def add_section_header(text: str) -> None:
        label = QLabel(text)
        label.setStyleSheet(
            "color: #6B7280; font-family: 'DM Sans'; font-size: 11px; "
            "font-weight: 600; text-transform: uppercase; "
            "padding: 16px 10px 4px 10px;"
        )
        layout.addWidget(label)

    def add_sample(family: str, weight_value, weight_name: str, size: int = 20) -> None:
        label = QLabel(f"{weight_name} — Účetní Program ABC 123 Kč 12 345,67")
        font = QFont(family)
        font.setPixelSize(size)
        font.setWeight(weight_value)
        label.setFont(font)
        layout.addWidget(label)

    # Space Grotesk variable — 5 vah
    add_section_header("Space Grotesk (variable font)")
    for weight_value, weight_name in [
        (QFont.Weight.Light, "Light 300"),
        (QFont.Weight.Normal, "Regular 400"),
        (QFont.Weight.Medium, "Medium 500"),
        (QFont.Weight.DemiBold, "SemiBold 600"),
        (QFont.Weight.Bold, "Bold 700"),
    ]:
        add_sample("Space Grotesk", weight_value, weight_name)

    # Separátor
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet("background: #E5E7EB; max-height: 1px; margin: 8px 0;")
    layout.addWidget(sep)

    # DM Sans static — 4 váhy
    add_section_header("DM Sans (static TTF)")
    for weight_value, weight_name in [
        (QFont.Weight.Light, "Light 300"),
        (QFont.Weight.Normal, "Regular 400"),
        (QFont.Weight.Medium, "Medium 500"),
        (QFont.Weight.Bold, "Bold 700"),
    ]:
        add_sample("DM Sans", weight_value, weight_name, size=16)

    layout.addStretch(1)
    w.show()

    if args.save:
        save_path = Path(args.save)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        def grab_and_quit() -> None:
            pixmap = w.grab()
            ok = pixmap.save(str(save_path), "PNG")
            print(f"  {'✓' if ok else '✗'} saved screenshot → {save_path}")
            app.quit()

        # Dvě single-shot vteřiny: první wait na layout/font activation,
        # pak grab. U Qt6 je grab deterministický po první event loop turn.
        QTimer.singleShot(400, grab_and_quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
