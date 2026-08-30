# tests/sprite/test_engine_presets.py
import dataclasses
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.sprite.exporters import engine_presets as engine_presets_mod
from core.sprite.exporters.engine_presets import (
    ATLAS_FORMATS, ENGINE_PRESETS, FORMAT_IDS, EnginePreset,
    export_with_preset, fps_reconciliation, with_pivot,
)
from core.sprite.exporters.grid import GridOptions
from core.sprite.models import FrameMeta, SheetMeta, TagMeta


def _on_disk_recursive(out_dir: Path) -> list:
    return sorted(str(p.relative_to(out_dir)) for p in Path(out_dir).rglob("*") if p.is_file())


def _png(path: Path, shade: int) -> Path:
    arr = np.zeros((8, 8, 4), dtype=np.uint8)
    arr[2:6, 2:6] = (shade, 40, 200, 255)
    Image.fromarray(arr, "RGBA").save(path)
    return path


def _meta(tmp_path: Path, durations=(100, 100, 100, 100)) -> SheetMeta:
    frames = []
    for i, ms in enumerate(durations):
        p = _png(tmp_path / f"{i + 1:04d}.png", 30 * i)
        frames.append(FrameMeta(name=f"hero_{i}", source_path=p, frame=(0, 0, 8, 8),
                                sprite_source_size=(0, 0, 8, 8), source_size=(8, 8), duration_ms=ms))
    tags = [TagMeta(name="walk", from_index=0, to_index=1), TagMeta(name="idle", from_index=2, to_index=3)]
    return SheetMeta(title="hero", frames=frames, tags=tags, cell_size=(8, 8))


def test_every_preset_is_well_formed():
    assert set(ENGINE_PRESETS) == {"unity", "godot4", "phaser3", "pixijs", "unreal", "libgdx", "rpgmaker_mz", "web_preview"}
    for pid, preset in ENGINE_PRESETS.items():
        assert isinstance(preset, EnginePreset) and preset.id == pid
        assert preset.formats and set(preset.formats) <= set(FORMAT_IDS)
        assert isinstance(preset.grid, GridOptions)
        assert 0.0 <= preset.pivot[0] <= 1.0 and 0.0 <= preset.pivot[1] <= 1.0
        assert preset.name_template.endswith(".png")
        sentences = [s for s in preset.how_to_import.replace("\n", " ").split(". ") if s.strip()]
        assert 2 <= len(sentences) <= 5, pid
        assert preset.json_layout in ("hash", "array")


def test_godot4_preset_writes_png_and_tres(tmp_path):
    out = tmp_path / "out"
    written = export_with_preset(_meta(tmp_path), "godot4", out)
    names = {p.name for p in written}
    assert {"hero.png", "hero.tres", "hero.tres.json"} <= names
    tres = (out / "hero.tres").read_text(encoding="utf-8")
    assert 'path="res://hero.png"' in tres and tres.count('[sub_resource type="AtlasTexture"') == 4
    assert all(p.exists() for p in written)


def test_phaser3_preset_writes_atlas_json(tmp_path):
    written = export_with_preset(_meta(tmp_path), "phaser3", tmp_path / "out")
    assert (tmp_path / "out" / "hero.atlas.json").exists()
    assert (tmp_path / "out" / "hero.png").exists()
    assert (tmp_path / "out" / "hero.atlas.json") in written


def test_web_preview_writes_gif_per_tag_and_frames(tmp_path):
    written = export_with_preset(_meta(tmp_path), "web_preview", tmp_path / "out")
    names = {p.name for p in written}
    assert {"hero_walk.gif", "hero_idle.gif"} <= names
    assert (tmp_path / "out" / "hero_walk.gif.json").exists()
    assert any(p.parent.name == "frames" for p in written)
    assert not (tmp_path / "out" / "hero.png").exists()  # no atlas format requested


def test_unknown_preset_raises():
    with pytest.raises(ValueError):
        export_with_preset(SheetMeta(title="x", frames=[], tags=[]), "gamemaker", Path("."))


def test_atlas_formats_subset():
    assert ATLAS_FORMATS <= set(FORMAT_IDS)


def test_with_pivot_copies_and_sets_every_frame(tmp_path):
    meta = _meta(tmp_path)
    pivoted = with_pivot(meta, (0.25, 0.75))
    assert all(f.pivot == (0.25, 0.75) for f in pivoted.frames)
    assert all(f.pivot == (0.5, 1.0) for f in meta.frames)      # original untouched


def test_fps_reconciliation_godot_reports_drift_and_unrolling(tmp_path):
    meta = _meta(tmp_path, durations=(100, 133, 100, 100))
    meta.tags[0].direction = "pingpong"
    meta.tags[0].to_index = 2
    notes = fps_reconciliation(meta, "godot")
    assert any("drift" in n for n in notes)
    assert any("unrolled" in n for n in notes)


def test_fps_reconciliation_godot_clean_when_uniform(tmp_path):
    assert fps_reconciliation(_meta(tmp_path), "godot") == []


def test_fps_reconciliation_gif_clamp_and_rounding(tmp_path):
    meta = _meta(tmp_path, durations=(15, 105, 100, 100))
    notes = fps_reconciliation(meta, "gif")
    assert any("frame 1" in n and "20 ms" in n for n in notes)
    assert any("frame 2" in n and "rounds" in n for n in notes)


def test_fps_reconciliation_unknown_target(tmp_path):
    with pytest.raises(ValueError):
        fps_reconciliation(_meta(tmp_path), "unity")


def test_manifest_matches_every_file_on_disk_for_atlas_preset(tmp_path):
    """The returned list is the export manifest: it must name every file written, no more, no less."""
    out = tmp_path / "out"
    written = export_with_preset(_meta(tmp_path), "phaser3", out)
    reported = sorted(str(p.relative_to(out)) for p in written)
    assert reported == _on_disk_recursive(out)
    # both grid sidecars are present, not just the first one found on disk
    assert "hero.json" in reported and "hero.png.json" in reported


def test_manifest_includes_every_scale_sheet_and_its_sidecars(tmp_path, monkeypatch):
    """Presets whose GridOptions carries multiple scales must report every @Nx PNG + its two sidecars."""
    base = ENGINE_PRESETS["phaser3"]
    scaled_grid = dataclasses.replace(base.grid, scales=(1, 2))
    scaled_preset = dataclasses.replace(base, grid=scaled_grid)
    monkeypatch.setitem(engine_presets_mod.ENGINE_PRESETS, "phaser3", scaled_preset)

    out = tmp_path / "out"
    written = export_with_preset(_meta(tmp_path), "phaser3", out)
    names = {p.name for p in written}
    assert {"hero.png", "hero.json", "hero.png.json",
            "hero@2x.png", "hero@2x.json", "hero@2x.png.json"} <= names
    reported = sorted(str(p.relative_to(out)) for p in written)
    assert reported == _on_disk_recursive(out)
