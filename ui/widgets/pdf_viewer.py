"""PdfViewerWidget — zobrazení PDF s přepínáním stránek a zoomem.

Používá pdf2image (poppler) pro rasterizaci. Fallback na placeholder
text pokud PDF chybí nebo není nainstalované pdf2image.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QImage, QPixmap, QWheelEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import Spacing

#: Dostupné úrovně zoomu.
_ZOOM_LEVELS = (75, 100, 125, 150, 200)
_DEFAULT_ZOOM_INDEX = 1  # 100%
_DPI_BASE = 150  # DPI pro 100% zoom


class PdfViewerWidget(QWidget):
    """Zobrazení PDF souboru s přepínáním stránek a zoomem."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pdf_path: Path | None = None
        self._pages: list[object] = []  # PIL images
        self._page_count = 0
        self._current_page = 0
        self._zoom_index = _DEFAULT_ZOOM_INDEX

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(Spacing.S2)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(Spacing.S2)

        self._prev_btn = QPushButton("\u25C0", self)
        self._prev_btn.setFixedSize(28, 28)
        self._prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_btn.clicked.connect(self._on_prev)
        toolbar.addWidget(self._prev_btn)

        self._page_label = QLabel("", self)
        self._page_label.setProperty("class", "form-help")
        toolbar.addWidget(self._page_label)

        self._next_btn = QPushButton("\u25B6", self)
        self._next_btn.setFixedSize(28, 28)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.clicked.connect(self._on_next)
        toolbar.addWidget(self._next_btn)

        toolbar.addStretch(1)

        self._zoom_out_btn = QPushButton("\u2212", self)
        self._zoom_out_btn.setFixedSize(28, 28)
        self._zoom_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._zoom_out_btn.clicked.connect(self._on_zoom_out)
        toolbar.addWidget(self._zoom_out_btn)

        self._zoom_label = QLabel("100%", self)
        self._zoom_label.setProperty("class", "form-help")
        self._zoom_label.setFixedWidth(40)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self._zoom_label)

        self._zoom_in_btn = QPushButton("+", self)
        self._zoom_in_btn.setFixedSize(28, 28)
        self._zoom_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._zoom_in_btn.clicked.connect(self._on_zoom_in)
        toolbar.addWidget(self._zoom_in_btn)

        self._open_btn = QPushButton("Otevrit externě", self)
        self._open_btn.setProperty("class", "secondary")
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.clicked.connect(self._on_open_external)
        toolbar.addWidget(self._open_btn)

        root.addLayout(toolbar)

        # Scroll area s obrazem
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setWidget(self._image_label)
        root.addWidget(self._scroll, stretch=1)

        self._toolbar_widget = toolbar
        self._set_toolbar_visible(False)
        self.set_placeholder("Zadne PDF")

    # ─── Public API ──────────────────────────────────────────────

    def load_pdf(self, path: Path) -> None:
        """Nacte PDF soubor a zobrazi prvni stranku."""
        self._pdf_path = path
        if not path.exists():
            self.set_placeholder(f"Soubor nenalezen: {path}")
            return

        try:
            from pdf2image import convert_from_path

            self._pages = convert_from_path(str(path), dpi=_DPI_BASE)
            self._page_count = len(self._pages)
            if self._page_count == 0:
                self.set_placeholder("PDF je prazdne")
                return
            self._current_page = 0
            self._zoom_index = _DEFAULT_ZOOM_INDEX
            self._set_toolbar_visible(True)
            self._render_current()
        except ImportError:
            self.set_placeholder(
                "pdf2image neni nainstalovano.\npip install pdf2image"
            )
        except Exception as exc:  # noqa: BLE001
            self.set_placeholder(f"Chyba nahledu: {exc}")

    def load_image(self, path: Path) -> None:
        """Nacte obrazek (JPG/PNG)."""
        self._pdf_path = path
        if not path.exists():
            self.set_placeholder(f"Soubor nenalezen: {path}")
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.set_placeholder("Nelze nacist obrazek")
            return
        self._pages = []
        self._page_count = 0
        self._set_toolbar_visible(False)
        self._open_btn.setVisible(True)
        self._image_label.setPixmap(pixmap.scaled(
            500, 700,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def set_placeholder(self, text: str) -> None:
        """Zobrazi placeholder text misto PDF."""
        self._pdf_path = None
        self._pages = []
        self._page_count = 0
        self._set_toolbar_visible(False)
        self._image_label.setPixmap(QPixmap())
        self._image_label.setText(text)
        self._image_label.setProperty("class", "form-help")

    # ─── Rendering ───────────────────────────────────────────────

    def _render_current(self) -> None:
        """Vyrenderuje aktualni stranku s aktualnim zoomem."""
        if not self._pages or self._current_page >= self._page_count:
            return

        pil_img = self._pages[self._current_page]
        zoom = _ZOOM_LEVELS[self._zoom_index]
        scale = zoom / 100.0

        w = int(pil_img.width * scale)
        h = int(pil_img.height * scale)
        resized = pil_img.resize((w, h))

        data = resized.tobytes("raw", "RGB")
        qimg = QImage(
            data, resized.width, resized.height,
            resized.width * 3,
            QImage.Format.Format_RGB888,
        )
        pixmap = QPixmap.fromImage(qimg)
        self._image_label.setPixmap(pixmap)

        # Update labels
        self._page_label.setText(
            f"Strana {self._current_page + 1} z {self._page_count}"
        )
        self._zoom_label.setText(f"{zoom}%")
        self._prev_btn.setEnabled(self._current_page > 0)
        self._next_btn.setEnabled(self._current_page < self._page_count - 1)
        self._zoom_out_btn.setEnabled(self._zoom_index > 0)
        self._zoom_in_btn.setEnabled(
            self._zoom_index < len(_ZOOM_LEVELS) - 1
        )

    def _set_toolbar_visible(self, visible: bool) -> None:
        """Zobraz/schovej toolbar elementy."""
        self._prev_btn.setVisible(visible)
        self._page_label.setVisible(visible)
        self._next_btn.setVisible(visible)
        self._zoom_out_btn.setVisible(visible)
        self._zoom_label.setVisible(visible)
        self._zoom_in_btn.setVisible(visible)
        self._open_btn.setVisible(visible)

    # ─── Slots ───────────────────────────────────────────────────

    def _on_prev(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self._render_current()

    def _on_next(self) -> None:
        if self._current_page < self._page_count - 1:
            self._current_page += 1
            self._render_current()

    def _on_zoom_in(self) -> None:
        if self._zoom_index < len(_ZOOM_LEVELS) - 1:
            self._zoom_index += 1
            self._render_current()

    def _on_zoom_out(self) -> None:
        if self._zoom_index > 0:
            self._zoom_index -= 1
            self._render_current()

    def _on_open_external(self) -> None:
        if self._pdf_path and self._pdf_path.exists():
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self._pdf_path))
            )

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Ctrl+scroll = zoom."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self._on_zoom_in()
            else:
                self._on_zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)
