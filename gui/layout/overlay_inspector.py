"""Overlay inspector: list + author comic text overlays.

Emits intent signals only; ``LayoutTab`` owns all model mutation (same split as
Geometry/Content inspectors).
"""
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSpinBox, QCheckBox,
)
from PySide6.QtCore import Signal, Qt

from core.layout.models import PageSpec, Overlay


class OverlayInspector(QWidget):
    addRequested = Signal(str)        # (kind)
    deleteRequested = Signal(str)     # (overlay_id)
    rotationChanged = Signal(str, int)  # (overlay_id, degrees)
    overlaySelected = Signal(str)     # (overlay_id)
    editToggled = Signal(str, bool)   # (overlay_id, on)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_id: Optional[str] = None
        self._build()
        self.set_selected(None)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(QLabel("Overlays"))

        self.overlay_list = QListWidget()
        # Cap the height so the list doesn't balloon and starve the panels below
        # it inside the control dock; it scrolls internally when overlays overflow.
        self.overlay_list.setMaximumHeight(140)
        self.overlay_list.itemSelectionChanged.connect(self._on_row_changed)
        root.addWidget(self.overlay_list)

        add_row = QHBoxLayout()
        self.add_speech_btn = QPushButton("+Speech")
        self.add_thought_btn = QPushButton("+Thought")
        self.add_caption_btn = QPushButton("+Caption")
        self.add_sfx_btn = QPushButton("+SFX")
        for btn, kind in ((self.add_speech_btn, "speech"),
                          (self.add_thought_btn, "thought"),
                          (self.add_caption_btn, "caption"),
                          (self.add_sfx_btn, "sfx")):
            btn.clicked.connect(lambda _checked=False, k=kind: self.addRequested.emit(k))
            add_row.addWidget(btn)
        root.addLayout(add_row)

        edit_row = QHBoxLayout()
        self.delete_btn = QPushButton("Delete overlay")
        self.delete_btn.clicked.connect(self._on_delete)
        edit_row.addWidget(self.delete_btn)
        self.edit_chk = QCheckBox("Edit on canvas")
        self.edit_chk.toggled.connect(self._on_edit)
        edit_row.addWidget(self.edit_chk)
        edit_row.addStretch(1)
        root.addLayout(edit_row)

        rot_row = QHBoxLayout()
        rot_row.addWidget(QLabel("Rotation:"))
        self.rotation_spin = QSpinBox()
        self.rotation_spin.setRange(0, 359)
        self.rotation_spin.setSuffix("°")
        self.rotation_spin.valueChanged.connect(self._on_rotation)
        rot_row.addWidget(self.rotation_spin)
        rot_row.addStretch(1)
        root.addLayout(rot_row)

    def set_page(self, page: Optional[PageSpec]):
        self.overlay_list.blockSignals(True)
        self.overlay_list.clear()
        if page is not None:
            for ov in page.overlays:
                item = QListWidgetItem(f"{ov.kind}: {ov.text[:20]}")
                item.setData(Qt.UserRole, ov.id)
                item._rotation = int(getattr(ov, "rotation", 0) or 0)
                self.overlay_list.addItem(item)
        self.overlay_list.blockSignals(False)
        self.set_selected(self._selected_id)

    def set_selected(self, overlay_id: Optional[str]):
        self._selected_id = overlay_id
        enabled = overlay_id is not None
        for w in (self.delete_btn, self.rotation_spin, self.edit_chk):
            w.setEnabled(enabled)
        # reflect rotation + edit toggle from the listed item, if present
        rot = 0
        for i in range(self.overlay_list.count()):
            it = self.overlay_list.item(i)
            if it.data(Qt.UserRole) == overlay_id:
                self.overlay_list.blockSignals(True)
                self.overlay_list.setCurrentRow(i)
                self.overlay_list.blockSignals(False)
                rot = getattr(it, "_rotation", 0)
                break
        self.edit_chk.blockSignals(True)
        self.edit_chk.setChecked(False)
        self.edit_chk.blockSignals(False)
        self.rotation_spin.blockSignals(True)
        self.rotation_spin.setValue(int(rot))
        self.rotation_spin.blockSignals(False)

    def _selected_overlay_id(self) -> Optional[str]:
        it = self.overlay_list.currentItem()
        return it.data(Qt.UserRole) if it is not None else None

    def _on_row_changed(self):
        oid = self._selected_overlay_id()
        if oid is not None:
            self._selected_id = oid
            self.overlaySelected.emit(oid)

    def _on_delete(self):
        if self._selected_id is not None:
            self.deleteRequested.emit(self._selected_id)

    def _on_rotation(self, value: int):
        if self._selected_id is not None:
            self.rotationChanged.emit(self._selected_id, int(value))

    def _on_edit(self, checked: bool):
        if self._selected_id is not None:
            self.editToggled.emit(self._selected_id, bool(checked))
