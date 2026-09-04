### Task 4: Export dialog — register the two formats and add the engine-preset box

**Files:**
- Create: `gui/sprite/export_formats.py`
- Create: `gui/sprite/engine_preset_box.py`
- Modify: `gui/sprite/export_dialog.py` (5b) — two calls at the end of `__init__`
- Test: `tests/sprite/gui/test_export_dialog_engine_presets.py`

**Interfaces:**
- Consumes (5b `gui/sprite/export_dialog.py`): `ExportDialog.register_format(id, label, fn, *, needs_sheet=False, takes_template=False, checked=False) -> QCheckBox` with `fn(meta: SheetMeta, out_dir: Path) -> List[Path]`; with `needs_sheet=True` the dialog has already run the grid exporter, so `meta` arrives with frame rects filled and the sheet PNG sits at `sheet_png_path(meta, out_dir)` (module-level function); widgets `format_checks: Dict[str, QCheckBox]`, `options_layout: QVBoxLayout` (profiles box at index 0, then formats box, `notes_label`, output box, grid box), `notes_label: QLabel` (word-wrapped, under the formats box, empty by default — the preset notes go here), `pivot_x_spin` / `pivot_y_spin: QDoubleSpinBox`, `name_template_edit: QLineEdit`; `set_grid_options(GridOptions)`, `current_meta() -> Optional[SheetMeta]`. Also `ENGINE_PRESETS`, `FORMAT_IDS`, `fps_reconciliation` (Task 2), `export_godot_tres` (Task 1), `export_aseprite` (Task 3).
- Produces: `FORMAT_GODOT = "godot_tres"`, `FORMAT_ASEPRITE = "aseprite_native"`; `write_godot_tres(meta, out_dir) -> List[Path]`; `write_aseprite_native(meta, out_dir) -> List[Path]`; `register_extra_formats(dialog) -> None`; `EnginePresetBox(QGroupBox)` with `presetChosen = Signal(str)`, `current_preset()`, `select(preset_id)`, `show_notes(meta)`; `install_engine_presets(dialog) -> EnginePresetBox` (also sets `dialog.engine_preset_box`).

Format ids are shared verbatim between `EnginePreset.formats` (Task 2 `FORMAT_IDS`), the dialog's built-ins (`grid`, `aseprite_json`, `texturepacker_json`, `png_sequence`, `gif`), the two ids registered here (`godot_tres`, `aseprite_native`), and the CLI's `--sprite-formats` (sub-project 7). Output names: `.tres` and `.aseprite` are `<title>_<profile>` beside the sheet; `atlas_res_path` is `res://<sheet_png_path(meta, out_dir).name>`.

- [ ] **Step 1: Write the failing test**

Create `tests/sprite/gui/test_export_dialog_engine_presets.py`:

