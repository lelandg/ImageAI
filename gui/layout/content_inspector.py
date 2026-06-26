"""Content inspector: edit the selected region's content (image ref or text)."""
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QLabel, QPushButton,
    QPlainTextEdit, QFileDialog, QComboBox, QSpinBox,
)
from PySide6.QtCore import Signal

from core.layout.models import Region, TextStyle

_DEFAULT_TEXT_PX = 48  # mirrors qt_renderer's readable fallback


class ContentInspector(QWidget):
    """Edits the content of the currently selected region.

    Emits ``regionContentChanged(region_id, value)``:
      - image region -> ``value`` is the chosen image path (becomes ``image_ref``)
      - text region  -> ``value`` is the new text

    Text regions also emit ``regionTextStyleChanged(region_id, family, size_px)``
    when "Apply text" is clicked, carrying the chosen system font + size.

    The inspector only *displays* the region; ``LayoutTab`` owns the mutation.
    """

    regionContentChanged = Signal(str, str)       # (region_id, new_value)
    regionTextStyleChanged = Signal(str, str, int)  # (region_id, family, size_px)
    regionPromptChanged = Signal(str, str)          # (region_id, image prompt)
    regionPromptSuggestRequested = Signal(str, str)  # (region_id, hint = current prompt)
    regionSendToImageRequested = Signal(str, str)    # (region_id, current prompt text)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._region: Optional[Region] = None
        self._font_loader = None  # keep a ref so the QThread isn't GC'd mid-run
        self._build()
        self._start_font_load()
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

        # Image-generation prompt (saved on the region; used by the AI handoff /
        # batch phases). "Suggest with AI" drafts one from the project theme.
        img_lay.addWidget(QLabel("Image prompt:"))
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText(
            "Prompt for generating this image (optional)…")
        self.prompt_edit.setFixedHeight(70)
        img_lay.addWidget(self.prompt_edit)
        prompt_btns = QHBoxLayout()
        self.suggest_prompt_btn = QPushButton("Suggest with AI")
        self.suggest_prompt_btn.clicked.connect(self._on_suggest_prompt)
        self.apply_prompt_btn = QPushButton("Apply prompt")
        self.apply_prompt_btn.clicked.connect(self._on_apply_prompt)
        prompt_btns.addWidget(self.suggest_prompt_btn)
        prompt_btns.addWidget(self.apply_prompt_btn)
        prompt_btns.addStretch(1)
        img_lay.addLayout(prompt_btns)

        # Hand this region's prompt off to the Image tab; the generated result is
        # routed back into this region by id (see LayoutTab.sendToImageRequested).
        self.send_to_image_btn = QPushButton("Send to Image →")
        self.send_to_image_btn.setToolTip(
            "Open the Image tab pre-filled with this region's prompt and size; "
            "the generated image is placed back into this region.")
        self.send_to_image_btn.clicked.connect(self._on_send_to_image)
        img_lay.addWidget(self.send_to_image_btn)

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

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Font:"))
        self.font_combo = QComboBox()
        self.font_combo.setEditable(True)  # accept families not yet enumerated
        self.font_combo.setMinimumContentsLength(16)
        font_row.addWidget(self.font_combo, 1)
        font_row.addWidget(QLabel("Size:"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(4, 2000)
        self.size_spin.setValue(_DEFAULT_TEXT_PX)
        font_row.addWidget(self.size_spin)
        txt_lay.addLayout(font_row)

        self.apply_text_btn = QPushButton("Apply text")
        self.apply_text_btn.clicked.connect(self._on_apply_text)
        txt_lay.addWidget(self.apply_text_btn)
        self.stack.addWidget(txt_page)

    # --- system fonts (loaded in the background) ---
    def _start_font_load(self):
        from gui.layout.font_loader import cached_families, FontLoader
        cached = cached_families()
        if cached:
            self._populate_fonts(cached)
            return
        self._font_loader = FontLoader(self)
        self._font_loader.loaded.connect(self._populate_fonts)
        self._font_loader.start()

    def _populate_fonts(self, families: List[str]):
        if not families:
            return
        current = self.font_combo.currentText()
        self.font_combo.blockSignals(True)
        self.font_combo.clear()
        self.font_combo.addItems(families)
        if current:
            self.font_combo.setEditText(current)  # preserve a selection made before load
        self.font_combo.blockSignals(False)

    def set_region(self, region: Optional[Region], text_style: Optional[TextStyle] = None):
        """Show the editor for ``region`` (or the empty page when None).

        ``text_style`` is the region's *resolved* style (explicit style or the
        role it inherits from the project) so the font/size controls reflect what
        is actually on screen and "Apply text" doesn't silently shrink it.
        """
        self._region = region
        if region is None:
            self.header.setText("No region selected")
            self.stack.setCurrentIndex(0)
            return
        label = region.name or region.id
        if region.kind == "image":
            self.header.setText(f"Image region: {label}")
            self.image_ref_label.setText(region.image_ref or "(no image)")
            self.prompt_edit.blockSignals(True)
            self.prompt_edit.setPlainText(region.prompt or "")
            self.prompt_edit.blockSignals(False)
            self.stack.setCurrentIndex(1)
        else:
            self.header.setText(f"Text region: {label}")
            self.text_edit.blockSignals(True)
            self.text_edit.setPlainText(region.text or "")
            self.text_edit.blockSignals(False)
            self._load_text_style(text_style)
            self.stack.setCurrentIndex(2)

    def _load_text_style(self, ts: Optional[TextStyle]):
        family = ts.family[0] if (ts and ts.family) else ""
        size = ts.size_px if (ts and ts.size_px) else _DEFAULT_TEXT_PX
        self.font_combo.blockSignals(True)
        self.font_combo.setEditText(family)
        self.font_combo.blockSignals(False)
        self.size_spin.blockSignals(True)
        self.size_spin.setValue(size)
        self.size_spin.blockSignals(False)

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
        if self._region is None:
            return
        self.image_ref_label.setText(path)
        self.regionContentChanged.emit(self._region.id, path)

    # --- image prompt ---
    def _on_apply_prompt(self):
        if self._region is None:
            return
        self.regionPromptChanged.emit(self._region.id, self.prompt_edit.toPlainText().strip())

    def _on_suggest_prompt(self):
        if self._region is None:
            return
        # The current text doubles as a hint to steer the suggestion.
        self.regionPromptSuggestRequested.emit(
            self._region.id, self.prompt_edit.toPlainText().strip())

    def _on_send_to_image(self):
        if self._region is None:
            return
        self.regionSendToImageRequested.emit(
            self._region.id, self.prompt_edit.toPlainText().strip())

    def set_prompt_text(self, region_id: str, text: str):
        """Push an AI-suggested prompt into the box (only if still showing it)."""
        if self._region is not None and self._region.id == region_id:
            self.prompt_edit.blockSignals(True)
            self.prompt_edit.setPlainText(text)
            self.prompt_edit.blockSignals(False)

    def set_suggest_enabled(self, enabled: bool):
        """Disable the Suggest button while a suggestion is in flight."""
        self.suggest_prompt_btn.setEnabled(enabled)

    # --- text ---
    def _on_apply_text(self):
        if self._region is None:
            return
        # Style first (so a font-only change still re-renders even when the text
        # is unchanged), then the content.
        self.regionTextStyleChanged.emit(
            self._region.id, self.font_combo.currentText().strip(), self.size_spin.value())
        self.regionContentChanged.emit(self._region.id, self.text_edit.toPlainText())
