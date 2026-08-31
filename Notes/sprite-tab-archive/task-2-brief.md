### Task 2: Engine presets + fps reconciliation

**Files:**
- Create: `core/sprite/exporters/engine_presets.py`
- Test: `tests/sprite/test_engine_presets.py`

**Interfaces:**
- Consumes: `GridOptions`, `export_grid` (`core/sprite/exporters/grid.py`); `export_aseprite_json`, `export_texturepacker_json`, `export_png_sequence`, `export_gif` (sub-project 1); `export_godot_tres`, `ordered_frame_indices` (Task 1); `ms_to_fps`; `sanitize_filename` (`core/utils.py:14`), `write_image_sidecar`, `sidecar_path` (`core/utils.py:188-233`).
- Produces: `EnginePreset` (frozen dataclass: `id, label, formats, grid, pivot, name_template, how_to_import, json_layout="hash"`); `ENGINE_PRESETS: Dict[str, EnginePreset]`; `FORMAT_IDS`; `ATLAS_FORMATS`; `with_pivot(meta: SheetMeta, pivot) -> SheetMeta` (deep copy with every `FrameMeta.pivot` set); `export_with_preset(meta: SheetMeta, preset_id: str, out_dir: Path) -> List[Path]`; `fps_reconciliation(meta: SheetMeta, target: str) -> List[str]`.

Output naming convention (shared with Task 4 and sub-project 7): the grid PNG is `<sanitized title>.png`; the grid's own Aseprite JSON sidecar stays at `<title>.json`; TexturePacker JSON is `<title>.atlas.json`; explicit Aseprite JSON is `<title>.aseprite.json`; Godot is `<title>.tres`; native Aseprite is `<title>.aseprite`; GIFs are `<title>_<tag>.gif`; PNG frames go to `frames/`.

- [ ] **Step 1: Write the failing test**

Create `tests/sprite/test_engine_presets.py`:

```python
# tests/sprite/test_engine_presets.py
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.sprite.exporters.engine_presets import (
    ATLAS_FORMATS, ENGINE_PRESETS, FORMAT_IDS, EnginePreset,
    export_with_preset, fps_reconciliation, with_pivot,
)
from core.sprite.exporters.grid import GridOptions
from core.sprite.models import FrameMeta, SheetMeta, TagMeta


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
```

- [ ] **Step 2: Run the test to see it fail**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_engine_presets.py -v` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement the presets**

Create `core/sprite/exporters/engine_presets.py`:

```python
"""Engine presets: one call exports everything an engine needs from a SheetMeta."""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from core.sprite.exporters.aseprite_json import export_aseprite_json
from core.sprite.exporters.gif import export_gif
from core.sprite.exporters.godot_tres import export_godot_tres, ordered_frame_indices
from core.sprite.exporters.grid import GridOptions, export_grid
from core.sprite.exporters.png_sequence import export_png_sequence
from core.sprite.exporters.texturepacker_json import export_texturepacker_json
from core.sprite.models import SheetMeta
from core.sprite.timing import ms_to_fps
from core.utils import sanitize_filename, sidecar_path, write_image_sidecar

logger = logging.getLogger(__name__)

FORMAT_IDS: Tuple[str, ...] = (
    "grid", "aseprite_json", "texturepacker_json", "png_sequence", "gif", "godot_tres", "aseprite_native",
)
# Formats that need frame rects from export_grid before they can run.
ATLAS_FORMATS = {"grid", "aseprite_json", "texturepacker_json", "godot_tres"}
GIF_MIN_MS = 20


@dataclass(frozen=True)
class EnginePreset:
    id: str
    label: str
    formats: Tuple[str, ...]
    grid: GridOptions
    pivot: Tuple[float, float]          # normalized, y down; (0.5, 1.0) = bottom-center
    name_template: str                  # png_sequence template
    how_to_import: str
    json_layout: str = "hash"           # aseprite_json / texturepacker_json layout


