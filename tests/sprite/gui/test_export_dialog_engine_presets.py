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
        Image.fromarray(arr).save(p)
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
