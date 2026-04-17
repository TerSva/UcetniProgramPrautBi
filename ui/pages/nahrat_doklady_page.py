"""NahratDokladyPage — OCR inbox pro hromadné zpracování dokladů.

Drop zone + seznam čekajících uploadů + akce (schválit/zamítnout).
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import Colors, Spacing
from ui.dialogs.ocr_upload_detail_dialog import OcrUploadDetailDialog
from ui.viewmodels.ocr_inbox_vm import OcrInboxViewModel


class DropZone(QWidget):
    """Drop zone pro přetažení souborů."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setProperty("class", "drop-zone")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(160)

        self._page: NahratDokladyPage | None = None

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel("PDF, JPG, PNG", self)
        icon_label.setProperty("class", "form-help")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        text_label = QLabel("Přetáhni sem soubory", self)
        text_label.setProperty("class", "section-title")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text_label)

        sub_label = QLabel("nebo", self)
        sub_label.setProperty("class", "form-help")
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub_label)

        self._select_btn = QPushButton("Vybrat soubory", self)
        self._select_btn.setProperty("class", "secondary")
        self._select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._select_btn.clicked.connect(self._on_select)
        layout.addWidget(
            self._select_btn, alignment=Qt.AlignmentFlag.AlignCenter,
        )

    def set_page(self, page: NahratDokladyPage) -> None:
        self._page = page

    def _on_select(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Vybrat doklady",
            "",
            "Doklady (*.pdf *.jpg *.jpeg *.png);;Všechny soubory (*)",
        )
        if files and self._page:
            self._page._handle_files([Path(f) for f in files])

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("class", "drop-zone-active")
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self.setProperty("class", "drop-zone")
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event) -> None:  # noqa: N802
        self.setProperty("class", "drop-zone")
        self.style().unpolish(self)
        self.style().polish(self)

        urls = event.mimeData().urls()
        paths = [Path(u.toLocalFile()) for u in urls if u.isLocalFile()]
        valid = [
            p for p in paths
            if p.suffix.lower() in (".pdf", ".jpg", ".jpeg", ".png")
        ]
        if valid and self._page:
            self._page._handle_files(valid)


