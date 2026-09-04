# Sprite Core Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `Plans/2026-08-29-sprite-tab-design.md` (§1, §2, §4.1, §5). Read it first.
**Goal:** Ship the headless sprite spine: data model, project persistence, presets, undo, the cached stage pipeline with its cancel/progress contract, frame extraction, sheet slicing, crop-and-pad stabilisation, and the five exporters, all under `core/sprite/` with tests under `tests/sprite/`.
**Architecture:** `core/sprite/` is pure Python (Pillow, numpy, OpenCV, ffmpeg via `core/video/ffmpeg_utils.py`), never Qt. `SheetMeta` is the single source of truth; every exporter is a pure function of it. `run_pipeline` walks `STAGES` in order, dispatches each stage through the `STAGE_RUNNERS` registry (`register_stage` lets sub-projects 3 and 4 replace the identity stages without touching the loop), skips a stage whose SHA-1 fingerprint (upstream fingerprint + `STAGE_SETTINGS[stage](project, action)` JSON + `STAGE_CODE_VERSION[stage]`) matches the recorded one, and writes `stages/<action_id>/<stage>/0001.png…`. External inputs enter at `extract` (video) or after it (PNG sequence, sheet).
**Tech Stack:** Python 3.12 (`.venv_linux`), Pillow 11.3, numpy 2.2, opencv-python 4.12, ffmpeg (system or the `imageio-ffmpeg` binary), pytest.
**Sub-project:** 1 of 8 — no dependencies on other sprite plans. Sub-projects 2–7 consume this one's public API.

## Global Constraints

- Branch: `feat/sprite-tab` (already checked out; the design spec is committed at `25788d3`). Never commit to `main`.
- Never `cd`. Use absolute paths everywhere. Git runs as `git -C /mnt/d/Documents/Code/GitHub/ImageAI …`.
- Python: every command below starts with `PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python` and runs tests as `$PY -m pytest <absolute path> -v`. The Bash working directory is the repo root; `python -m pytest` puts it on `sys.path`, which the `core` and `tests` imports need.
- GUI tests need `QT_QPA_PLATFORM=offscreen`; `tests/conftest.py` sets it. This sub-project has no GUI tests.
- Paths: `core/paths.py` owns every data location. Call `get_data_paths().sprite_projects()` and `.sprite_configs()`. Never join a platform directory by hand. `tests/test_no_hardcoded_paths.py` fails the build on a hand-built path.
- Sidecars: every exported PNG gets a `.png.json` sidecar through `core.utils.write_image_sidecar`; every exported GIF gets `<name>.gif.json` through `core.utils.sidecar_path`. Stage intermediates under `stages/` are cache, not artifacts, and get no sidecar.
- Images are scaled proportionally, never cropped to a different aspect and never distorted. `crop_and_pad` uses one scale factor for both axes.
- Conventional Commits. Commit at the end of every task with the exact command given. No version bump and no `CHANGELOG.md` entry in this sub-project (sub-project 7 owns the bump).
- No new hard dependencies. Only Pillow, numpy, opencv-python and ffmpeg. scikit-image/scipy arrive with sub-project 3.
- `core/sprite/` never imports PySide6. A test pins it.
- Prose in docstrings and messages: active voice, short sentences.

## Verified facts about this machine (2026-08-29)

- `which ffmpeg` finds nothing, but `core.video.ffmpeg_utils.get_ffmpeg_path()` returns the `imageio-ffmpeg` binary (`…/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2`). It encodes H.264 and runs the `select` and `fps` filters. It ships **no ffprobe**, so `probe_video` falls back to OpenCV.
- The prototype of every module in this plan passed 110 sprite tests + 5 migration-pin tests, plus the full existing suite (1062 passed, 19 skipped) against a shadow copy of the repo. The code blocks below are that prototype, verbatim.
- `core/video/__init__.py` imports the cloud video clients (`google.genai`, about 6 s). `core/sprite` therefore imports `core.video.ffmpeg_utils` lazily inside the two functions that need ffmpeg; `import core.sprite` takes under 1 s and a test pins that `core.video` stays out of `sys.modules`.
- Pillow 11.3 writes a per-frame `duration` in GIF centiseconds: 83 ms becomes 80 ms. The GIF exporter rounds on purpose and reports it.

## File Structure

| Path | Responsibility |
|---|---|
| `core/sprite/__init__.py` | Package docstring (Task 1); public API re-exports (Task 15) |
| `core/sprite/models.py` | `Rect`, `Size`, `FrameMeta`, `TagMeta`, `SheetMeta` with `to_dict`/`from_dict`/`frames_for` |
| `core/sprite/project.py` | Settings dataclasses, `ActionCard`, `ClipRecord`, `CostEntry`, `SpriteProject` (save/load/reanchor/sheet_meta/total_cost/purge), `SpriteProjectManager` |
| `core/sprite/presets.py` | Cell/canvas/fps/genre presets, `parse_cell_size`, integer-scale calculator |
| `core/sprite/undo.py` | `FrameListSnapshot`, `SnapshotStack` |
| `core/sprite/pipeline.py` | `CancelToken`, `Cancelled`, `ProgressFn`, `no_progress`, `STAGES`, the stage registry (`StageRunner`, `SettingsFn`, `STAGE_RUNNERS`, `STAGE_SETTINGS`, `STAGE_CODE_VERSION`, `register_stage`), fingerprints, `stage_dir`, `register_external_frames`, the default runners, `run_pipeline` |
| `core/sprite/extract.py` | `probe_video`, `extract_frames`, `estimate_frame_count`, `cull_duplicates`, `FFmpegError`, `ExtractResult` |
| `core/sprite/slicing.py` | `GridGuess`, `guess_grid`, `slice_sheet`, `import_png_sequence` |
| `core/sprite/stabilize.py` | `union_alpha_bbox`, `solid_border_bbox`, `crop_and_pad`, anchors |
| `core/sprite/exporters/__init__.py` | Exporter re-exports |
| `core/sprite/exporters/grid.py` | `GridOptions`, `export_grid` (padding, extrude, power-of-two, @2x/@4x, Aseprite sidecar) |
| `core/sprite/exporters/aseprite_json.py` | `export_aseprite_json` (hash + array) |
| `core/sprite/exporters/texturepacker_json.py` | `export_texturepacker_json` (hash + array + pivot + animations) |
| `core/sprite/exporters/png_sequence.py` | `export_png_sequence`, `export_single_frame`, name templates |
| `core/sprite/exporters/gif.py` | `export_gif` with the safe transparent recipe |
| `core/paths.py` (modify) | `sprite_projects()` and `sprite_configs()` accessors |
| `core/data_migration.py` (modify) | `"sprites"` in `GROUP_CONTENTS[Group.IMAGES]`; `"sprite_configs.json"` in `SETTINGS_FILES` |
| `tests/test_paths.py` (modify) | Two accessor assertions |
| `tests/migration/test_sprite_storage.py` | Pins the migration-journal entries |
| `tests/sprite/__init__.py` | Makes `tests/sprite` a package (module names stay unique) |
| `tests/sprite/synth.py` | numpy-drawn synthetic frames (moving red square on green or transparency) |
| `tests/sprite/conftest.py` | `alpha_frames`, `green_frames`, `ffmpeg_exe`, `synthetic_mp4` fixtures |
| `tests/sprite/golden/aseprite_hash.json` | Golden Aseprite hash document |
| `tests/sprite/golden/aseprite_array.json` | Golden Aseprite array document |
| `tests/sprite/golden/texturepacker_hash.json` | Golden TexturePacker hash document |
| `tests/sprite/test_models.py`, `test_project.py`, `test_presets.py`, `test_undo.py`, `test_pipeline.py`, `test_extract.py`, `test_slicing.py`, `test_stabilize.py`, `test_exporters.py`, `test_sprite_paths.py`, `test_package.py` | One test module per core module |

---

### Task 1: Frame metadata model and test scaffolding

**Files:**
- Create: `core/sprite/__init__.py`
- Create: `core/sprite/models.py`
- Create: `tests/sprite/__init__.py`
- Create: `tests/sprite/synth.py`
- Create: `tests/sprite/conftest.py`
- Create: `tests/sprite/test_models.py`

**Interfaces:**
- Consumes: `core.constants.VERSION`.
- Produces: `Rect = Tuple[int, int, int, int]`; `Size = Tuple[int, int]`; `DIRECTIONS`; `FrameMeta(name, source_path, frame, rotated=False, trimmed=False, sprite_source_size=(0,0,0,0), source_size=(0,0), duration_ms=100, pivot=(0.5, 1.0), overrides={})` with `to_dict() -> dict` / `from_dict(d) -> FrameMeta`; `TagMeta(name, from_index, to_index, direction="forward", repeat=0, fps_hint=None)` with `to_dict`/`from_dict`; `SheetMeta(title, frames, tags, sheet_size=(0,0), cell_size=(64,64), scale=1.0, palette=None, profile="hd", app="ImageAI", version=VERSION)` with `to_dict`, `from_dict`, `frames_for(tag) -> List[FrameMeta]`.
- Test helpers: `tests.sprite.synth.draw_frame(index, *, alpha, size=(112, 64), square=24, step=6) -> Image`; `write_frames(directory, count=12, *, alpha=True, size=(112, 64)) -> List[Path]`; fixtures `alpha_frames`, `green_frames` (12 PNGs each), `ffmpeg_exe` (session; skips without ffmpeg), `synthetic_mp4` (session; 12-frame 24 fps 112x64 H.264 clip).

- [ ] **Step 1: Create the test package, the synthetic-frame helpers and the fixtures.**

`tests/sprite/__init__.py` is an empty file. Create it with no content.

`tests/sprite/synth.py`:

```python
"""Synthetic sprite frames drawn with numpy (design section 5, G16).

A red square moves right across a canvas: ``alpha=True`` puts it on
transparency, ``alpha=False`` on an opaque chroma-green plate. Frame
``index`` has its square at ``x = 8 + index * STEP``; with twelve frames the
last square (x = 74..98) still fits inside the 112 px canvas, so the union
bounding box of all frames is ``(8, 20, 90, 24)``.
"""
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image

FRAME_SIZE = (112, 64)  # w, h
SQUARE = 24
STEP = 6
FRAME_COUNT = 12
RED = (200, 40, 40, 255)


def draw_frame(index: int, *, alpha: bool, size: Tuple[int, int] = FRAME_SIZE,
               square: int = SQUARE, step: int = STEP) -> Image.Image:
    """Frame ``index``: a red square at x = 8 + index*step on green or on transparency."""
    w, h = size
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    if not alpha:
        arr[..., 1] = 255
        arr[..., 3] = 255
    x = 8 + index * step
    y = (h - square) // 2
    arr[y:y + square, x:x + square] = RED
    return Image.fromarray(arr)


def write_frames(directory: Path, count: int = FRAME_COUNT, *, alpha: bool = True,
                 size: Tuple[int, int] = FRAME_SIZE) -> List[Path]:
    """Write ``count`` frames as 0001.png... and return their paths."""
    directory.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    for index in range(count):
        path = directory / f"{index + 1:04d}.png"
        draw_frame(index, alpha=alpha, size=size).save(path, format="PNG")
        paths.append(path)
    return paths
```

`tests/sprite/conftest.py`:

```python
"""Fixtures for the sprite suite (design section 5).

``alpha_frames`` and ``green_frames`` are twelve synthetic PNGs per test.
``synthetic_mp4`` encodes the green frames once per session with ffmpeg
and skips every test that needs it when ffmpeg is unavailable. The repo's
``tests/conftest.py`` already sandboxes ``core.paths`` and QSettings.
"""
import subprocess
from pathlib import Path
from typing import List

import pytest

from tests.sprite.synth import FRAME_COUNT, write_frames


@pytest.fixture
def alpha_frames(tmp_path) -> List[Path]:
    return write_frames(tmp_path / "alpha", alpha=True)


@pytest.fixture
def green_frames(tmp_path) -> List[Path]:
    return write_frames(tmp_path / "green", alpha=False)


@pytest.fixture(scope="session")
def ffmpeg_exe() -> str:
    """The ffmpeg executable, or skip. Resolved lazily so the FFmpegManager
    config write lands in the sandboxed user directory, not the real one."""
    from core.video.ffmpeg_utils import get_ffmpeg_path

    path = get_ffmpeg_path()
    if not path:
        pytest.skip("ffmpeg is not available")
    return path


@pytest.fixture(scope="session")
def synthetic_mp4(tmp_path_factory, ffmpeg_exe) -> Path:
    """A 12-frame, 24 fps, 112x64 H.264 clip of the moving square on green."""
    root = tmp_path_factory.mktemp("clip")
    write_frames(root / "src", FRAME_COUNT, alpha=False)
    out = root / "clip.mp4"
    cmd = [ffmpeg_exe, "-y", "-loglevel", "error", "-framerate", "24",
           "-i", str(root / "src" / "%04d.png"), "-c:v", "libx264",
           "-pix_fmt", "yuv420p", str(out)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0 or not out.exists():
        pytest.skip(f"ffmpeg could not encode the fixture clip: {result.stderr[-300:]}")
    return out
```

- [ ] **Step 2: Write the failing model test.**

`tests/sprite/test_models.py`:

```python
from pathlib import Path

from core.sprite.models import FrameMeta, SheetMeta, TagMeta
from core.constants import VERSION


def _sheet():
    frames = [FrameMeta(name=f"hero_walk_{i:02d}", source_path=Path(f"/x/{i}.png"), frame=(i * 16, 0, 16, 16),
                        sprite_source_size=(0, 0, 16, 16), source_size=(16, 16), duration_ms=80)
              for i in range(4)]
    tags = [TagMeta(name="walk", from_index=0, to_index=2, direction="pingpong", repeat=0, fps_hint=12),
            TagMeta(name="idle", from_index=3, to_index=3)]
    return SheetMeta(title="hero", frames=frames, tags=tags, sheet_size=(64, 16), cell_size=(16, 16))


def test_defaults_match_the_design():
    frame = FrameMeta(name="f", source_path=None, frame=(0, 0, 0, 0))
    assert frame.rotated is False
    assert frame.trimmed is False
    assert frame.duration_ms == 100
    assert frame.pivot == (0.5, 1.0)
    assert frame.overrides == {}
    tag = TagMeta(name="t", from_index=0, to_index=0)
    assert (tag.direction, tag.repeat, tag.fps_hint) == ("forward", 0, None)
    sheet = SheetMeta(title="s", frames=[], tags=[])
    assert sheet.cell_size == (64, 64)
    assert sheet.profile == "hd"
    assert sheet.app == "ImageAI"
    assert sheet.version == VERSION


def test_round_trip_through_dict_is_lossless():
    sheet = _sheet()
    sheet.palette = ["#000000", "#ffffff"]
    again = SheetMeta.from_dict(sheet.to_dict())
    assert again == sheet


def test_to_dict_uses_plain_json_types():
    import json
    data = _sheet().to_dict()
    json.dumps(data)
    assert data["frames"][0]["source_path"] == "/x/0.png"
    assert data["frames"][0]["frame"] == [0, 0, 16, 16]
    assert data["tags"][0]["direction"] == "pingpong"


def test_frames_for_returns_the_tag_range_inclusive():
    sheet = _sheet()
    walk = sheet.frames_for(sheet.tags[0])
    assert [f.name for f in walk] == ["hero_walk_00", "hero_walk_01", "hero_walk_02"]
    assert [f.name for f in sheet.frames_for(sheet.tags[1])] == ["hero_walk_03"]
    assert sheet.frames_for(TagMeta(name="empty", from_index=3, to_index=1)) == []


def test_from_dict_tolerates_missing_optional_keys():
    frame = FrameMeta.from_dict({"name": "f", "frame": [1, 2, 3, 4]})
    assert frame.source_path is None
    assert frame.frame == (1, 2, 3, 4)
    tag = TagMeta.from_dict({"name": "t", "from_index": 0, "to_index": 1})
    assert tag.fps_hint is None
```

