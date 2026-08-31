### Task 1: Godot 4 `SpriteFrames` `.tres` exporter (+ golden)

**Files:**
- Create: `core/sprite/exporters/godot_tres.py`
- Create: `tests/sprite/golden/godot.tres`
- Test: `tests/sprite/test_godot_tres.py`

**Interfaces:**
- Consumes: `SheetMeta`, `FrameMeta`, `TagMeta` (`core/sprite/models.py`); `ms_to_fps(durations_ms) -> Tuple[int, List[float]]` (`core/sprite/timing.py`); `write_image_sidecar` (`core/utils.py:193`).
- Produces: `export_godot_tres(meta: SheetMeta, out_tres: Path, *, atlas_res_path: str) -> Path`; `render_godot_tres(meta: SheetMeta, *, atlas_res_path: str) -> str`; `ordered_frame_indices(tag: TagMeta) -> List[int]`.

Godot facts used here (verified 2026-08-24): Godot 4 has no JSON atlas importer. A text `SpriteFrames` resource with one `AtlasTexture` sub-resource per frame is the engine-ready path. `AtlasTexture.margin = Rect2(x, y, w, h)` offsets the drawn texture by `(x, y)` inside a region enlarged by `(w, h)`, so `margin = Rect2(ox, oy, sw - w, sh - h)` restores a trimmed cell. Each animation carries `speed` (fps), `loop`, and per-frame `duration` multipliers. `load_steps` = ext resources + sub resources + 1. `SpriteFrames` has no direction field, so reverse and ping-pong tags are unrolled.

- [ ] **Step 1: Write the golden file**

Create `tests/sprite/golden/godot.tres` with this exact content:

```
[gd_resource type="SpriteFrames" load_steps=5 format=3]

[ext_resource type="Texture2D" path="res://hero.png" id="1"]

[sub_resource type="AtlasTexture" id="AtlasTexture_1"]
atlas = ExtResource("1")
region = Rect2(0, 0, 16, 16)

[sub_resource type="AtlasTexture" id="AtlasTexture_2"]
atlas = ExtResource("1")
region = Rect2(16, 0, 12, 14)
margin = Rect2(2, 1, 4, 2)

[sub_resource type="AtlasTexture" id="AtlasTexture_3"]
atlas = ExtResource("1")
region = Rect2(0, 16, 16, 16)

[resource]
animations = [{
"frames": [{
"duration": 1.0,
"texture": SubResource("AtlasTexture_1")
}, {
"duration": 1.0,
"texture": SubResource("AtlasTexture_2")
}],
"loop": true,
"name": &"walk",
"speed": 10.0
}, {
"frames": [{
"duration": 1.0,
"texture": SubResource("AtlasTexture_3")
}],
"loop": false,
"name": &"idle",
"speed": 5.0
}]
```

- [ ] **Step 2: Write the failing test**

Create `tests/sprite/test_godot_tres.py`:

