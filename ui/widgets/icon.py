"""Icon loader — barevné přebarvování Lucide SVG ikon přes QSvgRenderer.

Lucide ikony používají `stroke="currentColor"`. V Qt neexistuje `currentColor`,
takže si SVG načteme jako text, nahradíme `currentColor` za požadovaný hex
a vyrenderujeme do QPixmap přes QSvgRenderer.

Použití:
    icon = load_icon("layout-dashboard", color="#FFFFFF", size=20)
    button.setIcon(icon)
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer


_ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


def load_icon(name: str, color: str, size: int = 20) -> QIcon:
    """Načti Lucide SVG ikonu a přebarvi ji na požadovanou barvu.

    Args:
        name: název ikony bez .svg přípony (např. "layout-dashboard")
        color: hex barva (např. "#FFFFFF" nebo "#134E4A")
        size: cílová velikost v px (default 20)

    Returns:
        QIcon připravená k setIcon() na QPushButton/QAction.

    Raises:
        FileNotFoundError: pokud ikona s daným jménem neexistuje.
    """
    svg_path = _ICONS_DIR / f"{name}.svg"
    if not svg_path.exists():
        raise FileNotFoundError(f"Ikona nenalezena: {svg_path}")

    svg_text = svg_path.read_text(encoding="utf-8")
    svg_text = svg_text.replace("currentColor", color)

    # DPR awareness — na Retina displejích renderujeme 2× a pixmap si označí DPR.
    app = QGuiApplication.instance()
    dpr = app.devicePixelRatio() if app is not None else 1.0
    render_size = int(size * dpr)

    renderer = QSvgRenderer(svg_text.encode("utf-8"))
    pixmap = QPixmap(render_size, render_size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    pixmap.setDevicePixelRatio(dpr)
    icon = QIcon(pixmap)
    # Explicitní velikost pro QIcon (některé widgety ji berou v potaz)
    icon.actualSize(QSize(size, size))
    return icon