- [ ] **Step 3: Run it and watch it fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_models.py -v
```

Expected: collection error `ModuleNotFoundError: No module named 'core.sprite'`.

- [ ] **Step 4: Create the package and the model module.**

`core/sprite/__init__.py` (Task 15 replaces this file with the full export list):

```python
"""Sprite pipeline: pure Python, no Qt (design section 1).

Sub-project 1 (core spine). Task 15 fills in the public re-exports.
"""
```

`core/sprite/models.py`:

```python
"""Sprite sheet metadata: the one source of truth every exporter projects.

Stdlib dataclasses only. No Qt, no PIL. ``SheetMeta`` describes a set of
frames on disk plus the tags (animations) that group them. Exporters read a
``SheetMeta`` and write files; they never mutate the project.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.constants import VERSION

Rect = Tuple[int, int, int, int]  # x, y, w, h
Size = Tuple[int, int]  # w, h

DIRECTIONS = ("forward", "reverse", "pingpong", "pingpong_reverse")


def _rect(value: Any) -> Rect:
    x, y, w, h = (int(v) for v in value)
    return (x, y, w, h)


def _size(value: Any) -> Size:
    w, h = (int(v) for v in value)
    return (w, h)


@dataclass
class FrameMeta:
    """One frame of a sprite sheet."""

    name: str
    source_path: Optional[Path]
    frame: Rect
    rotated: bool = False
    trimmed: bool = False
    sprite_source_size: Rect = (0, 0, 0, 0)
    source_size: Size = (0, 0)
    duration_ms: int = 100
    pivot: Tuple[float, float] = (0.5, 1.0)
    overrides: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "source_path": str(self.source_path) if self.source_path else None,
            "frame": list(self.frame),
            "rotated": self.rotated,
            "trimmed": self.trimmed,
            "sprite_source_size": list(self.sprite_source_size),
            "source_size": list(self.source_size),
            "duration_ms": self.duration_ms,
            "pivot": list(self.pivot),
            "overrides": dict(self.overrides),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FrameMeta":
        source = data.get("source_path")
        pivot = data.get("pivot", [0.5, 1.0])
        return cls(
            name=str(data.get("name", "")),
            source_path=Path(source) if source else None,
            frame=_rect(data.get("frame", (0, 0, 0, 0))),
            rotated=bool(data.get("rotated", False)),
            trimmed=bool(data.get("trimmed", False)),
            sprite_source_size=_rect(data.get("sprite_source_size", (0, 0, 0, 0))),
            source_size=_size(data.get("source_size", (0, 0))),
            duration_ms=int(data.get("duration_ms", 100)),
            pivot=(float(pivot[0]), float(pivot[1])),
            overrides=dict(data.get("overrides") or {}),
        )


@dataclass
class TagMeta:
    """A named, contiguous range of frames (one animation)."""

    name: str
    from_index: int
    to_index: int
    direction: str = "forward"
    repeat: int = 0
    fps_hint: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "from_index": self.from_index,
            "to_index": self.to_index,
            "direction": self.direction,
            "repeat": self.repeat,
            "fps_hint": self.fps_hint,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TagMeta":
        fps_hint = data.get("fps_hint")
        return cls(
            name=str(data.get("name", "")),
            from_index=int(data.get("from_index", 0)),
            to_index=int(data.get("to_index", 0)),
            direction=str(data.get("direction", "forward")),
            repeat=int(data.get("repeat", 0)),
            fps_hint=int(fps_hint) if fps_hint is not None else None,
        )


@dataclass
class SheetMeta:
    """Everything an exporter needs to know about one sprite sheet."""

    title: str
    frames: List[FrameMeta]
    tags: List[TagMeta]
    sheet_size: Size = (0, 0)
    cell_size: Size = (64, 64)
    scale: float = 1.0
    palette: Optional[List[str]] = None
    profile: str = "hd"
    app: str = "ImageAI"
    version: str = VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "frames": [f.to_dict() for f in self.frames],
            "tags": [t.to_dict() for t in self.tags],
            "sheet_size": list(self.sheet_size),
            "cell_size": list(self.cell_size),
            "scale": self.scale,
            "palette": list(self.palette) if self.palette is not None else None,
            "profile": self.profile,
            "app": self.app,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SheetMeta":
        palette = data.get("palette")
        return cls(
            title=str(data.get("title", "")),
            frames=[FrameMeta.from_dict(f) for f in data.get("frames", [])],
            tags=[TagMeta.from_dict(t) for t in data.get("tags", [])],
            sheet_size=_size(data.get("sheet_size", (0, 0))),
            cell_size=_size(data.get("cell_size", (64, 64))),
            scale=float(data.get("scale", 1.0)),
            palette=[str(c) for c in palette] if palette is not None else None,
            profile=str(data.get("profile", "hd")),
            app=str(data.get("app", "ImageAI")),
            version=str(data.get("version", VERSION)),
        )

    def frames_for(self, tag: TagMeta) -> List[FrameMeta]:
        """Return the frames a tag covers, in sheet order."""
        if tag.to_index < tag.from_index:
            return []
        return self.frames[tag.from_index:tag.to_index + 1]
```

- [ ] **Step 5: Run the test again.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_models.py -v
```

Expected: `5 passed`.

- [ ] **Step 6: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/__init__.py core/sprite/models.py tests/sprite/__init__.py tests/sprite/synth.py tests/sprite/conftest.py tests/sprite/test_models.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): frame metadata model and synthetic test fixtures"
```

---

### Task 2: Sprite storage paths and the migration journal

**Files:**
- Modify: `core/paths.py` (insert after line 225, the end of `midjourney_storage`; insert after line 279, the end of `details`)
- Modify: `core/data_migration.py` (lines 29–32 `GROUP_CONTENTS[Group.IMAGES]`; line 64 `SETTINGS_FILES`)
- Modify: `tests/test_paths.py` (after line 195 and after line 206 inside `test_accessors_sit_under_the_right_roots`)
- Create: `tests/migration/test_sprite_storage.py`

**Interfaces:**
- Consumes: `DataPaths.root(Group)`, `GROUP_CONTENTS`, `SETTINGS_FILES`, `sources_for`.
- Produces: `DataPaths.sprite_projects() -> Path` (`<Images root>/sprites`); `DataPaths.sprite_configs() -> Path` (`<Settings root>/sprite_configs.json`); `"sprites" in GROUP_CONTENTS[Group.IMAGES]`; `"sprite_configs.json" in SETTINGS_FILES`.

- [ ] **Step 1: Write the failing tests.**

`tests/migration/test_sprite_storage.py`:

```python
"""Sprite storage joins the relocatable Images and Settings groups (design 1.6)."""
import json

from core.data_migration import GROUP_CONTENTS, SETTINGS_FILES, sources_for
from core.paths import DataPaths, Group


def test_sprites_travel_with_the_images_group():
    assert "sprites" in GROUP_CONTENTS[Group.IMAGES]


def test_sprite_configs_travel_with_the_settings_group():
    assert "sprite_configs.json" in SETTINGS_FILES


def test_group_contents_name_every_sprite_accessor_leaf(tmp_path):
    """The migrator only moves directories it knows; the accessor must match."""
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    dp = DataPaths(config_path=cfg)
    assert dp.sprite_projects().name in GROUP_CONTENTS[Group.IMAGES]
    assert dp.sprite_configs().name in SETTINGS_FILES


def test_sources_for_images_includes_an_existing_sprites_dir(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    dp = DataPaths(config_path=cfg)
    (tmp_path / "sprites").mkdir()
    names = [name for _, name in sources_for(Group.IMAGES, dp)]
    assert "sprites" in names


def test_sources_for_settings_includes_sprite_configs(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    dp = DataPaths(config_path=cfg)
    (tmp_path / "sprite_configs.json").write_text("{}", encoding="utf-8")
    names = [name for _, name in sources_for(Group.SETTINGS, dp)]
    assert "sprite_configs.json" in names
```

In `tests/test_paths.py`, inside `test_accessors_sit_under_the_right_roots`, use Edit. First edit — old string:

```python
    assert dp.midjourney_cache() == images / "midjourney_web_cache"
```

New string:

```python
    assert dp.midjourney_cache() == images / "midjourney_web_cache"
    assert dp.sprite_projects() == images / "sprites"
```

Second edit — old string:

```python
    assert dp.history_file("prompt") == tmp_path / "prompt_history.json"
```

New string:

```python
    assert dp.history_file("prompt") == tmp_path / "prompt_history.json"
    assert dp.sprite_configs() == tmp_path / "sprite_configs.json"
```

- [ ] **Step 2: Run them and watch them fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/migration/test_sprite_storage.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_paths.py::test_accessors_sit_under_the_right_roots -v
```

Expected: `AttributeError: 'DataPaths' object has no attribute 'sprite_projects'` in three tests and `AssertionError` in the two pin tests.

- [ ] **Step 3: Add the accessors and the journal entries.**

`core/paths.py`, Edit — old string:

```python
    def midjourney_storage(self) -> Path:
        return self.root(Group.IMAGES) / "midjourney_web_storage"
```

New string:

```python
    def midjourney_storage(self) -> Path:
        return self.root(Group.IMAGES) / "midjourney_web_storage"

    def sprite_projects(self) -> Path:
        """Sprite projects: intermediates and exports, a sibling of generated/."""
        return self.root(Group.IMAGES) / "sprites"
```

`core/paths.py`, Edit — old string:

```python
    def details(self) -> Path:
        return self.root(Group.SETTINGS) / "details.jsonl"
```

New string:

```python
    def details(self) -> Path:
        return self.root(Group.SETTINGS) / "details.jsonl"

    def sprite_configs(self) -> Path:
        """Named sprite generation configurations (NamedConfigStore)."""
        return self.root(Group.SETTINGS) / "sprite_configs.json"
```

`core/data_migration.py`, Edit — old string:

```python
    Group.IMAGES: [
        "generated", "images", "composites", "styles", "Characters",
        "Fonts", "midjourney_web_cache", "midjourney_web_storage",
    ],
```

New string:

```python
    Group.IMAGES: [
        "generated", "images", "composites", "styles", "Characters",
        "Fonts", "midjourney_web_cache", "midjourney_web_storage", "sprites",
    ],
```

`core/data_migration.py`, Edit — old string:

```python
SETTINGS_FILES = ("details.jsonl", "batch_jobs.json", "video_config.json")
```

New string:

```python
SETTINGS_FILES = (
    "details.jsonl", "batch_jobs.json", "video_config.json", "sprite_configs.json",
)
```

- [ ] **Step 4: Run the tests again, plus the guards.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/migration/test_sprite_storage.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_paths.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -v
```

Expected: `75 passed` (5 + 67 + 3).

- [ ] **Step 5: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/paths.py core/data_migration.py tests/test_paths.py tests/migration/test_sprite_storage.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): sprite storage paths join the migration journal"
```

---

### Task 3: Sprite project model, persistence and project manager

**Files:**
- Create: `core/sprite/project.py`
- Create: `tests/sprite/test_project.py`
- Create: `tests/sprite/test_sprite_paths.py`

**Interfaces:**
- Consumes: `core.recycle_bin.send_to_recycle_bin(Path) -> bool`; `core.utils.sanitize_filename`; `core.paths.get_data_paths().sprite_projects()`; `core.sprite.models`.
- Produces: `GenerationSettings`, `ExtractionSettings`, `KeySettings`, `StabilizeSettings`, `OutputProfile` (spec fields plus `upscale_small=False`, `upscale_method="lanczos"` for sub-project 4; each with `to_dict`/`from_dict`); `default_profiles() -> List[OutputProfile]` (`hd` at 256×256 and `pixel` at 64×64, both enabled per decision 2); `ClipRecord`, `ActionCard` (`ActionCard.new_id() -> str`), `CostEntry`; `SpriteProject` with `slug`, `action_by_id(id)`, `profile(name)`, `to_dict`, `from_dict`, `project_file()`, `save(path=None) -> Path`, `load(path) -> SpriteProject` (classmethod; re-anchors), `reanchor_media_paths() -> int`, `sheet_meta(profile) -> SheetMeta`, `total_cost() -> Tuple[float, float]`, `purge_intermediates() -> int`; `SpriteProjectManager(base_dir=None)` with `create_project(name)`, `list_projects() -> List[dict]` (keys `name, slug, path, created, modified, actions`; newest first), `load_project(path)` (dir or `.json`), `save_project(project) -> Path`, `find_project(name_or_slug) -> Optional[Path]`, `delete_project(project) -> bool`; constants `PROJECT_FILE_NAME = "project.iasprite.json"`, `PROJECT_SUBDIRS`, `SPRITES_DIR_NAME = "sprites"`.

- [ ] **Step 1: Write the failing tests.**

`tests/sprite/test_project.py`:

```python
import json
import shutil
from pathlib import Path

import pytest

from core.sprite.models import FrameMeta
from core.sprite.project import (
    PROJECT_FILE_NAME,
    ActionCard,
    ClipRecord,
    CostEntry,
    ExtractionSettings,
    GenerationSettings,
    KeySettings,
    OutputProfile,
    SpriteProject,
    SpriteProjectManager,
    StabilizeSettings,
    default_profiles,
)


def _write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


def _build(project_dir: Path) -> SpriteProject:
    project = SpriteProject(name="Hero Sprite")
    project.project_dir = project_dir
    project.character_source = _write(project_dir / "source" / "character.png")
    project.plate_path = _write(project_dir / "source" / "plate.png")
    project.turnaround = {"front": _write(project_dir / "source" / "turnaround" / "front.png")}
    action = ActionCard(id="a1", name="walk", prompt="walk cycle")
    action.clip = ClipRecord(path=_write(project_dir / "clips" / "a1.mp4"), provider="omni", model="m",
                             operation_id="op", params={"fps": 24}, prompt="p", generated_at="2026-08-29T10:00:00",
                             estimated_usd=0.5, actual_usd=None)
    action.frames = [FrameMeta(name="walk_00", source_path=_write(project_dir / "stages" / "a1" / "stabilize" / "0001.png"),
                               frame=(0, 0, 32, 32), source_size=(32, 32))]
    project.actions = [action]
    project.cost_ledger = [CostEntry(action_id="a1", action_name="walk", provider="omni", model="m", seconds=8,
                                     estimated_usd=0.5, actual_usd=0.4, timestamp="2026-08-29T10:00:00")]
    return project


def test_defaults_match_the_design():
    g = GenerationSettings()
    assert (g.provider, g.resolution, g.aspect_ratio, g.duration_s, g.fps) == ("omni", "720p", "16:9", 8, 24)
    assert g.loop_conditioning and g.plate_color == "#00FF00" and g.config_name == "Default"
    e = ExtractionSettings()
    assert (e.mode, e.every_n, e.target_fps, e.exact_n, e.duplicate_threshold) == ("every_n", 8, 12, 8, 0.02)
    k = KeySettings()
    assert (k.method, k.tolerance, k.softness, k.despill, k.ml_backend, k.ml_model) == ("chroma", 0.20, 0.10, "average", "mediapipe", "isnet-anime")
    s = StabilizeSettings()
    assert (s.anchor, s.dejitter, s.dejitter_method, s.pad_px) == ("bottom_center", True, "phase", 0)
    p = OutputProfile(name="hd")
    assert (p.enabled, p.cell_size, p.binary_alpha, p.alpha_threshold, p.dither, p.palette_lock) == (True, (64, 64), False, 128, "none", True)
    profiles = default_profiles()
    assert [p.name for p in profiles] == ["hd", "pixel"]
    assert all(p.enabled for p in profiles)
    assert (profiles[0].cell_size, profiles[1].cell_size) == ((256, 256), (64, 64))
    assert (p.upscale_small, p.upscale_method) == (False, "lanczos")
    assert OutputProfile.from_dict(profiles[1].to_dict()) == profiles[1]
    project = SpriteProject(name="x")
    assert project.genre_preset == "sidescroller"
    assert project.plate_color == "#00FF00"
    assert project.stage_fingerprints == {}


def test_save_and_load_round_trip(tmp_path):
    project = _build(tmp_path / "sprites" / "Hero_Sprite_20260829_100000")
    path = project.save()
    assert path.name == PROJECT_FILE_NAME
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format"] == "iasprite"
    loaded = SpriteProject.load(path)
    assert loaded.name == "Hero Sprite"
    assert loaded.project_dir == project.project_dir
    assert loaded.actions[0].clip.path == project.actions[0].clip.path
    assert loaded.actions[0].frames[0].source_path == project.actions[0].frames[0].source_path
    assert loaded.turnaround["front"] == project.turnaround["front"]
    assert loaded.cost_ledger[0].actual_usd == 0.4
    assert loaded.profiles[1].name == "pixel"
    assert loaded.to_dict()["actions"] == project.to_dict()["actions"]


def test_load_reanchors_media_after_a_storage_move(tmp_path):
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    project_dir = old_root / "sprites" / "Hero_Sprite_20260829_100000"
    project = _build(project_dir)
    project.save()
    new_root.mkdir()
    shutil.move(str(old_root / "sprites"), str(new_root / "sprites"))
    new_dir = new_root / "sprites" / "Hero_Sprite_20260829_100000"

    loaded = SpriteProject.load(new_dir / PROJECT_FILE_NAME)
    assert loaded.character_source == new_dir / "source" / "character.png"
    assert loaded.plate_path.exists()
    assert loaded.turnaround["front"] == new_dir / "source" / "turnaround" / "front.png"
    assert loaded.actions[0].clip.path == new_dir / "clips" / "a1.mp4"
    assert loaded.actions[0].frames[0].source_path == new_dir / "stages" / "a1" / "stabilize" / "0001.png"


def test_reanchor_leaves_existing_and_unresolvable_paths_alone(tmp_path):
    project = _build(tmp_path / "sprites" / "P_1")
    external = _write(tmp_path / "elsewhere" / "char.png")
    project.character_source = external
    project.plate_path = Path("/nowhere/plate.png")
    assert project.reanchor_media_paths() == 0
    assert project.character_source == external
    assert project.plate_path == Path("/nowhere/plate.png")


def test_load_rejects_empty_and_corrupt_files(tmp_path):
    empty = tmp_path / PROJECT_FILE_NAME
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        SpriteProject.load(empty)
    empty.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        SpriteProject.load(empty)
    assert (tmp_path / "project.iasprite.json.corrupted").exists() or (tmp_path / "project.json.corrupted").exists()


def test_total_cost_sums_the_ledger():
    project = SpriteProject(name="x")
    project.cost_ledger = [
        CostEntry("a", "walk", "omni", "m", 8, 0.5, 0.4, "t"),
        CostEntry("b", "run", "veo", "m", 8, None, 1.0, "t"),
    ]
    assert project.total_cost() == (0.5, 1.4)


def test_sheet_meta_points_frames_at_the_profile_stage(tmp_path):
    project = _build(tmp_path / "sprites" / "P_1")
    hd_file = _write(project.project_dir / "stages" / "a1" / "hd" / "0001.png")
    project.profiles[0].cell_size = (128, 128)
    meta = project.sheet_meta("hd")
    assert meta.title == "Hero_Sprite"
    assert meta.profile == "hd"
    assert meta.cell_size == (128, 128)
    assert meta.frames[0].source_path == hd_file
    assert meta.tags[0].name == "walk"
    assert (meta.tags[0].from_index, meta.tags[0].to_index) == (0, 0)
    assert meta.tags[0].fps_hint == 12
    assert (meta.tags[0].direction, meta.tags[0].repeat) == ("forward", 0)
    project.actions[0].loop = False
    assert project.sheet_meta("hd").tags[0].repeat == 1
    # No pixel stage output yet: fall back to the stabilize frame.
    pixel = project.sheet_meta("pixel")
    assert pixel.frames[0].source_path == project.actions[0].frames[0].source_path
    project.profiles[1].locked_palette = ["#000000", "#ffffff"]
    assert project.sheet_meta("pixel").palette == ["#000000", "#ffffff"]
    project.profiles[1].palette_size = None  # quantization off: no palette reported
    assert project.sheet_meta("pixel").palette is None
    with pytest.raises(ValueError):
        project.sheet_meta("nope")


def test_purge_intermediates_recycles_stages_and_clips(tmp_path, monkeypatch):
    project = _build(tmp_path / "sprites" / "P_1")
    recycled = []

    def fake_recycle(path):
        recycled.append(path)
        shutil.rmtree(path)
        return True

    monkeypatch.setattr("core.sprite.project.send_to_recycle_bin", fake_recycle)
    project.stage_fingerprints = {"a1": {"extract": "abc"}}
    removed = project.purge_intermediates()
    assert removed == 2  # one stage PNG + one clip
    assert sorted(p.name for p in recycled) == ["clips", "stages"]
    assert not (project.project_dir / "stages").exists()
    assert (project.project_dir / "source").exists()
    assert project.stage_fingerprints == {}


def test_manager_creates_lists_loads_and_deletes(tmp_path):
    manager = SpriteProjectManager(base_dir=tmp_path / "sprites")
    project = manager.create_project("My Hero!")
    assert project.project_dir.parent == tmp_path / "sprites"
    assert project.project_dir.name.startswith("My_Hero")
    for sub in ("source", "clips", "stages", "exports"):
        assert (project.project_dir / sub).is_dir()
    assert (project.project_dir / PROJECT_FILE_NAME).exists()
    listed = manager.list_projects()
    assert len(listed) == 1 and listed[0]["name"] == "My Hero!"
    assert listed[0]["slug"] == project.project_dir.name
    assert listed[0]["actions"] == 0
    loaded = manager.load_project(listed[0]["path"])
    assert loaded.name == "My Hero!"
    assert manager.load_project(project.project_dir).name == "My Hero!"
    assert manager.find_project("my hero!") == listed[0]["path"]
    assert manager.find_project(project.project_dir.name) == listed[0]["path"]
    assert manager.find_project("nope") is None
    assert manager.delete_project(loaded)
    assert manager.list_projects() == []


def test_manager_save_project_gives_a_homeless_project_a_directory(tmp_path):
    manager = SpriteProjectManager(base_dir=tmp_path / "sprites")
    project = SpriteProject(name="Loose")
    path = manager.save_project(project)
    assert path.parent == project.project_dir
    assert project.project_dir.parent == tmp_path / "sprites"
    assert (project.project_dir / "stages").is_dir()
    assert manager.save_project(project) == path


def test_manager_defaults_to_the_sprite_projects_path(tmp_path, monkeypatch):
    import core.paths as paths_mod

    class FakePaths:
        def sprite_projects(self):
            return tmp_path / "S" / "sprites"

    monkeypatch.setattr(paths_mod, "get_data_paths", lambda: FakePaths())
    assert SpriteProjectManager().base_dir == tmp_path / "S" / "sprites"
```

`tests/sprite/test_sprite_paths.py`:

```python
"""Sprite paths must resolve through the Images and Settings roots."""
import json

import core.paths as paths_mod
from core.paths import DataPaths


def test_sprite_project_manager_uses_the_images_root(tmp_path, monkeypatch):
    images = tmp_path / "I"
    images.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {"images": str(images)}}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))

    from core.sprite.project import SpriteProjectManager

    assert SpriteProjectManager().base_dir == images / "sprites"


def test_sprite_configs_follow_the_settings_root(tmp_path, monkeypatch):
    settings = tmp_path / "S"
    settings.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {"settings": str(settings)}}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))

    assert paths_mod.get_data_paths().sprite_configs() == settings / "sprite_configs.json"


def test_reanchor_marker_matches_the_accessor_leaf():
    """project._reanchored heals paths by the sprites/ marker; keep them in sync."""
    from core.sprite.project import SPRITES_DIR_NAME

    assert SPRITES_DIR_NAME == paths_mod.get_data_paths().sprite_projects().name


def test_core_sprite_imports_no_qt():
    """core/sprite is headless by design (design section 1)."""
    import pathlib

    offenders = []
    for path in pathlib.Path("core/sprite").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "PySide6" in text or "PyQt" in text:
            offenders.append(str(path))
    assert not offenders, f"Qt import in core/sprite: {offenders}"
```

- [ ] **Step 2: Run them and watch them fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_project.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_sprite_paths.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.sprite.project'` (collection error for `test_project.py`; the two manager/marker tests in `test_sprite_paths.py` fail the same way).

- [ ] **Step 3: Create the project module.**

`core/sprite/project.py`:

```python
"""Sprite project model and persistence (design section 2 and 1.6).

A project lives in ``<Images root>/sprites/<slug>_<timestamp>/`` and is
saved as ``project.iasprite.json``. Media paths are stored absolute; ``load``
re-anchors them under the current project directory after a storage move,
the way ``core.video.project.VideoProject`` does.
"""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.recycle_bin import send_to_recycle_bin
from core.utils import sanitize_filename

from .models import FrameMeta, SheetMeta, Size, TagMeta

logger = logging.getLogger(__name__)

PROJECT_FILE_NAME = "project.iasprite.json"
PROJECT_SUBDIRS = ("source", "clips", "stages", "exports")
SPRITES_DIR_NAME = "sprites"  # the DataPaths.sprite_projects() leaf name


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _path_or_none(value: Any) -> Optional[Path]:
    return Path(value) if value else None


def _reanchored(path: Optional[Path], project_dir: Optional[Path]) -> Optional[Path]:
    """Point ``path`` at ``project_dir`` when the stored copy is gone.

    Stored paths are absolute. After a storage move they still name the old
    root. When the stored path is missing, rebuild its tail under the current
    project directory and use that only when the file really exists there.
    A path this cannot resolve comes back unchanged.
    """
    if path is None or project_dir is None:
        return path
    try:
        if path.exists():
            return path
    except OSError:
        return path
    parts = path.parts
    for index, part in enumerate(parts):
        if part == project_dir.name and index + 1 < len(parts):
            candidate = project_dir.joinpath(*parts[index + 1:])
            if candidate.exists():
                return candidate
    for index, part in enumerate(parts):
        if part == SPRITES_DIR_NAME and index + 2 < len(parts):
            candidate = project_dir.joinpath(*parts[index + 2:])
            if candidate.exists():
                return candidate
    return path


# --- settings dataclasses ---------------------------------------------------


@dataclass
class GenerationSettings:
    provider: str = "omni"
    model: str = ""
    resolution: str = "720p"
    aspect_ratio: str = "16:9"
    duration_s: int = 8
    fps: int = 24
    loop_conditioning: bool = True
    plate_color: str = "#00FF00"
    use_turnaround_refs: bool = True
    include_audio: bool = False
    config_name: str = "Default"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenerationSettings":
        return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})


@dataclass
class ExtractionSettings:
    mode: str = "every_n"  # every_n | target_fps | exact_n
    every_n: int = 8
    target_fps: int = 12
    exact_n: int = 8
    trim_start_s: float = 0.0
    trim_end_s: float = 0.0
    cull_duplicates: bool = False
    duplicate_threshold: float = 0.02

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractionSettings":
        return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})


@dataclass
class KeySettings:
    method: str = "chroma"  # chroma | ml | none
    key_color: Optional[str] = None
    tolerance: float = 0.20
    softness: float = 0.10
    despill: str = "average"
    edge_decontaminate: bool = True
    choke_px: int = 0
    feather_px: int = 0
    despeckle_px: int = 0
    ml_backend: str = "mediapipe"
    ml_model: str = "isnet-anime"
    ml_refine_edges: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KeySettings":
        return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})


@dataclass
class StabilizeSettings:
    anchor: str = "bottom_center"
    dejitter: bool = True
    dejitter_method: str = "phase"
    pad_px: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StabilizeSettings":
        return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})


@dataclass
class OutputProfile:
    name: str
    enabled: bool = True
    cell_size: Size = (64, 64)
    binary_alpha: bool = False
    alpha_threshold: int = 128
    defringe_px: int = 0
    palette_size: Optional[int] = None
    dither: str = "none"
    palette_lock: bool = True
    locked_palette: Optional[List[str]] = None
    upscale_small: bool = False        # pixel: upscale a source smaller than the cell (sub-project 4)
    upscale_method: str = "lanczos"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["cell_size"] = list(self.cell_size)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OutputProfile":
        cell = data.get("cell_size", (64, 64))
        locked = data.get("locked_palette")
        return cls(
            name=str(data.get("name", "hd")),
            enabled=bool(data.get("enabled", True)),
            cell_size=(int(cell[0]), int(cell[1])),
            binary_alpha=bool(data.get("binary_alpha", False)),
            alpha_threshold=int(data.get("alpha_threshold", 128)),
            defringe_px=int(data.get("defringe_px", 0)),
            palette_size=int(data["palette_size"]) if data.get("palette_size") is not None else None,
            dither=str(data.get("dither", "none")),
            palette_lock=bool(data.get("palette_lock", True)),
            locked_palette=[str(c) for c in locked] if locked is not None else None,
            upscale_small=bool(data.get("upscale_small", False)),
            upscale_method=str(data.get("upscale_method", "lanczos")),
        )


def default_profiles() -> List[OutputProfile]:
    """The two profiles every new project starts with, both enabled (decision 2)."""
    return [
        OutputProfile(name="hd", enabled=True, cell_size=(256, 256)),
        OutputProfile(
            name="pixel", enabled=True, cell_size=(64, 64), binary_alpha=True,
            palette_size=32, dither="none",
        ),
    ]


# --- records ---------------------------------------------------------------


@dataclass
class ClipRecord:
    path: Path
    provider: str
    model: str
    operation_id: Optional[str]
    params: Dict[str, Any]
    prompt: str
    generated_at: str
    estimated_usd: Optional[float]
    actual_usd: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "provider": self.provider,
            "model": self.model,
            "operation_id": self.operation_id,
            "params": dict(self.params),
            "prompt": self.prompt,
            "generated_at": self.generated_at,
            "estimated_usd": self.estimated_usd,
            "actual_usd": self.actual_usd,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClipRecord":
        return cls(
            path=Path(data["path"]),
            provider=str(data.get("provider", "")),
            model=str(data.get("model", "")),
            operation_id=data.get("operation_id"),
            params=dict(data.get("params") or {}),
            prompt=str(data.get("prompt", "")),
            generated_at=str(data.get("generated_at", "")),
            estimated_usd=data.get("estimated_usd"),
            actual_usd=data.get("actual_usd"),
        )


@dataclass
class ActionCard:
    id: str
    name: str
    prompt: str
    duration_s: int = 8
    loop: bool = True
    target_frames: int = 8
    fps: int = 12
    status: str = "draft"  # draft | queued | rendering | rendered | failed | processed
    error: Optional[str] = None
    clip: Optional[ClipRecord] = None
    frames: List[FrameMeta] = field(default_factory=list)

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "prompt": self.prompt,
            "duration_s": self.duration_s,
            "loop": self.loop,
            "target_frames": self.target_frames,
            "fps": self.fps,
            "status": self.status,
            "error": self.error,
            "clip": self.clip.to_dict() if self.clip else None,
            "frames": [f.to_dict() for f in self.frames],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionCard":
        clip = data.get("clip")
        return cls(
            id=str(data.get("id") or cls.new_id()),
            name=str(data.get("name", "")),
            prompt=str(data.get("prompt", "")),
            duration_s=int(data.get("duration_s", 8)),
            loop=bool(data.get("loop", True)),
            target_frames=int(data.get("target_frames", 8)),
            fps=int(data.get("fps", 12)),
            status=str(data.get("status", "draft")),
            error=data.get("error"),
            clip=ClipRecord.from_dict(clip) if clip else None,
            frames=[FrameMeta.from_dict(f) for f in data.get("frames", [])],
        )


@dataclass
class CostEntry:
    action_id: str
    action_name: str
    provider: str
    model: str
    seconds: float
    estimated_usd: Optional[float]
    actual_usd: Optional[float]
    timestamp: str
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CostEntry":
        return cls(
            action_id=str(data.get("action_id", "")),
            action_name=str(data.get("action_name", "")),
            provider=str(data.get("provider", "")),
            model=str(data.get("model", "")),
            seconds=float(data.get("seconds", 0.0)),
            estimated_usd=data.get("estimated_usd"),
            actual_usd=data.get("actual_usd"),
            timestamp=str(data.get("timestamp", "")),
            note=str(data.get("note", "")),
        )


# --- project ----------------------------------------------------------------


@dataclass
class SpriteProject:
    name: str
    project_dir: Optional[Path] = None
    character_source: Optional[Path] = None
    plate_path: Optional[Path] = None
    plate_color: str = "#00FF00"
    turnaround: Dict[str, Path] = field(default_factory=dict)
    brief: str = ""
    genre_preset: str = "sidescroller"
    actions: List[ActionCard] = field(default_factory=list)
    generation: GenerationSettings = field(default_factory=GenerationSettings)
    extraction: ExtractionSettings = field(default_factory=ExtractionSettings)
    key: KeySettings = field(default_factory=KeySettings)
    stabilize: StabilizeSettings = field(default_factory=StabilizeSettings)
    profiles: List[OutputProfile] = field(default_factory=default_profiles)
    stage_fingerprints: Dict[str, Dict[str, str]] = field(default_factory=dict)
    cost_ledger: List[CostEntry] = field(default_factory=list)
    created: str = field(default_factory=_now)
    modified: str = field(default_factory=_now)

    # -- lookups ---------------------------------------------------------

    @property
    def slug(self) -> str:
        return sanitize_filename(self.name, max_len=60).replace(" ", "_") or "sprite"

    def action_by_id(self, action_id: str) -> Optional[ActionCard]:
        for action in self.actions:
            if action.id == action_id:
                return action
        return None

    def profile(self, name: str) -> Optional[OutputProfile]:
        for prof in self.profiles:
            if prof.name == name:
                return prof
        return None

    # -- serialisation ---------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": "iasprite",
            "format_version": 1,
            "name": self.name,
            "character_source": str(self.character_source) if self.character_source else None,
            "plate_path": str(self.plate_path) if self.plate_path else None,
            "plate_color": self.plate_color,
            "turnaround": {k: str(v) for k, v in self.turnaround.items()},
            "brief": self.brief,
            "genre_preset": self.genre_preset,
            "actions": [a.to_dict() for a in self.actions],
            "generation": self.generation.to_dict(),
            "extraction": self.extraction.to_dict(),
            "key": self.key.to_dict(),
            "stabilize": self.stabilize.to_dict(),
            "profiles": [p.to_dict() for p in self.profiles],
            "stage_fingerprints": {k: dict(v) for k, v in self.stage_fingerprints.items()},
            "cost_ledger": [c.to_dict() for c in self.cost_ledger],
            "created": self.created,
            "modified": self.modified,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpriteProject":
        profiles = data.get("profiles")
        return cls(
            name=str(data.get("name", "Untitled")),
            project_dir=None,
            character_source=_path_or_none(data.get("character_source")),
            plate_path=_path_or_none(data.get("plate_path")),
            plate_color=str(data.get("plate_color", "#00FF00")),
            turnaround={str(k): Path(v) for k, v in (data.get("turnaround") or {}).items() if v},
            brief=str(data.get("brief", "")),
            genre_preset=str(data.get("genre_preset", "sidescroller")),
            actions=[ActionCard.from_dict(a) for a in data.get("actions", [])],
            generation=GenerationSettings.from_dict(data.get("generation") or {}),
            extraction=ExtractionSettings.from_dict(data.get("extraction") or {}),
            key=KeySettings.from_dict(data.get("key") or {}),
            stabilize=StabilizeSettings.from_dict(data.get("stabilize") or {}),
            profiles=[OutputProfile.from_dict(p) for p in profiles] if profiles else default_profiles(),
            stage_fingerprints={
                str(k): {str(s): str(f) for s, f in (v or {}).items()}
                for k, v in (data.get("stage_fingerprints") or {}).items()
            },
            cost_ledger=[CostEntry.from_dict(c) for c in data.get("cost_ledger", [])],
            created=str(data.get("created") or _now()),
            modified=str(data.get("modified") or _now()),
        )

    def project_file(self) -> Path:
        if self.project_dir is None:
            raise ValueError("project_dir is not set")
        return self.project_dir / PROJECT_FILE_NAME

    def save(self, path: Optional[Path] = None) -> Path:
        """Write the project JSON. Returns the path written."""
        if path is None:
            path = self.project_file()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.modified = _now()
        payload = json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, path: Path) -> "SpriteProject":
        """Read a project JSON and re-anchor its media paths."""
        path = Path(path)
        if path.is_dir():
            path = path / PROJECT_FILE_NAME
        if not path.exists():
            raise FileNotFoundError(f"Sprite project file not found: {path}")
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError(f"Sprite project file is empty: {path}")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            backup = path.with_suffix(".json.corrupted")
            try:
                shutil.copy2(path, backup)
            except OSError:
                pass
            logger.error(f"Invalid JSON in sprite project {path}: {exc}")
            raise ValueError(f"Sprite project file contains invalid JSON: {path}") from exc
        project = cls.from_dict(data)
        project.project_dir = path.parent
        healed = project.reanchor_media_paths()
        if healed:
            logger.info(
                f"Re-anchored {healed} media path(s) in sprite project '{project.name}' "
                f"to {project.project_dir}"
            )
        return project

    # -- media ----------------------------------------------------------

    def reanchor_media_paths(self) -> int:
        """Point stored media paths at the current project directory.

        Returns the number of paths that changed. Paths that still exist, and
        paths with no counterpart under the new directory, are left alone.
        """
        count = 0

        def fix(value: Optional[Path]) -> Optional[Path]:
            nonlocal count
            new = _reanchored(value, self.project_dir)
            if new is not value:
                count += 1
            return new

        self.character_source = fix(self.character_source)
        self.plate_path = fix(self.plate_path)
        self.turnaround = {k: (fix(v) or v) for k, v in self.turnaround.items()}
        for action in self.actions:
            if action.clip is not None:
                action.clip.path = fix(action.clip.path) or action.clip.path
            for frame in action.frames:
                frame.source_path = fix(frame.source_path)
        return count

    def sheet_meta(self, profile: str) -> SheetMeta:
        """Build the SheetMeta for one output profile.

        ``ActionCard.frames`` is the single frame list (order, timing, pivot).
        Each entry's ``source_path`` names the stabilize-stage PNG. The
        profile stages write a file of the same name under
        ``stages/<action_id>/<profile>/``; when that file exists the sheet
        points at it, otherwise it falls back to the stabilize PNG.
        """
        prof = self.profile(profile)
        if prof is None:
            raise ValueError(f"Unknown output profile: {profile!r}")
        frames: List[FrameMeta] = []
        tags: List[TagMeta] = []
        for action in self.actions:
            if not action.frames:
                continue
            start = len(frames)
            for frame in action.frames:
                src = frame.source_path
                if src is not None and self.project_dir is not None:
                    candidate = self.project_dir / "stages" / action.id / profile / src.name
                    if candidate.exists():
                        src = candidate
                frames.append(FrameMeta(
                    name=frame.name,
                    source_path=src,
                    frame=frame.frame,
                    rotated=frame.rotated,
                    trimmed=frame.trimmed,
                    sprite_source_size=frame.sprite_source_size,
                    source_size=frame.source_size,
                    duration_ms=frame.duration_ms,
                    pivot=frame.pivot,
                    overrides=dict(frame.overrides),
                ))
            tags.append(TagMeta(
                name=action.name,
                from_index=start,
                to_index=len(frames) - 1,
                direction="forward",
                repeat=0 if action.loop else 1,
                fps_hint=action.fps,
            ))
        return SheetMeta(
            title=self.slug,
            frames=frames,
            tags=tags,
            cell_size=prof.cell_size,
            palette=list(prof.locked_palette) if prof.locked_palette and prof.palette_size else None,
            profile=profile,
        )

    def total_cost(self) -> Tuple[float, float]:
        """Return ``(estimated, actual)`` USD sums over the ledger."""
        estimated = sum(c.estimated_usd or 0.0 for c in self.cost_ledger)
        actual = sum(c.actual_usd or 0.0 for c in self.cost_ledger)
        return (round(estimated, 4), round(actual, 4))

    def purge_intermediates(self) -> int:
        """Send ``stages/`` and ``clips/`` to the recycle bin. Returns files removed.

        The sticky preference and the confirmation live in the GUI; this
        method only does the deletion. Frame entries that pointed into the
        purged directories keep their paths, so a later re-run rebuilds them.
        """
        if self.project_dir is None:
            return 0
        removed = 0
        for name in ("stages", "clips"):
            target = self.project_dir / name
            if not target.exists():
                continue
            files = sum(1 for p in target.rglob("*") if p.is_file())
            if send_to_recycle_bin(target):
                removed += files
            else:
                logger.warning(f"Could not recycle {target}; leaving it in place")
        self.stage_fingerprints = {}
        return removed


class SpriteProjectManager:
    """Creates, lists, loads and deletes sprite projects on disk."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        if base_dir is None:
            from core.paths import get_data_paths

            base_dir = get_data_paths().sprite_projects()
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_project(self, name: str) -> SpriteProject:
        project = SpriteProject(name=name)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = self.base_dir / f"{project.slug}_{stamp}"
        counter = 1
        while project_dir.exists():
            project_dir = self.base_dir / f"{project.slug}_{stamp}_{counter}"
            counter += 1
        project_dir.mkdir(parents=True)
        for sub in PROJECT_SUBDIRS:
            (project_dir / sub).mkdir(exist_ok=True)
        project.project_dir = project_dir
        project.save()
        logger.info(f"Created sprite project '{name}' at {project_dir}")
        return project

    def list_projects(self) -> List[Dict[str, Any]]:
        projects: List[Dict[str, Any]] = []
        for project_dir in self.base_dir.iterdir():
            if not project_dir.is_dir():
                continue
            project_file = project_dir / PROJECT_FILE_NAME
            if not project_file.exists():
                continue
            try:
                data = json.loads(project_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning(f"Failed to read sprite project {project_file}: {exc}")
                continue
            projects.append({
                "name": data.get("name", "Untitled"),
                "slug": project_dir.name,
                "path": project_file,
                "created": data.get("created"),
                "modified": data.get("modified"),
                "actions": len(data.get("actions", [])),
            })
        projects.sort(key=lambda p: p.get("modified") or "", reverse=True)
        return projects

    def load_project(self, path: Path) -> SpriteProject:
        """Load from a project directory or its ``project.iasprite.json``."""
        return SpriteProject.load(Path(path))

    def save_project(self, project: SpriteProject) -> Path:
        """Save; give a project with no directory one under ``base_dir`` first."""
        if project.project_dir is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project.project_dir = self.base_dir / f"{project.slug}_{stamp}"
            project.project_dir.mkdir(parents=True, exist_ok=True)
            for sub in PROJECT_SUBDIRS:
                (project.project_dir / sub).mkdir(exist_ok=True)
        return project.save()

    def find_project(self, name_or_slug: str) -> Optional[Path]:
        """Return the project file whose name or directory name matches.

        A directory name (``Hero_20260829_101500``) matches exactly; a project
        name matches case-insensitively; the newest match wins when two
        projects share a name. Returns ``None`` when nothing matches.
        """
        wanted = name_or_slug.strip()
        for info in self.list_projects():  # newest first
            if info["slug"] == wanted or str(info["name"]).lower() == wanted.lower():
                return info["path"]
        return None

    def delete_project(self, project: SpriteProject) -> bool:
        if not project.project_dir or not project.project_dir.exists():
            logger.warning(f"Sprite project directory not found: {project.project_dir}")
            return False
        try:
            shutil.rmtree(project.project_dir)
        except OSError as exc:
            logger.error(f"Failed to delete sprite project {project.project_dir}: {exc}")
            return False
        logger.info(f"Deleted sprite project '{project.name}' at {project.project_dir}")
        return True
```

- [ ] **Step 4: Run the tests again.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_project.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_sprite_paths.py -v
```

Expected: `15 passed`.

- [ ] **Step 5: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/project.py tests/sprite/test_project.py tests/sprite/test_sprite_paths.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): sprite project persistence and project manager"
```

---

### Task 4: Presets

**Files:**
- Create: `core/sprite/presets.py`
- Create: `tests/sprite/test_presets.py`

**Interfaces:**
- Consumes: `core.sprite.models.Size`.
- Produces: `CELL_PRESETS: Tuple[Tuple[str, Size], ...]` (8…1024 incl. 16×24, 16×32, 48 RPG Maker, 720); `DEFAULT_CELL = (64, 64)`; `CUSTOM_CELL_LABEL`; `CANVAS_PRESETS` (320×180 … 640×360); `TARGET_RESOLUTIONS = {"720p", "1080p", "4K"}`; `FPS_PRESETS` (8 "on threes", 12 "on twos", 24, 30, 60); `DEFAULT_FPS = 12`; `GENRE_PRESETS = ("sidescroller", "top_down", "fighting")`; `DEFAULT_GENRE`; `parse_cell_size(text) -> Size`; `format_cell_size(size) -> str`; `integer_scale(canvas, target) -> int`; `integer_scale_table(canvas) -> Dict[str, int]`.

- [ ] **Step 1: Write the failing test.**

`tests/sprite/test_presets.py`:

```python
import pytest