```python
# tests/sprite/gui/test_export_dialog_engine_presets.py
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QLabel, QLineEdit, QVBoxLayout, QWidget

from core.sprite.exporters.engine_presets import ENGINE_PRESETS, FORMAT_IDS
from core.sprite.exporters.grid import GridOptions, export_grid
from core.sprite.models import FrameMeta, SheetMeta, TagMeta
from gui.sprite.engine_preset_box import EnginePresetBox, install_engine_presets
from gui.sprite.export_dialog import sheet_png_path
from gui.sprite.export_formats import (
    FORMAT_ASEPRITE, FORMAT_GODOT, register_extra_formats, write_aseprite_native, write_godot_tres,
)


class _FakeDialog(QWidget):
    """Only the ExportDialog surface that the preset box and registration touch (5b names)."""

    def __init__(self, meta=None):
        super().__init__()
        self.options_layout = QVBoxLayout(self)
        self.options_layout.addWidget(QLabel("profiles box stand-in", self))
        self.format_checks = {fid: QCheckBox(fid, self) for fid in FORMAT_IDS}
        self.notes_label = QLabel("", self)
        self.grid = GridOptions()
        self.pivot_x_spin = QDoubleSpinBox(self)
        self.pivot_y_spin = QDoubleSpinBox(self)
        self.name_template_edit = QLineEdit(self)
        self._meta = meta
        self.registered = {}

    def set_grid_options(self, opts):
        self.grid = opts

    def grid_options(self):
        return self.grid

    def current_meta(self):
        return self._meta

    def register_format(self, fid, label, fn, *, needs_sheet=False, takes_template=False, checked=False):
        self.registered[fid] = (label, fn, needs_sheet)
        box = QCheckBox(label, self)
        box.setChecked(checked)
        self.format_checks[fid] = box
        return box


def _laid_out(tmp_path: Path, meta: SheetMeta):
    """What the 5b export runner does before a needs_sheet format runs: grid export into out_dir."""
    out = tmp_path / "out" / "hd"
    out.mkdir(parents=True, exist_ok=True)
    laid = export_grid(meta, sheet_png_path(meta, out), GridOptions())
    return laid, out


def _meta(tmp_path: Path) -> SheetMeta:
    frames = []
    for i in range(2):
        arr = np.zeros((8, 8, 4), dtype=np.uint8)
        arr[1:7, 1:7] = (200, 30 * i, 50, 255)
        p = tmp_path / f"{i + 1:04d}.png"
        Image.fromarray(arr, "RGBA").save(p)
        frames.append(FrameMeta(name=f"hero_{i}", source_path=p, frame=(0, 0, 8, 8),
                                sprite_source_size=(0, 0, 8, 8), source_size=(8, 8), duration_ms=133))
    return SheetMeta(title="hero", frames=frames, tags=[TagMeta(name="walk", from_index=0, to_index=1)], cell_size=(8, 8))


def test_box_lists_custom_plus_every_preset(qapp):
    box = EnginePresetBox()
    ids = [box.combo.itemData(i) for i in range(box.combo.count())]
    assert ids[0] == "" and ids[1:] == list(ENGINE_PRESETS)
    assert box.current_preset() is None


def test_preset_formats_are_dialog_format_ids():
    assert FORMAT_GODOT in FORMAT_IDS and FORMAT_ASEPRITE in FORMAT_IDS
    for preset in ENGINE_PRESETS.values():
        assert set(preset.formats) <= set(FORMAT_IDS), preset.id


def test_selecting_preset_applies_fields_and_notes(qapp, tmp_path):
    dialog = _FakeDialog(meta=_meta(tmp_path))
    box = install_engine_presets(dialog)
    assert dialog.engine_preset_box is box
    box.select("godot4")
    preset = ENGINE_PRESETS["godot4"]
    checked = {fid for fid, c in dialog.format_checks.items() if c.isChecked()}
    assert checked == set(preset.formats) == {"grid", FORMAT_GODOT}
    assert dialog.grid == preset.grid
    assert (dialog.pivot_x_spin.value(), dialog.pivot_y_spin.value()) == preset.pivot
    assert dialog.name_template_edit.text() == preset.name_template
    assert box.notes is dialog.notes_label                       # notes reuse the dialog's label
    assert preset.how_to_import in dialog.notes_label.text()
    assert "drift" in dialog.notes_label.text()                  # 133 ms cannot be represented exactly at integer fps
    assert dialog.options_layout.indexOf(box) == 1


def test_unity_and_libgdx_presets_check_their_formats(qapp, tmp_path):
    dialog = _FakeDialog()
    box = install_engine_presets(dialog)
    box.select("unity")
    assert {fid for fid, c in dialog.format_checks.items() if c.isChecked()} == {"grid", "texturepacker_json"}
    box.select("libgdx")
    assert {fid for fid, c in dialog.format_checks.items() if c.isChecked()} == {"grid", "aseprite_json"}


def test_custom_clears_notes_and_missing_meta_is_tolerated(qapp, tmp_path):
    dialog = _FakeDialog(meta=None)
    box = install_engine_presets(dialog)
    box.select("godot4")
    assert ENGINE_PRESETS["godot4"].how_to_import in dialog.notes_label.text()
    box.select("")
    assert dialog.notes_label.text() == ""


def test_register_extra_formats(qapp):
    dialog = _FakeDialog()
    register_extra_formats(dialog)
    assert set(dialog.registered) == {FORMAT_GODOT, FORMAT_ASEPRITE}
    assert dialog.registered[FORMAT_GODOT] == ("Godot 4 SpriteFrames (.tres + sheet PNG)", write_godot_tres, True)
    assert dialog.registered[FORMAT_ASEPRITE][1] is write_aseprite_native
    assert dialog.registered[FORMAT_ASEPRITE][2] is False


def test_write_godot_tres_uses_runner_sheet(tmp_path):
    laid, out = _laid_out(tmp_path, _meta(tmp_path))
    written = write_godot_tres(laid, out)
    tres = out / "hero_hd.tres"
    assert written == [tres] and tres.exists()
    assert f'path="res://{sheet_png_path(laid, out).name}"' in tres.read_text(encoding="utf-8")
    assert (out / "hero_hd.tres.json").exists()


def test_write_godot_tres_requires_sheet(tmp_path):
    out = tmp_path / "out" / "hd"
    out.mkdir(parents=True)
    with pytest.raises(ValueError):
        write_godot_tres(_meta(tmp_path), out)          # no rects and no sheet on disk


def test_write_aseprite_native(tmp_path):
    out = tmp_path / "out" / "hd"
    out.mkdir(parents=True)
    written = write_aseprite_native(_meta(tmp_path), out)
    assert written == [out / "hero_hd.aseprite"] and written[0].exists()
```