_DEFAULT_TEMPLATE = "{title}_{tag}_{frame01}.png"

ENGINE_PRESETS: Dict[str, EnginePreset] = {p.id: p for p in (
    EnginePreset(
        id="unity", label="Unity (Sprite Editor / TexturePacker JSON)",
        formats=("grid", "texturepacker_json"),
        grid=GridOptions(columns=0, border_px=0, shape_px=2, inner_px=0, extrude_px=1, power_of_two=False),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE,
        how_to_import=(
            "Import the PNG with Texture Type = Sprite (2D and UI), Sprite Mode = Multiple, and Filter Mode = Point for pixel art. "
            "Open the Sprite Editor and slice with Grid By Cell Size using the cell size from the JSON, or install the TexturePacker Importer package and let it read the .atlas.json. "
            "Set the pivot to Bottom so the feet stay planted."
        ),
    ),
    EnginePreset(
        id="godot4", label="Godot 4 (SpriteFrames .tres)",
        formats=("grid", "godot_tres"),
        grid=GridOptions(columns=0, border_px=0, shape_px=1, inner_px=0, extrude_px=0, power_of_two=False),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE,
        how_to_import=(
            "Copy the PNG and the .tres into the same folder of the Godot project. "
            "Select the PNG, set Filter to Nearest in the Import dock for pixel art, and click Reimport. "
            "Add an AnimatedSprite2D node and assign the .tres as its Sprite Frames. "
            "The .tres references the PNG as res://<png name>, so keep the two files together."
        ),
    ),
    EnginePreset(
        id="phaser3", label="Phaser 3 (atlas JSON hash)",
        formats=("grid", "texturepacker_json"),
        grid=GridOptions(columns=0, border_px=0, shape_px=1, inner_px=0, extrude_px=1, power_of_two=False),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE,
        how_to_import=(
            "Load the atlas in preload() with this.load.atlas('hero', 'hero.png', 'hero.atlas.json'). "
            "Create each animation with this.anims.create({ key: 'walk', frames: this.anims.generateFrameNames('hero', { prefix: 'hero_walk_', start: 1, end: N, zeroPad: 2 }), frameRate: fps, repeat: -1 }). "
            "Set pixelArt: true in the game config for crisp scaling."
        ),
    ),
    EnginePreset(
        id="pixijs", label="PixiJS (spritesheet JSON hash)",
        formats=("grid", "texturepacker_json"),
        grid=GridOptions(columns=0, border_px=0, shape_px=1, inner_px=0, extrude_px=1, power_of_two=False),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE,
        how_to_import=(
            "Load the sheet with const sheet = await Assets.load('hero.atlas.json'); PixiJS resolves the PNG from meta.image. "
            "Build an AnimatedSprite with new AnimatedSprite(sheet.animations['walk']) and set animationSpeed to fps / 60. "
            "Set the texture scale mode to nearest for pixel art."
        ),
    ),
    EnginePreset(
        id="unreal", label="Unreal Engine 5 (Paper2D)",
        formats=("grid", "texturepacker_json"),
        grid=GridOptions(columns=0, border_px=0, shape_px=2, inner_px=0, extrude_px=1, power_of_two=False),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE, json_layout="array",
        how_to_import=(
            "Import the PNG into the Content Browser, then import the .atlas.json; Paper2D reads TexturePacker array JSON and creates one Paper Sprite per frame. "
            "Right-click the texture and choose Sprite Actions > Apply Paper2D Texture Settings for nearest filtering. "
            "Create a Flipbook from the sprites and set Frames Per Second to the fps value."
        ),
    ),
    EnginePreset(
        id="libgdx", label="libGDX (grid + TextureRegion.split)",
        formats=("grid", "aseprite_json"),
        grid=GridOptions(columns=0, border_px=0, shape_px=0, inner_px=0, extrude_px=0, power_of_two=True),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE,
        how_to_import=(
            "Load the PNG as a Texture and call TextureRegion.split(texture, cellWidth, cellHeight); the cell size and the per-tag rows are in the JSON. "
            "Build one Animation<TextureRegion> per tag with frameDuration = 1f / fps. "
            "Set the texture filter to Nearest for pixel art."
        ),
    ),
    EnginePreset(
        id="rpgmaker_mz", label="RPG Maker MZ (character sheet)",
        formats=("grid",),
        grid=GridOptions(columns=3, border_px=0, shape_px=0, inner_px=0, extrude_px=0, power_of_two=False),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE,
        how_to_import=(
            "RPG Maker MZ expects 3 columns per walk cycle and 48x48 cells, so export the pixel profile with a 48x48 cell. "
            "Copy the PNG into img/characters and prefix the file name with $ so MZ reads it as a single-character sheet. "
            "Rows map to down, left, right, and up in that order."
        ),
    ),
    EnginePreset(
        id="web_preview", label="Web preview (GIF + PNG frames)",
        formats=("gif", "png_sequence"),
        grid=GridOptions(),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE,
        how_to_import=(
            "Open a GIF in any browser or image viewer to check the loop. "
            "Use the PNG frames for hand-placed HTML or CSS sprite animations."
        ),
    ),
)}