from core.sprite import presets


def test_cell_presets_cover_the_design_list():
    sizes = [size for _, size in presets.CELL_PRESETS]
    for expected in [(8, 8), (16, 16), (16, 24), (24, 24), (16, 32), (32, 32), (48, 48),
                     (64, 64), (96, 96), (128, 128), (256, 256), (512, 512), (720, 720), (1024, 1024)]:
        assert expected in sizes
    assert presets.DEFAULT_CELL == (64, 64)


def test_canvas_and_fps_and_genre_presets():
    assert [s for _, s in presets.CANVAS_PRESETS] == [(320, 180), (384, 216), (400, 240), (480, 270), (640, 360)]
    assert [f for f, _ in presets.FPS_PRESETS] == [8, 12, 24, 30, 60]
    assert presets.DEFAULT_FPS == 12
    assert presets.GENRE_PRESETS == ("sidescroller", "top_down", "fighting")


def test_integer_scale_calculator():
    assert presets.integer_scale((320, 180), (1280, 720)) == 4
    assert presets.integer_scale((640, 360), (1920, 1080)) == 3
    assert presets.integer_scale((384, 216), (3840, 2160)) == 10
    assert presets.integer_scale((400, 240), (1280, 720)) == 3
    assert presets.integer_scale_table((320, 180)) == {"720p": 4, "1080p": 6, "4K": 12}


@pytest.mark.parametrize("text,expected", [
    ("64", (64, 64)), ("16x24", (16, 24)), ("16×24", (16, 24)), (" 720 X 720 ", (720, 720)),
])
def test_parse_cell_size(text, expected):
    assert presets.parse_cell_size(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "0", "16x0", "16x"])
def test_parse_cell_size_rejects_bad_input(text):
    with pytest.raises(ValueError):
        presets.parse_cell_size(text)
```

- [ ] **Step 2: Run it and watch it fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_presets.py -v
```

Expected: `ImportError: cannot import name 'presets' from 'core.sprite'`.

- [ ] **Step 3: Create the presets module.**

`core/sprite/presets.py`:

```python
"""Cell, canvas, FPS, and genre presets for the Sprite tab (design section 2)."""

from __future__ import annotations

import re
from typing import Dict, Tuple

from .models import Size

# (label, (w, h)); the label uses the multiplication sign the UI shows.
CELL_PRESETS: Tuple[Tuple[str, Size], ...] = (
    ("8×8", (8, 8)),
    ("16×16", (16, 16)),
    ("16×24", (16, 24)),
    ("24×24", (24, 24)),
    ("16×32", (16, 32)),
    ("32×32", (32, 32)),
    ("48×48 (RPG Maker)", (48, 48)),
    ("64×64", (64, 64)),
    ("96×96", (96, 96)),
    ("128×128", (128, 128)),
    ("256×256", (256, 256)),
    ("512×512", (512, 512)),
    ("720×720", (720, 720)),
    ("1024×1024", (1024, 1024)),
)
DEFAULT_CELL: Size = (64, 64)
CUSTOM_CELL_LABEL = "Custom…"

CANVAS_PRESETS: Tuple[Tuple[str, Size], ...] = (
    ("320×180", (320, 180)),
    ("384×216", (384, 216)),
    ("400×240", (400, 240)),
    ("480×270", (480, 270)),
    ("640×360", (640, 360)),
)
TARGET_RESOLUTIONS: Dict[str, Size] = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4K": (3840, 2160),
}

# (fps, note)
FPS_PRESETS: Tuple[Tuple[int, str], ...] = (
    (8, "on threes"),
    (12, "on twos"),
    (24, ""),
    (30, ""),
    (60, ""),
)
DEFAULT_FPS = 12

GENRE_PRESETS: Tuple[str, ...] = ("sidescroller", "top_down", "fighting")
DEFAULT_GENRE = "sidescroller"

_SIZE_RE = re.compile(r"^\s*(\d+)\s*(?:[x×X\*]\s*(\d+))?\s*$")


def parse_cell_size(text: str) -> Size:
    """Parse ``"64"``, ``"16x24"``, ``"16×24"`` or ``"16*24"`` into a size.

    A single number means a square cell. Raises ValueError on anything else
    or on a zero dimension.
    """
    match = _SIZE_RE.match(text or "")
    if not match:
        raise ValueError(f"Not a cell size: {text!r} (use W or WxH)")
    w = int(match.group(1))
    h = int(match.group(2)) if match.group(2) else w
    if w < 1 or h < 1:
        raise ValueError(f"Cell size must be at least 1x1: {text!r}")
    return (w, h)


def format_cell_size(size: Size) -> str:
    return f"{size[0]}×{size[1]}"


def integer_scale(canvas: Size, target: Size) -> int:
    """Largest integer k with ``canvas * k`` inside ``target``; 0 when none fits."""
    cw, ch = canvas
    tw, th = target
    if cw < 1 or ch < 1:
        raise ValueError("canvas dimensions must be positive")
    return min(tw // cw, th // ch)


def integer_scale_table(canvas: Size) -> Dict[str, int]:
    """Integer scale of ``canvas`` for every entry in TARGET_RESOLUTIONS."""
    return {name: integer_scale(canvas, size) for name, size in TARGET_RESOLUTIONS.items()}
```

- [ ] **Step 4: Run the test again.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_presets.py -v
```

Expected: `12 passed`.

- [ ] **Step 5: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/presets.py tests/sprite/test_presets.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): cell, canvas, fps and genre presets"
```

---

### Task 5: Snapshot undo stack

**Files:**
- Create: `core/sprite/undo.py`
- Create: `tests/sprite/test_undo.py`

**Interfaces:**
- Consumes: `core.sprite.models.FrameMeta`.
- Produces: `FrameListSnapshot(action_id: str, frames: Tuple[FrameMeta, ...], label: str)` (frozen) with classmethod `capture(action_id, frames, label)` (deep copy); `SnapshotStack(depth=50)` with `push(snap)`, `undo(current) -> Optional[FrameListSnapshot]`, `redo() -> Optional[FrameListSnapshot]`, `can_undo`, `can_redo`, `clear()`.

- [ ] **Step 1: Write the failing test.**

`tests/sprite/test_undo.py`:

```python
from pathlib import Path

from core.sprite.models import FrameMeta
from core.sprite.undo import FrameListSnapshot, SnapshotStack


def _frames(n):
    return [FrameMeta(name=f"f{i}", source_path=Path(f"/f/{i}.png"), frame=(0, 0, 8, 8)) for i in range(n)]


def test_capture_deep_copies_the_frames():
    frames = _frames(2)
    snap = FrameListSnapshot.capture("a1", frames, "delete frame 1")
    frames[0].duration_ms = 999
    assert snap.frames[0].duration_ms == 100
    assert snap.label == "delete frame 1"
    assert isinstance(snap.frames, tuple)


def test_undo_returns_previous_state_and_parks_current_for_redo():
    stack = SnapshotStack()
    before = FrameListSnapshot.capture("a1", _frames(3), "before delete")
    stack.push(before)
    assert stack.can_undo and not stack.can_redo
    current = FrameListSnapshot.capture("a1", _frames(2), "after delete")
    restored = stack.undo(current)
    assert restored is before
    assert not stack.can_undo and stack.can_redo
    assert stack.redo() is current
    assert stack.can_undo and not stack.can_redo


def test_push_clears_redo():
    stack = SnapshotStack()
    stack.push(FrameListSnapshot.capture("a", _frames(1), "one"))
    stack.undo(FrameListSnapshot.capture("a", _frames(0), "now"))
    assert stack.can_redo
    stack.push(FrameListSnapshot.capture("a", _frames(2), "two"))
    assert not stack.can_redo


def test_depth_drops_the_oldest_snapshot():
    stack = SnapshotStack(depth=2)
    snaps = [FrameListSnapshot.capture("a", _frames(i), str(i)) for i in range(3)]
    for snap in snaps:
        stack.push(snap)
    current = FrameListSnapshot.capture("a", _frames(9), "cur")
    assert stack.undo(current) is snaps[2]
    assert stack.undo(snaps[2]) is snaps[1]
    assert stack.undo(snaps[1]) is None


def test_empty_stack_returns_none():
    stack = SnapshotStack()
    assert stack.undo(FrameListSnapshot.capture("a", [], "x")) is None
    assert stack.redo() is None
```

- [ ] **Step 2: Run it and watch it fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_undo.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.sprite.undo'`.

- [ ] **Step 3: Create the undo module.**

`core/sprite/undo.py`:

```python
"""Snapshot undo for destructive frame-list edits (design section 1.4).

Pipeline re-runs never enter this stack: they are non-destructive by the
stage cache. Only frame-list edits (delete, reorder, duplicate, insert,
duration edit, retouch, override edit) push a snapshot before they act.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .models import FrameMeta


@dataclass(frozen=True)
class FrameListSnapshot:
    action_id: str
    frames: Tuple[FrameMeta, ...]
    label: str

    @classmethod
    def capture(cls, action_id: str, frames, label: str) -> "FrameListSnapshot":
        """Deep-copy ``frames`` so later edits cannot reach into the snapshot."""
        return cls(action_id=action_id, frames=tuple(copy.deepcopy(list(frames))), label=label)


class SnapshotStack:
    """A bounded undo/redo stack of frame-list snapshots."""

    def __init__(self, depth: int = 50) -> None:
        if depth < 1:
            raise ValueError("depth must be at least 1")
        self._depth = depth
        self._undo: List[FrameListSnapshot] = []
        self._redo: List[FrameListSnapshot] = []

    def push(self, snap: FrameListSnapshot) -> None:
        """Record the state *before* a destructive edit. Clears redo."""
        self._undo.append(snap)
        if len(self._undo) > self._depth:
            del self._undo[0]
        self._redo.clear()

    def undo(self, current: FrameListSnapshot) -> Optional[FrameListSnapshot]:
        """Return the state to restore, and park ``current`` for redo."""
        if not self._undo:
            return None
        self._redo.append(current)
        return self._undo.pop()

    def redo(self) -> Optional[FrameListSnapshot]:
        """Return the state to restore, and move it back onto the undo stack."""
        if not self._redo:
            return None
        snap = self._redo.pop()
        self._undo.append(snap)
        return snap

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()
```

- [ ] **Step 4: Run the test again.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_undo.py -v
```

Expected: `5 passed`.

- [ ] **Step 5: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/undo.py tests/sprite/test_undo.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): snapshot undo stack"
```

---

### Task 6: Pipeline contract — cancel token, progress, stage registry, fingerprints

**Files:**
- Create: `core/sprite/pipeline.py` (contract half; Task 10 appends the runners and the loop)
- Create: `tests/sprite/test_pipeline.py` (contract tests; Task 10 appends the runner tests)

**Interfaces:**
- Consumes: `core.sprite.project.SpriteProject`, `ActionCard`.
- Produces: `Cancelled(Exception)`; `CancelToken()` with `cancel()`, `cancelled`, `raise_if_cancelled()`; `ProgressFn = Callable[[str, int, int, str], None]`; `no_progress(stage, done, total, message)`; `check(token)`; `PipelineError(user_message)` with `.user_message`; `STAGES = ("extract", "key", "cleanup", "alpha", "stabilize", "hd", "pixel")`; `UPSTREAM` (key←extract, cleanup←key, alpha←cleanup, stabilize←alpha, hd←stabilize, pixel←stabilize); `PROFILE_STAGES = ("hd", "pixel")`.
- Registry (the contract sub-projects 3 and 4 code against): `StageRunner = Callable[[SpriteProject, ActionCard, List[Path], Path, ProgressFn, Optional[CancelToken]], List[Path]]` — `(project, action, input_frames, out_dir, progress, token) -> output frames written into out_dir as NNNN.png, sorted`; `SettingsFn = Callable[[SpriteProject, ActionCard], Dict[str, Any]]`; `STAGE_RUNNERS: Dict[str, StageRunner]`; `STAGE_SETTINGS: Dict[str, SettingsFn]`; `STAGE_CODE_VERSION: Dict[str, int]`; `register_stage(stage, runner, settings_fn=None, code_version=1) -> None` (re-registering replaces all three; unknown stage → `ValueError`). Default settings functions, all `(project, action) -> dict`: `extract_stage_settings`, `key_stage_settings`, `cleanup_stage_settings`, `alpha_stage_settings`, `stabilize_stage_settings`, `hd_stage_settings`, `pixel_stage_settings`; `DEFAULT_STAGE_SETTINGS` maps every stage to them and this task installs them into `STAGE_SETTINGS`/`STAGE_CODE_VERSION` (runners arrive in Task 10).
- Fingerprints and helpers: `stage_dir(project, action, stage) -> Path`; `list_frames(directory) -> List[Path]`; `stage_settings(project, action, stage) -> dict` (calls `STAGE_SETTINGS[stage](project, action)`); `stage_fingerprint(project, action, stage) -> str` (SHA-1 of upstream fingerprint + settings JSON + `STAGE_CODE_VERSION[stage]`); `is_stage_current(project, action, stage) -> bool`; `record_fingerprint(project, action, stage) -> str`; `register_external_frames(project, action) -> List[Path]`.

- [ ] **Step 1: Write the failing contract tests.**

`tests/sprite/test_pipeline.py`:

```python
import pytest

from core.sprite.pipeline import (
    STAGE_CODE_VERSION,
    STAGE_RUNNERS,
    STAGE_SETTINGS,
    STAGES,
    UPSTREAM,
    CancelToken,
    Cancelled,
    PipelineError,
    key_stage_settings,
    no_progress,
    register_external_frames,
    register_stage,
    stage_dir,
    stage_fingerprint,
    stage_settings,
)
from core.sprite.project import ActionCard, SpriteProject


def _project(tmp_path):
    project = SpriteProject(name="P")
    project.project_dir = tmp_path / "proj"
    project.project_dir.mkdir()
    action = ActionCard(id="a1", name="walk", prompt="walk")
    project.actions = [action]
    return project, action


@pytest.fixture
def registry():
    """Restore the stage registry after a test that re-registers a stage."""
    saved = (dict(STAGE_RUNNERS), dict(STAGE_SETTINGS), dict(STAGE_CODE_VERSION))
    yield
    for table, copy in zip((STAGE_RUNNERS, STAGE_SETTINGS, STAGE_CODE_VERSION), saved):
        table.clear()
        table.update(copy)


def test_cancel_token_contract():
    token = CancelToken()
    assert not token.cancelled
    token.raise_if_cancelled()
    token.cancel()
    assert token.cancelled
    with pytest.raises(Cancelled):
        token.raise_if_cancelled()
    no_progress("extract", 0, 0, "ok")


def test_stage_order_and_dirs(tmp_path):
    project, action = _project(tmp_path)
    assert STAGES == ("extract", "key", "cleanup", "alpha", "stabilize", "hd", "pixel")
    assert UPSTREAM["pixel"] == "stabilize" and UPSTREAM["hd"] == "stabilize"
    assert stage_dir(project, action, "key") == project.project_dir / "stages" / "a1" / "key"
    with pytest.raises(ValueError):
        stage_dir(project, action, "nope")


def test_every_stage_has_registered_settings_and_a_code_version(tmp_path):
    project, action = _project(tmp_path)
    assert set(STAGE_SETTINGS) == set(STAGES)
    assert set(STAGE_CODE_VERSION) == set(STAGES)
    assert stage_settings(project, action, "key")["key"]["tolerance"] == 0.20
    assert stage_settings(project, action, "extract")["clip"] is None
    with pytest.raises(ValueError):
        stage_settings(project, action, "nope")


def test_fingerprint_changes_only_downstream_of_a_changed_setting(tmp_path):
    project, action = _project(tmp_path)
    before = {s: stage_fingerprint(project, action, s) for s in STAGES}
    project.key.tolerance = 0.5
    after = {s: stage_fingerprint(project, action, s) for s in STAGES}
    assert after["extract"] == before["extract"]
    for stage in ("key", "cleanup", "alpha", "stabilize", "hd", "pixel"):
        assert after[stage] != before[stage], stage
    project.stabilize.pad_px = 4
    later = {s: stage_fingerprint(project, action, s) for s in STAGES}
    assert later["alpha"] == after["alpha"]
    assert later["stabilize"] != after["stabilize"]


def test_register_stage_replaces_settings_and_code_version(tmp_path, registry):
    project, action = _project(tmp_path)
    before = stage_fingerprint(project, action, "key")

    def runner(project, action, input_frames, out_dir, progress, token):
        return []

    register_stage("key", runner, key_stage_settings, code_version=2)
    assert STAGE_RUNNERS["key"] is runner
    assert STAGE_CODE_VERSION["key"] == 2
    assert stage_fingerprint(project, action, "key") != before
    register_stage("key", runner)  # no settings function -> empty settings
    assert stage_settings(project, action, "key") == {}
    with pytest.raises(ValueError):
        register_stage("bogus", runner)


def test_register_external_frames_requires_frames(tmp_path):
    project, action = _project(tmp_path)
    with pytest.raises(PipelineError):
        register_external_frames(project, action)
```