- [ ] **Step 2: Run the test to see it fail**

`QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_export_dialog_engine_presets.py -v` → `ModuleNotFoundError: gui.sprite.engine_preset_box`.

- [ ] **Step 3: Implement the format writers**

Create `gui/sprite/export_formats.py`:

```python
"""Extra export formats registered into the sprite ExportDialog (sub-project 6).

``gui.sprite.export_dialog`` imports this module at load time, so the
``sheet_png_path`` import below stays inside the function.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from core.sprite.exporters.aseprite_native import export_aseprite
from core.sprite.exporters.godot_tres import export_godot_tres
from core.sprite.models import SheetMeta

logger = logging.getLogger(__name__)

FORMAT_GODOT = "godot_tres"
FORMAT_ASEPRITE = "aseprite_native"


def _stem(meta: SheetMeta) -> str:
    return f"{meta.title}_{meta.profile}"


def write_godot_tres(meta: SheetMeta, out_dir: Path) -> List[Path]:
    """``<title>_<profile>.tres`` beside the sheet PNG the export runner wrote (needs_sheet=True)."""
    from gui.sprite.export_dialog import sheet_png_path
    out_dir = Path(out_dir)
    png = sheet_png_path(meta, out_dir)
    if tuple(meta.sheet_size) == (0, 0) or not png.exists():
        raise ValueError(f"godot_tres needs the sheet PNG at {png}; register it with needs_sheet=True")
    out = export_godot_tres(meta, out_dir / f"{_stem(meta)}.tres", atlas_res_path=f"res://{png.name}")
    logger.info("Godot SpriteFrames: %s", out)
    return [out]


def write_aseprite_native(meta: SheetMeta, out_dir: Path) -> List[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = export_aseprite(meta, out_dir / f"{_stem(meta)}.aseprite")
    logger.info("Aseprite file: %s", out)
    return [out]


def register_extra_formats(dialog) -> None:
    """Register the sub-project 6 formats on an ExportDialog (5b ``register_format`` contract)."""
    dialog.register_format(FORMAT_GODOT, "Godot 4 SpriteFrames (.tres + sheet PNG)", write_godot_tres,
                           needs_sheet=True)
    dialog.register_format(FORMAT_ASEPRITE, "Aseprite file (.aseprite)", write_aseprite_native)
```

- [ ] **Step 4: Implement the preset box**

Create `gui/sprite/engine_preset_box.py`:

```python
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
```

- [ ] **Step 5: Wire the dialog (5b file)**

Modify `gui/sprite/export_dialog.py`: add the two imports at module top and, in `ExportDialog.__init__`, right after the built-in formats are registered and before saved settings are restored (so saved format choices still apply to the new checkboxes), add:

```python
from gui.sprite.engine_preset_box import install_engine_presets
from gui.sprite.export_formats import register_extra_formats
...
        register_extra_formats(self)
        install_engine_presets(self)
```

- [ ] **Step 6: Run the tests to see them pass**

`QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui -v` → the 9 new tests pass and the 5b export-dialog tests still pass (the two new ids appear at the end of `formats()`).

- [ ] **Step 7: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/export_formats.py gui/sprite/engine_preset_box.py gui/sprite/export_dialog.py tests/sprite/gui/test_export_dialog_engine_presets.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): export dialog gains Godot/.aseprite formats and an engine-preset picker"
```

---