```python
# tests/sprite/test_godot_tres.py
from pathlib import Path

import pytest

from core.sprite.exporters.godot_tres import (
    export_godot_tres, ordered_frame_indices, render_godot_tres,
)
from core.sprite.models import FrameMeta, SheetMeta, TagMeta

GOLDEN = Path(__file__).parent / "golden" / "godot.tres"


def _meta() -> SheetMeta:
    frames = [
        FrameMeta(name="hero_walk_01", source_path=None, frame=(0, 0, 16, 16),
                  sprite_source_size=(0, 0, 16, 16), source_size=(16, 16), duration_ms=100),
        FrameMeta(name="hero_walk_02", source_path=None, frame=(16, 0, 12, 14), trimmed=True,
                  sprite_source_size=(2, 1, 12, 14), source_size=(16, 16), duration_ms=100),
        FrameMeta(name="hero_idle_01", source_path=None, frame=(0, 16, 16, 16),
                  sprite_source_size=(0, 0, 16, 16), source_size=(16, 16), duration_ms=200),
    ]
    tags = [
        TagMeta(name="walk", from_index=0, to_index=1),
        TagMeta(name="idle", from_index=2, to_index=2, repeat=1),
    ]
    return SheetMeta(title="hero", frames=frames, tags=tags, sheet_size=(32, 32), cell_size=(16, 16))


def _norm(text: str) -> str:
    return " ".join(text.split())


def test_export_matches_golden_after_whitespace_normalization(tmp_path):
    out = export_godot_tres(_meta(), tmp_path / "hero.tres", atlas_res_path="res://hero.png")
    assert out.exists()
    assert _norm(out.read_text(encoding="utf-8")) == _norm(GOLDEN.read_text(encoding="utf-8"))


def test_export_writes_json_sidecar(tmp_path):
    out = export_godot_tres(_meta(), tmp_path / "hero.tres", atlas_res_path="res://hero.png")
    sidecar = tmp_path / "hero.tres.json"
    assert sidecar.exists()
    assert '"godot_tres"' in sidecar.read_text(encoding="utf-8")


def test_load_steps_is_ext_plus_subs_plus_resource():
    text = render_godot_tres(_meta(), atlas_res_path="res://hero.png")
    assert "load_steps=5" in text.splitlines()[0]


def test_margin_only_on_trimmed_frames():
    text = render_godot_tres(_meta(), atlas_res_path="res://hero.png")
    assert text.count("margin = ") == 1
    assert "margin = Rect2(2, 1, 4, 2)" in text


def test_loop_false_when_repeat_set():
    text = render_godot_tres(_meta(), atlas_res_path="res://hero.png")
    assert '"loop": false' in text and '"loop": true' in text


def test_pingpong_and_reverse_are_unrolled():
    assert ordered_frame_indices(TagMeta(name="a", from_index=0, to_index=3, direction="pingpong")) == [0, 1, 2, 3, 2, 1]
    assert ordered_frame_indices(TagMeta(name="a", from_index=0, to_index=3, direction="reverse")) == [3, 2, 1, 0]
    assert ordered_frame_indices(TagMeta(name="a", from_index=1, to_index=3, direction="pingpong_reverse")) == [3, 2, 1, 2]
    assert ordered_frame_indices(TagMeta(name="a", from_index=2, to_index=2, direction="pingpong")) == [2]


def test_requires_filled_grid_rects():
    meta = _meta()
    meta.sheet_size = (0, 0)
    with pytest.raises(ValueError):
        render_godot_tres(meta, atlas_res_path="res://hero.png")


def test_requires_frames():
    with pytest.raises(ValueError):
        render_godot_tres(SheetMeta(title="x", frames=[], tags=[], sheet_size=(1, 1)), atlas_res_path="res://x.png")
```