- [ ] **Step 2: Run them and watch them fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pipeline.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.sprite.pipeline'`.

- [ ] **Step 3: Create the contract half of the pipeline module.**

`core/sprite/pipeline.py`:

```python
"""Processing spine: stage registry, cache, cancel and progress contract.

Design sections 1.1 and 1.2. Every stage reads the previous stage's PNGs
from ``stages/<action_id>/<upstream>/`` and writes ``stages/<action_id>/<stage>/``.
A stage whose recorded fingerprint equals the computed one, and whose output
directory holds frames, is skipped. Raw clips and extracted frames are never
overwritten by a later stage.

Stages are pluggable. ``register_stage`` binds a stage name to a runner, a
settings function (what the fingerprint hashes) and a code version. Sub-project
1 registers ``extract``, ``stabilize`` and ``hd`` with real runners and
``key``, ``cleanup``, ``alpha``, ``pixel`` with ``identity_runner``.
Sub-project 3 re-registers the keying stages; sub-project 4 re-registers
``pixel``. ``run_pipeline`` never needs to change for that.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .project import ActionCard, SpriteProject

logger = logging.getLogger(__name__)


class Cancelled(Exception):
    """Raised by ``CancelToken.raise_if_cancelled`` when the user cancels."""


class CancelToken:
    """Thread-safe cancel flag. Stages poll it between frames and stages."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise Cancelled()


ProgressFn = Callable[[str, int, int, str], None]
# (stage_name, done, total, message) — done/total may be 0, 0 for indeterminate.


def no_progress(stage: str, done: int, total: int, message: str) -> None:
    """Default progress sink: does nothing."""


def check(token: Optional[CancelToken]) -> None:
    """Raise Cancelled when ``token`` is set. Safe to call with None."""
    if token is not None:
        token.raise_if_cancelled()


class PipelineError(Exception):
    """A stage cannot run. ``user_message`` is safe to show in the UI."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


# --- stage registry ---------------------------------------------------------

STAGES = ("extract", "key", "cleanup", "alpha", "stabilize", "hd", "pixel")
UPSTREAM: Dict[str, Optional[str]] = {
    "extract": None,
    "key": "extract",
    "cleanup": "key",
    "alpha": "cleanup",
    "stabilize": "alpha",
    "hd": "stabilize",
    "pixel": "stabilize",
}
PROFILE_STAGES = ("hd", "pixel")

StageRunner = Callable[
    [SpriteProject, ActionCard, List[Path], Path, ProgressFn, Optional[CancelToken]], List[Path]
]
# (project, action, input_frames, out_dir, progress, token) -> output frames,
# written into out_dir as NNNN.png and returned sorted.
SettingsFn = Callable[[SpriteProject, ActionCard], Dict[str, Any]]
# Returns the JSON-able settings that decide a stage's output; the
# fingerprint hashes it, so per-frame overrides belong in it too.

STAGE_RUNNERS: Dict[str, StageRunner] = {}
STAGE_SETTINGS: Dict[str, SettingsFn] = {}
STAGE_CODE_VERSION: Dict[str, int] = {}


def _no_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    return {}


def register_stage(stage: str, runner: StageRunner, settings_fn: Optional[SettingsFn] = None,
                   code_version: int = 1) -> None:
    """Bind a stage name to its runner, settings function and code version.

    Re-registering a stage replaces all three. Bump ``code_version`` when the
    runner's output changes for the same settings, so cached frames rebuild.
    """
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage!r}; use one of {STAGES}")
    STAGE_RUNNERS[stage] = runner
    STAGE_SETTINGS[stage] = settings_fn or _no_settings
    STAGE_CODE_VERSION[stage] = int(code_version)


def stage_dir(project: SpriteProject, action: ActionCard, stage: str) -> Path:
    if project.project_dir is None:
        raise ValueError("project_dir is not set")
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage!r}")
    return project.project_dir / "stages" / action.id / stage


def list_frames(directory: Path) -> List[Path]:
    """PNG frames in a stage directory, in numeric name order."""
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.png") if p.is_file())


# --- default settings functions (sub-project 1) -----------------------------


def _clip_info(action: ActionCard) -> Optional[Dict[str, object]]:
    if action.clip is None:
        return None
    path = Path(action.clip.path)
    info: Dict[str, object] = {"path": str(path)}
    try:
        st = path.stat()
        info["size"] = st.st_size
        info["mtime"] = int(st.st_mtime)
    except OSError:
        info["missing"] = True
    return info


def extract_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    """Extraction settings plus the clip identity, or the imported file list (G9)."""
    clip = _clip_info(action)
    settings: Dict[str, Any] = {"extraction": asdict(project.extraction), "clip": clip}
    if clip is None and project.project_dir is not None:
        frames = list_frames(stage_dir(project, action, "extract"))
        settings["external"] = [[p.name, p.stat().st_size] for p in frames]
    return settings


def key_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    return {"key": asdict(project.key), "plate_color": project.plate_color}


def cleanup_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    key = asdict(project.key)
    return {k: key[k] for k in ("despill", "edge_decontaminate", "choke_px", "feather_px", "despeckle_px")}


def alpha_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    return {"method": project.key.method, "ml_refine_edges": project.key.ml_refine_edges}


def stabilize_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    return {"stabilize": asdict(project.stabilize)}


def _profile_settings(project: SpriteProject, name: str) -> Dict[str, Any]:
    prof = project.profile(name)
    return {"profile": prof.to_dict() if prof else None, "anchor": project.stabilize.anchor}


def hd_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    return _profile_settings(project, "hd")


def pixel_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    return _profile_settings(project, "pixel")


DEFAULT_STAGE_SETTINGS: Dict[str, SettingsFn] = {
    "extract": extract_stage_settings,
    "key": key_stage_settings,
    "cleanup": cleanup_stage_settings,
    "alpha": alpha_stage_settings,
    "stabilize": stabilize_stage_settings,
    "hd": hd_stage_settings,
    "pixel": pixel_stage_settings,
}
for _stage, _settings_fn in DEFAULT_STAGE_SETTINGS.items():
    STAGE_SETTINGS[_stage] = _settings_fn
    STAGE_CODE_VERSION[_stage] = 1


# --- fingerprints ------------------------------------------------------------


def stage_settings(project: SpriteProject, action: ActionCard, stage: str) -> Dict[str, Any]:
    """The registered settings for a stage (empty dict when none is registered)."""
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage!r}")
    return STAGE_SETTINGS.get(stage, _no_settings)(project, action)


def stage_fingerprint(project: SpriteProject, action: ActionCard, stage: str) -> str:
    """SHA-1 of (upstream fingerprint + stage settings JSON + stage code version)."""
    upstream = UPSTREAM[stage]
    parent = stage_fingerprint(project, action, upstream) if upstream else ""
    payload = json.dumps(
        {"parent": parent, "settings": stage_settings(project, action, stage),
         "code": STAGE_CODE_VERSION.get(stage, 1)},
        sort_keys=True, default=str,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def is_stage_current(project: SpriteProject, action: ActionCard, stage: str) -> bool:
    recorded = project.stage_fingerprints.get(action.id, {}).get(stage)
    if recorded is None:
        return False
    if not list_frames(stage_dir(project, action, stage)):
        return False
    return recorded == stage_fingerprint(project, action, stage)


def record_fingerprint(project: SpriteProject, action: ActionCard, stage: str) -> str:
    fp = stage_fingerprint(project, action, stage)
    project.stage_fingerprints.setdefault(action.id, {})[stage] = fp
    return fp


def register_external_frames(project: SpriteProject, action: ActionCard) -> List[Path]:
    """Mark frames placed in the extract directory by an import as current (G9).

    ``slicing.import_png_sequence`` and ``slicing.slice_sheet`` write into
    ``stage_dir(project, action, "extract")``. Calling this afterwards is
    optional: ``run_pipeline`` also accepts a populated extract directory
    with ``action.clip is None`` and treats extraction as done. This helper
    records the fingerprint up front and clears a stale clip reference.
    """
    frames = list_frames(stage_dir(project, action, "extract"))
    if not frames:
        raise PipelineError("No frames were imported for this action")
    action.clip = None
    record_fingerprint(project, action, "extract")
    return frames
```

- [ ] **Step 4: Run the tests again.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pipeline.py -v
```

Expected: `6 passed`.

- [ ] **Step 5: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/pipeline.py tests/sprite/test_pipeline.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): pipeline cancel/progress contract, stage registry and cache fingerprints"
```

---

### Task 7: Frame extraction with ffmpeg

**Files:**
- Create: `core/sprite/extract.py`
- Create: `tests/sprite/test_extract.py`

**Interfaces:**
- Consumes: `core.video.ffmpeg_utils.get_ffmpeg_path()`, `get_ffmpeg_manager().ffprobe_path` — imported lazily inside `_ffmpeg()`/`_ffprobe()`, never at module level, because `core.video`'s package import loads the cloud clients; `core.sprite.pipeline.CancelToken`, `ProgressFn`, `check`, `no_progress`; `core.sprite.project.ExtractionSettings`; `cv2.VideoCapture` (probe fallback).
- Produces: `FFmpegError(user_message)` with `.user_message`; `ExtractResult(frames: List[Path], source_fps: float, source_frames: int, duration_s: float)`; `probe_video(path) -> Dict[str, Any]` with keys `fps`, `nb_frames`, `duration`, `width`, `height`, `source`; `extract_frames(video, out_dir, settings, *, progress=no_progress, token=None) -> ExtractResult`; `estimate_frame_count(probe, settings) -> int`; `cull_duplicates(frames, threshold) -> List[Path]`.
- ffmpeg arguments: `every_n` → `-vf select=not(mod(n\,N)) -fps_mode vfr`; `target_fps` → `-vf fps=F`; `exact_n` → every frame into a temp dir beside `out_dir`, then indices `round(i*(count-1)/(N-1))`; trim → `-ss START` before `-i` and `-t SPAN` after it. Output `%04d.png`.

- [ ] **Step 1: Write the failing tests.**

`tests/sprite/test_extract.py`:

```python
import pytest
from PIL import Image

from core.sprite.extract import (
    FFmpegError,
    cull_duplicates,
    estimate_frame_count,
    extract_frames,
    probe_video,
)
from core.sprite.pipeline import CancelToken, Cancelled
from core.sprite.project import ExtractionSettings
from tests.sprite.synth import write_frames


def test_probe_reports_fps_frames_duration_and_size(synthetic_mp4):
    probe = probe_video(synthetic_mp4)
    assert probe["fps"] == pytest.approx(24.0)
    assert probe["nb_frames"] == 12
    assert probe["duration"] == pytest.approx(0.5, abs=0.05)
    assert (probe["width"], probe["height"]) == (112, 64)
    assert probe["source"] in ("ffprobe", "opencv")


def test_probe_missing_file_raises(tmp_path):
    with pytest.raises(FFmpegError):
        probe_video(tmp_path / "nope.mp4")


def test_estimate_frame_count_for_every_mode():
    probe = {"fps": 24.0, "nb_frames": 48, "duration": 2.0}
    assert estimate_frame_count(probe, ExtractionSettings(mode="every_n", every_n=8)) == 6
    assert estimate_frame_count(probe, ExtractionSettings(mode="target_fps", target_fps=12)) == 24
    assert estimate_frame_count(probe, ExtractionSettings(mode="exact_n", exact_n=8)) == 8
    assert estimate_frame_count(probe, ExtractionSettings(mode="exact_n", exact_n=99)) == 48
    trimmed = ExtractionSettings(mode="every_n", every_n=8, trim_start_s=0.5, trim_end_s=0.5)
    assert estimate_frame_count(probe, trimmed) == 3
    assert estimate_frame_count({"fps": 0, "duration": 0}, ExtractionSettings()) == 0
    with pytest.raises(ValueError):
        estimate_frame_count(probe, ExtractionSettings(mode="bogus"))


def test_extract_every_n(tmp_path, synthetic_mp4):
    result = extract_frames(synthetic_mp4, tmp_path / "out", ExtractionSettings(mode="every_n", every_n=4))
    assert [p.name for p in result.frames] == ["0001.png", "0002.png", "0003.png"]
    assert result.source_fps == pytest.approx(24.0)
    assert result.source_frames == 12
    with Image.open(result.frames[0]) as im:
        assert im.size == (112, 64)


def test_extract_target_fps(tmp_path, synthetic_mp4):
    result = extract_frames(synthetic_mp4, tmp_path / "out", ExtractionSettings(mode="target_fps", target_fps=12))
    assert len(result.frames) == 6


def test_extract_exact_n_picks_evenly_spaced_frames(tmp_path, synthetic_mp4):
    result = extract_frames(synthetic_mp4, tmp_path / "out", ExtractionSettings(mode="exact_n", exact_n=4))
    assert [p.name for p in result.frames] == ["0001.png", "0002.png", "0003.png", "0004.png"]
    # Picks are source frames 0, 4, 7, 11: the square's left edge moves 6 px per frame.
    edges = []
    for path in result.frames:
        with Image.open(path) as im:
            rgb = im.convert("RGB")
            row = [rgb.getpixel((x, 32)) for x in range(112)]
        edges.append(next(x for x, px in enumerate(row) if px[0] > 120))
    assert edges[0] < edges[1] < edges[2] < edges[3]
    assert not list((tmp_path / "out").parent.glob("extract_all_*"))


def test_extract_exact_n_of_one_keeps_the_first_frame(tmp_path, synthetic_mp4):
    result = extract_frames(synthetic_mp4, tmp_path / "out", ExtractionSettings(mode="exact_n", exact_n=1))
    assert len(result.frames) == 1


def test_extract_honours_trim(tmp_path, synthetic_mp4):
    settings = ExtractionSettings(mode="every_n", every_n=1, trim_start_s=0.25, trim_end_s=0.125)
    result = extract_frames(synthetic_mp4, tmp_path / "out", settings)
    assert 2 <= len(result.frames) <= 4


def test_extract_clears_stale_output(tmp_path, synthetic_mp4):
    out = tmp_path / "out"
    out.mkdir()
    (out / "9999.png").write_bytes(b"stale")
    extract_frames(synthetic_mp4, out, ExtractionSettings(mode="every_n", every_n=6))
    assert not (out / "9999.png").exists()


def test_extract_cancel(tmp_path, synthetic_mp4):
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        extract_frames(synthetic_mp4, tmp_path / "out", ExtractionSettings(), token=token)


def test_extract_bad_video_raises_ffmpeg_error(tmp_path, ffmpeg_exe):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(FFmpegError) as info:
        extract_frames(bad, tmp_path / "out", ExtractionSettings())
    assert info.value.user_message


def test_cull_duplicates_keeps_distinct_frames(tmp_path):
    frames = write_frames(tmp_path / "f", 4, alpha=False)
    dup = tmp_path / "f" / "0005.png"
    Image.open(frames[3]).save(dup)
    kept = cull_duplicates(frames + [dup], threshold=0.001)
    assert kept == frames
    assert cull_duplicates(frames, threshold=0.99) == [frames[0]]


def test_extract_with_cull_renumbers(tmp_path, synthetic_mp4):
    settings = ExtractionSettings(mode="every_n", every_n=1, cull_duplicates=True, duplicate_threshold=0.5)
    result = extract_frames(synthetic_mp4, tmp_path / "out", settings)
    assert [p.name for p in result.frames] == ["0001.png"]
```

- [ ] **Step 2: Run them and watch them fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_extract.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.sprite.extract'`.

- [ ] **Step 3: Create the extraction module.**

`core/sprite/extract.py`:

```python
"""Frame extraction from video clips via ffmpeg (design section 4.1).

Modes: ``every_n`` keeps one frame in N; ``target_fps`` resamples with the
``fps`` filter; ``exact_n`` extracts every frame to a temp dir, then keeps N
evenly spaced frames. Output is ``0001.png``, ``0002.png``, ... in ``out_dir``.
"""

from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

from .pipeline import CancelToken, ProgressFn, check, no_progress
from .project import ExtractionSettings

logger = logging.getLogger(__name__)

FFMPEG_TIMEOUT_S = 600
STDERR_TAIL = 800


class FFmpegError(Exception):
    """ffmpeg/ffprobe failed. ``user_message`` is safe to show in the UI."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass
class ExtractResult:
    frames: List[Path]
    source_fps: float
    source_frames: int
    duration_s: float


def _ffmpeg() -> str:
    # Imported here on purpose: core.video's package import pulls in the
    # cloud video clients (several seconds); the GUI tab and CLI must not pay
    # that on ``import core.sprite``.
    from core.video.ffmpeg_utils import get_ffmpeg_path

    path = get_ffmpeg_path()
    if not path:
        raise FFmpegError("ffmpeg is not available. Install ffmpeg or the imageio-ffmpeg package.")
    return path


def _ffprobe() -> Optional[str]:
    from core.video.ffmpeg_utils import get_ffmpeg_manager

    manager = get_ffmpeg_manager()
    if manager.ffprobe_path:
        return manager.ffprobe_path
    if manager.ffmpeg_path:
        sibling = Path(manager.ffmpeg_path).parent / "ffprobe"
        if sibling.exists():
            return str(sibling)
    found = shutil.which("ffprobe")
    return found


def _parse_rate(text: str) -> float:
    if not text or text == "0/0":
        return 0.0
    if "/" in text:
        num, den = text.split("/", 1)
        try:
            return float(num) / float(den) if float(den) else 0.0
        except ValueError:
            return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _probe_with_ffprobe(ffprobe: str, path: Path) -> Dict[str, Any]:
    cmd = [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    logger.info(f"ffprobe: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise FFmpegError(f"ffprobe failed on {path.name}: {result.stderr[-STDERR_TAIL:]}")
    data = json.loads(result.stdout or "{}")
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise FFmpegError(f"No video stream in {path.name}")
    fps = _parse_rate(str(video.get("avg_frame_rate") or video.get("r_frame_rate") or ""))
    duration = 0.0
    for holder in (video, data.get("format", {})):
        try:
            duration = float(holder.get("duration"))
            if duration > 0:
                break
        except (TypeError, ValueError):
            continue
    try:
        nb_frames = int(video.get("nb_frames"))
    except (TypeError, ValueError):
        nb_frames = int(round(duration * fps)) if fps else 0
    return {
        "fps": fps,
        "nb_frames": nb_frames,
        "duration": duration,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "source": "ffprobe",
    }


def _probe_with_opencv(path: Path) -> Dict[str, Any]:
    import cv2

    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise FFmpegError(f"Cannot open video: {path}")
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        nb_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    finally:
        cap.release()
    duration = nb_frames / fps if fps else 0.0
    return {"fps": fps, "nb_frames": nb_frames, "duration": duration,
            "width": width, "height": height, "source": "opencv"}


def probe_video(path: Path) -> Dict[str, Any]:
    """Return fps, nb_frames, duration, width, height for a video.

    Uses ffprobe when one is installed. The imageio-ffmpeg package ships no
    ffprobe, so the fallback reads the same numbers through OpenCV.
    """
    path = Path(path)
    if not path.exists():
        raise FFmpegError(f"Video not found: {path}")
    ffprobe = _ffprobe()
    if ffprobe:
        try:
            return _probe_with_ffprobe(ffprobe, path)
        except (FFmpegError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            logger.warning(f"ffprobe failed ({exc}); falling back to OpenCV")
    return _probe_with_opencv(path)


def _usable_span(probe: Dict[str, Any], settings: ExtractionSettings) -> float:
    duration = float(probe.get("duration") or 0.0)
    span = duration - max(0.0, settings.trim_start_s) - max(0.0, settings.trim_end_s)
    return max(0.0, span)


def estimate_frame_count(probe: Dict[str, Any], settings: ExtractionSettings) -> int:
    """Predict how many frames ``extract_frames`` will write."""
    fps = float(probe.get("fps") or 0.0)
    span = _usable_span(probe, settings)
    if span <= 0 or fps <= 0:
        return 0
    in_range = max(1, int(round(span * fps)))
    if settings.mode == "every_n":
        return math.ceil(in_range / max(1, settings.every_n))
    if settings.mode == "target_fps":
        return max(1, int(round(span * max(1, settings.target_fps))))
    if settings.mode == "exact_n":
        return min(max(1, settings.exact_n), in_range)
    raise ValueError(f"Unknown extraction mode: {settings.mode!r}")


def _run_ffmpeg(cmd: List[str]) -> None:
    logger.info(f"ffmpeg: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(f"ffmpeg timed out after {FFMPEG_TIMEOUT_S}s") from exc
    except OSError as exc:
        raise FFmpegError(f"ffmpeg could not start: {exc}") from exc
    if result.returncode != 0:
        tail = (result.stderr or "").strip()[-STDERR_TAIL:]
        raise FFmpegError(f"ffmpeg failed (exit {result.returncode}): {tail}")


def _renumber(paths: List[Path], out_dir: Path) -> List[Path]:
    """Move ``paths`` into ``out_dir`` as 0001.png, 0002.png, ..."""
    out_dir.mkdir(parents=True, exist_ok=True)
    staged: List[Path] = []
    for index, src in enumerate(paths, start=1):
        tmp = out_dir / f".tmp_{index:04d}.png"
        shutil.move(str(src), str(tmp))
        staged.append(tmp)
    final: List[Path] = []
    for index, tmp in enumerate(staged, start=1):
        dest = out_dir / f"{index:04d}.png"
        tmp.replace(dest)
        final.append(dest)
    return final


def cull_duplicates(frames: List[Path], threshold: float) -> List[Path]:
    """Drop frames whose mean absolute RGB difference to the last kept frame is < threshold.

    ``threshold`` is on a 0..1 scale. The first frame is always kept. Files
    are not deleted; the caller decides what to do with the dropped paths.
    """
    kept: List[Path] = []
    last: Optional[np.ndarray] = None
    for path in frames:
        with Image.open(path) as im:
            arr = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
        if last is not None and arr.shape == last.shape:
            if float(np.mean(np.abs(arr - last))) < threshold:
                continue
        kept.append(path)
        last = arr
    return kept


def extract_frames(video: Path, out_dir: Path, settings: ExtractionSettings, *,
                   progress: ProgressFn = no_progress,
                   token: Optional[CancelToken] = None) -> ExtractResult:
    """Extract frames from ``video`` into ``out_dir`` per ``settings``."""
    video = Path(video)
    out_dir = Path(out_dir)
    ffmpeg = _ffmpeg()
    probe = probe_video(video)
    span = _usable_span(probe, settings)
    check(token)
    progress("extract", 0, 0, f"extract: probing {video.name}")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    cmd: List[str] = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    if settings.trim_start_s > 0:
        cmd += ["-ss", f"{settings.trim_start_s:.3f}"]
    cmd += ["-i", str(video)]
    if settings.trim_end_s > 0 and span > 0:
        cmd += ["-t", f"{span:.3f}"]

    if settings.mode == "every_n":
        n = max(1, int(settings.every_n))
        cmd += ["-vf", f"select=not(mod(n\\,{n}))", "-fps_mode", "vfr", str(out_dir / "%04d.png")]
        _run_ffmpeg(cmd)
        frames = sorted(out_dir.glob("*.png"))
    elif settings.mode == "target_fps":
        cmd += ["-vf", f"fps={max(1, int(settings.target_fps))}", str(out_dir / "%04d.png")]
        _run_ffmpeg(cmd)
        frames = sorted(out_dir.glob("*.png"))
    elif settings.mode == "exact_n":
        n = max(1, int(settings.exact_n))
        temp = Path(tempfile.mkdtemp(prefix="extract_all_", dir=out_dir.parent))
        try:
            cmd += [str(temp / "%04d.png")]
            _run_ffmpeg(cmd)
            everything = sorted(temp.glob("*.png"))
            count = len(everything)
            if count == 0:
                raise FFmpegError(f"ffmpeg produced no frames from {video.name}")
            if n == 1 or count == 1:
                picks = [0]
            else:
                picks = sorted({int(round(i * (count - 1) / (n - 1))) for i in range(min(n, count))})
            frames = _renumber([everything[i] for i in picks], out_dir)
        finally:
            shutil.rmtree(temp, ignore_errors=True)
    else:
        raise ValueError(f"Unknown extraction mode: {settings.mode!r}")

    check(token)
    if not frames:
        raise FFmpegError(f"ffmpeg produced no frames from {video.name}")

    if settings.cull_duplicates and len(frames) > 1:
        kept = cull_duplicates(frames, settings.duplicate_threshold)
        if len(kept) != len(frames):
            for path in frames:
                if path not in kept:
                    path.unlink()
            frames = _renumber(kept, out_dir)

    progress("extract", len(frames), len(frames), f"extract: {len(frames)} frames")
    return ExtractResult(
        frames=frames,
        source_fps=float(probe.get("fps") or 0.0),
        source_frames=int(probe.get("nb_frames") or 0),
        duration_s=float(probe.get("duration") or 0.0),
    )
```

- [ ] **Step 4: Run the tests again.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_extract.py -v
```

Expected: `13 passed` with ffmpeg present. Without ffmpeg the ten clip tests skip and `3 passed, 10 skipped` is the result; ffmpeg is present on this machine through `imageio-ffmpeg`, so expect `13 passed`.

- [ ] **Step 5: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/extract.py tests/sprite/test_extract.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): ffmpeg frame extraction (every-N, target fps, exact-N)"
```

---

### Task 8: Sheet slicing and PNG-sequence import

