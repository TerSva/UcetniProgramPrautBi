"""PdfUploadZone — drag & drop + tlacitko pro vyber PDF souboru.

Signal ``file_selected`` emituje cestu k vybranemu souboru.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import Colors, Spacing


class PdfUploadZone(QWidget):
    """Drop zona pro PDF soubory s tlacitkem pro vyber."""

    file_selected = pyqtSignal(str)  # absolute path

    def __init__(
        self,
        message: str = "Pretahni sem PDF soubor",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        self._message = message
        self._build_ui()
        self._apply_style(active=False)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(Spacing.S2)

        self._icon_label = QLabel("PDF", self)
        self._icon_label.setProperty("class", "form-help")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon_label)

        self._text_label = QLabel(self._message, self)
        self._text_label.setProperty("class", "section-title")
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._text_label)

        self._or_label = QLabel("nebo", self)
        self._or_label.setProperty("class", "form-help")
        self._or_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._or_label)

        self._select_btn = QPushButton("Vybrat soubor", self)
        self._select_btn.setProperty("class", "secondary")
        self._select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._select_btn.clicked.connect(self._on_select)
        layout.addWidget(
            self._select_btn, alignment=Qt.AlignmentFlag.AlignCenter,
        )

    def _on_select(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Vybrat PDF",
            "",
            "PDF soubory (*.pdf);;Vsechny soubory (*)",
        )
        if path:
            self.file_selected.emit(path)

    # ─── Drag & drop ─────────────────────────────────────────────

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(
                u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf")
                for u in urls
            ):
                event.acceptProposedAction()
                self._apply_style(active=True)
                return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._apply_style(active=False)

    def dropEvent(self, event) -> None:  # noqa: N802
        self._apply_style(active=False)
        urls = event.mimeData().urls()
        for u in urls:
            if u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf"):
                self.file_selected.emit(u.toLocalFile())
                return

    def _apply_style(self, active: bool) -> None:
        border_color = Colors.PRIMARY_400 if active else Colors.GRAY_300
        bg = Colors.PRIMARY_25 if active else Colors.GRAY_50
        self.setStyleSheet(
            f"PdfUploadZone {{"
            f"  border: 2px dashed {border_color};"
            f"  border-radius: 8px;"
            f"  background: {bg};"
            f"  padding: 16px;"
            f"}}"
        )