class NahratDokladyPage(QWidget):
    """OCR inbox — nahrání a zpracování dokladů."""

    def __init__(
        self,
        view_model: OcrInboxViewModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setProperty("class", "page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._drop_zone: DropZone
        self._table: QTableWidget
        self._batch_button: QPushButton
        self._count_label: QLabel
        self._error_label: QLabel
        self._schvalene_table: QTableWidget

        self._build_ui()
        if self._vm is not None:
            self._vm.load()
            self._refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            Spacing.S8, Spacing.S8, Spacing.S8, Spacing.S8,
        )
        root.setSpacing(Spacing.S4)

        title = QLabel("Nahrát doklady", self)
        title.setProperty("class", "page-title")
        root.addWidget(title)

        subtitle = QLabel(
            "Hromadné zpracování faktur přes OCR.",
            self,
        )
        subtitle.setProperty("class", "page-subtitle")
        root.addWidget(subtitle)

        # Drop zone
        self._drop_zone = DropZone(self)
        self._drop_zone.set_page(self)
        root.addWidget(self._drop_zone)

        # Header row: count + batch button
        header_row = QHBoxLayout()
        header_row.setSpacing(Spacing.S3)
        self._count_label = QLabel("Čeká na zpracování (0)", self)
        self._count_label.setProperty("class", "section-title")
        header_row.addWidget(self._count_label)
        header_row.addStretch(1)

        self._batch_button = QPushButton("Schválit vše", self)
        self._batch_button.setProperty("class", "primary")
        self._batch_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._batch_button.clicked.connect(self._on_batch_approve)
        self._batch_button.setVisible(False)
        header_row.addWidget(self._batch_button)
        root.addLayout(header_row)

        # Pending table
        self._table = QTableWidget(self)
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Soubor", "Typ", "Dodavatel", "Částka", "Datum",
            "OCR", "",
        ])
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._table.verticalHeader().setVisible(False)
        h = self._table.horizontalHeader()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(0, 200)
        h.resizeSection(1, 50)
        h.resizeSection(3, 120)
        h.resizeSection(4, 100)
        h.resizeSection(5, 80)
        h.resizeSection(6, 180)
        self._table.cellDoubleClicked.connect(self._on_row_double_click)
        root.addWidget(self._table, stretch=1)

        # Error
        self._error_label = QLabel("", self)
        self._error_label.setProperty("class", "dialog-error")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        # Schválené section (collapsed)
        schvalene_title = QLabel("Nedávno schválené", self)
        schvalene_title.setProperty("class", "section-title")
        root.addWidget(schvalene_title)

        self._schvalene_table = QTableWidget(self)
        self._schvalene_table.setColumnCount(4)
        self._schvalene_table.setHorizontalHeaderLabels([
            "Soubor", "Dodavatel", "Částka", "Doklad",
        ])
        self._schvalene_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._schvalene_table.verticalHeader().setVisible(False)
        sh = self._schvalene_table.horizontalHeader()
        sh.setStretchLastSection(True)
        self._schvalene_table.setMaximumHeight(150)
        root.addWidget(self._schvalene_table)

    def _handle_files(self, paths: list[Path]) -> None:
        """Zpracuje nahrané soubory."""
        if self._vm is None:
            return
        self._vm.upload_files(paths)
        if self._vm.error:
            self._show_error(self._vm.error)
        else:
            self._hide_error()
        self._refresh()

    def _on_batch_approve(self) -> None:
        """Hromadné schválení všech zpracovaných uploadů."""
        if self._vm is None:
            return
        from datetime import date
        from domain.doklady.typy import TypDokladu

        items = self._vm.zpracovane_items
        if not items:
            return

        ids = [i.id for i in items]
        self._vm.batch_approve(
            upload_ids=ids,
            typ=TypDokladu.FAKTURA_PRIJATA,
            cislo_prefix=f"FP-{date.today().year}-OCR",
            datum_vystaveni=date.today(),
            k_doreseni=True,
        )
        if self._vm.error:
            self._show_error(self._vm.error)
        else:
            self._hide_error()
        self._refresh()

    def _on_approve_single(self, upload_id: int) -> None:
        """Schválí jeden upload jako NOVY doklad s k_doreseni."""
        if self._vm is None:
            return
        from datetime import date
        from domain.doklady.typy import TypDokladu
        from domain.shared.money import Money

        # Find the item
        item = next((i for i in self._vm.items if i.id == upload_id), None)
        if item is None:
            return

        typ = TypDokladu.FAKTURA_PRIJATA
        if item.parsed_typ:
            try:
                typ = TypDokladu(item.parsed_typ)
            except ValueError:
                pass

        castka = item.parsed_castka or Money(0)
        datum = item.parsed_datum or date.today()
        cislo = f"FP-{datum.year}-{upload_id:04d}"

        self._vm.approve(
            upload_id=upload_id,
            typ=typ,
            cislo=cislo,
            datum_vystaveni=datum,
            castka_celkem=castka,
            popis=f"OCR: {item.file_name}",
            k_doreseni=True,
        )
        if self._vm.error:
            self._show_error(self._vm.error)
        else:
            self._hide_error()
        self._refresh()

    def _on_reject_single(self, upload_id: int) -> None:
        """Zamítne upload."""
        if self._vm is None:
            return
        self._vm.reject(upload_id)
        self._refresh()

    def _refresh(self) -> None:
        if self._vm is None:
            return

        zpracovane = self._vm.zpracovane_items
        schvalene = self._vm.schvalene_items

        # Count label
        self._count_label.setText(
            f"Čeká na zpracování ({len(zpracovane)})"
        )
        self._batch_button.setVisible(len(zpracovane) > 1)

        # Pending table
        self._table.setRowCount(len(zpracovane))
        for i, item in enumerate(zpracovane):
            self._table.setItem(i, 0, QTableWidgetItem(item.file_name))
            self._table.setItem(
                i, 1, QTableWidgetItem(
                    (item.parsed_typ or "?").upper(),
                ),
            )

            dodavatel_text = item.parsed_dodavatel or "—"
            if item.is_pytlovani:
                dodavatel_text += f"\n⚠ Společník: {item.pytlovani_jmeno}"
            self._table.setItem(i, 2, QTableWidgetItem(dodavatel_text))

            castka_text = item.parsed_castka.format_cz() if item.parsed_castka else "—"
            castka_item = QTableWidgetItem(castka_text)
            castka_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            self._table.setItem(i, 3, castka_item)

            datum_text = (
                item.parsed_datum.strftime("%d.%m.%Y")
                if item.parsed_datum else "—"
            )
            self._table.setItem(i, 4, QTableWidgetItem(datum_text))

            ocr_text = f"{item.ocr_method or '?'}"
            if item.ocr_confidence is not None:
                ocr_text += f" ({item.ocr_confidence}%)"
            self._table.setItem(i, 5, QTableWidgetItem(ocr_text))

            # Actions
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(4)

            btn_approve = QPushButton("Uložit", actions)
            btn_approve.setProperty("class", "primary-sm")
            btn_approve.setCursor(Qt.CursorShape.PointingHandCursor)
            uid = item.id
            btn_approve.clicked.connect(
                lambda _c, uid=uid: self._on_approve_single(uid),
            )
            actions_layout.addWidget(btn_approve)

            btn_reject = QPushButton("Zamítnout", actions)
            btn_reject.setProperty("class", "danger-sm")
            btn_reject.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_reject.clicked.connect(
                lambda _c, uid=uid: self._on_reject_single(uid),
            )
            actions_layout.addWidget(btn_reject)

            self._table.setCellWidget(i, 6, actions)

        # Schválené table
        self._schvalene_table.setRowCount(len(schvalene))
        for i, item in enumerate(schvalene):
            self._schvalene_table.setItem(
                i, 0, QTableWidgetItem(item.file_name),
            )
            self._schvalene_table.setItem(
                i, 1, QTableWidgetItem(item.parsed_dodavatel or "—"),
            )
            castka_text = (
                item.parsed_castka.format_cz() if item.parsed_castka else "—"
            )
            self._schvalene_table.setItem(i, 2, QTableWidgetItem(castka_text))
            self._schvalene_table.setItem(
                i, 3, QTableWidgetItem("OK"),
            )

    def _on_row_double_click(self, row: int, _col: int) -> None:
        """Otevře detail dialog pro vybraný upload."""
        if self._vm is None:
            return
        items = self._vm.zpracovane_items
        if row < 0 or row >= len(items):
            return
        item = items[row]

        dlg = OcrUploadDetailDialog(
            item=item,
            file_path=item.file_path,
            parent=self,
        )
        if not dlg.exec():
            return  # Closed without action

        if dlg.result_action == "approve":
            self._vm.approve(
                upload_id=item.id,
                typ=dlg.typ,
                cislo=dlg.cislo,
                datum_vystaveni=dlg.datum_vystaveni,
                castka_celkem=dlg.castka_celkem,
                popis=dlg.popis,
                k_doreseni=True,
            )
            if self._vm.error:
                self._show_error(self._vm.error)
            else:
                self._hide_error()
        elif dlg.result_action == "reject":
            self._vm.reject(item.id)

        self._refresh()

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.setVisible(True)

    def _hide_error(self) -> None:
        self._error_label.setVisible(False)

    # ─── Test-only accessors ─────────────────────────────────────

    @property
    def _table_widget(self) -> QTableWidget:
        return self._table

    @property
    def _drop_zone_widget(self) -> DropZone:
        return self._drop_zone

    @property
    def _batch_widget(self) -> QPushButton:
        return self._batch_button

    @property
    def _count_widget(self) -> QLabel:
        return self._count_label