**Files:**
- Create: `core/sprite/slicing.py`
- Create: `tests/sprite/test_slicing.py`

**Interfaces:**
- Consumes: Pillow, numpy; `core.sprite.models.Size`.
- Produces: `GridGuess(columns, rows, cell: Size, confidence: float)`; `foreground_mask(sheet, key_color=None) -> np.ndarray`; `guess_grid(sheet: Image, key_color=None) -> GridGuess` (confidence < 0.6 = ask the user); `slice_sheet(sheet: Path, out_dir, columns, rows, cell=None, margin=0, spacing=0) -> List[Path]`; `import_png_sequence(paths, out_dir) -> List[Path]`. Both writers produce `0001.png…` RGBA; the caller then runs `pipeline.register_external_frames`.

- [ ] **Step 1: Write the failing tests.**

`tests/sprite/test_slicing.py`:

```python
import numpy as np
import pytest
from PIL import Image

from core.sprite.slicing import GridGuess, guess_grid, import_png_sequence, slice_sheet
from tests.sprite.synth import draw_frame


def _sheet(columns=4, rows=2, cell=32, alpha=True, margin=0, spacing=0):
    w = 2 * margin + columns * cell + (columns - 1) * spacing
    h = 2 * margin + rows * cell + (rows - 1) * spacing
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    if not alpha:
        arr[..., 1] = 255
        arr[..., 3] = 255
    for r in range(rows):
        for c in range(columns):
            x = margin + c * (cell + spacing) + 8
            y = margin + r * (cell + spacing) + 8
            arr[y:y + 16, x:x + 16] = (200, 40, 40, 255)
    return Image.fromarray(arr)


def test_guess_grid_on_a_transparent_sheet():
    guess = guess_grid(_sheet())
    assert isinstance(guess, GridGuess)
    assert (guess.columns, guess.rows, guess.cell) == (4, 2, (32, 32))
    assert guess.confidence >= 0.6


def test_guess_grid_on_a_chroma_sheet_with_and_without_key_color():
    sheet = _sheet(alpha=False)
    assert guess_grid(sheet, key_color="#00FF00").columns == 4
    assert guess_grid(sheet).rows == 2


def test_guess_grid_low_confidence_for_a_single_sprite():
    guess = guess_grid(_sheet(columns=1, rows=1))
    assert (guess.columns, guess.rows) == (1, 1)
    assert guess.confidence < 0.6


def test_slice_sheet_writes_row_major_frames(tmp_path):
    sheet = tmp_path / "sheet.png"
    _sheet(columns=3, rows=2, cell=32).save(sheet)
    frames = slice_sheet(sheet, tmp_path / "out", columns=3, rows=2)
    assert [p.name for p in frames] == [f"{i:04d}.png" for i in range(1, 7)]
    with Image.open(frames[0]) as im:
        assert im.size == (32, 32) and im.mode == "RGBA"
        assert im.getpixel((8, 8)) == (200, 40, 40, 255)


def test_slice_sheet_with_margin_and_spacing(tmp_path):
    sheet = tmp_path / "sheet.png"
    _sheet(columns=2, rows=2, cell=32, margin=4, spacing=2).save(sheet)
    frames = slice_sheet(sheet, tmp_path / "out", columns=2, rows=2, margin=4, spacing=2)
    assert len(frames) == 4
    with Image.open(frames[3]) as im:
        assert im.size == (32, 32)
        assert im.getpixel((8, 8)) == (200, 40, 40, 255)


def test_slice_sheet_rejects_cells_outside_the_sheet(tmp_path):
    sheet = tmp_path / "sheet.png"
    _sheet(columns=2, rows=1, cell=32).save(sheet)
    with pytest.raises(ValueError):
        slice_sheet(sheet, tmp_path / "out", columns=3, rows=1, cell=(32, 32))
    with pytest.raises(ValueError):
        slice_sheet(sheet, tmp_path / "out", columns=0, rows=1)


def test_import_png_sequence_copies_in_order_and_renumbers(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    paths = []
    for name, index in (("b.png", 1), ("a.jpg", 0)):
        path = src / name
        draw_frame(index, alpha=name.endswith(".png")).convert("RGBA" if name.endswith(".png") else "RGB").save(path)
        paths.append(path)
    out = import_png_sequence(paths, tmp_path / "out")
    assert [p.name for p in out] == ["0001.png", "0002.png"]
    with Image.open(out[1]) as im:
        assert im.mode == "RGBA"
```

- [ ] **Step 2: Run them and watch them fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_slicing.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.sprite.slicing'`.

- [ ] **Step 3: Create the slicing module.**

`core/sprite/slicing.py`:

```python
"""Sheet slicing and PNG-sequence import (design section 4.1, gap G9).

External inputs enter the spine after ``extract``: both functions here write
``0001.png``... into an extract directory, and the caller registers them with
``pipeline.register_external_frames``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from .models import Size

logger = logging.getLogger(__name__)

BACKGROUND_TOLERANCE = 12  # per-channel, 0..255
ALPHA_BACKGROUND = 8       # alpha at or below this counts as background


@dataclass
class GridGuess:
    columns: int
    rows: int
    cell: Size
    confidence: float


def _hex_to_rgb(text: str) -> Tuple[int, int, int]:
    text = text.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"Not a #RRGGBB color: {text!r}")
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def foreground_mask(sheet: Image.Image, key_color: Optional[str] = None) -> np.ndarray:
    """True where a pixel belongs to a sprite, False where it is background.

    Order of evidence: real transparency, then the key color, then the
    top-left corner color.
    """
    rgba = np.asarray(sheet.convert("RGBA"))
    alpha = rgba[..., 3]
    if np.any(alpha <= ALPHA_BACKGROUND):
        return alpha > ALPHA_BACKGROUND
    rgb = rgba[..., :3].astype(np.int16)
    bg = np.array(_hex_to_rgb(key_color), dtype=np.int16) if key_color else rgb[0, 0]
    diff = np.abs(rgb - bg).max(axis=2)
    return diff > BACKGROUND_TOLERANCE


def _runs(flags: np.ndarray) -> List[Tuple[int, int]]:
    """Start/end (exclusive) of each run of True in a 1-D bool array."""
    runs: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for index, flag in enumerate(flags.tolist()):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(flags)))
    return runs


def _axis_confidence(runs: List[Tuple[int, int]]) -> Optional[float]:
    if len(runs) < 2:
        return None
    if len(runs) == 2:
        return 0.8
    centers = np.array([(a + b) / 2.0 for a, b in runs])
    pitches = np.diff(centers)
    mean = float(pitches.mean())
    if mean <= 0:
        return 0.0
    return float(max(0.0, min(1.0, 1.0 - pitches.std() / mean)))


def guess_grid(sheet: Image.Image, key_color: Optional[str] = None) -> GridGuess:
    """Guess columns, rows and cell size from the gaps between sprites.

    Projects the foreground mask onto both axes; each run of foreground is a
    column (or row) of cells. ``confidence`` below 0.6 means "ask the user".
    """
    mask = foreground_mask(sheet, key_color)
    height, width = mask.shape
    col_runs = _runs(mask.any(axis=0))
    row_runs = _runs(mask.any(axis=1))
    columns = max(1, len(col_runs))
    rows = max(1, len(row_runs))
    scores = [s for s in (_axis_confidence(col_runs), _axis_confidence(row_runs)) if s is not None]
    confidence = min(scores) if scores else 0.3
    cell = (max(1, width // columns), max(1, height // rows))
    return GridGuess(columns=columns, rows=rows, cell=cell, confidence=round(confidence, 3))


def slice_sheet(sheet: Path, out_dir: Path, columns: int, rows: int,
                cell: Optional[Size] = None, margin: int = 0, spacing: int = 0) -> List[Path]:
    """Cut a sheet into ``columns * rows`` RGBA PNG frames, row-major."""
    if columns < 1 or rows < 1:
        raise ValueError("columns and rows must be at least 1")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(sheet) as im:
        image = im.convert("RGBA")
    width, height = image.size
    if cell is None:
        cw = (width - 2 * margin - (columns - 1) * spacing) // columns
        ch = (height - 2 * margin - (rows - 1) * spacing) // rows
        cell = (cw, ch)
    cw, ch = cell
    if cw < 1 or ch < 1:
        raise ValueError(f"Cell size {cell} does not fit a {width}x{height} sheet")
    written: List[Path] = []
    index = 1
    for row in range(rows):
        for col in range(columns):
            x = margin + col * (cw + spacing)
            y = margin + row * (ch + spacing)
            if x + cw > width or y + ch > height:
                raise ValueError(
                    f"Cell ({col},{row}) at {x},{y} size {cw}x{ch} lies outside the {width}x{height} sheet"
                )
            frame = image.crop((x, y, x + cw, y + ch))
            dest = out_dir / f"{index:04d}.png"
            frame.save(dest, format="PNG")
            written.append(dest)
            index += 1
    logger.info(f"Sliced {sheet} into {len(written)} frames ({columns}x{rows}, cell {cw}x{ch})")
    return written


def import_png_sequence(paths: Sequence[Path], out_dir: Path) -> List[Path]:
    """Copy images into ``out_dir`` as RGBA PNGs numbered 0001.png... in the given order."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for index, src in enumerate(paths, start=1):
        with Image.open(src) as im:
            frame = im.convert("RGBA")
        dest = out_dir / f"{index:04d}.png"
        frame.save(dest, format="PNG")
        written.append(dest)
    logger.info(f"Imported {len(written)} frames into {out_dir}")
    return written
```

- [ ] **Step 4: Run the tests again.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_slicing.py -v
```

Expected: `7 passed`.

- [ ] **Step 5: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/slicing.py tests/sprite/test_slicing.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): sheet slicing and PNG sequence import"
```

---

### Task 9: Stabilise — union bbox, solid-border bbox, crop and pad

**Files:**
- Create: `core/sprite/stabilize.py`
- Create: `tests/sprite/test_stabilize.py`

**Interfaces:**
- Consumes: `core.sprite.pipeline.CancelToken`, `ProgressFn`, `check`, `no_progress`; `core.sprite.models.Rect`, `Size`.
- Produces: `ANCHORS = ("bottom_center", "center", "top_left", "top_center", "bottom_left")`; `has_transparency(frame) -> bool`; `union_alpha_bbox(frames) -> Rect`; `solid_border_bbox(frames, variance=5.0) -> Rect`; `anchor_offset(anchor, content, cell) -> Tuple[int, int]`; `fit_size(content, cell) -> Size`; `crop_and_pad(frames, out_dir, bbox, cell, anchor="bottom_center", pad_px=0, *, progress=no_progress, token=None) -> List[Path]` (LANCZOS, one scale factor for both axes, transparent canvas, output names equal input names).

- [ ] **Step 1: Write the failing tests.**

`tests/sprite/test_stabilize.py`:

```python
import pytest
from PIL import Image

from core.sprite.pipeline import CancelToken, Cancelled
from core.sprite.stabilize import (
    ANCHORS,
    anchor_offset,
    crop_and_pad,
    fit_size,
    has_transparency,
    solid_border_bbox,
    union_alpha_bbox,
)


def test_union_alpha_bbox_covers_every_frame(alpha_frames):
    assert union_alpha_bbox(alpha_frames) == (8, 20, 90, 24)
    assert union_alpha_bbox(alpha_frames[:1]) == (8, 20, 24, 24)


def test_solid_border_bbox_on_chroma_frames(green_frames):
    assert solid_border_bbox(green_frames) == (8, 20, 90, 24)
    assert has_transparency(green_frames[0]) is False


def test_has_transparency(alpha_frames):
    assert has_transparency(alpha_frames[0]) is True


def test_fit_size_never_distorts():
    assert fit_size((90, 24), (48, 48)) == (48, 13)
    assert fit_size((24, 24), (48, 48)) == (48, 48)
    assert fit_size((100, 50), (50, 50)) == (50, 25)


@pytest.mark.parametrize("anchor,expected", [
    ("bottom_center", (12, 40)), ("center", (12, 20)), ("top_left", (0, 0)),
    ("top_center", (12, 0)), ("bottom_left", (0, 40)),
])
def test_anchor_offset(anchor, expected):
    assert anchor_offset(anchor, (40, 24), (64, 64)) == expected


def test_anchor_offset_rejects_unknown_names():
    with pytest.raises(ValueError):
        anchor_offset("upper_right", (1, 1), (2, 2))
    assert ANCHORS == ("bottom_center", "center", "top_left", "top_center", "bottom_left")


def test_crop_and_pad_scales_proportionally_and_anchors(tmp_path, alpha_frames):
    bbox = union_alpha_bbox(alpha_frames)
    out = crop_and_pad(alpha_frames, tmp_path / "cells", bbox, (64, 64), anchor="bottom_center", pad_px=0)
    assert len(out) == 12 and out[0].name == "0001.png"
    with Image.open(out[0]) as im:
        assert im.size == (64, 64)
        alpha = im.getchannel("A")
        solid = alpha.point(lambda v: 255 if v >= 128 else 0).getbbox()
        # The 90x24 crop scales by 64/90 to 64x17 and sits on the bottom edge.
        assert solid[3] == 64
        assert solid[1] >= 64 - 18
        # Frame 0 holds the square at the crop's left edge: 24 px scaled to ~17 px.
        assert solid[0] == 0
        assert 15 <= solid[2] - solid[0] <= 19
        assert alpha.getpixel((32, 2)) == 0


def test_crop_and_pad_identity_when_cell_equals_crop(tmp_path, alpha_frames):
    bbox = union_alpha_bbox(alpha_frames)
    cell = (bbox[2] + 4, bbox[3] + 4)
    out = crop_and_pad(alpha_frames, tmp_path / "cells", bbox, cell, anchor="top_left", pad_px=2)
    with Image.open(out[0]) as im, Image.open(alpha_frames[0]) as src:
        assert im.size == cell
        assert im.getpixel((2, 2)) == src.getpixel((8, 20))
        assert im.getpixel((0, 0)) == (0, 0, 0, 0)


def test_crop_and_pad_cancel_and_validation(tmp_path, alpha_frames):
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        crop_and_pad(alpha_frames, tmp_path / "c", (0, 0, 8, 8), (8, 8), token=token)
    with pytest.raises(ValueError):
        crop_and_pad(alpha_frames, tmp_path / "c", (0, 0, 8, 8), (0, 8))
    with pytest.raises(ValueError):
        crop_and_pad(alpha_frames, tmp_path / "c", (0, 0, 8, 8), (8, 8), anchor="nope")
```

- [ ] **Step 2: Run them and watch them fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_stabilize.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.sprite.stabilize'`.

- [ ] **Step 3: Create the stabilise module.**

`core/sprite/stabilize.py`:

```python
"""Auto-crop and pad frames into a fixed cell (design section 4.1).

``crop_and_pad`` scales proportionally and never distorts: the crop is
resized with one scale factor for both axes, then placed on a transparent
canvas of the cell size at the requested anchor.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from .models import Rect, Size
from .pipeline import CancelToken, ProgressFn, check, no_progress

logger = logging.getLogger(__name__)

ANCHORS = ("bottom_center", "center", "top_left", "top_center", "bottom_left")


def has_transparency(frame: Path) -> bool:
    with Image.open(frame) as im:
        if im.mode not in ("RGBA", "LA", "P"):
            return False
        alpha = np.asarray(im.convert("RGBA"))[..., 3]
    return bool(np.any(alpha < 255))


def union_alpha_bbox(frames: Sequence[Path]) -> Rect:
    """Smallest rect covering every non-transparent pixel of every frame."""
    x0 = y0 = None
    x1 = y1 = None
    size: Optional[Tuple[int, int]] = None
    for path in frames:
        with Image.open(path) as im:
            size = size or im.size
            box = im.convert("RGBA").getchannel("A").getbbox()
        if box is None:
            continue
        x0 = box[0] if x0 is None else min(x0, box[0])
        y0 = box[1] if y0 is None else min(y0, box[1])
        x1 = box[2] if x1 is None else max(x1, box[2])
        y1 = box[3] if y1 is None else max(y1, box[3])
    if x0 is None or size is None:
        w, h = size or (0, 0)
        return (0, 0, w, h)
    return (x0, y0, x1 - x0, y1 - y0)


def solid_border_bbox(frames: Sequence[Path], variance: float = 5.0) -> Rect:
    """Union bbox of pixels that differ from each frame's top-left color.

    Pre-key path: the frames still carry the chroma plate, so alpha is
    useless. ``variance`` is the per-channel tolerance (0..255).
    """
    x0 = y0 = None
    x1 = y1 = None
    size: Optional[Tuple[int, int]] = None
    for path in frames:
        with Image.open(path) as im:
            rgb = np.asarray(im.convert("RGB"), dtype=np.int16)
        size = size or (rgb.shape[1], rgb.shape[0])
        diff = np.abs(rgb - rgb[0, 0]).max(axis=2)
        ys, xs = np.nonzero(diff > variance)
        if xs.size == 0:
            continue
        bx0, bx1 = int(xs.min()), int(xs.max()) + 1
        by0, by1 = int(ys.min()), int(ys.max()) + 1
        x0 = bx0 if x0 is None else min(x0, bx0)
        y0 = by0 if y0 is None else min(y0, by0)
        x1 = bx1 if x1 is None else max(x1, bx1)
        y1 = by1 if y1 is None else max(y1, by1)
    if x0 is None or size is None:
        w, h = size or (0, 0)
        return (0, 0, w, h)
    return (x0, y0, x1 - x0, y1 - y0)


def anchor_offset(anchor: str, content: Size, cell: Size) -> Tuple[int, int]:
    """Top-left position of ``content`` inside ``cell`` for an anchor name."""
    if anchor not in ANCHORS:
        raise ValueError(f"Unknown anchor {anchor!r}; use one of {ANCHORS}")
    cw, ch = cell
    w, h = content
    vertical, _, horizontal = anchor.partition("_")
    if anchor == "center":
        vertical, horizontal = "center", "center"
    x = {"left": 0, "center": (cw - w) // 2}[horizontal]
    y = {"top": 0, "center": (ch - h) // 2, "bottom": ch - h}[vertical]
    return (x, y)


def fit_size(content: Size, cell: Size) -> Size:
    """Largest size with the aspect of ``content`` that fits inside ``cell``."""
    w, h = content
    cw, ch = cell
    if w < 1 or h < 1:
        return (0, 0)
    scale = min(cw / w, ch / h)
    return (max(1, int(round(w * scale))), max(1, int(round(h * scale))))


def crop_and_pad(frames: Sequence[Path], out_dir: Path, bbox: Rect, cell: Size,
                 anchor: str = "bottom_center", pad_px: int = 0,
                 *, progress: ProgressFn = no_progress,
                 token: Optional[CancelToken] = None) -> List[Path]:
    """Crop every frame to ``bbox`` (+pad), scale proportionally into ``cell``, anchor.

    Output files keep their input names. Frames are never distorted; a
    crop larger than the cell shrinks, a smaller one grows, both with
    ``Image.LANCZOS`` and one scale factor for both axes.
    """
    if anchor not in ANCHORS:
        raise ValueError(f"Unknown anchor {anchor!r}; use one of {ANCHORS}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    x, y, w, h = bbox
    pad = max(0, int(pad_px))
    cw, ch = cell
    if cw < 1 or ch < 1:
        raise ValueError(f"cell must be positive, got {cell}")
    written: List[Path] = []
    total = len(frames)
    for index, path in enumerate(frames, start=1):
        check(token)
        with Image.open(path) as im:
            rgba = im.convert("RGBA")
        # Expand by pad on a transparent canvas so the crop never reads outside the image.
        crop = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
        crop.paste(rgba.crop((x, y, x + w, y + h)), (pad, pad))
        target = fit_size(crop.size, cell)
        if target != crop.size:
            crop = crop.resize(target, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        canvas.paste(crop, anchor_offset(anchor, crop.size, cell))
        dest = out_dir / path.name
        canvas.save(dest, format="PNG")
        written.append(dest)
        progress("stabilize", index, total, f"stabilize: {path.name}")
    return written
```

- [ ] **Step 4: Run the tests again.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_stabilize.py -v
```

Expected: `13 passed`.

- [ ] **Step 5: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/stabilize.py tests/sprite/test_stabilize.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): union bbox, crop and pad with anchors"
```

---

### Task 10: `run_pipeline` — default runners, cached stages, hd profile

**Files:**
- Modify: `core/sprite/pipeline.py` (two import edits + append the runner half)
- Modify: `tests/sprite/test_pipeline.py` (append the runner tests)

**Interfaces:**
- Consumes: `core.sprite.extract.extract_frames`; `core.sprite.stabilize.crop_and_pad`, `has_transparency`, `solid_border_bbox`, `union_alpha_bbox`; everything from Task 6.
- Produces: default runners, all with the `StageRunner` signature `(project, action, input_frames, out_dir, progress, token) -> List[Path]`: `identity_runner` (copies inputs into `out_dir`; registered for `key`, `cleanup`, `alpha`, `pixel`), `extract_runner` (runs ffmpeg when `action.clip` exists, else accepts the frames an importer placed in `out_dir`), `stabilize_runner` (crops every frame to the union bbox — alpha bbox when the frames carry transparency, solid-border bbox otherwise — plus `pad_px`, without scaling), `hd_runner` (scales proportionally into `OutputProfile("hd").cell_size` at `StabilizeSettings.anchor`). Module import calls `register_stage` for all seven stages. `run_pipeline(project, action, *, upto="pixel", progress=no_progress, token=None, force=False) -> Dict[str, List[Path]]` iterates `STAGES`, looks up `STAGE_RUNNERS[stage]` (missing → `PipelineError`), passes the previous stage's output list as `input_frames` (`[]` for `extract`), skips a stage when `is_stage_current`, rebuilds `action.frames` after `stabilize` while carrying `duration_ms`, `pivot` and `overrides` over from the previous `FrameMeta` **at the same index** (orchestrator decision; new indices get defaults, so a per-frame keying override survives a re-run and the `key` fingerprint stays stable — pinned by `test_sync_frames_keeps_user_edits_by_index`), and skips a disabled profile stage. `progress` messages end in `running`, `cached` or `done`. The caller saves the project afterwards.

- [ ] **Step 1: Append the failing runner tests.**

Append the following to the end of `tests/sprite/test_pipeline.py`, after two blank lines:

