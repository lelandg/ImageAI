"""Geometry inspector: per-region bleed / borderless / z toggles.

Emits intent signals; ``LayoutTab`` owns the model mutation (same split as
ContentInspector). The "Edit shape" toggle is added in #5a Task 4.
"""
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QSpinBox,
)
from PySide6.QtCore import Signal

from core.layout.models import Region


class GeometryInspector(QWidget):
    bleedToggled = Signal(str, bool)        # (region_id, bleed)
    borderlessToggled = Signal(str, bool)   # (region_id, borderless)
    zChanged = Signal(str, int)             # (region_id, z)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._region: Optional[Region] = None
        self._build()
        self.set_region(None)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.header = QLabel("No region selected")
        self.header.setStyleSheet("font-weight: bold;")
        root.addWidget(self.header)

        self.shape_label = QLabel("")
        self.shape_label.setStyleSheet("color: #666; font-size: 11px;")
        root.addWidget(self.shape_label)

        self.bleed_chk = QCheckBox("Bleed (extend to page edge)")
        self.bleed_chk.toggled.connect(self._on_bleed)
        root.addWidget(self.bleed_chk)

        self.borderless_chk = QCheckBox("Borderless (no panel stroke)")
        self.borderless_chk.toggled.connect(self._on_borderless)
        root.addWidget(self.borderless_chk)

        z_row = QHBoxLayout()
        z_row.addWidget(QLabel("Z-order:"))
        self.z_spin = QSpinBox()
        self.z_spin.setRange(-1000, 1000)
        self.z_spin.valueChanged.connect(self._on_z)
        z_row.addWidget(self.z_spin)
        z_row.addStretch(1)
        root.addLayout(z_row)

    def set_region(self, region: Optional[Region]):
        self._region = region
        enabled = region is not None
        for w in (self.bleed_chk, self.borderless_chk, self.z_spin):
            w.setEnabled(enabled)
        if region is None:
            self.header.setText("No region selected")
            self.shape_label.setText("")
            return
        self.header.setText(f"Geometry: {region.name or region.id}")
        self.shape_label.setText(f"shape: {region.shape}")
        stroke = region.image_style.stroke_px if region.image_style else 0
        self.bleed_chk.blockSignals(True)
        self.bleed_chk.setChecked(bool(region.bleed))
        self.bleed_chk.blockSignals(False)
        self.borderless_chk.blockSignals(True)
        self.borderless_chk.setChecked(stroke == 0)
        self.borderless_chk.blockSignals(False)
        self.z_spin.blockSignals(True)
        self.z_spin.setValue(int(region.z))
        self.z_spin.blockSignals(False)

    def _on_bleed(self, checked: bool):
        if self._region is not None:
            self.bleedToggled.emit(self._region.id, bool(checked))

    def _on_borderless(self, checked: bool):
        if self._region is not None:
            self.borderlessToggled.emit(self._region.id, bool(checked))

    def _on_z(self, value: int):
        if self._region is not None:
            self.zChanged.emit(self._region.id, int(value))
