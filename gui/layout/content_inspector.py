"""Content inspector: edit the selected region's content (image ref or text)."""
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QLabel, QPushButton,
    QPlainTextEdit, QFileDialog,
)
from PySide6.QtCore import Signal

from core.layout.models import Region


class ContentInspector(QWidget):
    """Edits the content of the currently selected region.

    Emits ``regionContentChanged(region_id, value)``:
      - image region -> ``value`` is the chosen image path (becomes ``image_ref``)
      - text region  -> ``value`` is the new text

    The inspector only *displays* the region; ``LayoutTab`` owns the mutation.
    """

    regionContentChanged = Signal(str, str)  # (region_id, new_value)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._region: Optional[Region] = None
        self._build()
        self.set_region(None)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.header = QLabel("No region selected")
        self.header.setStyleSheet("font-weight: bold;")
        root.addWidget(self.header)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # page 0 — nothing selected
        self.stack.addWidget(QWidget())

        # page 1 — image controls
        img_page = QWidget()
        img_lay = QVBoxLayout(img_page)
        img_lay.setContentsMargins(0, 0, 0, 0)
        btn_row = QHBoxLayout()
        self.import_btn = QPushButton("Import image…")
        self.import_btn.clicked.connect(self._on_import_image)
        self.history_btn = QPushButton("From history…")
        self.history_btn.clicked.connect(self._on_from_history)
        btn_row.addWidget(self.import_btn)
        btn_row.addWidget(self.history_btn)
        btn_row.addStretch(1)
        img_lay.addLayout(btn_row)
        self.image_ref_label = QLabel("(no image)")
        self.image_ref_label.setWordWrap(True)
        self.image_ref_label.setStyleSheet("color: #666; font-size: 11px;")
        img_lay.addWidget(self.image_ref_label)
        img_lay.addStretch(1)
        self.stack.addWidget(img_page)

        # page 2 — text editor
        txt_page = QWidget()
        txt_lay = QVBoxLayout(txt_page)
        txt_lay.setContentsMargins(0, 0, 0, 0)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Type the text for this region…")
        self.text_edit.setFixedHeight(90)
        txt_lay.addWidget(self.text_edit)
        self.apply_text_btn = QPushButton("Apply text")
        self.apply_text_btn.clicked.connect(self._on_apply_text)
        txt_lay.addWidget(self.apply_text_btn)
        self.stack.addWidget(txt_page)

    def set_region(self, region: Optional[Region]):
        """Show the editor for ``region`` (or the empty page when None)."""
        self._region = region
        if region is None:
            self.header.setText("No region selected")
            self.stack.setCurrentIndex(0)
            return
        label = region.name or region.id
        if region.kind == "image":
            self.header.setText(f"Image region: {label}")
            self.image_ref_label.setText(region.image_ref or "(no image)")
            self.stack.setCurrentIndex(1)
        else:
            self.header.setText(f"Text region: {label}")
            self.text_edit.blockSignals(True)
            self.text_edit.setPlainText(region.text or "")
            self.text_edit.blockSignals(False)
            self.stack.setCurrentIndex(2)

    # --- image ---
    def _on_import_image(self):
        if self._region is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Image", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if path:
            self._set_image_ref(path)

    def _on_from_history(self):
        if self._region is None:
            return
        from gui.layout.image_history_dialog import ImageHistoryDialog
        dlg = ImageHistoryDialog(self._config, self)
        if dlg.exec():
            path = dlg.get_selected_image()
            if path:
                self._set_image_ref(path)

    def _set_image_ref(self, path: str):
        self.image_ref_label.setText(path)
        self.regionContentChanged.emit(self._region.id, path)

    # --- text ---
    def _on_apply_text(self):
        if self._region is None:
            return
        self.regionContentChanged.emit(self._region.id, self.text_edit.toPlainText())