```python
# --- run_pipeline (Task 10) -------------------------------------------------------
from PIL import Image  # noqa: E402 - grouped with the tests it serves

from core.sprite import pipeline  # noqa: E402
from core.sprite.pipeline import identity_runner, run_pipeline  # noqa: E402
from core.sprite.project import ClipRecord  # noqa: E402
from core.sprite.slicing import import_png_sequence  # noqa: E402


def test_every_stage_has_a_registered_runner():
    """Sub-projects 3 and 4 re-register key/cleanup/alpha and pixel, so this
    test pins only that every stage has a callable runner and that the
    extract runner is this module's."""
    assert set(STAGE_RUNNERS) == set(STAGES)
    assert all(callable(runner) for runner in STAGE_RUNNERS.values())
    assert STAGE_RUNNERS["extract"] is pipeline.extract_runner


def test_missing_input_is_a_pipeline_error(tmp_path):
    project, action = _project(tmp_path)
    with pytest.raises(PipelineError) as info:
        run_pipeline(project, action, upto="extract")
    assert "no clip" in info.value.user_message


def test_pipeline_runs_external_frames_through_hd(tmp_path, alpha_frames):
    project, action = _project(tmp_path)
    project.stabilize.pad_px = 2
    project.profiles[0].cell_size = (48, 48)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    events = []
    out = run_pipeline(project, action, upto="hd", progress=lambda *a: events.append(a))
    assert set(out) == {"extract", "key", "cleanup", "alpha", "stabilize", "hd"}
    assert len(out["hd"]) == 12
    with Image.open(out["hd"][0]) as im:
        assert im.size == (48, 48)
    # The moving square spans x 8..98 => union bbox 90 wide, 24 tall, +2 pad each side.
    with Image.open(out["stabilize"][0]) as im:
        assert im.size == (94, 28)
    assert len(action.frames) == 12
    assert action.frames[0].name == "walk_00"
    assert action.frames[0].source_path == out["stabilize"][0]
    assert action.frames[0].duration_ms == round(1000 / 12)
    assert action.status == "processed"
    assert set(project.stage_fingerprints["a1"]) == set(out)
    assert any(e[0] == "stabilize" and e[3].endswith("done") for e in events)


def test_imported_frames_without_registration_count_as_extracted(tmp_path, alpha_frames):
    """G9 entry contract: a populated extract dir and no clip means extract is done."""
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    messages = []
    out = run_pipeline(project, action, upto="key", progress=lambda s, d, t, m: messages.append(m))
    assert len(out["extract"]) == 12 and len(out["key"]) == 12
    assert "extract: running" in messages  # the runner accepted the frames as-is
    messages.clear()
    run_pipeline(project, action, upto="key", progress=lambda s, d, t, m: messages.append(m))
    assert messages == ["extract: cached", "key: cached"]


def test_pixel_stage_is_skipped_while_disabled_and_runs_when_enabled(tmp_path, alpha_frames):
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    project.profiles[1].enabled = False
    out = run_pipeline(project, action)
    assert "pixel" not in out
    project.profiles[1].enabled = True
    out = run_pipeline(project, action)
    assert [p.name for p in out["pixel"]] == [p.name for p in out["stabilize"]]
    assert out["pixel"][0].parent == stage_dir(project, action, "pixel")


def test_identity_runner_copies_inputs_byte_for_byte(tmp_path, alpha_frames):
    project, action = _project(tmp_path)
    out = identity_runner(project, action, alpha_frames, tmp_path / "proj" / "stages" / "a1" / "key",
                          no_progress, None)
    assert [p.name for p in out] == [p.name for p in alpha_frames]
    assert out[3].read_bytes() == alpha_frames[3].read_bytes()


def test_cached_stages_are_skipped_and_a_changed_slider_reruns_downstream(tmp_path, alpha_frames):
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    run_pipeline(project, action, upto="hd")
    messages = []
    run_pipeline(project, action, upto="hd", progress=lambda s, d, t, m: messages.append(m))
    assert all(m.endswith("cached") for m in messages)
    project.key.tolerance = 0.9
    messages.clear()
    run_pipeline(project, action, upto="hd", progress=lambda s, d, t, m: messages.append(m))
    assert "extract: cached" in messages
    assert "key: running" in messages
    assert "hd: running" in messages


def test_a_replacement_key_runner_changes_output_and_invalidates_downstream(tmp_path, alpha_frames, registry):
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    run_pipeline(project, action, upto="hd")
    before = dict(project.stage_fingerprints["a1"])

    def blue_corner_runner(project, action, input_frames, out_dir, progress, token):
        out = identity_runner(project, action, input_frames, out_dir, progress, token)
        for path in out:
            with Image.open(path) as im:
                rgba = im.convert("RGBA")
            rgba.putpixel((0, 0), (0, 0, 255, 255))
            rgba.save(path)
        return out

    register_stage("key", blue_corner_runner, key_stage_settings, code_version=2)
    messages = []
    out = run_pipeline(project, action, upto="hd", progress=lambda s, d, t, m: messages.append(m))
    assert "extract: cached" in messages
    for stage in ("key", "cleanup", "alpha", "stabilize", "hd"):
        assert f"{stage}: running" in messages, stage
    with Image.open(out["key"][0]) as im:
        assert im.getpixel((0, 0)) == (0, 0, 255, 255)
    with Image.open(out["cleanup"][0]) as im:
        assert im.getpixel((0, 0)) == (0, 0, 255, 255)  # identity stages carry it forward
    after = project.stage_fingerprints["a1"]
    assert after["extract"] == before["extract"]
    for stage in ("key", "cleanup", "alpha", "stabilize", "hd"):
        assert after[stage] != before[stage], stage


def test_force_reruns_everything_but_never_extract_without_a_clip(tmp_path, alpha_frames):
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    run_pipeline(project, action, upto="stabilize")
    messages = []
    run_pipeline(project, action, upto="stabilize", force=True,
                 progress=lambda s, d, t, m: messages.append(m))
    assert "extract: running" in messages and "stabilize: running" in messages
    assert len(pipeline.list_frames(stage_dir(project, action, "extract"))) == 12


def test_sync_frames_keeps_user_edits_by_index(tmp_path, alpha_frames):
    """Per-frame edits survive a re-run and keep the key fingerprint stable."""
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    run_pipeline(project, action, upto="stabilize")
    action.frames[1].overrides = {"tolerance": 0.95}
    action.frames[2].duration_ms = 250
    action.frames[2].pivot = (0.25, 0.75)
    key_before = stage_fingerprint(project, action, "key")
    project.stabilize.pad_px = 1
    out = run_pipeline(project, action, upto="stabilize")
    assert action.frames[1].overrides == {"tolerance": 0.95}
    assert action.frames[2].duration_ms == 250 and action.frames[2].pivot == (0.25, 0.75)
    assert action.frames[0].overrides == {} and action.frames[0].duration_ms == round(1000 / 12)
    assert action.frames[2].source_path == out["stabilize"][2]
    assert stage_fingerprint(project, action, "key") == key_before
    # A shorter old list: indices beyond it get defaults.
    action.frames = action.frames[:2]
    run_pipeline(project, action, upto="stabilize", force=True)
    assert len(action.frames) == 12
    assert action.frames[1].overrides == {"tolerance": 0.95}
    assert action.frames[2].duration_ms == round(1000 / 12)


def test_cancel_stops_between_frames(tmp_path, alpha_frames):
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    token = CancelToken()

    def cancel_after_two(stage, done, total, message):
        if stage == "key" and done == 2:
            token.cancel()

    with pytest.raises(Cancelled):
        run_pipeline(project, action, progress=cancel_after_two, token=token)
    assert "key" not in project.stage_fingerprints.get("a1", {})


def test_unregistered_stage_is_a_pipeline_error(tmp_path, alpha_frames, registry):
    project, action = _project(tmp_path)
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    del STAGE_RUNNERS["cleanup"]
    with pytest.raises(PipelineError) as info:
        run_pipeline(project, action, upto="cleanup")
    assert "cleanup" in info.value.user_message


def test_pipeline_extracts_from_a_clip(tmp_path, synthetic_mp4):
    project, action = _project(tmp_path)
    project.extraction.mode = "every_n"
    project.extraction.every_n = 4
    action.clip = ClipRecord(path=synthetic_mp4, provider="omni", model="m", operation_id=None, params={},
                             prompt="p", generated_at="t", estimated_usd=None, actual_usd=None)
    out = run_pipeline(project, action, upto="stabilize")
    assert len(out["extract"]) == 3
    assert len(action.frames) == 3
```

- [ ] **Step 2: Run them and watch them fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pipeline.py -v
```

Expected: `ImportError: cannot import name 'identity_runner' from 'core.sprite.pipeline'`.

- [ ] **Step 3: Extend the imports and append the runners and the loop.**

`core/sprite/pipeline.py`, Edit — old string:

```python
import logging
import threading
```

New string:

```python
import logging
import shutil
import threading
```

`core/sprite/pipeline.py`, Edit — old string:

```python
from typing import Any, Callable, Dict, List, Optional

from .project import ActionCard, SpriteProject
```

New string:

```python
from typing import Any, Callable, Dict, List, Optional

from PIL import Image

from .models import FrameMeta
from .project import ActionCard, SpriteProject
```

Then append the following to the end of `core/sprite/pipeline.py`, after two blank lines:

```python
def _reset_dir(directory: Path) -> Path:
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)
    return directory


# --- default runners (sub-project 1) ------------------------------------------