def _title(meta: SheetMeta) -> str:
    return sanitize_filename(meta.title) or "sprite"


def with_pivot(meta: SheetMeta, pivot: Tuple[float, float]) -> SheetMeta:
    """Deep copy of ``meta`` with every frame pivot set to ``pivot`` (engine presets own the pivot)."""
    copied = copy.deepcopy(meta)
    for frame in copied.frames:
        frame.pivot = (float(pivot[0]), float(pivot[1]))
    return copied


Writer = Callable[[SheetMeta, Path, str, EnginePreset], List[Path]]


def _write_aseprite_json(meta: SheetMeta, out_dir: Path, title: str, preset: EnginePreset) -> List[Path]:
    out = out_dir / f"{title}.aseprite.json"
    export_aseprite_json(meta, out, image_name=f"{title}.png", layout=preset.json_layout)
    return [out]


def _write_texturepacker_json(meta: SheetMeta, out_dir: Path, title: str, preset: EnginePreset) -> List[Path]:
    out = out_dir / f"{title}.atlas.json"
    export_texturepacker_json(meta, out, image_name=f"{title}.png", layout=preset.json_layout)
    return [out]


def _write_godot_tres(meta: SheetMeta, out_dir: Path, title: str, preset: EnginePreset) -> List[Path]:
    out = export_godot_tres(meta, out_dir / f"{title}.tres", atlas_res_path=f"res://{title}.png")
    return [out, sidecar_path(out)]


def _write_png_sequence(meta: SheetMeta, out_dir: Path, title: str, preset: EnginePreset) -> List[Path]:
    return list(export_png_sequence(meta, out_dir / "frames", template=preset.name_template))


def _write_gif(meta: SheetMeta, out_dir: Path, title: str, preset: EnginePreset) -> List[Path]:
    paths: List[Path] = []
    for tag in meta.tags:
        out = export_gif(meta, tag, out_dir / f"{title}_{tag.name}.gif")
        write_image_sidecar(out, {
            "format": "gif", "title": meta.title, "tag": tag.name, "profile": meta.profile,
            "frames": tag.to_index - tag.from_index + 1, "direction": tag.direction,
            "app": meta.app, "version": meta.version,
        })
        paths.extend([out, sidecar_path(out)])
    return paths


def _write_aseprite_native(meta: SheetMeta, out_dir: Path, title: str, preset: EnginePreset) -> List[Path]:
    from core.sprite.exporters.aseprite_native import export_aseprite  # Task 3
    out = export_aseprite(meta, out_dir / f"{title}.aseprite")
    return [out, sidecar_path(out)]