- [ ] **Step 3: Run the test to see it fail**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_godot_tres.py -v` → `ModuleNotFoundError: core.sprite.exporters.godot_tres`.

- [ ] **Step 4: Implement the exporter**

Create `core/sprite/exporters/godot_tres.py`:

```python
"""Godot 4 ``SpriteFrames`` (.tres) exporter — a pure projection of SheetMeta.

Godot 4 has no JSON atlas importer. A text resource with one ``AtlasTexture``
sub-resource per frame is the engine-ready path: copy the PNG and the .tres
into the project and assign the .tres to an ``AnimatedSprite2D``.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from core.sprite.models import FrameMeta, SheetMeta, TagMeta
from core.sprite.timing import ms_to_fps
from core.utils import write_image_sidecar

logger = logging.getLogger(__name__)

GODOT_FORMAT = 3


def _fmt_float(value: float) -> str:
    """Godot text floats always carry a decimal point ("12.0", "1.5")."""
    text = f"{float(value):.4f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return text


def ordered_frame_indices(tag: TagMeta) -> List[int]:
    """Unroll a tag direction into the explicit frame order Godot plays.

    ``SpriteFrames`` has no direction field, so reverse and ping-pong tags
    become a plain sequence.
    """
    forward = list(range(tag.from_index, tag.to_index + 1))
    if tag.direction == "reverse":
        return forward[::-1]
    if tag.direction == "pingpong":
        return forward + forward[-2:0:-1]
    if tag.direction == "pingpong_reverse":
        back = forward[::-1]
        return back + back[-2:0:-1]
    return forward


def _atlas_block(index: int, frame: FrameMeta) -> str:
    x, y, w, h = frame.frame
    lines = [
        f'[sub_resource type="AtlasTexture" id="AtlasTexture_{index}"]',
        'atlas = ExtResource("1")',
        f"region = Rect2({x}, {y}, {w}, {h})",
    ]
    ox, oy, _, _ = frame.sprite_source_size
    sw, sh = frame.source_size
    if frame.trimmed and sw > 0 and sh > 0:
        margin = (ox, oy, sw - w, sh - h)
        if any(margin):
            lines.append(f"margin = Rect2({margin[0]}, {margin[1]}, {margin[2]}, {margin[3]})")
    return "\n".join(lines)


def _animation_block(meta: SheetMeta, tag: TagMeta) -> str:
    indices = ordered_frame_indices(tag)
    durations = [meta.frames[i].duration_ms for i in indices]
    fps, multipliers = ms_to_fps(durations)
    entries = []
    for i, mult in zip(indices, multipliers):
        entries.append(
            "{\n"
            f'"duration": {_fmt_float(mult)},\n'
            f'"texture": SubResource("AtlasTexture_{i + 1}")\n'
            "}"
        )
    loop = "true" if tag.repeat == 0 else "false"
    return (
        "{\n"
        '"frames": [' + ", ".join(entries) + "],\n"
        f'"loop": {loop},\n'
        f'"name": &"{tag.name}",\n'
        f'"speed": {_fmt_float(fps)}\n'
        "}"
    )


def render_godot_tres(meta: SheetMeta, *, atlas_res_path: str) -> str:
    """Return the .tres text for ``meta``. Frame rects must be filled by export_grid."""
    if not meta.frames:
        raise ValueError("SheetMeta has no frames")
    if tuple(meta.sheet_size) == (0, 0):
        raise ValueError("SheetMeta.sheet_size is (0, 0): run export_grid before export_godot_tres")
    load_steps = 1 + len(meta.frames) + 1
    parts = [
        f'[gd_resource type="SpriteFrames" load_steps={load_steps} format={GODOT_FORMAT}]',
        "",
        f'[ext_resource type="Texture2D" path="{atlas_res_path}" id="1"]',
        "",
    ]
    for index, frame in enumerate(meta.frames, start=1):
        parts.append(_atlas_block(index, frame))
        parts.append("")
    parts.append("[resource]")
    animations = ", ".join(_animation_block(meta, tag) for tag in meta.tags)
    parts.append(f"animations = [{animations}]")
    return "\n".join(parts) + "\n"


def export_godot_tres(meta: SheetMeta, out_tres: Path, *, atlas_res_path: str) -> Path:
    """Write ``meta`` as a Godot 4 SpriteFrames text resource plus a JSON sidecar."""
    out_tres = Path(out_tres)
    out_tres.parent.mkdir(parents=True, exist_ok=True)
    text = render_godot_tres(meta, atlas_res_path=atlas_res_path)
    out_tres.write_text(text, encoding="utf-8")
    write_image_sidecar(out_tres, {
        "format": "godot_tres",
        "atlas": atlas_res_path,
        "title": meta.title,
        "profile": meta.profile,
        "frames": len(meta.frames),
        "tags": [t.name for t in meta.tags],
        "app": meta.app,
        "version": meta.version,
    })
    logger.info("Godot SpriteFrames written: %s (%d frames, %d animations)",
                out_tres, len(meta.frames), len(meta.tags))
    return out_tres
```

- [ ] **Step 5: Run the test to see it pass**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_godot_tres.py -v` → 8 passed.

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/exporters/godot_tres.py tests/sprite/test_godot_tres.py tests/sprite/golden/godot.tres
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): Godot 4 SpriteFrames .tres exporter with golden test"
```

---

