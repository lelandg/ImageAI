"""Engine preset picker for the sprite ExportDialog."""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout

from core.sprite.exporters.engine_presets import ENGINE_PRESETS, EnginePreset, fps_reconciliation
from core.sprite.models import SheetMeta

logger = logging.getLogger(__name__)

CUSTOM_ID = ""


class EnginePresetBox(QGroupBox):
    """Combo of engine presets plus a notes label (how to import + timing notes)."""

    presetChosen = Signal(str)   # preset id; "" = custom

    def __init__(self, parent=None, *, notes_label: Optional[QLabel] = None):
        """``notes_label``: reuse the dialog's own label (5b ``ExportDialog.notes_label``) when given."""
        super().__init__("Engine preset", parent)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Target:"))
        self.combo = QComboBox()
        self.combo.addItem("Custom", CUSTOM_ID)
        for preset in ENGINE_PRESETS.values():
            self.combo.addItem(preset.label, preset.id)
        row.addWidget(self.combo, 1)
        layout.addLayout(row)
        if notes_label is None:
            notes_label = QLabel("")
            layout.addWidget(notes_label)
        self.notes = notes_label
        self.notes.setWordWrap(True)
        self.notes.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.combo.currentIndexChanged.connect(self._on_changed)

    def current_preset(self) -> Optional[EnginePreset]:
        return ENGINE_PRESETS.get(self.combo.currentData())

    def select(self, preset_id: str) -> None:
        index = self.combo.findData(preset_id)
        if index < 0:
            logger.warning("EnginePresetBox.select: unknown preset %r", preset_id)
            return
        self.combo.setCurrentIndex(index)

    def show_notes(self, meta: Optional[SheetMeta]) -> None:
        preset = self.current_preset()
        if preset is None:
            self.notes.setText("")
            return
        lines = [preset.how_to_import]
        if meta is not None and meta.frames:
            if "godot_tres" in preset.formats:
                lines.extend(fps_reconciliation(meta, "godot"))
            if "gif" in preset.formats:
                lines.extend(fps_reconciliation(meta, "gif"))
        self.notes.setText("\n\n".join(lines))

    def _on_changed(self, _index: int) -> None:
        self.presetChosen.emit(self.combo.currentData())


def install_engine_presets(dialog) -> EnginePresetBox:
    """Insert an EnginePresetBox above the formats box and drive the dialog fields from it.

    Notes go to the dialog's own ``notes_label`` (5b), which sits directly under the formats box.
    """
    box = EnginePresetBox(dialog, notes_label=dialog.notes_label)
    dialog.options_layout.insertWidget(1, box)      # index 0 = profiles box, then this, then formats

    def apply(preset_id: str) -> None:
        preset = ENGINE_PRESETS.get(preset_id)
        if preset is None:
            box.show_notes(None)
            return
        for fmt_id, check in dialog.format_checks.items():
            check.setChecked(fmt_id in preset.formats)
        dialog.set_grid_options(preset.grid)
        dialog.pivot_x_spin.setValue(preset.pivot[0])
        dialog.pivot_y_spin.setValue(preset.pivot[1])
        dialog.name_template_edit.setText(preset.name_template)
        box.show_notes(dialog.current_meta())
        logger.info("Export dialog: applied engine preset %s (formats %s)", preset_id, list(preset.formats))

    box.presetChosen.connect(apply)
    dialog.engine_preset_box = box
    return box