FORMAT_WRITERS: Dict[str, Writer] = {
    "aseprite_json": _write_aseprite_json,
    "texturepacker_json": _write_texturepacker_json,
    "godot_tres": _write_godot_tres,
    "png_sequence": _write_png_sequence,
    "gif": _write_gif,
    "aseprite_native": _write_aseprite_native,
}


def export_with_preset(meta: SheetMeta, preset_id: str, out_dir: Path) -> List[Path]:
    """Run every exporter of ``preset_id`` into ``out_dir``; return the written paths."""
    preset = ENGINE_PRESETS.get(preset_id)
    if preset is None:
        raise ValueError(f"Unknown engine preset {preset_id!r}; known: {', '.join(sorted(ENGINE_PRESETS))}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    title = _title(meta)
    meta = with_pivot(meta, preset.pivot)
    written: List[Path] = []
    laid = meta
    if ATLAS_FORMATS.intersection(preset.formats):
        png = out_dir / f"{title}.png"
        laid = export_grid(meta, png, preset.grid)
        written.append(png)
        for candidate in (png.with_suffix(".json"), sidecar_path(png)):
            if candidate.exists():
                written.append(candidate)
                break
    for fmt in preset.formats:
        if fmt == "grid":
            continue
        writer = FORMAT_WRITERS.get(fmt)
        if writer is None:
            raise ValueError(f"Preset {preset_id!r} names unknown format {fmt!r}")
        written.extend(writer(laid, out_dir, title, preset))
    logger.info("Engine preset %s exported %d file(s) to %s", preset_id, len(written), out_dir)
    return written


def fps_reconciliation(meta: SheetMeta, target: str) -> List[str]:
    """Human-readable notes about timing that the target cannot represent exactly."""
    notes: List[str] = []
    if target == "godot":
        for tag in meta.tags:
            indices = ordered_frame_indices(tag)
            durations = [meta.frames[i].duration_ms for i in indices]
            if not durations:
                continue
            fps, multipliers = ms_to_fps(durations)
            base_ms = 1000.0 / fps
            for i, (orig, mult) in enumerate(zip(durations, multipliers), start=1):
                played = mult * base_ms
                drift = played - orig
                if abs(drift) >= 0.5:
                    notes.append(
                        f"Godot: tag '{tag.name}' frame {i} plays {played:.1f} ms at {fps} fps "
                        f"(source {orig} ms, drift {drift:+.1f} ms)."
                    )
            if tag.direction != "forward":
                notes.append(
                    f"Godot: tag '{tag.name}' direction '{tag.direction}' is unrolled into "
                    f"{len(indices)} frames because SpriteFrames has no direction field."
                )
            if tag.repeat > 1:
                notes.append(f"Godot: tag '{tag.name}' repeat={tag.repeat} becomes loop=false; Godot loops forever or plays once.")
        return notes
    if target == "gif":
        for i, frame in enumerate(meta.frames, start=1):
            ms = frame.duration_ms
            if ms < GIF_MIN_MS:
                notes.append(f"GIF: frame {i} duration {ms} ms is below {GIF_MIN_MS} ms; the exporter writes 20 ms and browsers may clamp it to 100 ms.")
            elif ms % 10:
                notes.append(f"GIF: frame {i} duration {ms} ms rounds to {round(ms / 10) * 10} ms because GIF stores centiseconds.")
        return notes
    raise ValueError(f"Unknown reconciliation target {target!r}; use 'godot' or 'gif'")
```

- [ ] **Step 4: Run the test to see it pass**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_engine_presets.py -v` → 11 passed. If `test_web_preview_writes_gif_per_tag_and_frames` fails on the `frames` parent name, check the sub-project 1 `export_png_sequence` return value; it must return the written frame paths.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/exporters/engine_presets.py tests/sprite/test_engine_presets.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): engine presets (8 targets) with one-call export and fps reconciliation"
```

---