def identity_runner(project: SpriteProject, action: ActionCard, input_frames: List[Path],
                    out_dir: Path, progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    """Copy every input frame unchanged. The placeholder for stages later sub-projects fill."""
    stage = out_dir.name
    _reset_dir(out_dir)
    written: List[Path] = []
    total = len(input_frames)
    for index, path in enumerate(input_frames, start=1):
        check(token)
        dest = out_dir / path.name
        shutil.copy2(path, dest)
        written.append(dest)
        progress(stage, index, total, f"{stage}: {path.name}")
    return written


def extract_runner(project: SpriteProject, action: ActionCard, input_frames: List[Path],
                   out_dir: Path, progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    """Extract from ``action.clip``; or accept frames an importer placed in ``out_dir``."""
    from .extract import extract_frames

    if action.clip is not None:
        clip = Path(action.clip.path)
        if not clip.exists():
            raise PipelineError(f"Clip not found: {clip}")
        result = extract_frames(clip, out_dir, project.extraction, progress=progress, token=token)
        return result.frames
    frames = list_frames(out_dir)
    if not frames:
        raise PipelineError(
            f"Action '{action.name}' has no clip and no imported frames; "
            "render it or import a video, PNG sequence, or sheet first"
        )
    return frames


def stabilize_runner(project: SpriteProject, action: ActionCard, input_frames: List[Path],
                     out_dir: Path, progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    """Crop every frame to the union bbox plus ``pad_px``; no resampling."""
    from .stabilize import crop_and_pad, has_transparency, solid_border_bbox, union_alpha_bbox

    if not input_frames:
        raise PipelineError("No frames to stabilize")
    if has_transparency(input_frames[0]):
        bbox = union_alpha_bbox(input_frames)
    else:
        bbox = solid_border_bbox(input_frames)
    pad = max(0, project.stabilize.pad_px)
    cell = (bbox[2] + 2 * pad, bbox[3] + 2 * pad)
    _reset_dir(out_dir)
    return crop_and_pad(input_frames, out_dir, bbox, cell, anchor=project.stabilize.anchor,
                        pad_px=pad, progress=progress, token=token)


def hd_runner(project: SpriteProject, action: ActionCard, input_frames: List[Path],
              out_dir: Path, progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    """Scale the stabilised frames proportionally into the hd profile cell."""
    from .stabilize import crop_and_pad

    prof = project.profile("hd")
    if prof is None or not input_frames:
        raise PipelineError("hd profile is missing")
    with Image.open(input_frames[0]) as first:
        w, h = first.size
    _reset_dir(out_dir)
    return crop_and_pad(input_frames, out_dir, (0, 0, w, h), prof.cell_size,
                        anchor=project.stabilize.anchor, pad_px=0,
                        progress=progress, token=token)


register_stage("extract", extract_runner, extract_stage_settings)
register_stage("key", identity_runner, key_stage_settings)
register_stage("cleanup", identity_runner, cleanup_stage_settings)
register_stage("alpha", identity_runner, alpha_stage_settings)
register_stage("stabilize", stabilize_runner, stabilize_stage_settings)
register_stage("hd", hd_runner, hd_stage_settings)
register_stage("pixel", identity_runner, pixel_stage_settings)


# --- the runner loop ----------------------------------------------------------


def _sync_frames(action: ActionCard, frames: List[Path]) -> None:
    """Rebuild ``action.frames`` after a stabilize run, keeping user edits.

    The entry at each index carries over ``duration_ms``, ``pivot`` and
    ``overrides`` from the previous ``FrameMeta`` at the same index, so a
    per-frame keying override or an edited duration survives a re-run and
    the key fingerprint stays stable. Indices beyond the old list get
    defaults; old entries beyond the new count are dropped.
    """
    rebuilt: List[FrameMeta] = []
    for index, path in enumerate(frames):
        with Image.open(path) as im:
            w, h = im.size
        prev = action.frames[index] if index < len(action.frames) else None
        rebuilt.append(FrameMeta(
            name=f"{action.name}_{index:02d}",
            source_path=path,
            frame=(0, 0, w, h),
            sprite_source_size=(0, 0, w, h),
            source_size=(w, h),
            duration_ms=prev.duration_ms if prev else round(1000 / max(1, action.fps)),
            pivot=prev.pivot if prev else (0.5, 1.0),
            overrides=dict(prev.overrides) if prev else {},
        ))
    action.frames = rebuilt


def run_pipeline(project: SpriteProject, action: ActionCard, *, upto: str = "pixel",
                 progress: ProgressFn = no_progress, token: Optional[CancelToken] = None,
                 force: bool = False) -> Dict[str, List[Path]]:
    """Run every registered stage up to and including ``upto``; return stage -> frames.

    Each stage's runner receives the previous stage's output list (``[]`` for
    ``extract``). Cached stages are skipped unless ``force`` is set. A disabled
    profile stage is skipped and absent from the result. After ``stabilize``
    runs, ``action.frames`` is rebuilt from its output. ``project.stage_fingerprints``
    is updated in place; the caller saves the project.
    """
    if upto not in STAGES:
        raise ValueError(f"Unknown stage: {upto!r}")
    if project.project_dir is None:
        raise ValueError("project_dir is not set")
    outputs: Dict[str, List[Path]] = {}
    stop = STAGES.index(upto)
    for stage in STAGES[:stop + 1]:
        check(token)
        if stage in PROFILE_STAGES:
            prof = project.profile(stage)
            if prof is None or not prof.enabled:
                continue
        runner = STAGE_RUNNERS.get(stage)
        if runner is None:
            raise PipelineError(f"No runner is registered for stage {stage!r}")
        out_dir = stage_dir(project, action, stage)
        if not force and is_stage_current(project, action, stage):
            outputs[stage] = list_frames(out_dir)
            progress(stage, 0, 0, f"{stage}: cached")
            continue
        upstream = UPSTREAM[stage]
        input_frames = outputs.get(upstream, []) if upstream else []
        progress(stage, 0, 0, f"{stage}: running")
        frames = runner(project, action, input_frames, out_dir, progress, token)
        if stage == "stabilize":
            _sync_frames(action, frames)
        outputs[stage] = frames
        record_fingerprint(project, action, stage)
        progress(stage, len(frames), len(frames), f"{stage}: done")
    if action.frames and action.status in ("rendered", "draft"):
        action.status = "processed"
    return outputs
```

- [ ] **Step 4: Run the tests again.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pipeline.py -v
```

Expected: `19 passed` (`18 passed, 1 skipped` without ffmpeg).

- [ ] **Step 5: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/pipeline.py tests/sprite/test_pipeline.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): run_pipeline with registered runners, cached stages and hd profile"
```

---

### Task 11: Grid sheet export with the Aseprite JSON sidecar (hash + array)

**Files:**
- Create: `core/sprite/exporters/__init__.py`
- Create: `core/sprite/exporters/aseprite_json.py`
- Create: `core/sprite/exporters/grid.py`
- Create: `tests/sprite/golden/aseprite_hash.json`
- Create: `tests/sprite/golden/aseprite_array.json`
- Create: `tests/sprite/test_exporters.py` (grid + Aseprite sections; Tasks 12–14 append)

**Interfaces:**
- Consumes: `core.utils.write_image_sidecar`; `core.sprite.models`.
- Produces: `GridOptions(columns=0, border_px=0, shape_px=1, inner_px=0, extrude_px=0, power_of_two=False, scales=(1,))`; `next_power_of_two(n) -> int`; `export_grid(meta, out_png, opts) -> SheetMeta` (returns a copy with `frame`, `sprite_source_size`, `source_size`, `sheet_size`, `cell_size` filled; writes `<stem>.json` Aseprite hash sidecar and `<name>.png.json` metadata sidecar for the base PNG and for every `@Nx` nearest-neighbour copy); `aseprite_document(meta, *, image_name, layout="hash") -> dict`; `export_aseprite_json(meta, out_json, *, image_name, layout="hash") -> None`; `frame_key(frame) -> str` (Aseprite key = `frame.name`).
- Aseprite key names: `frames{name: {frame{x,y,w,h}, rotated, trimmed, spriteSourceSize{x,y,w,h}, sourceSize{w,h}, duration}}`; `meta{app, version, image, format, size{w,h}, scale, frameTags[{name, from, to, direction, color[, repeat]}], layers, slices}`. Array layout adds `filename` to each entry.
- Extrude rule: `2 * extrude_px <= shape_px` and `extrude_px <= border_px`, so two neighbours' extrusions never overlap.

- [ ] **Step 1: Write the golden files.**

`tests/sprite/golden/aseprite_hash.json`:

```json
{
 "frames": {
  "hero_walk_00": {
   "frame": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "duration": 83
  },
  "hero_walk_01": {
   "frame": {
    "x": 16,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "duration": 83
  },
  "hero_walk_02": {
   "frame": {
    "x": 32,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "duration": 83
  },
  "hero_idle_00": {
   "frame": {
    "x": 0,
    "y": 16,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "duration": 200
  },
  "hero_idle_01": {
   "frame": {
    "x": 16,
    "y": 16,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "duration": 200
  }
 },
 "meta": {
  "app": "ImageAI",
  "version": "TEST",
  "image": "hero.png",
  "format": "RGBA8888",
  "size": {
   "w": 48,
   "h": 32
  },
  "scale": "1",
  "frameTags": [
   {
    "name": "walk",
    "from": 0,
    "to": 2,
    "direction": "forward",
    "color": "#000000ff"
   },
   {
    "name": "idle",
    "from": 3,
    "to": 4,
    "direction": "pingpong",
    "color": "#000000ff",
    "repeat": "2"
   }
  ],
  "layers": [
   {
    "name": "Layer 1",
    "opacity": 255,
    "blendMode": "normal"
   }
  ],
  "slices": []
 }
}
```

`tests/sprite/golden/aseprite_array.json`:

```json
{
 "frames": [
  {
   "filename": "hero_walk_00",
   "frame": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "duration": 83
  },
  {
   "filename": "hero_walk_01",
   "frame": {
    "x": 16,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "duration": 83
  },
  {
   "filename": "hero_walk_02",
   "frame": {
    "x": 32,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "duration": 83
  },
  {
   "filename": "hero_idle_00",
   "frame": {
    "x": 0,
    "y": 16,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "duration": 200
  },
  {
   "filename": "hero_idle_01",
   "frame": {
    "x": 16,
    "y": 16,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "duration": 200
  }
 ],
 "meta": {
  "app": "ImageAI",
  "version": "TEST",
  "image": "hero.png",
  "format": "RGBA8888",
  "size": {
   "w": 48,
   "h": 32
  },
  "scale": "1",
  "frameTags": [
   {
    "name": "walk",
    "from": 0,
    "to": 2,
    "direction": "forward",
    "color": "#000000ff"
   },
   {
    "name": "idle",
    "from": 3,
    "to": 4,
    "direction": "pingpong",
    "color": "#000000ff",
    "repeat": "2"
   }
  ],
  "layers": [
   {
    "name": "Layer 1",
    "opacity": 255,
    "blendMode": "normal"
   }
  ],
  "slices": []
 }
}
```

- [ ] **Step 2: Write the failing tests.**

`tests/sprite/test_exporters.py`:

```python
import json
from pathlib import Path

import pytest
from PIL import Image

from core.sprite.exporters import GridOptions, aseprite_document, export_aseprite_json, export_grid
from core.sprite.exporters.grid import next_power_of_two
from core.sprite.models import FrameMeta, SheetMeta, TagMeta
from tests.sprite.synth import draw_frame

GOLDEN = Path(__file__).parent / "golden"


def _meta(tmp_path, cell=16, walk=3, idle=2):
    """Deterministic sheet: walk (3 frames) + idle (2 frames), 16x16 cells."""
    frames = []
    for index in range(walk + idle):
        path = tmp_path / "src" / f"{index + 1:04d}.png"
        path.parent.mkdir(exist_ok=True)
        draw_frame(index, alpha=True, size=(cell, cell), square=6, step=1).save(path)
        tag = "walk" if index < walk else "idle"
        local = index if index < walk else index - walk
        frames.append(FrameMeta(name=f"hero_{tag}_{local:02d}", source_path=path, frame=(0, 0, cell, cell),
                                sprite_source_size=(0, 0, cell, cell), source_size=(cell, cell),
                                duration_ms=83 if tag == "walk" else 200))
    tags = [TagMeta(name="walk", from_index=0, to_index=walk - 1, direction="forward", fps_hint=12),
            TagMeta(name="idle", from_index=walk, to_index=walk + idle - 1, direction="pingpong", repeat=2)]
    return SheetMeta(title="hero", frames=frames, tags=tags, cell_size=(cell, cell))


def _normalized(document):
    document = json.loads(json.dumps(document))
    document["meta"]["version"] = "TEST"
    return document


# --- grid -------------------------------------------------------------------

def test_export_grid_one_row_per_tag_fills_rects_and_writes_sidecars(tmp_path):
    meta = _meta(tmp_path)
    out = tmp_path / "exports" / "hero.png"
    filled = export_grid(meta, out, GridOptions(shape_px=0))
    assert filled.sheet_size == (48, 32)
    assert [f.frame for f in filled.frames] == [(0, 0, 16, 16), (16, 0, 16, 16), (32, 0, 16, 16),
                                                (0, 16, 16, 16), (16, 16, 16, 16)]
    assert filled.frames[0].source_size == (16, 16)
    assert meta.frames[0].frame == (0, 0, 16, 16)  # input meta untouched
    with Image.open(out) as im:
        assert im.size == (48, 32)
        assert im.getpixel((12, 8)) == (200, 40, 40, 255)
    assert (tmp_path / "exports" / "hero.json").exists()  # Aseprite sidecar, always
    assert (tmp_path / "exports" / "hero.png.json").exists()  # ImageAI metadata sidecar
    aseprite = json.loads((tmp_path / "exports" / "hero.json").read_text())
    assert aseprite["meta"]["image"] == "hero.png"
    assert aseprite["frames"]["hero_idle_01"]["frame"] == {"x": 16, "y": 16, "w": 16, "h": 16}


def test_export_grid_padding_knobs_and_fixed_columns(tmp_path):
    meta = _meta(tmp_path)
    opts = GridOptions(columns=2, border_px=2, shape_px=3, inner_px=1)
    filled = export_grid(meta, tmp_path / "s.png", opts)
    # cell = 18x18, 2 cols x 3 rows: w = 4 + 36 + 3 = 43; h = 4 + 54 + 6 = 64
    assert filled.sheet_size == (43, 64)
    assert filled.cell_size == (18, 18)
    assert filled.frames[0].frame == (3, 3, 16, 16)
    assert filled.frames[1].frame == (3 + 18 + 3, 3, 16, 16)
    assert filled.frames[2].frame == (3, 3 + 18 + 3, 16, 16)


def test_export_grid_extrude_repeats_edge_pixels(tmp_path):
    meta = _meta(tmp_path)
    # Make frame 0 fully opaque red so the extruded border is visible.
    Image.new("RGBA", (16, 16), (200, 40, 40, 255)).save(meta.frames[0].source_path)
    filled = export_grid(meta, tmp_path / "s.png", GridOptions(border_px=2, shape_px=4, extrude_px=2))
    x, y, w, h = filled.frames[0].frame
    with Image.open(tmp_path / "s.png") as im:
        assert im.getpixel((x - 1, y)) == (200, 40, 40, 255)
        assert im.getpixel((x - 2, y - 2)) == (200, 40, 40, 255)
        assert im.getpixel((x + w, y + h)) == (200, 40, 40, 255)
    with pytest.raises(ValueError):
        export_grid(meta, tmp_path / "t.png", GridOptions(shape_px=3, border_px=2, extrude_px=2))
    with pytest.raises(ValueError):
        export_grid(meta, tmp_path / "t.png", GridOptions(shape_px=4, border_px=1, extrude_px=2))


def test_export_grid_power_of_two_and_scaled_copies(tmp_path):
    meta = _meta(tmp_path)
    out = tmp_path / "hero.png"
    filled = export_grid(meta, out, GridOptions(shape_px=0, power_of_two=True, scales=(1, 2, 4)))
    assert filled.sheet_size == (64, 32)
    for scale in (2, 4):
        copy = tmp_path / f"hero@{scale}x.png"
        with Image.open(copy) as im:
            assert im.size == (64 * scale, 32 * scale)
            assert im.getpixel((12 * scale, 8 * scale)) == (200, 40, 40, 255)
        data = json.loads(copy.with_suffix(".json").read_text())
        assert data["meta"]["scale"] == str(scale)
        assert data["frames"]["hero_walk_01"]["frame"]["x"] == 16 * scale
        assert copy.with_name(copy.name + ".json").exists()
    assert next_power_of_two(48) == 64 and next_power_of_two(64) == 64 and next_power_of_two(1) == 1
    with pytest.raises(ValueError):
        export_grid(meta, tmp_path / "x.png", GridOptions(scales=(2,)))


def test_export_grid_requires_frames_and_files(tmp_path):
    with pytest.raises(ValueError):
        export_grid(SheetMeta(title="e", frames=[], tags=[]), tmp_path / "e.png", GridOptions())
    meta = _meta(tmp_path)
    meta.frames[0].source_path = tmp_path / "missing.png"
    with pytest.raises(FileNotFoundError):
        export_grid(meta, tmp_path / "m.png", GridOptions())


# --- aseprite ----------------------------------------------------------------

def test_aseprite_hash_matches_golden(tmp_path):
    filled = export_grid(_meta(tmp_path), tmp_path / "hero.png", GridOptions(shape_px=0))
    document = aseprite_document(filled, image_name="hero.png", layout="hash")
    assert _normalized(document) == json.loads((GOLDEN / "aseprite_hash.json").read_text())


def test_aseprite_array_matches_golden(tmp_path):
    filled = export_grid(_meta(tmp_path), tmp_path / "hero.png", GridOptions(shape_px=0))
    out = tmp_path / "hero_array.json"
    export_aseprite_json(filled, out, image_name="hero.png", layout="array")
    assert _normalized(json.loads(out.read_text())) == json.loads((GOLDEN / "aseprite_array.json").read_text())


def test_aseprite_rejects_unknown_layout(tmp_path):
    with pytest.raises(ValueError):
        aseprite_document(_meta(tmp_path), image_name="x.png", layout="tree")
```

- [ ] **Step 3: Run them and watch them fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_exporters.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.sprite.exporters'`.

- [ ] **Step 4: Create the exporters package, the Aseprite writer and the grid writer.**

`core/sprite/exporters/__init__.py` (Tasks 12–14 replace this file as exporters land):

```python
"""Exporters: pure projections of a SheetMeta onto files."""

from .grid import GridOptions, export_grid
from .aseprite_json import export_aseprite_json, aseprite_document

__all__ = [
    "GridOptions", "export_grid",
    "export_aseprite_json", "aseprite_document",
]
```

`core/sprite/exporters/aseprite_json.py`:

```python
"""Aseprite JSON export (hash and array layouts).

Key names match Aseprite's own ``--data`` output so engine importers
(Phaser ``createFromAseprite``, Unity/Godot community importers) read it
without changes. ``meta.app`` and ``meta.version`` name ImageAI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ..models import FrameMeta, SheetMeta

LAYOUTS = ("hash", "array")
DEFAULT_TAG_COLOR = "#000000ff"


def frame_key(frame: FrameMeta) -> str:
    return frame.name


def _frame_entry(frame: FrameMeta) -> Dict[str, Any]:
    x, y, w, h = frame.frame
    sx, sy, sw, sh = frame.sprite_source_size
    return {
        "frame": {"x": x, "y": y, "w": w, "h": h},
        "rotated": frame.rotated,
        "trimmed": frame.trimmed,
        "spriteSourceSize": {"x": sx, "y": sy, "w": sw, "h": sh},
        "sourceSize": {"w": frame.source_size[0], "h": frame.source_size[1]},
        "duration": frame.duration_ms,
    }


def aseprite_document(meta: SheetMeta, *, image_name: str, layout: str = "hash") -> Dict[str, Any]:
    if layout not in LAYOUTS:
        raise ValueError(f"layout must be one of {LAYOUTS}, got {layout!r}")
    if layout == "hash":
        frames: Any = {frame_key(f): _frame_entry(f) for f in meta.frames}
    else:
        frames = [dict(filename=frame_key(f), **_frame_entry(f)) for f in meta.frames]
    frame_tags: List[Dict[str, Any]] = []
    for tag in meta.tags:
        entry: Dict[str, Any] = {
            "name": tag.name,
            "from": tag.from_index,
            "to": tag.to_index,
            "direction": tag.direction,
            "color": DEFAULT_TAG_COLOR,
        }
        if tag.repeat > 0:
            entry["repeat"] = str(tag.repeat)
        frame_tags.append(entry)
    scale = int(meta.scale) if float(meta.scale).is_integer() else meta.scale
    return {
        "frames": frames,
        "meta": {
            "app": meta.app,
            "version": meta.version,
            "image": image_name,
            "format": "RGBA8888",
            "size": {"w": meta.sheet_size[0], "h": meta.sheet_size[1]},
            "scale": str(scale),
            "frameTags": frame_tags,
            "layers": [{"name": "Layer 1", "opacity": 255, "blendMode": "normal"}],
            "slices": [],
        },
    }


def export_aseprite_json(meta: SheetMeta, out_json: Path, *, image_name: str,
                         layout: str = "hash") -> None:
    out_json = Path(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    document = aseprite_document(meta, image_name=image_name, layout=layout)
    out_json.write_text(json.dumps(document, indent=1), encoding="utf-8")
```

`core/sprite/exporters/grid.py`:

```python
"""Grid sprite-sheet export (design section 4.1).

Layout: one row per tag by default (``columns=0``), or a fixed column
count. ``border_px`` surrounds the sheet, ``shape_px`` separates cells,
``inner_px`` pads inside each cell, ``extrude_px`` repeats sprite edge pixels
outward into the gap. Always writes an Aseprite JSON sidecar next to the
PNG, plus the ImageAI ``.png.json`` metadata sidecar.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from PIL import Image

from core.utils import write_image_sidecar

from ..models import SheetMeta
from .aseprite_json import export_aseprite_json

logger = logging.getLogger(__name__)


@dataclass
class GridOptions:
    columns: int = 0
    border_px: int = 0
    shape_px: int = 1
    inner_px: int = 0
    extrude_px: int = 0
    power_of_two: bool = False
    scales: Tuple[int, ...] = (1,)


def next_power_of_two(value: int) -> int:
    result = 1
    while result < value:
        result *= 2
    return result


def _grid_shape(meta: SheetMeta, opts: GridOptions) -> Tuple[int, int, List[Tuple[int, int]]]:
    """Return (columns, rows, [(col, row) per frame])."""
    count = len(meta.frames)
    if count == 0:
        return (0, 0, [])
    if opts.columns > 0:
        columns = opts.columns
        cells = [(i % columns, i // columns) for i in range(count)]
        rows = (count + columns - 1) // columns
        return (columns, rows, cells)
    # One row per tag; frames outside every tag go on a final row.
    cells: List[Tuple[int, int]] = [(-1, -1)] * count
    row = 0
    columns = 0
    covered = [False] * count
    for tag in meta.tags:
        span = [i for i in range(tag.from_index, tag.to_index + 1) if 0 <= i < count and not covered[i]]
        if not span:
            continue
        for col, index in enumerate(span):
            cells[index] = (col, row)
            covered[index] = True
        columns = max(columns, len(span))
        row += 1
    leftovers = [i for i in range(count) if not covered[i]]
    if leftovers:
        for col, index in enumerate(leftovers):
            cells[index] = (col, row)
        columns = max(columns, len(leftovers))
        row += 1
    return (columns, row, cells)


def _extrude(sheet: Image.Image, sprite: Image.Image, x: int, y: int, px: int) -> None:
    """Repeat the sprite's edge pixels ``px`` times outward."""
    w, h = sprite.size
    if px <= 0 or w == 0 or h == 0:
        return
    left = sprite.crop((0, 0, 1, h))
    right = sprite.crop((w - 1, 0, w, h))
    top = sprite.crop((0, 0, w, 1))
    bottom = sprite.crop((0, h - 1, w, h))
    for i in range(1, px + 1):
        sheet.paste(left, (x - i, y))
        sheet.paste(right, (x + w - 1 + i, y))
        sheet.paste(top, (x, y - i))
        sheet.paste(bottom, (x, y + h - 1 + i))
    corners = {
        (x - px, y - px): sprite.getpixel((0, 0)),
        (x + w, y - px): sprite.getpixel((w - 1, 0)),
        (x - px, y + h): sprite.getpixel((0, h - 1)),
        (x + w, y + h): sprite.getpixel((w - 1, h - 1)),
    }
    for (cx, cy), color in corners.items():
        sheet.paste(Image.new("RGBA", (px, px), color), (cx, cy))


def _scaled_meta(meta: SheetMeta, scale: int) -> SheetMeta:
    scaled = copy.deepcopy(meta)
    scaled.scale = float(scale)
    scaled.sheet_size = (meta.sheet_size[0] * scale, meta.sheet_size[1] * scale)
    scaled.cell_size = (meta.cell_size[0] * scale, meta.cell_size[1] * scale)
    for frame in scaled.frames:
        fx, fy, fw, fh = frame.frame
        frame.frame = (fx * scale, fy * scale, fw * scale, fh * scale)
        sx, sy, sw, sh = frame.sprite_source_size
        frame.sprite_source_size = (sx * scale, sy * scale, sw * scale, sh * scale)
        frame.source_size = (frame.source_size[0] * scale, frame.source_size[1] * scale)
    return scaled


def export_grid(meta: SheetMeta, out_png: Path, opts: GridOptions) -> SheetMeta:
    """Write the sheet PNG (+ Aseprite JSON + metadata sidecar); return filled meta."""
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    if not meta.frames:
        raise ValueError("SheetMeta has no frames to export")
    if opts.extrude_px < 0 or opts.shape_px < 0 or opts.border_px < 0 or opts.inner_px < 0:
        raise ValueError("padding values must not be negative")
    if opts.extrude_px > 0 and (2 * opts.extrude_px > opts.shape_px or opts.extrude_px > opts.border_px):
        raise ValueError(
            "extrude_px needs room: shape_px must be at least 2*extrude_px and "
            "border_px at least extrude_px"
        )
    if any(s < 1 for s in opts.scales) or 1 not in opts.scales:
        raise ValueError("scales must be positive and include 1")

    images: List[Image.Image] = []
    for frame in meta.frames:
        if frame.source_path is None or not Path(frame.source_path).exists():
            raise FileNotFoundError(f"Frame '{frame.name}' has no source PNG: {frame.source_path}")
        with Image.open(frame.source_path) as im:
            images.append(im.convert("RGBA"))

    cw = max(im.size[0] for im in images) + 2 * opts.inner_px
    ch = max(im.size[1] for im in images) + 2 * opts.inner_px
    columns, rows, cells = _grid_shape(meta, opts)
    width = 2 * opts.border_px + columns * cw + max(0, columns - 1) * opts.shape_px
    height = 2 * opts.border_px + rows * ch + max(0, rows - 1) * opts.shape_px
    if opts.power_of_two:
        width, height = next_power_of_two(width), next_power_of_two(height)

    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    filled = copy.deepcopy(meta)
    filled.sheet_size = (width, height)
    filled.cell_size = (cw, ch)
    for frame, image, (col, row) in zip(filled.frames, images, cells):
        cell_x = opts.border_px + col * (cw + opts.shape_px)
        cell_y = opts.border_px + row * (ch + opts.shape_px)
        # Centre the sprite inside its (inner-padded) cell.
        sx = cell_x + (cw - image.size[0]) // 2
        sy = cell_y + (ch - image.size[1]) // 2
        if opts.extrude_px:
            _extrude(sheet, image, sx, sy, opts.extrude_px)
        sheet.paste(image, (sx, sy))
        frame.frame = (sx, sy, image.size[0], image.size[1])
        frame.rotated = False
        frame.trimmed = False
        frame.sprite_source_size = (0, 0, image.size[0], image.size[1])
        frame.source_size = (image.size[0], image.size[1])

    for scale in opts.scales:
        if scale == 1:
            target, target_meta = out_png, filled
            image = sheet
        else:
            target = out_png.with_name(f"{out_png.stem}@{scale}x{out_png.suffix}")
            target_meta = _scaled_meta(filled, scale)
            image = sheet.resize((width * scale, height * scale), Image.Resampling.NEAREST)
        image.save(target, format="PNG")
        export_aseprite_json(target_meta, target.with_suffix(".json"), image_name=target.name, layout="hash")
        write_image_sidecar(target, {
            "type": "sprite_sheet",
            "title": meta.title,
            "profile": meta.profile,
            "scale": scale,
            "frames": len(filled.frames),
            "tags": [t.name for t in filled.tags],
            "sheet_size": list(target_meta.sheet_size),
            "cell_size": list(target_meta.cell_size),
            "grid_options": {
                "columns": opts.columns, "border_px": opts.border_px, "shape_px": opts.shape_px,
                "inner_px": opts.inner_px, "extrude_px": opts.extrude_px,
                "power_of_two": opts.power_of_two,
            },
            "app": meta.app,
            "version": meta.version,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        logger.info(f"Wrote sprite sheet {target} ({image.size[0]}x{image.size[1]})")
    return filled
```

- [ ] **Step 5: Run the tests again.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_exporters.py -v
```

Expected: `8 passed`.

- [ ] **Step 6: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/exporters/__init__.py core/sprite/exporters/aseprite_json.py core/sprite/exporters/grid.py tests/sprite/golden/aseprite_hash.json tests/sprite/golden/aseprite_array.json tests/sprite/test_exporters.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): grid sheet export with Aseprite JSON sidecar"
```

---

### Task 12: TexturePacker JSON export

**Files:**
- Create: `core/sprite/exporters/texturepacker_json.py`
- Create: `tests/sprite/golden/texturepacker_hash.json`
- Modify: `core/sprite/exporters/__init__.py` (replace whole file)
- Modify: `tests/sprite/test_exporters.py` (append)

**Interfaces:**
- Consumes: `core.sprite.models`.
- Produces: `texturepacker_document(meta, *, image_name, layout="hash") -> dict`; `export_texturepacker_json(meta, out_json, *, image_name, layout="hash") -> None`; `frame_key(frame) -> str` (`f"{frame.name}.png"`). Each frame entry carries `pivot{x,y}`; the top-level `animations` map lists frame keys per tag (PixiJS/Phaser convention).

- [ ] **Step 1: Write the golden file and append the failing tests.**

`tests/sprite/golden/texturepacker_hash.json`:

```json
{
 "frames": {
  "hero_walk_00.png": {
   "frame": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "pivot": {
    "x": 0.5,
    "y": 1.0
   }
  },
  "hero_walk_01.png": {
   "frame": {
    "x": 16,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "pivot": {
    "x": 0.5,
    "y": 1.0
   }
  },
  "hero_walk_02.png": {
   "frame": {
    "x": 32,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "pivot": {
    "x": 0.5,
    "y": 1.0
   }
  },
  "hero_idle_00.png": {
   "frame": {
    "x": 0,
    "y": 16,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "pivot": {
    "x": 0.5,
    "y": 1.0
   }
  },
  "hero_idle_01.png": {
   "frame": {
    "x": 16,
    "y": 16,
    "w": 16,
    "h": 16
   },
   "rotated": false,
   "trimmed": false,
   "spriteSourceSize": {
    "x": 0,
    "y": 0,
    "w": 16,
    "h": 16
   },
   "sourceSize": {
    "w": 16,
    "h": 16
   },
   "pivot": {
    "x": 0.5,
    "y": 1.0
   }
  }
 },
 "animations": {
  "walk": [
   "hero_walk_00.png",
   "hero_walk_01.png",
   "hero_walk_02.png"
  ],
  "idle": [
   "hero_idle_00.png",
   "hero_idle_01.png"
  ]
 },
 "meta": {
  "app": "ImageAI",
  "version": "TEST",
  "image": "hero.png",
  "format": "RGBA8888",
  "size": {
   "w": 48,
   "h": 32
  },
  "scale": "1"
 }
}
```

Append the following to the end of `tests/sprite/test_exporters.py`, after two blank lines:

```python
# --- texturepacker --------------------------------------------------------------
from core.sprite.exporters.texturepacker_json import (  # noqa: E402 - grouped with the tests it serves
    export_texturepacker_json,
    texturepacker_document,
)


def test_texturepacker_hash_matches_golden(tmp_path):
    filled = export_grid(_meta(tmp_path), tmp_path / "hero.png", GridOptions(shape_px=0))
    out = tmp_path / "hero_tp.json"
    export_texturepacker_json(filled, out, image_name="hero.png", layout="hash")
    assert _normalized(json.loads(out.read_text())) == json.loads((GOLDEN / "texturepacker_hash.json").read_text())


def test_texturepacker_array_has_filenames_and_animations(tmp_path):
    filled = export_grid(_meta(tmp_path), tmp_path / "hero.png", GridOptions(shape_px=0))
    document = texturepacker_document(filled, image_name="hero.png", layout="array")
    assert document["frames"][0]["filename"] == "hero_walk_00.png"
    assert document["frames"][0]["pivot"] == {"x": 0.5, "y": 1.0}
    assert document["animations"] == {"walk": ["hero_walk_00.png", "hero_walk_01.png", "hero_walk_02.png"],
                                      "idle": ["hero_idle_00.png", "hero_idle_01.png"]}
```

- [ ] **Step 2: Run them and watch them fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_exporters.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.sprite.exporters.texturepacker_json'`.

- [ ] **Step 3: Create the writer and re-export it.**

`core/sprite/exporters/texturepacker_json.py`:

```python
"""TexturePacker-style JSON export (hash and array) with pivot and animations.

The ``animations`` block is the top-level map PixiJS and Phaser read:
``{"walk": ["hero_walk_00.png", ...]}``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ..models import FrameMeta, SheetMeta

LAYOUTS = ("hash", "array")


def frame_key(frame: FrameMeta) -> str:
    return f"{frame.name}.png"


def _frame_entry(frame: FrameMeta) -> Dict[str, Any]:
    x, y, w, h = frame.frame
    sx, sy, sw, sh = frame.sprite_source_size
    return {
        "frame": {"x": x, "y": y, "w": w, "h": h},
        "rotated": frame.rotated,
        "trimmed": frame.trimmed,
        "spriteSourceSize": {"x": sx, "y": sy, "w": sw, "h": sh},
        "sourceSize": {"w": frame.source_size[0], "h": frame.source_size[1]},
        "pivot": {"x": frame.pivot[0], "y": frame.pivot[1]},
    }


def texturepacker_document(meta: SheetMeta, *, image_name: str, layout: str = "hash") -> Dict[str, Any]:
    if layout not in LAYOUTS:
        raise ValueError(f"layout must be one of {LAYOUTS}, got {layout!r}")
    if layout == "hash":
        frames: Any = {frame_key(f): _frame_entry(f) for f in meta.frames}
    else:
        frames = [dict(filename=frame_key(f), **_frame_entry(f)) for f in meta.frames]
    animations = {tag.name: [frame_key(f) for f in meta.frames_for(tag)] for tag in meta.tags}
    scale = int(meta.scale) if float(meta.scale).is_integer() else meta.scale
    return {
        "frames": frames,
        "animations": animations,
        "meta": {
            "app": meta.app,
            "version": meta.version,
            "image": image_name,
            "format": "RGBA8888",
            "size": {"w": meta.sheet_size[0], "h": meta.sheet_size[1]},
            "scale": str(scale),
        },
    }


def export_texturepacker_json(meta: SheetMeta, out_json: Path, *, image_name: str,
                              layout: str = "hash") -> None:
    out_json = Path(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    document = texturepacker_document(meta, image_name=image_name, layout=layout)
    out_json.write_text(json.dumps(document, indent=1), encoding="utf-8")
```

Replace the whole content of `core/sprite/exporters/__init__.py` with:

```python
"""Exporters: pure projections of a SheetMeta onto files."""

from .grid import GridOptions, export_grid
from .aseprite_json import export_aseprite_json, aseprite_document
from .texturepacker_json import export_texturepacker_json, texturepacker_document

__all__ = [
    "GridOptions", "export_grid",
    "export_aseprite_json", "aseprite_document",
    "export_texturepacker_json", "texturepacker_document",
]
```

- [ ] **Step 4: Run the tests again.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_exporters.py -v
```

Expected: `10 passed`.

- [ ] **Step 5: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/exporters/__init__.py core/sprite/exporters/texturepacker_json.py tests/sprite/golden/texturepacker_hash.json tests/sprite/test_exporters.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): TexturePacker JSON export with pivot and animations"
```

---

### Task 13: Per-tag PNG sequence and single-frame export

**Files:**
- Create: `core/sprite/exporters/png_sequence.py`
- Modify: `core/sprite/exporters/__init__.py` (replace whole file)
- Modify: `tests/sprite/test_exporters.py` (append)

**Interfaces:**
- Consumes: `core.utils.sanitize_filename`, `write_image_sidecar`; `core.sprite.models`.
- Produces: `DEFAULT_TEMPLATE = "{title}_{tag}_{frame01}.png"`; `UNTAGGED = "untagged"`; `render_frame_name(template, *, title, tag, frame, tagframe) -> str` (`{frame}` = 0-based sheet index, `{tagframe}` = 0-based index inside the tag, `{frame01}` = 1-based index inside the tag, 2 digits; the stem is sanitised); `export_png_sequence(meta, out_dir, template=DEFAULT_TEMPLATE) -> List[Path]`; `export_single_frame(frame, out_png) -> Path`.

- [ ] **Step 1: Append the failing tests.**

Append the following to the end of `tests/sprite/test_exporters.py`, after two blank lines:

```python
# --- png sequence ---------------------------------------------------------------
from core.sprite.exporters.png_sequence import (  # noqa: E402 - grouped with the tests it serves
    export_png_sequence,
    export_single_frame,
    render_frame_name,
)


def test_render_frame_name_fields():
    assert render_frame_name("{title}_{tag}_{frame01}.png", title="hero", tag="walk", frame=4, tagframe=1) == "hero_walk_02.png"
    assert render_frame_name("{tag}-{tagframe}-{frame}.png", title="h", tag="idle", frame=4, tagframe=1) == "idle-1-4.png"
    assert render_frame_name("{title}/{tag}.png", title="a b", tag="x", frame=0, tagframe=0) == "a_b_x.png"


def test_export_png_sequence_writes_per_tag_files_with_sidecars(tmp_path):
    meta = _meta(tmp_path)
    out = export_png_sequence(meta, tmp_path / "seq")
    names = [p.name for p in out]
    assert names == ["hero_walk_01.png", "hero_walk_02.png", "hero_walk_03.png", "hero_idle_01.png", "hero_idle_02.png"]
    for path in out:
        assert path.with_name(path.name + ".json").exists()
    sidecar = json.loads((tmp_path / "seq" / "hero_idle_01.png.json").read_text())
    assert sidecar["tag"] == "idle" and sidecar["index"] == 3 and sidecar["duration_ms"] == 200


def test_export_png_sequence_puts_untagged_frames_last(tmp_path):
    meta = _meta(tmp_path)
    meta.tags = meta.tags[:1]
    out = export_png_sequence(meta, tmp_path / "seq", template="{tag}_{frame01}.png")
    assert [p.name for p in out][-2:] == ["untagged_01.png", "untagged_02.png"]


def test_export_single_frame(tmp_path):
    meta = _meta(tmp_path)
    out = export_single_frame(meta.frames[4], tmp_path / "one" / "frame.png")
    assert out.exists() and out.with_name("frame.png.json").exists()
    with Image.open(out) as im:
        assert im.size == (16, 16) and im.mode == "RGBA"
```

- [ ] **Step 2: Run them and watch them fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_exporters.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.sprite.exporters.png_sequence'`.

- [ ] **Step 3: Create the writer and re-export it.**

`core/sprite/exporters/png_sequence.py`:

```python
"""Per-tag PNG sequence export and single-frame export.

Template fields: ``{title}``, ``{tag}``, ``{frame}`` (0-based index on the
sheet), ``{frame01}`` (1-based index inside the tag, 2 digits),
``{tagframe}`` (0-based index inside the tag).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import List

from PIL import Image

from core.utils import sanitize_filename, write_image_sidecar

from ..models import FrameMeta, SheetMeta

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = "{title}_{tag}_{frame01}.png"
UNTAGGED = "untagged"


def render_frame_name(template: str, *, title: str, tag: str, frame: int, tagframe: int) -> str:
    name = template.format(title=title, tag=tag, frame=frame, tagframe=tagframe,
                           frame01=f"{tagframe + 1:02d}")
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, "png"
    return f"{sanitize_filename(stem)}.{ext}"


def _write_frame(frame: FrameMeta, dest: Path, extra: dict) -> Path:
    if frame.source_path is None or not Path(frame.source_path).exists():
        raise FileNotFoundError(f"Frame '{frame.name}' has no source PNG: {frame.source_path}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(frame.source_path) as im:
        im.convert("RGBA").save(dest, format="PNG")
    meta = {
        "type": "sprite_frame",
        "name": frame.name,
        "duration_ms": frame.duration_ms,
        "pivot": list(frame.pivot),
        "source": str(frame.source_path),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    meta.update(extra)
    write_image_sidecar(dest, meta)
    return dest


def export_png_sequence(meta: SheetMeta, out_dir: Path,
                        template: str = DEFAULT_TEMPLATE) -> List[Path]:
    """Write every frame as its own PNG, named per tag. Returns the paths."""
    out_dir = Path(out_dir)
    written: List[Path] = []
    covered = set()
    for tag in meta.tags:
        for tagframe, frame in enumerate(meta.frames_for(tag)):
            index = tag.from_index + tagframe
            covered.add(index)
            name = render_frame_name(template, title=meta.title, tag=tag.name,
                                     frame=index, tagframe=tagframe)
            written.append(_write_frame(frame, out_dir / name, {"tag": tag.name, "index": index}))
    leftovers = [i for i in range(len(meta.frames)) if i not in covered]
    for tagframe, index in enumerate(leftovers):
        name = render_frame_name(template, title=meta.title, tag=UNTAGGED,
                                 frame=index, tagframe=tagframe)
        written.append(_write_frame(meta.frames[index], out_dir / name,
                                    {"tag": UNTAGGED, "index": index}))
    logger.info(f"Wrote {len(written)} PNG frames to {out_dir}")
    return written


def export_single_frame(frame: FrameMeta, out_png: Path) -> Path:
    """Write one frame as a PNG with its sidecar."""
    return _write_frame(frame, Path(out_png), {})
```

Replace the whole content of `core/sprite/exporters/__init__.py` with:

```python
"""Exporters: pure projections of a SheetMeta onto files."""

from .grid import GridOptions, export_grid
from .aseprite_json import export_aseprite_json, aseprite_document
from .texturepacker_json import export_texturepacker_json, texturepacker_document
from .png_sequence import export_png_sequence, export_single_frame, render_frame_name

__all__ = [
    "GridOptions", "export_grid",
    "export_aseprite_json", "aseprite_document",
    "export_texturepacker_json", "texturepacker_document",
    "export_png_sequence", "export_single_frame", "render_frame_name",
]
```

- [ ] **Step 4: Run the tests again.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_exporters.py -v
```

Expected: `14 passed`.

- [ ] **Step 5: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/exporters/__init__.py core/sprite/exporters/png_sequence.py tests/sprite/test_exporters.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): per-tag PNG sequence and single-frame export"
```

---

### Task 14: Transparent GIF export

**Files:**
- Create: `core/sprite/exporters/gif.py`
- Modify: `core/sprite/exporters/__init__.py` (replace whole file)
- Modify: `tests/sprite/test_exporters.py` (append)

**Interfaces:**
- Consumes: `core.utils.sidecar_path`; `core.sprite.models`.
- Produces: `TRANSPARENT_INDEX = 255`, `MIN_DURATION_MS = 20`, `GIF_UNIT_MS = 10`; `gif_durations(frames) -> Tuple[List[int], List[str]]`; `ordered_frames(meta, tag) -> List[FrameMeta]` (applies `direction`); `to_palette_frame(image) -> Image` (255-colour quantize, index 255 reserved); `export_gif(meta, tag, out_gif, *, loop=0, warnings=None) -> Path`. Save arguments: `save_all=True, duration=<list>, loop=loop, disposal=2, optimize=False, transparency=255`. Sidecar `<name>.gif.json` records durations and warnings.

- [ ] **Step 1: Append the failing tests.**

Append the following to the end of `tests/sprite/test_exporters.py`, after two blank lines:

```python
# --- gif -----------------------------------------------------------------------
from core.sprite.exporters.gif import export_gif, gif_durations  # noqa: E402 - grouped with the tests it serves


def test_gif_durations_clamp_and_warn(tmp_path):
    meta = _meta(tmp_path)
    meta.frames[0].duration_ms = 5
    durations, warnings = gif_durations(meta.frames)
    assert durations == [20, 80, 80, 200, 200]
    assert len(warnings) == 2
    assert "hero_walk_00" in warnings[0] and "5 ms" in warnings[0]
    assert "2 frame duration(s) rounded" in warnings[1]


def test_export_gif_transparent_recipe(tmp_path):
    meta = _meta(tmp_path)
    meta.frames[1].duration_ms = 10
    warnings = []
    out = export_gif(meta, meta.tags[0], tmp_path / "walk.gif", warnings=warnings)
    assert warnings and "10 ms raised to 20 ms" in warnings[0]
    assert (tmp_path / "walk.gif.json").exists()
    with Image.open(out) as gif:
        assert gif.n_frames == 3
        assert gif.info["transparency"] == 255
        assert gif.info["loop"] == 0
        for index, expected in enumerate([80, 20, 80]):
            gif.seek(index)
            assert gif.disposal_method == 2
            assert gif.info["duration"] == expected
            rgba = gif.convert("RGBA")
            assert rgba.getpixel((0, 0))[3] == 0
            assert rgba.getpixel((8 + index, 8))[3] == 255


def test_export_gif_pingpong_and_reverse(tmp_path):
    meta = _meta(tmp_path)
    ping = export_gif(meta, meta.tags[1], tmp_path / "idle.gif")  # 2 frames: pingpong stays 2
    with Image.open(ping) as gif:
        assert gif.n_frames == 2
    walk = TagMeta(name="walk", from_index=0, to_index=2, direction="pingpong")
    with Image.open(export_gif(meta, walk, tmp_path / "pp.gif")) as gif:
        assert gif.n_frames == 4
    rev = TagMeta(name="walk", from_index=0, to_index=2, direction="reverse")
    with Image.open(export_gif(meta, rev, tmp_path / "rev.gif", loop=3)) as gif:
        assert gif.n_frames == 3 and gif.info["loop"] == 3
    with pytest.raises(ValueError):
        export_gif(meta, TagMeta(name="x", from_index=5, to_index=4), tmp_path / "x.gif")
```

- [ ] **Step 2: Run them and watch them fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_exporters.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.sprite.exporters.gif'`.

- [ ] **Step 3: Create the writer and re-export it.**

`core/sprite/exporters/gif.py`:

```python
"""Transparent GIF export with the safe Pillow recipe (design section 4.1).

Recipe, regression-tested: every frame is quantized to 255 colours, index
255 is reserved for transparency, ``disposal=2`` clears each frame before
the next, ``optimize=False`` keeps Pillow from merging palettes, and every
duration is clamped to at least 20 ms because browsers treat shorter delays
as 100 ms.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

from core.utils import sidecar_path

from ..models import FrameMeta, SheetMeta, TagMeta

logger = logging.getLogger(__name__)

TRANSPARENT_INDEX = 255
MIN_DURATION_MS = 20
GIF_UNIT_MS = 10  # the GIF delay field counts hundredths of a second
ALPHA_CUTOFF = 128


def gif_durations(frames: List[FrameMeta]) -> Tuple[List[int], List[str]]:
    """Round durations to the GIF 10 ms unit and clamp to >= 20 ms.

    Returns ``(durations, warnings)``. Each clamp gets its own warning; all
    roundings share one summary warning, because a 12 fps sheet (83 ms)
    rounds on every frame and a warning per frame would only be noise.
    """
    durations: List[int] = []
    warnings: List[str] = []
    rounded = 0
    for frame in frames:
        ms = int(frame.duration_ms)
        if ms < MIN_DURATION_MS:
            warnings.append(
                f"Frame '{frame.name}' duration {ms} ms raised to {MIN_DURATION_MS} ms "
                "(GIF viewers ignore shorter delays)"
            )
            durations.append(MIN_DURATION_MS)
            continue
        unit = int(round(ms / GIF_UNIT_MS)) * GIF_UNIT_MS
        if unit != ms:
            rounded += 1
        durations.append(unit)
    if rounded:
        warnings.append(f"{rounded} frame duration(s) rounded to the GIF {GIF_UNIT_MS} ms unit")
    return durations, warnings


def ordered_frames(meta: SheetMeta, tag: TagMeta) -> List[FrameMeta]:
    """Apply the tag direction to its frame range."""
    frames = meta.frames_for(tag)
    if tag.direction == "reverse":
        return list(reversed(frames))
    if tag.direction == "pingpong" and len(frames) > 2:
        return frames + list(reversed(frames[1:-1]))
    if tag.direction == "pingpong_reverse" and len(frames) > 2:
        back = list(reversed(frames))
        return back + frames[1:-1]
    return list(frames)


def to_palette_frame(image: Image.Image) -> Image.Image:
    """RGBA -> P with index 255 reserved for fully transparent pixels."""
    rgba = image.convert("RGBA")
    rgb = rgba.convert("RGB")
    alpha = rgba.getchannel("A")
    quantized = rgb.quantize(colors=TRANSPARENT_INDEX, method=Image.Quantize.MEDIANCUT,
                             dither=Image.Dither.NONE)
    palette = (quantized.getpalette() or [])[:TRANSPARENT_INDEX * 3]
    palette += [0] * (TRANSPARENT_INDEX * 3 - len(palette)) + [0, 0, 0]
    quantized.putpalette(palette)
    mask = alpha.point(lambda v: 255 if v < ALPHA_CUTOFF else 0)
    quantized.paste(TRANSPARENT_INDEX, mask=mask)
    return quantized


def export_gif(meta: SheetMeta, tag: TagMeta, out_gif: Path, *, loop: int = 0,
               warnings: Optional[List[str]] = None) -> Path:
    """Write one tag as a looping transparent GIF. Collects warnings when a list is given."""
    out_gif = Path(out_gif)
    out_gif.parent.mkdir(parents=True, exist_ok=True)
    frames = ordered_frames(meta, tag)
    if not frames:
        raise ValueError(f"Tag '{tag.name}' covers no frames")
    durations, notes = gif_durations(frames)
    for note in notes:
        logger.warning(note)
    if warnings is not None:
        warnings.extend(notes)
    palette_frames: List[Image.Image] = []
    for frame in frames:
        if frame.source_path is None or not Path(frame.source_path).exists():
            raise FileNotFoundError(f"Frame '{frame.name}' has no source PNG: {frame.source_path}")
        with Image.open(frame.source_path) as im:
            palette_frames.append(to_palette_frame(im))
    first, rest = palette_frames[0], palette_frames[1:]
    first.save(
        out_gif, format="GIF", save_all=True, append_images=rest,
        duration=durations, loop=loop, disposal=2, optimize=False,
        transparency=TRANSPARENT_INDEX,
    )
    sidecar_path(out_gif).write_text(json.dumps({
        "type": "sprite_gif",
        "title": meta.title,
        "tag": tag.name,
        "direction": tag.direction,
        "frames": len(frames),
        "durations_ms": durations,
        "loop": loop,
        "warnings": notes,
        "app": meta.app,
        "version": meta.version,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8")
    logger.info(f"Wrote GIF {out_gif} ({len(frames)} frames, tag '{tag.name}')")
    return out_gif
```

Replace the whole content of `core/sprite/exporters/__init__.py` with:

```python
"""Exporters: pure projections of a SheetMeta onto files."""

from .grid import GridOptions, export_grid
from .aseprite_json import export_aseprite_json, aseprite_document
from .texturepacker_json import export_texturepacker_json, texturepacker_document
from .png_sequence import export_png_sequence, export_single_frame, render_frame_name
from .gif import export_gif, gif_durations

__all__ = [
    "GridOptions", "export_grid",
    "export_aseprite_json", "aseprite_document",
    "export_texturepacker_json", "texturepacker_document",
    "export_png_sequence", "export_single_frame", "render_frame_name",
    "export_gif", "gif_durations",
]
```

- [ ] **Step 4: Run the tests again.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_exporters.py -v
```

Expected: `17 passed`.

- [ ] **Step 5: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/exporters/__init__.py core/sprite/exporters/gif.py tests/sprite/test_exporters.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): transparent GIF export with the safe Pillow recipe"
```

---

### Task 15: Public package API and the full-suite gate

**Files:**
- Modify: `core/sprite/__init__.py` (replace whole file)
- Create: `tests/sprite/test_package.py`

**Interfaces:**
- Produces: `core.sprite.__all__` re-exporting every public symbol listed in the Self-review table below, so sub-projects 2–7 can `from core.sprite import SpriteProject, run_pipeline, export_grid, …`.

- [ ] **Step 1: Write the failing test.**

`tests/sprite/test_package.py`:

```python
"""The core.sprite package exports the whole sub-project 1 API (design 4.1)."""
import importlib

import core.sprite as sprite


def test_every_exported_name_resolves():
    for name in sprite.__all__:
        assert hasattr(sprite, name), name


def test_spec_symbols_are_exported():
    expected = {
        "FrameMeta", "TagMeta", "SheetMeta", "SpriteProject", "SpriteProjectManager",
        "GenerationSettings", "ExtractionSettings", "KeySettings", "StabilizeSettings",
        "OutputProfile", "ActionCard", "ClipRecord", "CostEntry",
        "FrameListSnapshot", "SnapshotStack",
        "CancelToken", "Cancelled", "ProgressFn", "no_progress", "STAGES", "STAGE_CODE_VERSION",
        "STAGE_RUNNERS", "STAGE_SETTINGS", "StageRunner", "SettingsFn", "register_stage",
        "identity_runner", "stage_fingerprint", "run_pipeline", "stage_dir",
        "ExtractResult", "probe_video", "extract_frames", "estimate_frame_count", "cull_duplicates",
        "FFmpegError", "GridGuess", "guess_grid", "slice_sheet", "import_png_sequence",
        "union_alpha_bbox", "solid_border_bbox", "crop_and_pad",
        "GridOptions", "export_grid", "export_aseprite_json", "export_texturepacker_json",
        "export_png_sequence", "export_single_frame", "export_gif",
    }
    missing = expected - set(sprite.__all__)
    assert not missing, missing


def test_import_does_not_load_the_cloud_video_clients():
    """core.video's package import costs seconds (google.genai); core.sprite must not pay it."""
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    code = "import sys, core.sprite; sys.exit(1 if 'core.video' in sys.modules else 0)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            timeout=120, cwd=repo_root)
    assert result.returncode == 0, result.stderr[-500:]


def test_submodules_import_cleanly():
    for module in ("models", "project", "presets", "undo", "pipeline", "extract", "slicing",
                   "stabilize", "exporters", "exporters.grid", "exporters.aseprite_json",
                   "exporters.texturepacker_json", "exporters.png_sequence", "exporters.gif"):
        importlib.import_module(f"core.sprite.{module}")
```

- [ ] **Step 2: Run it and watch it fail.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_package.py -v
```

Expected: `AttributeError: module 'core.sprite' has no attribute '__all__'` in the first two tests; the other two pass.

- [ ] **Step 3: Replace the package `__init__` with the full export list.**

Replace the whole content of `core/sprite/__init__.py` with:

```python
"""Sprite pipeline: pure Python, no Qt (design section 1).

Sub-project 1 (core spine) exports the data model, project persistence,
presets, undo, the stage pipeline, extraction, slicing, stabilisation and
the exporters. Later sub-projects add keying, pixel-art, generation, GUI and
CLI on top of this API.
"""

from .models import DIRECTIONS, FrameMeta, Rect, SheetMeta, Size, TagMeta
from .project import (
    PROJECT_FILE_NAME,
    ActionCard,
    ClipRecord,
    CostEntry,
    ExtractionSettings,
    GenerationSettings,
    KeySettings,
    OutputProfile,
    SpriteProject,
    SpriteProjectManager,
    StabilizeSettings,
    default_profiles,
)
from .presets import (
    CANVAS_PRESETS,
    CELL_PRESETS,
    DEFAULT_CELL,
    DEFAULT_FPS,
    DEFAULT_GENRE,
    FPS_PRESETS,
    GENRE_PRESETS,
    TARGET_RESOLUTIONS,
    format_cell_size,
    integer_scale,
    integer_scale_table,
    parse_cell_size,
)
from .undo import FrameListSnapshot, SnapshotStack
from .pipeline import (
    PROFILE_STAGES,
    STAGE_CODE_VERSION,
    STAGE_RUNNERS,
    STAGE_SETTINGS,
    STAGES,
    UPSTREAM,
    CancelToken,
    Cancelled,
    PipelineError,
    ProgressFn,
    SettingsFn,
    StageRunner,
    identity_runner,
    is_stage_current,
    list_frames,
    no_progress,
    record_fingerprint,
    register_external_frames,
    register_stage,
    run_pipeline,
    stage_dir,
    stage_fingerprint,
    stage_settings,
)
from .extract import ExtractResult, FFmpegError, cull_duplicates, estimate_frame_count, extract_frames, probe_video
from .slicing import GridGuess, guess_grid, import_png_sequence, slice_sheet
from .stabilize import ANCHORS, crop_and_pad, solid_border_bbox, union_alpha_bbox
from .exporters import (
    GridOptions,
    export_aseprite_json,
    export_gif,
    export_grid,
    export_png_sequence,
    export_single_frame,
    export_texturepacker_json,
)

__all__ = [
    # models
    "DIRECTIONS", "FrameMeta", "Rect", "SheetMeta", "Size", "TagMeta",
    # project
    "PROJECT_FILE_NAME", "ActionCard", "ClipRecord", "CostEntry", "ExtractionSettings",
    "GenerationSettings", "KeySettings", "OutputProfile", "SpriteProject",
    "SpriteProjectManager", "StabilizeSettings", "default_profiles",
    # presets
    "CANVAS_PRESETS", "CELL_PRESETS", "DEFAULT_CELL", "DEFAULT_FPS", "DEFAULT_GENRE",
    "FPS_PRESETS", "GENRE_PRESETS", "TARGET_RESOLUTIONS", "format_cell_size",
    "integer_scale", "integer_scale_table", "parse_cell_size",
    # undo
    "FrameListSnapshot", "SnapshotStack",
    # pipeline
    "PROFILE_STAGES", "STAGE_CODE_VERSION", "STAGE_RUNNERS", "STAGE_SETTINGS", "STAGES",
    "UPSTREAM", "CancelToken", "Cancelled", "PipelineError", "ProgressFn", "SettingsFn",
    "StageRunner", "identity_runner", "is_stage_current", "list_frames", "no_progress",
    "record_fingerprint", "register_external_frames", "register_stage", "run_pipeline",
    "stage_dir", "stage_fingerprint", "stage_settings",
    # extract / slicing / stabilize
    "ExtractResult", "FFmpegError", "cull_duplicates", "estimate_frame_count",
    "extract_frames", "probe_video", "GridGuess", "guess_grid", "import_png_sequence",
    "slice_sheet", "ANCHORS", "crop_and_pad", "solid_border_bbox", "union_alpha_bbox",
    # exporters
    "GridOptions", "export_aseprite_json", "export_gif", "export_grid",
    "export_png_sequence", "export_single_frame", "export_texturepacker_json",
]
```

- [ ] **Step 4: Run the package test, lint the new files, then run the whole suite.**

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_package.py -v
```

Expected: `4 passed`.

```bash
ruff check --select F,E9 /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite /mnt/d/Documents/Code/GitHub/ImageAI/tests/migration/test_sprite_storage.py
```

Expected: `All checks passed!` (`ruff` is at `/home/leland/.local/bin/ruff`; if it is missing, run `PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; $PY -m compileall -q /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite` and expect no output).

```bash
PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python; QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests -q
```

Expected: about `1172 passed, 19 skipped` (1057 before this sub-project + 115 added here) and no failures. Takes about 2.5 minutes.

- [ ] **Step 5: Commit.**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/__init__.py tests/sprite/test_package.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): public package API for the core spine"
```

- [ ] **Step 6: Update the plan status.** Mark every checkbox above done and set the design spec's status line for sub-project 1 to "implemented" in `Plans/2026-08-29-sprite-tab-design.md` only if the orchestrator asks; otherwise leave the spec alone. Do not push and do not open a PR — sub-project 7 owns the PR.

---

## Self-review

### Spec coverage (design §4.1 and §1.1/§1.2/§1.4/§1.6/§2 → task)

| Design symbol | Where | Task |
|---|---|---|
| `Rect`, `Size`, `FrameMeta`, `TagMeta`, `SheetMeta.to_dict/from_dict/frames_for` (§2) | `core/sprite/models.py` | 1 |
| `DataPaths.sprite_projects()`, `DataPaths.sprite_configs()`, `"sprites"` in `GROUP_CONTENTS[Group.IMAGES]`, `"sprite_configs.json"` in `SETTINGS_FILES`, migration pin test (§1.6, §5) | `core/paths.py`, `core/data_migration.py`, `tests/migration/test_sprite_storage.py` | 2 |
| `GenerationSettings`, `ExtractionSettings`, `KeySettings`, `StabilizeSettings`, `OutputProfile`, `ActionCard`, `ClipRecord`, `CostEntry`, `SpriteProject.save/load/reanchor_media_paths/sheet_meta/total_cost/purge_intermediates` (§2, §1.6), `SpriteProjectManager` | `core/sprite/project.py` | 3 |
| Cell/canvas/fps/genre presets + integer-scale calculator (§2) | `core/sprite/presets.py` | 4 |
| `FrameListSnapshot`, `SnapshotStack` depth 50 (§1.4) | `core/sprite/undo.py` | 5 |
| `CancelToken`, `Cancelled`, `ProgressFn`, `no_progress` (§1.1); `STAGES`, `STAGE_CODE_VERSION`, `stage_fingerprint`, `stage_dir` (§1.2, §4.1); the orchestrator's stage-runner registry `StageRunner`, `SettingsFn`, `STAGE_RUNNERS`, `STAGE_SETTINGS`, `register_stage` | `core/sprite/pipeline.py` | 6 |
| `ExtractResult`, `probe_video`, `extract_frames` (every_n / target_fps / exact_n, trim), `estimate_frame_count`, `cull_duplicates`, `FFmpegError` (§4.1) | `core/sprite/extract.py` | 7 |
| `GridGuess`, `guess_grid`, `slice_sheet`, `import_png_sequence` (§4.1, G9) | `core/sprite/slicing.py` | 8 |
| `union_alpha_bbox`, `solid_border_bbox`, `crop_and_pad` with anchors bottom_center/center/top_left/top_center/bottom_left (§4.1) | `core/sprite/stabilize.py` | 9 |
| `run_pipeline` dispatching through `STAGE_RUNNERS`, cache skip, `identity_runner` for `key/cleanup/alpha/pixel`, `stabilize_runner`, proportional `hd_runner`; external inputs enter at/after extract (§1.2, §4.1, G9, G17); test: a replacement `key` runner changes output and invalidates downstream while `extract` stays cached | `core/sprite/pipeline.py` | 10 |
| `GridOptions`, `export_grid` (padding knobs, extrude, power-of-two, `@2x/@4x` nearest copies, always-written Aseprite sidecar); `export_aseprite_json` hash + array with real Aseprite key names and `frameTags` direction (§4.1, gap 18) | `core/sprite/exporters/grid.py`, `aseprite_json.py` | 11 |
| `export_texturepacker_json` hash + array + pivot + `animations` (§4.1) | `core/sprite/exporters/texturepacker_json.py` | 12 |
| `export_png_sequence` with `{title} {tag} {frame} {frame01} {tagframe}`, `export_single_frame` (§4.1, "export individual frames") | `core/sprite/exporters/png_sequence.py` | 13 |
| `export_gif` safe recipe: reserved transparent index, `disposal=2`, `optimize=False`, durations ≥ 20 ms with warnings (§4.1, §6) | `core/sprite/exporters/gif.py` | 14 |
| Package exports (`core/layout/__init__.py` style) | `core/sprite/__init__.py` | 15 |
| Tests: numpy synthetic frames, ffmpeg session MP4 fixture with skip, golden JSON compared as parsed structures, GIF reload assertions, no-hardcoded-path guard stays green (§5, G16) | `tests/sprite/*`, `tests/sprite/golden/*` | 1, 7, 11, 12, 14, 15 |

### Placeholder scan

The generator asserted that no code block in this file contains `TBD`, `TODO`, `similar to Task`, `add validation`, `...` as a statement, or `pass  # implement`. Every code block is the verified prototype verbatim; the expander re-assembled each split file (`pipeline.py`, `test_pipeline.py`, `test_exporters.py`, `exporters/__init__.py`) from its task pieces and compared the result with the file that passed the tests.

### Type consistency

- `Rect`/`Size` are plain tuples everywhere; `to_dict` emits lists and `from_dict` casts back with `_rect`/`_size`.
- `FrameMeta.source_path` is `Optional[Path]`; every writer raises `FileNotFoundError` when it is `None` or missing.
- `ProgressFn` is the same 4-argument callable in `pipeline`, `extract`, `stabilize`; `token` is always `Optional[CancelToken]` and always polled through `check(token)` per frame.
- `run_pipeline` returns `Dict[str, List[Path]]` keyed by stage name; `stage_fingerprints` is `Dict[action_id, Dict[stage, sha1]]` and round-trips through the project JSON.
- `export_grid` returns a deep copy; the input `SheetMeta` is never mutated (test pins it).
- `_sync_frames` carries `duration_ms`, `pivot`, `overrides` over by index, so `key_stage_settings` in sub-project 3 can hash `action.frames[i].overrides` without the fingerprint flipping between runs.
- `SheetMeta.version` defaults to `core.constants.VERSION`; golden comparisons normalise it to `"TEST"` so a version bump never breaks them.

## Deviations from the design

1. **`SpriteProject` field defaults.** §2 lists `turnaround: Dict[str, Path]` and later fields with no default after `plate_color: str = "#00FF00"`. A dataclass cannot have a non-default field after a default one, so every field after `name` has a default (`project_dir=None`, `turnaround={}`, `actions=[]`, settings objects, `profiles=default_profiles()`, `created`/`modified` = now). Same reason: `SheetMeta`, `ActionCard`, `OutputProfile` keep the spec's defaults exactly.
2. **`export_gif` warnings.** §4.1 says the recipe returns a warning list, but the signature returns `Path`. The signature stays `-> Path`; a keyword-only `warnings: Optional[List[str]] = None` collects the messages when the caller passes a list. `gif_durations(frames)` exposes the same list on its own. GIF delays are stored in 10 ms units, so durations are also rounded to that unit (83 ms → 80 ms) with one summary warning; the spec did not mention the unit.
3. **`probe_video` fallback.** The `imageio-ffmpeg` binary this machine uses ships no `ffprobe`. `probe_video` tries ffprobe first and falls back to `cv2.VideoCapture` for fps, frame count, duration and size; the dict gains a `source` key (`"ffprobe"` or `"opencv"`).
4. **Stage directory names.** §1.2's code says `stages/<action_id>/<stage>/`; the §1.6 tree listing shows looser names (`extracted/ keyed/ cleaned/ cells/`). The plan follows §1.2: directories are named after `STAGES` (`extract`, `key`, `cleanup`, `alpha`, `stabilize`, `hd`, `pixel`).
5. **What `stabilize` and `hd` do in this sub-project.** §4.1 says `crop_and_pad` scales into `cell` (it does). The pipeline calls it twice: `stabilize` crops to the union bbox + `pad_px` with `cell` equal to that size (no resampling, so sub-projects 3–4 get lossless frames), and `hd` scales the result proportionally into `OutputProfile("hd").cell_size`. `pixel` is an identity copy until sub-project 4.
6. **Extra helpers not named in the spec** (additions only): `pipeline.PipelineError`, `UPSTREAM`, `PROFILE_STAGES`, `check`, `stage_settings`, `is_stage_current`, `record_fingerprint`, `register_external_frames`, `list_frames`, the default runners and settings functions; `stabilize.ANCHORS`, `has_transparency`, `anchor_offset`, `fit_size`; `slicing.foreground_mask`; `exporters.grid.next_power_of_two`; `exporters.aseprite_json.aseprite_document`, `texturepacker_json.texturepacker_document`; `png_sequence.render_frame_name`; `gif.gif_durations`, `ordered_frames`, `to_palette_frame`; `project.default_profiles`, `SpriteProject.slug/action_by_id/profile/project_file`, `ActionCard.new_id`, `PROJECT_FILE_NAME`, `PROJECT_SUBDIRS`, `SPRITES_DIR_NAME`, `SpriteProjectManager.save_project/find_project` (asked for by the GUI-5a and CLI plans).
7. **Two JSON files beside a grid PNG.** The Aseprite sidecar is `<stem>.json` (what engines look for) and the ImageAI metadata sidecar is `<name>.png.json` (the repo's every-image rule). Both are always written.
8. **`sheet_meta` tag direction.** `TagMeta.direction` is always `"forward"`; a non-looping action gets `repeat=1` (play once) instead of `repeat=0` (loop forever). The spec's `ActionCard.loop` has no stated mapping; this one keeps Aseprite semantics.
9. **Frame keys.** Aseprite JSON keys are `FrameMeta.name` (`hero_walk_00`); TexturePacker keys are `FrameMeta.name + ".png"`. The spec left key naming open.
10. **`SpriteProjectManager.delete_project`** uses `shutil.rmtree` like `core/video/project_manager.py`; only `purge_intermediates` goes through `core/recycle_bin.py`, as §1.6 states.
11. **Stage-runner registry** (orchestrator decision, 2026-08-29, additive to §4.1): `StageRunner`, `SettingsFn`, `STAGE_RUNNERS`, `STAGE_SETTINGS`, `STAGE_CODE_VERSION`, `register_stage(stage, runner, settings_fn=None, code_version=1)`. `run_pipeline` dispatches through the registry so sub-project 3 (key/cleanup/alpha, dejitter inside stabilize) and sub-project 4 (pixel) replace stages by re-registering them instead of editing the loop. `stage_fingerprint` reads `STAGE_SETTINGS[stage](project, action)` and `STAGE_CODE_VERSION[stage]`.
12. **Lazy ffmpeg import.** `core/sprite/extract.py` imports `core.video.ffmpeg_utils` inside `_ffmpeg()`/`_ffprobe()`, not at module level: `core/video/__init__.py` loads the cloud video clients (about 6 s), and the Sprite tab and the CLI must not pay that on `import core.sprite`. A test pins that `core.video` is absent from `sys.modules` after the import.
13. **Runner-registration test scope.** `test_every_stage_has_a_registered_runner` pins only that every stage has a callable runner and that `extract` is this module's; it does not pin `identity_runner` for `key`/`cleanup`/`alpha`/`pixel`, because sub-projects 3 and 4 re-register those on package import and the assertion would flip. `SheetMeta.palette` reports `locked_palette` only while `palette_size` is set (quantization on), at sub-project 4's request.
