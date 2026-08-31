# Sprite Image Route, Retouch & Engine Exports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Spec:** `Plans/2026-08-29-sprite-tab-design.md` §2 (data model), §3 row 6, §4.6 (image route, retouch, engine exports), §5 (testing).

**Last Updated:** 2026-08-30 20:05 — sub-project 6 COMPLETE. Tasks 1-11 done, final review + fix wave + scoped re-review closed. Suite 1903 passed / 19 skipped / 2 warnings at `dd48719`.

**Goal:** Ship Route B of the sprite pipeline (image-model sheets and edit-chains, with optional difference matting), a non-destructive per-frame AI retouch, and three engine-ready exporters (Godot 4 `.tres`, native `.aseprite`, engine presets), wired into the Sprite tab.

**Architecture:** Every new core module is pure Python under `core/sprite/` and takes an already-built provider object (`GoogleProvider` / `OpenAIProvider`) plus a `log` callable. Exporters are pure projections of `SheetMeta` (design §2). The GUI adds three small modules (`engine_preset_box.py`, `retouch_dialog.py`, `image_route_dialog.py`) plus two wiring modules that touch 5a/5b widgets through a handful of named attributes, so the 5a/5b files change by one or two lines each. Long work runs in `SpriteWorker` (design §1.1) with a `CancelToken`; provider calls never run on the UI thread.

**Tech Stack:** Python 3.11+, Pillow, numpy, `struct`/`zlib` (stdlib) for `.aseprite`, PySide6 for the dialogs, litellm via `core.llm_params.build_completion_kwargs` for the pose-steps contract, pytest with `MagicMock(spec=...)` providers.

**Sub-project:** 6 of 8 — depends on 1 (models, slicing, exporters, pipeline, timing), 2 (errors, prompts, action cards, cost), 3 (`matting.difference_matte`), 5a (`SpriteWorker`, `ActionCardsPanel`, `SpriteTab`), 5b (`ExportDialog`, `FrameStrip`, `PixelView`, undo); consumed by 7 (CLI `--sprite-export --sprite-preset`).

## Global Constraints

- Interpreter: `PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python`. Never `cd`; always absolute paths; `git -C /mnt/d/Documents/Code/GitHub/ImageAI …`.
- Tests: `$PY -m pytest <path> -v`. GUI tests: `QT_QPA_PLATFORM=offscreen $PY -m pytest tests/sprite/gui -v`. The full suite must stay green before every commit: `QT_QPA_PLATFORM=offscreen $PY -m pytest -q`.
- Branch `feat/sprite-tab`. Conventional Commits (`feat(sprite): …`, `test(sprite): …`). One commit per task. **No version bump and no CHANGELOG entry** in this sub-project; sub-project 7 does both.
- **Model IDs:** never write a `claude-*`/`gpt-*`/`gemini-*` string in runtime code. Chat models come from `resolve_model(provider, "chat")`; image models come from `provider.get_default_model()` or from the `MODEL_CAPS` table (`providers/openai.py:46-168`) by capability lookup. Tests may pick a table key by capability, never by literal.
- **Prompt text:** never put "transparent", an aspect ratio, or pixel dimensions in a prompt. `inject_chroma` (`core/sprite/generation/prompts.py`) strips `FORBIDDEN_WORDS`; the sheet prompt passes through it. Aspect goes through the `aspect_ratio=` kwarg (Gemini) or the `size=` kwarg (OpenAI).
- **Logging:** every provider call logs the full request (provider, model, params, prompt) and the full response (image count, byte sizes, model text) to the module logger and to the `log` callable (status console). Every user-facing error is logged.
- **Sidecars:** every artifact written by this sub-project gets a `.json` sidecar through `core.utils.write_image_sidecar` (`core/utils.py:193`). `sidecar_path()` appends `.json` to the full name (`hero.tres` → `hero.tres.json`).
- **Paths:** never build a data path by hand; project-relative paths come from `SpriteProject.project_dir` and `core.sprite.pipeline.stage_dir`. `tests/test_no_hardcoded_paths.py` must stay green.
- **Never overwrite raw frames.** Retouch writes `NNNN.r<k>.png` beside the original. A re-render archives the previous extract directory instead of deleting it.
- Provider calls in tests are `MagicMock(spec=GoogleProvider)` / `MagicMock(spec=OpenAIProvider)`; no network. Live tests are out of scope here.
- Prose in commit bodies, docstrings, and `how_to_import` text follows Simplified Technical English style (active voice, one instruction per sentence).

### Names assumed from sibling plans (keep identical)

Verified on 2026-08-29 against the sibling plan files (`Plans/2026-08-29-sprite-core-spine-plan.md`, `-video-route-plan.md`, `-keying-plan.md`, `-gui-a-plan.md`, `-gui-b-plan.md`), the authors' replies, and the orchestrator's decision on the 5a/5b plugin surface:

Sub-project 1: `core.sprite.models.{FrameMeta, TagMeta, SheetMeta, Rect, Size}` (`SheetMeta.frames_for(tag)`); `core.sprite.exporters.grid.{GridOptions(columns=0, border_px=0, shape_px=1, inner_px=0, extrude_px=0, power_of_two=False, scales=(1,)), export_grid(meta, out_png, opts) -> SheetMeta}` (writes `<stem>.json` Aseprite sidecar + `<name>.png.json`); `core.sprite.exporters.aseprite_json.export_aseprite_json(meta, out_json, *, image_name, layout="hash")`; `core.sprite.exporters.texturepacker_json.export_texturepacker_json(meta, out_json, *, image_name, layout="hash")`; `core.sprite.exporters.png_sequence.export_png_sequence(meta, out_dir, template)`; `core.sprite.exporters.gif.export_gif(meta, tag, out_gif, *, loop=0)`; `core.sprite.slicing.{guess_grid(sheet, key_color=None) -> GridGuess, slice_sheet(sheet, out_dir, columns, rows, cell=None, margin=0, spacing=0)}`; `core.sprite.pipeline.{CancelToken, Cancelled, ProgressFn, no_progress, run_pipeline(project, action, *, upto, progress, token, force), stage_dir(project, action, stage)}`; `core.sprite.project.{ActionCard, SpriteProject}`; `core.sprite.undo.{FrameListSnapshot, SnapshotStack}`.
Sub-project 2: `core.sprite.generation.errors.{SpriteGenerationError(user_message, *, retryable=None, ...), ProviderError, classify_provider_error(exc, *, provider="")}`; `core.sprite.generation.prompts.{inject_chroma(prompt, plate_color, *, loop), color_name, FORBIDDEN_WORDS}`; `core.sprite.generation.cost.record_actual(project, action, usd, note="", *, provider=None, model=None, seconds=None, estimated_usd=None) -> CostEntry` (keyword overrides keep video figures off image-route rows; `seconds` is the unit count — edits — for this route); `core.sprite.timing.ms_to_fps(durations_ms) -> (fps, multipliers)` (`[100, 100, 200] -> (10, [1.0, 1.0, 2.0])`); action-cards convention `completion_fn(**kwargs)` + `response.choices[0].message.content`.
Sub-project 3: `core.sprite.matting.difference_matte(on_white, on_black) -> Image`.
Sub-project 5a: `gui.sprite.workers.SpriteWorker(job, *, label="job", parent=None)` where `job(progress, token)`; signals `progress(str,int,int,str)`, `finished(object)`, `failed(str)` (uses `user_message` when present), `cancelled()`; `cancel()`, `token`; `gui.sprite.action_cards_panel.ActionCardsPanel.add_card_action(label, callback: Callable[[ActionCard], None]) -> None` (one button per card row, existing and future rows) and `.llm_provider() -> str`; `SpriteTab.make_provider(name: str = "google") -> ImageProvider` (raises `ValueError` with a user-facing message when the key is missing — call it inside a worker job); `SpriteTab.{config, console: DialogStatusConsole, log(message, level), current_project, current_action() -> Optional[ActionCard], action_cards_panel, add_toolbar_action(text, slot) -> QPushButton}`; signals `SpriteTab.projectChanged()`, `SpriteTab.actionSelected(str)`; `config.get_api_key(provider)`, `config.get_auth_mode(provider)` (`core/config.py:470`).
Sub-project 5b: `gui.sprite.export_dialog.{ExportDialog(project, parent=None), ExportRequest(project, profiles, formats, out_dir, template, grid, pivot, purge), FormatFn = Callable[[SheetMeta, Path], List[Path]], ExportFormat(id, label, fn, needs_sheet=False, takes_template=False), sheet_png_path(meta, out_dir) -> Path}`; `ExportDialog.register_format(id, label, fn, *, needs_sheet=False, takes_template=False, checked=False) -> QCheckBox` — `fn(meta, out_dir)`; with `needs_sheet=True` the dialog has already run the grid exporter, so `meta` arrives with frame rects filled and the sheet PNG sits at `sheet_png_path(meta, out_dir)`; built-in ids `grid`, `aseprite_json`, `texturepacker_json`, `png_sequence`, `gif`; widgets `format_checks: Dict[str, QCheckBox]`, `profile_checks`, `options_layout: QVBoxLayout` (profiles box, formats box, `notes_label`, output box, grid box), `notes_label: QLabel`, `pivot_x_spin` / `pivot_y_spin: QDoubleSpinBox`, `name_template_edit: QLineEdit`; methods `set_grid_options(GridOptions)`, `grid_options()`, `current_meta() -> Optional[SheetMeta]`, `selected_profiles()`, `selected_formats()`, `request()`; registering an id twice raises `ValueError`. `FrameStrip.retouchRequested = Signal(int)`, `FrameStrip.frames()`, `FrameStrip.refresh()`; `PixelView.{set_select_mode(bool), select_mode(), selection_rect() -> Optional[Rect], set_selection_rect(Optional[Rect]), clear_selection(), selectionChanged = Signal(object)}` (5b ships the region selection; sub-project 6 only reads `selection_rect()`); `FramesWorkspace.apply_frames(action_id: str, frames: List[FrameMeta], label: str) -> None` (public: pushes the undo snapshot of the CURRENT `action.frames` itself, writes `action.frames`, reloads strip + player, logs, emits `projectChanged()` — callers pass a NEW deep-copied list and never mutate live `FrameMeta` objects first); attributes on the tab: `tab.frame_strip`, `tab.pixel_view`, `tab.frames_workspace`, `tab.undo_controller`, `tab.undo_stack`, `tab.refresh_frames()` (not used here).

## File Structure

| Path | Action | Purpose |
|---|---|---|
| `core/sprite/exporters/godot_tres.py` | Create | `export_godot_tres`, `render_godot_tres`, `ordered_frame_indices` |
| `core/sprite/exporters/engine_presets.py` | Create | `EnginePreset`, `ENGINE_PRESETS`, `export_with_preset`, `fps_reconciliation`, `FORMAT_IDS` |
| `core/sprite/exporters/aseprite_native.py` | Create | `export_aseprite`, `read_aseprite_summary`, chunk constants |
| `core/sprite/generation/pose_steps.py` | Create | LLM contract "Sprite Pose Steps — Strict v1.0": `build_pose_messages`, `parse_pose_steps`, `fallback_pose_steps`, `generate_pose_instructions` |
| `core/sprite/generation/image_route.py` | Create | `sheet_prompt`, `generate_sheet`, `slice_generated_sheet`, `edit_chain`, shared provider helpers; re-exports `generate_pose_instructions` |
| `core/sprite/generation/retouch.py` | Create | `retouch_frame`, `next_retouch_path`, `build_region_mask`, `fit_to_size`, `validate_retouch` |
| `gui/sprite/export_formats.py` | Create | `register_extra_formats(dialog)`, `write_godot_tres`, `write_aseprite_native` |
| `gui/sprite/engine_preset_box.py` | Create | `EnginePresetBox`, `install_engine_presets(dialog, meta_fn)` |
| `gui/sprite/export_dialog.py` | Modify (2 lines) | call `register_extra_formats(self)` and `install_engine_presets(self)` at the end of `__init__` |
| `gui/sprite/retouch_dialog.py` | Create | `RetouchDialog(DialogCleanupMixin, QDialog)` |
| `gui/sprite/retouch_wiring.py` | Create | `install_retouch(tab)`, `open_retouch_dialog(tab, index)`, `apply_retouch(tab, action, index, new_path)` |
| `gui/sprite/image_route_dialog.py` | Create | `ImageRouteDialog(DialogCleanupMixin, QDialog)`, `install_image_route(tab)`, `archive_existing_frames(dir)` |
| `gui/sprite/sprite_tab.py` | Modify (2 lines) | `install_retouch(self)`, `install_image_route(self)` at the end of `__init__` |
| `tests/sprite/golden/godot.tres` | Create | golden Godot output |
| `tests/sprite/test_godot_tres.py` | Create | golden + unit tests |
| `tests/sprite/test_engine_presets.py` | Create | preset dispatch + reconciliation tests |
| `tests/sprite/test_aseprite_native.py` | Create | byte-level round-trip tests |
| `tests/sprite/test_pose_steps.py` | Create | contract parser + completion injection tests |
| `tests/sprite/test_image_route.py` | Create | sheet + edit-chain tests |
| `tests/sprite/test_retouch.py` | Create | retouch core tests |
| `tests/sprite/gui/test_export_dialog_engine_presets.py` | Create | preset box + registration tests |
| `tests/sprite/gui/test_retouch_dialog.py` | Create | dialog + wiring tests |
| `tests/sprite/gui/test_image_route_dialog.py` | Create | dialog + install tests |

---

### Task 1: Godot 4 `SpriteFrames` `.tres` exporter (+ golden)

**Files:**
- Create: `core/sprite/exporters/godot_tres.py`
- Create: `tests/sprite/golden/godot.tres`
- Test: `tests/sprite/test_godot_tres.py`

**Interfaces:**
- Consumes: `SheetMeta`, `FrameMeta`, `TagMeta` (`core/sprite/models.py`); `ms_to_fps(durations_ms) -> Tuple[int, List[float]]` (`core/sprite/timing.py`); `write_image_sidecar` (`core/utils.py:193`).
- Produces: `export_godot_tres(meta: SheetMeta, out_tres: Path, *, atlas_res_path: str) -> Path`; `render_godot_tres(meta: SheetMeta, *, atlas_res_path: str) -> str`; `ordered_frame_indices(tag: TagMeta) -> List[int]`.

Godot facts used here (verified 2026-08-24): Godot 4 has no JSON atlas importer. A text `SpriteFrames` resource with one `AtlasTexture` sub-resource per frame is the engine-ready path. `AtlasTexture.margin = Rect2(x, y, w, h)` offsets the drawn texture by `(x, y)` inside a region enlarged by `(w, h)`, so `margin = Rect2(ox, oy, sw - w, sh - h)` restores a trimmed cell. Each animation carries `speed` (fps), `loop`, and per-frame `duration` multipliers. `load_steps` = ext resources + sub resources + 1. `SpriteFrames` has no direction field, so reverse and ping-pong tags are unrolled.

- [x] **Step 1: Write the golden file**

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

- [x] **Step 2: Write the failing test**

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

- [x] **Step 3: Run the test to see it fail**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_godot_tres.py -v` → `ModuleNotFoundError: core.sprite.exporters.godot_tres`.

- [x] **Step 4: Implement the exporter**

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

- [x] **Step 5: Run the test to see it pass**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_godot_tres.py -v` → 8 passed.

- [x] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/exporters/godot_tres.py tests/sprite/test_godot_tres.py tests/sprite/golden/godot.tres
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): Godot 4 SpriteFrames .tres exporter with golden test"
```

---

### Task 2: Engine presets + fps reconciliation

**Files:**
- Create: `core/sprite/exporters/engine_presets.py`
- Test: `tests/sprite/test_engine_presets.py`

**Interfaces:**
- Consumes: `GridOptions`, `export_grid` (`core/sprite/exporters/grid.py`); `export_aseprite_json`, `export_texturepacker_json`, `export_png_sequence`, `export_gif` (sub-project 1); `export_godot_tres`, `ordered_frame_indices` (Task 1); `ms_to_fps`; `sanitize_filename` (`core/utils.py:14`), `write_image_sidecar`, `sidecar_path` (`core/utils.py:188-233`).
- Produces: `EnginePreset` (frozen dataclass: `id, label, formats, grid, pivot, name_template, how_to_import, json_layout="hash"`); `ENGINE_PRESETS: Dict[str, EnginePreset]`; `FORMAT_IDS`; `ATLAS_FORMATS`; `with_pivot(meta: SheetMeta, pivot) -> SheetMeta` (deep copy with every `FrameMeta.pivot` set); `export_with_preset(meta: SheetMeta, preset_id: str, out_dir: Path) -> List[Path]`; `fps_reconciliation(meta: SheetMeta, target: str) -> List[str]`.

Output naming convention (shared with Task 4 and sub-project 7): the grid PNG is `<sanitized title>.png`; the grid's own Aseprite JSON sidecar stays at `<title>.json`; TexturePacker JSON is `<title>.atlas.json`; explicit Aseprite JSON is `<title>.aseprite.json`; Godot is `<title>.tres`; native Aseprite is `<title>.aseprite`; GIFs are `<title>_<tag>.gif`; PNG frames go to `frames/`.

- [x] **Step 1: Write the failing test**

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

- [x] **Step 2: Run the test to see it fail**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_engine_presets.py -v` → `ModuleNotFoundError`.

- [x] **Step 3: Implement the presets**

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

- [x] **Step 4: Run the test to see it pass**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_engine_presets.py -v` → 11 passed. If `test_web_preview_writes_gif_per_tag_and_frames` fails on the `frames` parent name, check the sub-project 1 `export_png_sequence` return value; it must return the written frame paths.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/exporters/engine_presets.py tests/sprite/test_engine_presets.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): engine presets (8 targets) with one-call export and fps reconciliation"
```

---

### Task 3: Native `.aseprite` writer (+ minimal reader for tests)

**Files:**
- Create: `core/sprite/exporters/aseprite_native.py`
- Test: `tests/sprite/test_aseprite_native.py`

**Interfaces:**
- Consumes: `SheetMeta`, `FrameMeta` (frames point at RGBA PNGs), `write_image_sidecar`.
- Produces: `export_aseprite(meta: SheetMeta, out_ase: Path) -> Path`; `read_aseprite_summary(path: Path) -> dict` (test-only reader); constants `HEADER_MAGIC`, `FRAME_MAGIC`, `CHUNK_LAYER`, `CHUNK_CEL`, `CHUNK_COLOR_PROFILE`, `CHUNK_TAGS`, `CHUNK_PALETTE`, `DIRECTIONS`.

#### Byte layouts (copied from `docs/ase-file-specs.md`, fetched 2026-08-29 from github.com/aseprite/aseprite)

All values little-endian. Types: `BYTE` u8, `WORD` u16, `SHORT` i16, `DWORD` u32, `LONG` i32, `FIXED` 32-bit 16.16, `STRING` = `WORD` length + `BYTE[length]` UTF-8, `PIXEL` (RGBA) = `BYTE[4]`.

```
Header (128 bytes)
DWORD  File size
WORD   Magic number (0xA5E0)
WORD   Frames
WORD   Width in pixels
WORD   Height in pixels
WORD   Color depth (32 = RGBA, 16 = Grayscale, 8 = Indexed)
DWORD  Flags (1 = Layer opacity has valid value, 2 = layer blend/opacity valid for groups, 4 = layers have UUID)
WORD   Speed (ms between frames; DEPRECATED, use frame duration)
DWORD  Set to 0
DWORD  Set to 0
BYTE   Palette entry (index) for transparent color
BYTE[3] Ignore
WORD   Number of colors (0 means 256 for old sprites)
BYTE   Pixel width
BYTE   Pixel height
SHORT  X position of the grid
SHORT  Y position of the grid
WORD   Grid width (0 = no grid)
WORD   Grid height (0 = no grid)
BYTE[84] For future (set to zero)

Frame header (16 bytes)
DWORD  Bytes in this frame
WORD   Magic number (always 0xF1FA)
WORD   Old field: number of chunks (0xFFFF = use new field)
WORD   Frame duration (ms)
BYTE[2] For future (set to zero)
DWORD  New field: number of chunks (0 = use old field)

Chunk header
DWORD  Chunk size (includes this DWORD and the WORD type; >= 6)
WORD   Chunk type
BYTE[] Chunk data

Layer Chunk (0x2004)
WORD   Flags (1 Visible, 2 Editable, 4 Lock movement, 8 Background, 16 Prefer linked cels, 32 Group collapsed, 64 Reference)
WORD   Layer type (0 Normal image, 1 Group, 2 Tilemap)
WORD   Layer child level
WORD   Default layer width (ignored)
WORD   Default layer height (ignored)
WORD   Blend mode (0 = Normal)
BYTE   Opacity
BYTE[3] For future (set to zero)
STRING Layer name
(+ DWORD tileset index if type = 2; + UUID if header flag 4)

Cel Chunk (0x2005)
WORD   Layer index
SHORT  X position
SHORT  Y position
BYTE   Opacity level
WORD   Cel type (0 Raw, 1 Linked, 2 Compressed Image, 3 Compressed Tilemap)
SHORT  Z-Index
BYTE[5] For future (set to zero)
  type 2: WORD width, WORD height, PIXEL[] raw cel data compressed with ZLIB

Color Profile Chunk (0x2007)
WORD   Type (0 none, 1 sRGB, 2 embedded ICC)
WORD   Flags (1 = use special fixed gamma)
FIXED  Fixed gamma (1.0 = linear)
BYTE[8] Reserved (set to zero)
(+ DWORD length + BYTE[] ICC data if type = 2)

Tags Chunk (0x2018)
WORD   Number of tags
BYTE[8] For future (set to zero)
  per tag:
  WORD   From frame
  WORD   To frame
  BYTE   Loop direction (0 Forward, 1 Reverse, 2 Ping-pong, 3 Ping-pong Reverse)
  WORD   Repeat N times (0 = not specified, 1 = once, n = N times)
  BYTE[6] For future (set to zero)
  BYTE[3] RGB tag color (deprecated)
  BYTE   Extra byte (zero)
  STRING Tag name

Palette Chunk (0x2019)
DWORD  New palette size (total entries)
DWORD  First color index to change
DWORD  Last color index to change
BYTE[8] For future (set to zero)
  per entry in [first, last]:
  WORD   Entry flags (1 = has name)
  BYTE   Red, BYTE Green, BYTE Blue, BYTE Alpha
  (+ STRING color name if flag 1)

Old palette chunks 0x0004 / 0x0011: ignore when 0x2019 is present (not written here).
```

Struct formats derived from the layout (sizes checked: header 128, frame header 16, chunk header 6, layer 16 + name, cel 16 + 4 + zlib, color profile 16, tag 17 + name, palette head 20, palette entry 6):

| Struct | Format |
|---|---|
| header | `<IHHHHHIHIIB3xHBBhhHH84x` |
| frame header | `<IHHH2xI` |
| chunk header | `<IH` |
| layer | `<HHHHHHB3x` + STRING |
| cel | `<HhhBHh5x` + `<HH` + zlib |
| color profile | `<HHI8x` |
| tags head / tag | `<H8x` / `<HHBH6xBBBB` + STRING |
| palette head / entry | `<III8x` / `<HBBBB` |

- [x] **Step 1: Write the failing test**

Create `tests/sprite/test_aseprite_native.py`:

```python
# tests/sprite/test_aseprite_native.py
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.sprite.exporters.aseprite_native import (
    CHUNK_CEL, CHUNK_COLOR_PROFILE, CHUNK_LAYER, CHUNK_PALETTE, CHUNK_TAGS,
    FRAME_MAGIC, HEADER_MAGIC, export_aseprite, read_aseprite_summary,
)
from core.sprite.models import FrameMeta, SheetMeta, TagMeta


def _frame_png(path: Path, seed: int, size=(8, 8)) -> bytes:
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, size=(size[1], size[0], 4), dtype=np.uint8)
    Image.fromarray(arr, "RGBA").save(path)
    return arr.tobytes()


def _meta(tmp_path: Path, palette=None):
    frames, raw = [], []
    for i in range(3):
        p = tmp_path / f"{i + 1:04d}.png"
        raw.append(_frame_png(p, i))
        frames.append(FrameMeta(name=f"hero_{i}", source_path=p, frame=(0, 0, 8, 8),
                                sprite_source_size=(0, 0, 8, 8), source_size=(8, 8),
                                duration_ms=100 + 50 * i))
    tags = [TagMeta(name="walk", from_index=0, to_index=1, direction="pingpong"),
            TagMeta(name="idle", from_index=2, to_index=2, repeat=1)]
    return SheetMeta(title="hero", frames=frames, tags=tags, cell_size=(8, 8), palette=palette), raw


def test_header_fields(tmp_path):
    meta, _ = _meta(tmp_path)
    out = export_aseprite(meta, tmp_path / "hero.aseprite")
    s = read_aseprite_summary(out)
    assert s["magic"] == HEADER_MAGIC
    assert s["frames"] == 3 and s["width"] == 8 and s["height"] == 8 and s["depth"] == 32
    assert s["file_size"] == s["actual_size"]
    assert s["frame_magics"] == [FRAME_MAGIC] * 3
    assert (tmp_path / "hero.aseprite.json").exists()


def test_chunk_layout_first_frame_carries_metadata(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    first = [ctype for ctype, _size in s["chunks"][0]]
    assert first == [CHUNK_COLOR_PROFILE, CHUNK_LAYER, CHUNK_TAGS, CHUNK_CEL]
    assert [[c for c, _ in frame] for frame in s["chunks"][1:]] == [[CHUNK_CEL], [CHUNK_CEL]]
    assert all(size >= 6 for frame in s["chunks"] for _c, size in frame)


def test_frame_sizes_sum_to_file_size(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert 128 + sum(s["frame_sizes"]) == s["actual_size"]
    for frame_size, chunks in zip(s["frame_sizes"], s["chunks"]):
        assert frame_size == 16 + sum(size for _c, size in chunks)


def test_cel_pixels_round_trip(tmp_path):
    meta, raw = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert [c["pixels"] for c in s["cels"]] == raw
    assert all(c["type"] == 2 and c["width"] == 8 and c["height"] == 8 and c["layer"] == 0 for c in s["cels"])


def test_durations_and_layer_name(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert s["frame_durations"] == [100, 150, 200]
    assert s["layers"] == ["Sprite"]


def test_tags_directions_and_repeat(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert s["tags"] == [
        {"name": "walk", "from": 0, "to": 1, "direction": 2, "repeat": 0},
        {"name": "idle", "from": 2, "to": 2, "direction": 0, "repeat": 1},
    ]


def test_palette_chunk_when_quantized(tmp_path):
    meta, _ = _meta(tmp_path, palette=["#FF0000", "#00FF00", "#0000FF"])
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    first = [ctype for ctype, _ in s["chunks"][0]]
    assert first == [CHUNK_COLOR_PROFILE, CHUNK_PALETTE, CHUNK_LAYER, CHUNK_TAGS, CHUNK_CEL]
    assert s["palette"] == ["#FF0000", "#00FF00", "#0000FF"]
    assert s["ncolors"] == 3


def test_no_palette_chunk_without_palette(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert CHUNK_PALETTE not in [c for c, _ in s["chunks"][0]]
    assert s["ncolors"] == 0


def test_oversized_frame_is_fit_proportionally(tmp_path):
    meta, _ = _meta(tmp_path)
    wide = tmp_path / "wide.png"
    _frame_png(wide, 9, size=(16, 8))
    meta.frames[1].source_path = wide
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    cel = s["cels"][1]
    assert (cel["width"], cel["height"]) == (8, 4)
    assert (cel["x"], cel["y"]) == (0, 2)


def test_requires_frames(tmp_path):
    with pytest.raises(ValueError):
        export_aseprite(SheetMeta(title="x", frames=[], tags=[]), tmp_path / "x.aseprite")
```

- [x] **Step 2: Run the test to see it fail**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_aseprite_native.py -v` → `ModuleNotFoundError`.

- [x] **Step 3: Implement the writer and reader**

Create `core/sprite/exporters/aseprite_native.py`:

```python
"""Native ``.aseprite`` writer plus a minimal reader used by the tests.

Byte layout follows docs/ase-file-specs.md (Aseprite repository, fetched
2026-08-29; the layouts are copied into the implementation plan). One RGBA
layer, one zlib-compressed cel (type 2) per frame, one Tags chunk, an
optional Palette chunk, and an sRGB Color Profile chunk. Little-endian.
"""
from __future__ import annotations

import logging
import struct
import zlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.sprite.models import FrameMeta, SheetMeta
from core.utils import write_image_sidecar

logger = logging.getLogger(__name__)

HEADER_MAGIC = 0xA5E0
FRAME_MAGIC = 0xF1FA
CHUNK_LAYER = 0x2004
CHUNK_CEL = 0x2005
CHUNK_COLOR_PROFILE = 0x2007
CHUNK_TAGS = 0x2018
CHUNK_PALETTE = 0x2019
HEADER_SIZE = 128
FRAME_HEADER_SIZE = 16
COLOR_DEPTH_RGBA = 32
HEADER_FLAG_LAYER_OPACITY_VALID = 1
LAYER_FLAGS_VISIBLE_EDITABLE = 1 | 2
CEL_TYPE_COMPRESSED_IMAGE = 2
COLOR_PROFILE_SRGB = 1
DIRECTIONS = {"forward": 0, "reverse": 1, "pingpong": 2, "pingpong_reverse": 3}

_HEADER = struct.Struct("<IHHHHHIHIIB3xHBBhhHH84x")   # 128 bytes
_FRAME_HEADER = struct.Struct("<IHHH2xI")               # 16 bytes
_CHUNK_HEADER = struct.Struct("<IH")                     # 6 bytes
_LAYER = struct.Struct("<HHHHHHB3x")                     # + STRING name
_CEL = struct.Struct("<HhhBHh5x")                        # + WORD w, WORD h, zlib pixels
_CEL_SIZE = struct.Struct("<HH")
_COLOR_PROFILE = struct.Struct("<HHI8x")
_TAGS_HEAD = struct.Struct("<H8x")
_TAG = struct.Struct("<HHBH6xBBBB")                      # + STRING name
_PALETTE_HEAD = struct.Struct("<III8x")
_PALETTE_ENTRY = struct.Struct("<HBBBB")
_WORD = struct.Struct("<H")

assert _HEADER.size == HEADER_SIZE and _FRAME_HEADER.size == FRAME_HEADER_SIZE


def _string(text: str) -> bytes:
    raw = text.encode("utf-8")
    return _WORD.pack(len(raw)) + raw


def _read_string(data: bytes, pos: int) -> Tuple[str, int]:
    (length,) = _WORD.unpack_from(data, pos)
    start = pos + _WORD.size
    return data[start:start + length].decode("utf-8"), start + length


def _chunk(chunk_type: int, payload: bytes) -> bytes:
    return _CHUNK_HEADER.pack(_CHUNK_HEADER.size + len(payload), chunk_type) + payload


def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
    c = color.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _frame_image(frame: FrameMeta, cell: Tuple[int, int]) -> Tuple[Image.Image, int, int]:
    """Load the frame as RGBA fitted proportionally into ``cell``; return (image, x, y)."""
    if frame.source_path is None:
        raise ValueError(f"frame {frame.name!r} has no source_path")
    with Image.open(frame.source_path) as src:
        img = src.convert("RGBA")
    if img.size == cell:
        return img, 0, 0
    fitted = img.copy()
    fitted.thumbnail(cell, Image.LANCZOS)          # proportional; never distorts
    x = (cell[0] - fitted.width) // 2
    y = (cell[1] - fitted.height) // 2
    return fitted, x, y


def _layer_chunk(name: str) -> bytes:
    return _chunk(CHUNK_LAYER, _LAYER.pack(LAYER_FLAGS_VISIBLE_EDITABLE, 0, 0, 0, 0, 0, 255) + _string(name))


def _cel_chunk(img: Image.Image, x: int, y: int) -> bytes:
    payload = (_CEL.pack(0, x, y, 255, CEL_TYPE_COMPRESSED_IMAGE, 0)
               + _CEL_SIZE.pack(img.width, img.height)
               + zlib.compress(img.tobytes()))
    return _chunk(CHUNK_CEL, payload)


def _color_profile_chunk() -> bytes:
    return _chunk(CHUNK_COLOR_PROFILE, _COLOR_PROFILE.pack(COLOR_PROFILE_SRGB, 0, 0))


def _tags_chunk(meta: SheetMeta) -> bytes:
    body = _TAGS_HEAD.pack(len(meta.tags))
    for tag in meta.tags:
        direction = DIRECTIONS.get(tag.direction, 0)
        body += _TAG.pack(tag.from_index, tag.to_index, direction, tag.repeat, 0, 0, 0, 0) + _string(tag.name)
    return _chunk(CHUNK_TAGS, body)


def _palette_chunk(palette: List[str]) -> bytes:
    body = _PALETTE_HEAD.pack(len(palette), 0, len(palette) - 1)
    for color in palette:
        r, g, b = _hex_to_rgb(color)
        body += _PALETTE_ENTRY.pack(0, r, g, b, 255)
    return _chunk(CHUNK_PALETTE, body)


def _frame_bytes(duration_ms: int, chunks: List[bytes]) -> bytes:
    body = b"".join(chunks)
    count = len(chunks)
    old_count = count if count < 0xFFFF else 0xFFFF
    duration = max(1, min(int(duration_ms), 0xFFFF))
    return _FRAME_HEADER.pack(_FRAME_HEADER.size + len(body), FRAME_MAGIC, old_count, duration, count) + body


def export_aseprite(meta: SheetMeta, out_ase: Path) -> Path:
    """Write ``meta`` as a native Aseprite file (one layer, one cel per frame)."""
    if not meta.frames:
        raise ValueError("SheetMeta has no frames")
    cell = (int(meta.cell_size[0]), int(meta.cell_size[1]))
    if cell[0] <= 0 or cell[1] <= 0:
        raise ValueError(f"invalid cell_size {meta.cell_size}")
    palette = list(meta.palette) if meta.palette else []
    frames_blob = b""
    for index, frame in enumerate(meta.frames):
        img, x, y = _frame_image(frame, cell)
        chunks: List[bytes] = []
        if index == 0:
            chunks.append(_color_profile_chunk())
            if palette:
                chunks.append(_palette_chunk(palette))
            chunks.append(_layer_chunk("Sprite"))
            if meta.tags:
                chunks.append(_tags_chunk(meta))
        chunks.append(_cel_chunk(img, x, y))
        frames_blob += _frame_bytes(frame.duration_ms, chunks)
    header = _HEADER.pack(
        HEADER_SIZE + len(frames_blob), HEADER_MAGIC, len(meta.frames), cell[0], cell[1],
        COLOR_DEPTH_RGBA, HEADER_FLAG_LAYER_OPACITY_VALID,
        max(1, min(meta.frames[0].duration_ms, 0xFFFF)), 0, 0,
        0, len(palette), 1, 1, 0, 0, 0, 0,
    )
    out_ase = Path(out_ase)
    out_ase.parent.mkdir(parents=True, exist_ok=True)
    out_ase.write_bytes(header + frames_blob)
    write_image_sidecar(out_ase, {
        "format": "aseprite", "title": meta.title, "profile": meta.profile,
        "frames": len(meta.frames), "cell_size": list(cell), "palette": palette or None,
        "tags": [t.name for t in meta.tags], "app": meta.app, "version": meta.version,
    })
    logger.info("Aseprite file written: %s (%d frames, %dx%d)", out_ase, len(meta.frames), cell[0], cell[1])
    return out_ase


def read_aseprite_summary(path: Path) -> Dict[str, Any]:
    """Parse header, frame headers, and the chunks this writer emits. Test helper."""
    data = Path(path).read_bytes()
    (size, magic, frames, width, height, depth, flags, _speed, _z1, _z2,
     _transparent, ncolors, _pw, _ph, _gx, _gy, _gw, _gh) = _HEADER.unpack_from(data, 0)
    summary: Dict[str, Any] = {
        "file_size": size, "actual_size": len(data), "magic": magic, "frames": frames,
        "width": width, "height": height, "depth": depth, "flags": flags, "ncolors": ncolors,
        "frame_magics": [], "frame_durations": [], "frame_sizes": [], "chunks": [],
        "layers": [], "tags": [], "palette": [], "cels": [],
    }
    pos = HEADER_SIZE
    for frame_index in range(frames):
        frame_size, frame_magic, old_count, duration, new_count = _FRAME_HEADER.unpack_from(data, pos)
        count = old_count if new_count == 0 else new_count
        summary["frame_magics"].append(frame_magic)
        summary["frame_durations"].append(duration)
        summary["frame_sizes"].append(frame_size)
        chunk_pos = pos + FRAME_HEADER_SIZE
        types: List[Tuple[int, int]] = []
        for _ in range(count):
            chunk_size, chunk_type = _CHUNK_HEADER.unpack_from(data, chunk_pos)
            payload = data[chunk_pos + _CHUNK_HEADER.size: chunk_pos + chunk_size]
            types.append((chunk_type, chunk_size))
            if chunk_type == CHUNK_LAYER:
                name, _ = _read_string(payload, _LAYER.size)
                summary["layers"].append(name)
            elif chunk_type == CHUNK_CEL:
                layer, x, y, _opacity, cel_type, _z = _CEL.unpack_from(payload, 0)
                w, h = _CEL_SIZE.unpack_from(payload, _CEL.size)
                pixels = zlib.decompress(payload[_CEL.size + _CEL_SIZE.size:]) if cel_type == CEL_TYPE_COMPRESSED_IMAGE else b""
                summary["cels"].append({"frame": frame_index, "layer": layer, "x": x, "y": y,
                                        "type": cel_type, "width": w, "height": h, "pixels": pixels})
            elif chunk_type == CHUNK_TAGS:
                (ntags,) = _TAGS_HEAD.unpack_from(payload, 0)
                tpos = _TAGS_HEAD.size
                for _ in range(ntags):
                    frm, to, direction, repeat, _r, _g, _b, _extra = _TAG.unpack_from(payload, tpos)
                    name, tpos = _read_string(payload, tpos + _TAG.size)
                    summary["tags"].append({"name": name, "from": frm, "to": to, "direction": direction, "repeat": repeat})
            elif chunk_type == CHUNK_PALETTE:
                _psize, first, last = _PALETTE_HEAD.unpack_from(payload, 0)
                epos = _PALETTE_HEAD.size
                for _ in range(last - first + 1):
                    eflags, r, g, b, _a = _PALETTE_ENTRY.unpack_from(payload, epos)
                    epos += _PALETTE_ENTRY.size
                    if eflags & 1:
                        _name, epos = _read_string(payload, epos)
                    summary["palette"].append(f"#{r:02X}{g:02X}{b:02X}")
            chunk_pos += chunk_size
        summary["chunks"].append(types)
        pos += frame_size
    return summary
```

- [x] **Step 4: Run the test to see it pass**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_aseprite_native.py -v` → 10 passed. Then run `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_engine_presets.py -q` again (the `aseprite_native` writer import in Task 2 now resolves).

- [x] **Step 5: Manual check (optional, not gated)**

Open the produced file in Aseprite (or `aseprite -b hero.aseprite --list-tags`) once, and record the result in the commit body. The byte-level test is the gate.

- [x] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/exporters/aseprite_native.py tests/sprite/test_aseprite_native.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): native .aseprite writer (layer, zlib cels, tags, palette, sRGB) with byte-level reader test"
```

---

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

- [x] **Step 1: Write the failing test**

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

- [x] **Step 2: Run the test to see it fail**

`QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_export_dialog_engine_presets.py -v` → `ModuleNotFoundError: gui.sprite.engine_preset_box`.

- [x] **Step 3: Implement the format writers**

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

- [x] **Step 4: Implement the preset box**

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

- [x] **Step 5: Wire the dialog (5b file)**

Modify `gui/sprite/export_dialog.py`: add the two imports at module top and, in `ExportDialog.__init__`, right after the built-in formats are registered and before saved settings are restored (so saved format choices still apply to the new checkboxes), add:

```python
from gui.sprite.engine_preset_box import install_engine_presets
from gui.sprite.export_formats import register_extra_formats
...
        register_extra_formats(self)
        install_engine_presets(self)
```

- [x] **Step 6: Run the tests to see them pass**

`QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui -v` → the 9 new tests pass and the 5b export-dialog tests still pass (the two new ids appear at the end of `formats()`).

- [x] **Step 7: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/export_formats.py gui/sprite/engine_preset_box.py gui/sprite/export_dialog.py tests/sprite/gui/test_export_dialog_engine_presets.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): export dialog gains Godot/.aseprite formats and an engine-preset picker"
```

---

### Task 5: LLM contract "Sprite Pose Steps — Strict v1.0"

**Files:**
- Create: `core/sprite/generation/pose_steps.py`
- Test: `tests/sprite/test_pose_steps.py`

**Interfaces:**
- Consumes: `resolve_model(provider_id, family, static_default=None)` (`core/llm_models.py:63`); `LLMParams` (`core/llm_params.py:66-73`), `build_completion_kwargs(provider, model, messages, params, *, api_key, api_base, auth_mode, strict, on_warning)` (`core/llm_params.py:473`); `LLMResponseParser.parse_json_response(content, expected_type)` (`core/llm_parsing.py:19`); `FORBIDDEN_WORDS` (`core/sprite/generation/prompts.py`); `classify_provider_error` (`core/sprite/generation/errors.py`); `ActionCard` (`core/sprite/project.py`).
- Produces: `CONTRACT_NAME`, `POSE_STEPS_SCHEMA`, `SYSTEM_PROMPT`, `PoseStepsContractError(ValueError)`, `build_pose_messages(action, frames, character_notes="") -> List[Dict[str, str]]`, `parse_pose_steps(text, frames) -> List[str]`, `fallback_pose_steps(action, frames) -> List[str]`, `generate_pose_instructions(action, frames, *, provider="google", model=None, api_key=None, auth_mode=None, character_notes="", completion_fn=None, log=logger.info) -> List[str]`.

Contract (per `Docs/LLM-Contracts.md`): the system prompt names the contract and embeds the JSON Schema; the user prompt carries the action and reiterates `frames`; the code handler validates version, count, order, and non-empty poses, strips forbidden words, and falls back to generic evenly spaced poses on any contract violation. `completion_fn` is called as `completion_fn(**kwargs)` with the litellm kwargs (same convention as `action_cards.generate_action_cards`).

- [x] **Step 1: Write the failing test**

Create `tests/sprite/test_pose_steps.py`:

```python
# tests/sprite/test_pose_steps.py
import json
from types import SimpleNamespace

import pytest

from core.sprite.generation.errors import SpriteGenerationError
from core.sprite.generation.pose_steps import (
    CONTRACT_NAME, PoseStepsContractError, build_pose_messages, fallback_pose_steps,
    generate_pose_instructions, parse_pose_steps,
)
from core.sprite.project import ActionCard


def _action(loop=True) -> ActionCard:
    return ActionCard(id="a1", name="walk", prompt="walks briskly to the right", duration_s=4,
                      loop=loop, target_frames=4, fps=12)


def _reply(frames=4, version="1.0"):
    steps = [{"index": k, "pose": f"Pose {k}: left foot forward, arms swing.", "change": f"step {k}"} for k in range(1, frames + 1)]
    return json.dumps({"version": version, "action": "walk", "frames": frames, "steps": steps})


def _fake_response(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def test_messages_name_contract_and_frames():
    msgs = build_pose_messages(_action(), 4, "red scarf")
    assert msgs[0]["role"] == "system" and CONTRACT_NAME in msgs[0]["content"]
    assert "Exactly 4 steps" in msgs[0]["content"]
    assert "frames=4" in msgs[1]["content"] and "red scarf" in msgs[1]["content"]
    for m in msgs:
        assert "transparent" not in m["content"].lower().replace("transparency", "")


def test_parse_valid_and_fenced():
    assert len(parse_pose_steps(_reply(), 4)) == 4
    fenced = "```json\n" + _reply() + "\n```"
    steps = parse_pose_steps(fenced, 4)
    assert steps[0].startswith("Pose 1") and steps[0].endswith("Change: step 1.")


def test_parse_rejects_wrong_count_version_order_and_empty():
    with pytest.raises(PoseStepsContractError):
        parse_pose_steps(_reply(frames=3), 4)
    with pytest.raises(PoseStepsContractError):
        parse_pose_steps(_reply(version="0.9"), 4)
    bad_order = json.loads(_reply())
    bad_order["steps"][0]["index"] = 2
    with pytest.raises(PoseStepsContractError):
        parse_pose_steps(json.dumps(bad_order), 4)
    empty = json.loads(_reply())
    empty["steps"][1]["pose"] = "  "
    with pytest.raises(PoseStepsContractError):
        parse_pose_steps(json.dumps(empty), 4)
    with pytest.raises(PoseStepsContractError):
        parse_pose_steps("not json", 4)


def test_parse_strips_forbidden_words():
    data = json.loads(_reply())
    data["steps"][0]["pose"] = "Jumps on a transparent checkerboard floor"
    steps = parse_pose_steps(json.dumps(data), 4)
    assert "transparent" not in steps[0].lower() and "checkerboard" not in steps[0].lower()
    assert "Jumps on a floor" in steps[0]


def test_fallback_steps_count_and_loop_hint():
    steps = fallback_pose_steps(_action(loop=True), 3)
    assert len(steps) == 3 and "walk" in steps[0] and "starting pose" in steps[-1]
    assert "starting pose" not in fallback_pose_steps(_action(loop=False), 3)[-1]


def test_generate_uses_completion_fn_and_logs_request(monkeypatch):
    seen = {}
    logged = []

    def fake_completion(**kwargs):
        seen.update(kwargs)
        return _fake_response(_reply())

    steps = generate_pose_instructions(_action(), 4, provider="google", model="test-chat-model",
                                       api_key="k", auth_mode="api-key", completion_fn=fake_completion,
                                       log=logged.append)
    assert len(steps) == 4
    assert seen["model"].endswith("test-chat-model") and seen["api_key"] == "k"
    assert seen["messages"][1]["content"].startswith("TASK:")
    assert any("request" in line and "test-chat-model" in line for line in logged)
    assert any("response" in line for line in logged)
    assert not any("api_key': 'k'" in line for line in logged)


def test_generate_accepts_plain_string_reply():
    steps = generate_pose_instructions(_action(), 4, model="m", completion_fn=lambda **kw: _reply())
    assert len(steps) == 4


def test_generate_falls_back_on_contract_violation():
    steps = generate_pose_instructions(_action(), 4, model="m", completion_fn=lambda **kw: "garbage")
    assert steps == fallback_pose_steps(_action(), 4)


def test_generate_wraps_provider_errors():
    def boom(**kw):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")
    with pytest.raises(SpriteGenerationError):
        generate_pose_instructions(_action(), 4, model="m", completion_fn=boom)


def test_generate_resolves_model_when_missing(monkeypatch):
    monkeypatch.setattr("core.sprite.generation.pose_steps.resolve_model", lambda p, f: "resolved-model")
    seen = {}

    def fake(**kw):
        seen.update(kw)
        return _reply()

    generate_pose_instructions(_action(), 4, provider="openai", completion_fn=fake)
    assert seen["model"].endswith("resolved-model")
```

- [x] **Step 2: Run the test to see it fail**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pose_steps.py -v` → `ModuleNotFoundError`.

- [x] **Step 3: Implement the contract**

Create `core/sprite/generation/pose_steps.py`:

```python
"""LLM contract "Sprite Pose Steps — Strict v1.0" (pattern: Docs/LLM-Contracts.md).

Turns one action card into N per-frame pose sentences for the edit-chain
image route. The handler validates the reply and falls back to generic
evenly spaced poses, so the caller always gets exactly ``frames`` strings.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

from core.llm_models import resolve_model
from core.llm_params import LLMParams, build_completion_kwargs
from core.llm_parsing import LLMResponseParser
from core.sprite.generation.errors import classify_provider_error
from core.sprite.generation.prompts import FORBIDDEN_WORDS
from core.sprite.project import ActionCard

logger = logging.getLogger(__name__)

CONTRACT_NAME = "Sprite Pose Steps — Strict v1.0"
CONTRACT_VERSION = "1.0"
MAX_POSE_CHARS = 240

POSE_STEPS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["version", "action", "frames", "steps"],
    "properties": {
        "version": {"const": CONTRACT_VERSION},
        "action": {"type": "string"},
        "frames": {"type": "integer", "minimum": 1},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["index", "pose"],
                "properties": {
                    "index": {"type": "integer", "minimum": 1},
                    "pose": {"type": "string", "minLength": 1, "maxLength": MAX_POSE_CHARS},
                    "change": {"type": "string"},
                },
            },
        },
    },
}

SYSTEM_PROMPT = (
    f'You are "{CONTRACT_NAME}".\n'
    'Output must be a single JSON object that conforms exactly to the "Sprite Pose Steps Output Contract v1.0".\n'
    "Do not include commentary, Markdown, or code fences.\n\n"
    "Contract (JSON Schema):\n"
    f"{json.dumps(POSE_STEPS_SCHEMA, indent=2)}\n\n"
    "Rules:\n"
    "- Exactly FRAMES steps, index 1..FRAMES, in play order.\n"
    "- Every pose shows the same character, in the same view, at the same position in the frame. Only the body pose changes.\n"
    '- "pose" is one present-tense sentence about the full body (feet, legs, torso, arms, head).\n'
    '- "change" is one short phrase: what moved since the previous step.\n'
    "- Never mention the background, the camera, lighting, image size, or pixel dimensions.\n"
    "- For a looping action, the last step leads back into step 1.\n"
)

_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in FORBIDDEN_WORDS) + r")\b", re.IGNORECASE)


class PoseStepsContractError(ValueError):
    """The LLM reply does not satisfy the contract."""


def build_pose_messages(action: ActionCard, frames: int, character_notes: str = "") -> List[Dict[str, str]]:
    system = SYSTEM_PROMPT.replace("FRAMES", str(frames))
    user = (
        f"TASK: Break the action below into {frames} key poses for a sprite animation.\n"
        f"ACTION: name={action.name}; loop={'true' if action.loop else 'false'}; "
        f"duration_s={action.duration_s}; fps={action.fps}\n"
        f"DESCRIPTION: {action.prompt.strip()}\n"
        f"CHARACTER NOTES: {character_notes.strip() or '(none)'}\n"
        f"Return exactly one JSON object per the Sprite Pose Steps Output Contract v1.0 with frames={frames}."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_pose_steps(text: str, frames: int) -> List[str]:
    """Validate a reply against the contract and return ``frames`` pose sentences."""
    data = LLMResponseParser.parse_json_response(text, dict)
    if data is None:
        raise PoseStepsContractError("reply is not a JSON object")
    if str(data.get("version")) != CONTRACT_VERSION:
        raise PoseStepsContractError(f"version {data.get('version')!r} != {CONTRACT_VERSION!r}")
    steps = data.get("steps")
    if not isinstance(steps, list) or len(steps) != frames:
        got = len(steps) if isinstance(steps, list) else type(steps).__name__
        raise PoseStepsContractError(f"expected {frames} steps, got {got}")
    out: List[str] = []
    for k, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise PoseStepsContractError(f"step {k} is not an object")
        try:
            index = int(step.get("index", k))
        except (TypeError, ValueError):
            raise PoseStepsContractError(f"step {k} has a non-integer index")
        if index != k:
            raise PoseStepsContractError(f"step {k} has index {index}")
        pose = str(step.get("pose", "")).strip()
        if not pose:
            raise PoseStepsContractError(f"step {k} has an empty pose")
        change = str(step.get("change", "")).strip()
        sentence = pose if pose.endswith((".", "!")) else pose + "."
        if change:
            sentence += f" Change: {change.rstrip('.')}."
        sentence = _FORBIDDEN_RE.sub("", sentence)
        sentence = re.sub(r"\s{2,}", " ", sentence).strip()
        out.append(sentence[: MAX_POSE_CHARS * 2])
    return out


def fallback_pose_steps(action: ActionCard, frames: int) -> List[str]:
    """Generic evenly spaced poses when the LLM reply breaks the contract."""
    label = action.name.replace("_", " ")
    steps: List[str] = []
    for k in range(1, frames + 1):
        text = f"Key pose {k} of {frames} in the {label} cycle."
        if action.loop and k == frames:
            text += " The body returns toward the starting pose."
        steps.append(text)
    return steps


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    try:
        return response.choices[0].message.content or ""
    except (AttributeError, IndexError, TypeError):
        return str(response)


def generate_pose_instructions(
    action: ActionCard,
    frames: int,
    *,
    provider: str = "google",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    auth_mode: Optional[str] = None,
    character_notes: str = "",
    completion_fn: Optional[Callable[..., Any]] = None,
    log: Callable[[str], None] = logger.info,
) -> List[str]:
    """Ask the chat model for ``frames`` pose sentences; always returns ``frames`` strings."""
    if frames < 1:
        raise ValueError("frames must be >= 1")
    messages = build_pose_messages(action, frames, character_notes)
    model = model or resolve_model(provider, "chat")
    if completion_fn is None:
        import litellm
        completion_fn = litellm.completion
    kwargs = build_completion_kwargs(
        provider, model, messages, LLMParams(temperature=0.4, max_tokens=2000),
        api_key=api_key, auth_mode=auth_mode,
    )
    redacted = {k: v for k, v in kwargs.items() if k not in ("api_key", "messages")}
    request_log = (
        f"[pose steps] request: provider={provider} model={kwargs.get('model')} params={redacted}\n"
        + "\n".join(f"--- {m['role']} ---\n{m['content']}" for m in messages)
    )
    logger.info(request_log)
    log(request_log)
    try:
        response = completion_fn(**kwargs)
    except Exception as exc:  # noqa: BLE001 — every provider failure becomes a SpriteGenerationError
        logger.error("[pose steps] completion failed: %s", exc)
        log(f"[pose steps] completion failed: {exc}")
        raise classify_provider_error(exc) from exc
    text = _response_text(response)
    logger.info("[pose steps] response:\n%s", text)
    log(f"[pose steps] response:\n{text}")
    try:
        return parse_pose_steps(text, frames)
    except PoseStepsContractError as exc:
        logger.warning("[pose steps] contract violation (%s); using fallback steps", exc)
        log(f"[pose steps] contract violation: {exc}; using generic fallback steps")
        return fallback_pose_steps(action, frames)
```

- [x] **Step 4: Run the test to see it pass**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pose_steps.py -v` → 10 passed.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/pose_steps.py tests/sprite/test_pose_steps.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): Sprite Pose Steps strict v1.0 LLM contract with fallback"
```

---

### Task 6: Image route — sheet generation and slicing

**Files:**
- Create: `core/sprite/generation/image_route.py`
- Test: `tests/sprite/test_image_route.py`

**Interfaces:**
- Consumes: `GoogleProvider.edit_image(image, prompt, model=None, **kwargs)` (`providers/google.py:1832-1905`; honors `aspect_ratio=` via `image_config`); `OpenAIProvider.edit_image(image, prompt, model=None, mask=None, size="1024x1024", n=1, **kwargs)` (`providers/openai.py:821-940`); `MODEL_CAPS` (`providers/openai.py:46-168`); `validate_custom_size`, `parse_size_string` (`core/image_size.py:12-69`); `inject_chroma` (sub-project 2); `guess_grid`, `slice_sheet` (sub-project 1); `ProviderError`, `classify_provider_error` (sub-project 2); `CancelToken`; `write_image_sidecar`.
- Produces: `provider_kind(provider) -> str`; `call_provider(provider, method, *args, what, **kwargs)`; `first_image(texts, images, *, what) -> bytes`; `save_png(data, out_png) -> Path`; `log_request(...)`, `log_response(...)`; `openai_sheet_size(model) -> str`; `sheet_prompt(action, frames, plate_color) -> str`; `generate_sheet(provider, character, action, out_png, *, frames, plate_color, model=None, log=logger.info, token=None) -> Path`; `slice_generated_sheet(sheet_png, out_dir, frames, plate_color, *, log=logger.info) -> List[Path]`; re-export `generate_pose_instructions`.

- [x] **Step 1: Write the failing test**

Create `tests/sprite/test_image_route.py`:

```python
# tests/sprite/test_image_route.py
import json
import re
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

from core.image_size import parse_size_string
from core.sprite.generation import image_route
from core.sprite.generation.errors import ProviderError, SpriteGenerationError
from core.sprite.generation.image_route import (
    generate_sheet, openai_sheet_size, sheet_prompt, slice_generated_sheet,
)
from core.sprite.generation.prompts import FORBIDDEN_WORDS
from core.sprite.pipeline import CancelToken, Cancelled
from core.sprite.project import ActionCard
from core.sprite.slicing import GridGuess
from providers.google import GoogleProvider
from providers.openai import MODEL_CAPS, OpenAIProvider


def png_bytes(w=48, h=16, color=(0, 255, 0, 255), squares=3) -> bytes:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[...] = color
    cell = w // squares
    for i in range(squares):
        x0 = i * cell + 3
        arr[4:12, x0:x0 + 8] = (200, 40 + 40 * i, 60, 255)
    buf = BytesIO()
    Image.fromarray(arr, "RGBA").save(buf, "PNG")
    return buf.getvalue()


def _action() -> ActionCard:
    return ActionCard(id="a1", name="walk", prompt="walks briskly to the right", duration_s=4,
                      loop=True, target_frames=3, fps=12)


def _character(tmp_path: Path) -> Path:
    p = tmp_path / "character.png"
    p.write_bytes(png_bytes(w=16, h=16, squares=1))
    return p


def _google(reply=None):
    provider = MagicMock(spec=GoogleProvider)
    provider.get_default_model.return_value = "default-google-image-model"
    provider.edit_image.return_value = ([], [reply or png_bytes()])
    return provider


def _openai(reply=None):
    provider = MagicMock(spec=OpenAIProvider)
    provider.get_default_model.return_value = next(m for m, c in MODEL_CAPS.items() if c["supports_custom_size"])
    provider.edit_image.return_value = ([], [reply or png_bytes()])
    return provider


def test_sheet_prompt_is_clean():
    text = sheet_prompt(_action(), 6, "#00FF00")
    lowered = text.lower()
    assert "horizontal" in lowered and "6" in text and "#00FF00" in text
    assert not re.search(r"\d+\s*[x×]\s*\d+", text), "no pixel dimensions"
    assert not re.search(r"\b\d+:\d+\b", text), "no aspect ratio"
    for word in FORBIDDEN_WORDS:
        assert word not in lowered
    assert "seamless loop" in lowered


def test_generate_sheet_google_uses_aspect_kwarg_not_prompt(tmp_path):
    provider = _google()
    out = generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "sheet.png",
                         frames=3, plate_color="#00FF00")
    assert out.exists()
    args, kwargs = provider.edit_image.call_args
    assert kwargs["aspect_ratio"] == image_route.SHEET_ASPECT_GEMINI
    assert kwargs["model"] == "default-google-image-model"
    assert image_route.SHEET_ASPECT_GEMINI not in args[1]
    sidecar = json.loads((tmp_path / "sheet.png.json").read_text(encoding="utf-8"))
    assert sidecar["route"] == "image_sheet" and sidecar["frames"] == 3 and sidecar["provider"] == "google"
    assert Image.open(out).mode == "RGBA"


def test_generate_sheet_openai_uses_custom_3to1_size(tmp_path):
    provider = _openai()
    model = provider.get_default_model()
    generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "sheet.png",
                   frames=4, plate_color="#00FF00", model=model)
    args, kwargs = provider.edit_image.call_args
    w, h = parse_size_string(kwargs["size"])
    assert w / h == 3.0 and w % 16 == 0 and h % 16 == 0
    assert kwargs["model"] == model and kwargs["n"] == 1
    assert isinstance(args[0], list) and Path(args[0][0]).name == "character.png"


def test_openai_sheet_size_without_custom_size_picks_widest_preset():
    model = next(m for m, c in MODEL_CAPS.items() if not c["supports_custom_size"] and c["supports_multi_reference"])
    size = openai_sheet_size(model)
    widths = {parse_size_string(s) for s in MODEL_CAPS[model]["valid_sizes"] if s != "auto"}
    assert parse_size_string(size) == max(widths, key=lambda wh: wh[0] / wh[1])


def test_generate_sheet_no_image_raises_provider_error(tmp_path):
    provider = _google()
    provider.edit_image.return_value = (["I cannot draw that."], [])
    with pytest.raises(ProviderError) as info:
        generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "s.png", frames=3, plate_color="#00FF00")
    assert "cannot draw" in str(info.value)


def test_generate_sheet_wraps_provider_exception(tmp_path):
    provider = _google()
    provider.edit_image.side_effect = RuntimeError("Google image editing failed: 429 RESOURCE_EXHAUSTED")
    with pytest.raises(SpriteGenerationError):
        generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "s.png", frames=3, plate_color="#00FF00")


def test_generate_sheet_logs_request_and_response(tmp_path):
    lines = []
    generate_sheet(_google(), _character(tmp_path), _action(), tmp_path / "s.png",
                   frames=3, plate_color="#00FF00", log=lines.append)
    assert any("request" in l and "prompt:" in l for l in lines)
    assert any("response" in l and "1 image" in l for l in lines)


def test_generate_sheet_honors_cancel_token(tmp_path):
    token = CancelToken()
    token.cancel()
    provider = _google()
    with pytest.raises(Cancelled):
        generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "s.png",
                       frames=3, plate_color="#00FF00", token=token)
    provider.edit_image.assert_not_called()


def test_generate_sheet_rejects_fewer_than_two_frames(tmp_path):
    with pytest.raises(ValueError):
        generate_sheet(_google(), _character(tmp_path), _action(), tmp_path / "s.png", frames=1, plate_color="#00FF00")


def test_slice_uses_guess_when_confident(tmp_path, monkeypatch):
    sheet = tmp_path / "sheet.png"
    sheet.write_bytes(png_bytes(w=48, h=16, squares=3))
    monkeypatch.setattr(image_route, "guess_grid", lambda img, key_color=None: GridGuess(columns=3, rows=1, cell=(16, 16), confidence=0.95))
    frames = slice_generated_sheet(sheet, tmp_path / "frames", 3, "#00FF00")
    assert [p.name for p in frames] == ["0001.png", "0002.png", "0003.png"]
    assert all(Image.open(p).size == (16, 16) for p in frames)
    assert (tmp_path / "frames" / "0001.png.json").exists()


def test_slice_falls_back_to_one_row_when_guess_disagrees(tmp_path, monkeypatch):
    sheet = tmp_path / "sheet.png"
    sheet.write_bytes(png_bytes(w=48, h=16, squares=3))
    monkeypatch.setattr(image_route, "guess_grid", lambda img, key_color=None: GridGuess(columns=2, rows=2, cell=(24, 8), confidence=0.9))
    logged = []
    frames = slice_generated_sheet(sheet, tmp_path / "frames", 3, "#00FF00", log=logged.append)
    assert len(frames) == 3 and Image.open(frames[0]).size == (16, 16)
    assert any("rejected" in l for l in logged)
```

- [x] **Step 2: Run the test to see it fail**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_image_route.py -v` → `ModuleNotFoundError`.

- [x] **Step 3: Implement the module (sheet half)**

Create `core/sprite/generation/image_route.py`:

```python
"""Route B — image-model sprite generation: one horizontal sheet, or an edit-chain.

Both entry points take an already-built provider (GoogleProvider or
OpenAIProvider), write PNGs with JSON sidecars, log every request and
response in full, and raise ``SpriteGenerationError`` subclasses on failure.
"""
from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from PIL import Image

from core.sprite.generation.errors import ProviderError, classify_provider_error
from core.sprite.generation.pose_steps import generate_pose_instructions  # noqa: F401 — re-export (design §4.6)
from core.sprite.generation.prompts import inject_chroma
from core.sprite.models import Size
from core.sprite.pipeline import CancelToken
from core.sprite.project import ActionCard
from core.sprite.slicing import guess_grid, slice_sheet
from core.utils import write_image_sidecar

logger = logging.getLogger(__name__)
LogFn = Callable[[str], None]

SHEET_ASPECT_GEMINI = "21:9"      # widest ratio Gemini accepts (AGENTS.md list); kwarg only, never prompt text
SHEET_SIZE_CUSTOM = "3072x1024"   # 3:1 strip for OpenAI models with supports_custom_size
MIN_GRID_CONFIDENCE = 0.6

STEP_PROMPT = (
    "This is the same character. Change only the body pose: {instruction} "
    "Keep the identical character design, art style, scale, and position in the frame."
)


# --------------------------------------------------------------------------- shared helpers

def provider_kind(provider) -> str:
    """'openai' for OpenAIProvider instances, else 'google'."""
    from providers.openai import OpenAIProvider
    return "openai" if isinstance(provider, OpenAIProvider) else "google"


def default_openai_edit_model() -> str:
    """First MODEL_CAPS row that supports multi-reference edits with a mask (capability lookup, no literal)."""
    from providers.openai import MODEL_CAPS
    return next(mid for mid, caps in MODEL_CAPS.items() if caps["supports_multi_reference"] and caps["supports_mask"])


def _timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def first_image(texts: Sequence[str], images: Sequence[bytes], *, what: str) -> bytes:
    if images:
        return images[0]
    detail = " ".join(t.strip() for t in texts if t and t.strip())[:300]
    raise ProviderError(f"{what}: the model returned no image." + (f" Model text: {detail}" if detail else ""))


def save_png(data: bytes, out_png: Path) -> Path:
    """Decode any image bytes the model returned and store them as RGBA PNG."""
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(data)) as img:
        img.convert("RGBA").save(out_png, "PNG")
    return out_png


def log_request(log: LogFn, *, what: str, provider: str, model: Optional[str], prompt: str, params: Dict) -> None:
    message = (f"[image route] {what} request: provider={provider} model={model or 'default'} "
               f"params={params}\nprompt: {prompt}")
    logger.info(message)
    log(message)


def log_response(log: LogFn, *, what: str, texts: Sequence[str], images: Sequence[bytes]) -> None:
    text = " | ".join(t.strip() for t in texts if t and t.strip()) or "(none)"
    message = f"[image route] {what} response: {len(images)} image(s) {[len(b) for b in images]} bytes; text: {text}"
    logger.info(message)
    log(message)


def call_provider(provider, method: str, *args, what: str, **kwargs) -> Tuple[List[str], List[bytes]]:
    """Call ``provider.<method>`` and map any exception to a SpriteGenerationError."""
    try:
        return getattr(provider, method)(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — classify_provider_error decides the subclass
        logger.error("[image route] %s failed: %s", what, exc)
        raise classify_provider_error(exc) from exc


def openai_sheet_size(model: str) -> str:
    """3:1 custom size when the model allows it, else the widest preset size."""
    from core.image_size import parse_size_string, validate_custom_size
    from providers.openai import MODEL_CAPS
    caps = MODEL_CAPS.get(model) or MODEL_CAPS["gpt-image-1"]
    if caps.get("supports_custom_size"):
        w, h = parse_size_string(SHEET_SIZE_CUSTOM)
        ok, why = validate_custom_size(w, h, caps)
        if ok:
            return SHEET_SIZE_CUSTOM
        logger.warning("custom sheet size %s rejected for %s (%s); using preset sizes", SHEET_SIZE_CUSTOM, model, why)
    presets = [s for s in caps["valid_sizes"] if s != "auto"]
    return max(presets, key=lambda s: (lambda wh: wh[0] / wh[1])(parse_size_string(s)))


def openai_edit_size(model: str, size: Size) -> str:
    """Closest legal edit size for a source of ``size``; custom size when allowed and in range."""
    from core.image_size import parse_size_string, validate_custom_size
    from providers.openai import MODEL_CAPS
    caps = MODEL_CAPS.get(model) or MODEL_CAPS["gpt-image-1"]
    w, h = int(size[0]), int(size[1])
    if caps.get("supports_custom_size"):
        multiple = int(caps.get("custom_size_edge_multiple", 16))
        cw, ch = max(multiple, round(w / multiple) * multiple), max(multiple, round(h / multiple) * multiple)
        ok, _why = validate_custom_size(cw, ch, caps)
        if ok:
            return f"{cw}x{ch}"
    presets = [s for s in caps["valid_sizes"] if s != "auto"]
    target = w / h

    def score(s: str) -> float:
        pw, ph = parse_size_string(s)
        return abs(pw / ph - target)

    return min(presets, key=score)


# --------------------------------------------------------------------------- sheet route

def sheet_prompt(action: ActionCard, frames: int, plate_color: str) -> str:
    """Prompt for one horizontal strip; chroma suffix and loop hint come from inject_chroma."""
    label = action.name.replace("_", " ")
    base = (
        f"A {frames}-frame {label} animation of this exact character as one horizontal sprite sheet: "
        f"{frames} equal cells in a single row from left to right, one key pose per cell, in play order. "
        "Same character, same art style, same scale, and the same position inside every cell. "
        "No labels, no numbers, no cell borders, no text. "
        f"{action.prompt.strip()}"
    )
    return inject_chroma(base, plate_color, loop=action.loop)


def generate_sheet(
    provider,
    character: Path,
    action: ActionCard,
    out_png: Path,
    *,
    frames: int,
    plate_color: str,
    model: Optional[str] = None,
    log: LogFn = logger.info,
    token: Optional[CancelToken] = None,
) -> Path:
    """Generate one horizontal sheet from the character image; returns the sheet PNG path."""
    if frames < 2:
        raise ValueError("frames must be >= 2 for a sheet")
    if token is not None:
        token.raise_if_cancelled()
    character = Path(character)
    if not character.exists():
        raise FileNotFoundError(character)
    kind = provider_kind(provider)
    model = model or provider.get_default_model()
    prompt = sheet_prompt(action, frames, plate_color)
    if kind == "openai":
        size = openai_sheet_size(model)
        params: Dict = {"size": size, "n": 1}
        log_request(log, what="sheet", provider=kind, model=model, prompt=prompt, params=params)
        texts, images = call_provider(provider, "edit_image", [character], prompt, what="sheet",
                                      model=model, size=size, n=1)
    else:
        params = {"aspect_ratio": SHEET_ASPECT_GEMINI}
        log_request(log, what="sheet", provider=kind, model=model, prompt=prompt, params=params)
        texts, images = call_provider(provider, "edit_image", character, prompt, what="sheet",
                                      model=model, aspect_ratio=SHEET_ASPECT_GEMINI)
    log_response(log, what="sheet", texts=texts, images=images)
    out = save_png(first_image(texts, images, what="sheet"), out_png)
    write_image_sidecar(out, {
        "prompt": prompt, "provider": kind, "model": model, "timestamp": _timestamp(),
        "route": "image_sheet", "action": action.name, "action_id": action.id,
        "frames": frames, "plate_color": plate_color, "params": params,
        "reference_images": [str(character)],
    })
    log(f"[image route] sheet saved: {out}")
    return out


def slice_generated_sheet(
    sheet_png: Path,
    out_dir: Path,
    frames: int,
    plate_color: str,
    *,
    log: LogFn = logger.info,
) -> List[Path]:
    """Cut a generated sheet into ``frames`` PNGs (guess the grid; fall back to one row)."""
    sheet_png = Path(sheet_png)
    with Image.open(sheet_png) as img:
        guess = guess_grid(img.convert("RGBA"), key_color=plate_color)
    columns, rows = frames, 1
    if guess.confidence >= MIN_GRID_CONFIDENCE and guess.columns * guess.rows == frames:
        columns, rows = guess.columns, guess.rows
        log(f"[image route] grid detected: {columns}x{rows} (confidence {guess.confidence:.2f})")
    else:
        log(f"[image route] grid guess {guess.columns}x{guess.rows} (confidence {guess.confidence:.2f}) "
            f"rejected; slicing {frames}x1")
    paths = list(slice_sheet(sheet_png, Path(out_dir), columns, rows))
    for index, path in enumerate(paths, start=1):
        write_image_sidecar(path, {
            "route": "image_sheet", "source_sheet": str(sheet_png), "cell_index": index,
            "columns": columns, "rows": rows, "timestamp": _timestamp(),
        })
    return paths
```

- [x] **Step 4: Run the test to see it pass**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_image_route.py -v` → 12 passed.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/image_route.py tests/sprite/test_image_route.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): image route sheet generation (Gemini aspect kwarg, gpt-image 3:1 custom size) and slicing"
```

---

### Task 7: Image route — edit-chain (+ difference-matte pairs)

**Files:**
- Modify: `core/sprite/generation/image_route.py` (Task 6) — append `edit_chain`
- Test: `tests/sprite/test_image_route.py` — append the chain tests

**Interfaces:**
- Consumes: `GoogleProvider.start_edit_session(character_image: bytes, style_context=None, model=None) -> bool` (`providers/google.py:2016-2085`), `reset_edit_session()` (`:2087-2095`), `edit_image` with a list input (multi-reference, `:1832-1905`); `OpenAIProvider.edit_image` with a list of bytes (`providers/openai.py:855-877` normalizes bytes/paths); `difference_matte(on_white, on_black) -> Image` (`core/sprite/matting.py`, sub-project 3); `CancelToken`.
- Produces: `edit_chain(provider, character, action, out_dir, *, frames, pose_instructions, plate_color, model=None, log=logger.info, token=None, matte_pairs=False) -> List[Path]`.

Continuity: frame k is an edit whose inputs are `[character, frame k-1]`, so identity comes from the character and motion continuity from the previous frame. `edit_image` on both providers is single-shot; the Gemini chat session started by `start_edit_session` establishes style context and is reset in `finally`. With `matte_pairs=True` every step is rendered twice (white plate `#FFFFFF`, black plate `#000000`); `difference_matte` produces the RGBA frame, the two plates stay on disk as `NNNN.white.png` / `NNNN.black.png`, and the chain continues from the white plate.

- [x] **Step 1: Write the failing tests**

Append to `tests/sprite/test_image_route.py`:

```python
from core.sprite.generation.image_route import default_openai_edit_model, edit_chain, openai_edit_size


def _distinct_replies(n):
    return [png_bytes(w=16, h=16, squares=1, color=(0, 255, 0, 255)) if i % 2 == 0
            else png_bytes(w=16, h=16, squares=1, color=(0, 250, 5, 255)) for i in range(n)]


def test_edit_chain_google_chains_previous_frame(tmp_path):
    provider = _google()
    provider.start_edit_session.return_value = True
    replies = _distinct_replies(3)
    provider.edit_image.side_effect = [([], [r]) for r in replies]
    character = _character(tmp_path)
    out = edit_chain(provider, character, _action(), tmp_path / "chain", frames=3,
                     pose_instructions=["pose one", "pose two", "pose three"], plate_color="#00FF00")
    assert [p.name for p in out] == ["0001.png", "0002.png", "0003.png"]
    calls = provider.edit_image.call_args_list
    assert calls[0].args[0] == [character.read_bytes(), character.read_bytes()]
    assert calls[1].args[0] == [character.read_bytes(), replies[0]]
    assert calls[2].args[0] == [character.read_bytes(), replies[1]]
    assert all(c.kwargs["model"] == "default-google-image-model" for c in calls)
    assert "pose two" in calls[1].args[1] and "#00FF00" in calls[1].args[1]
    provider.start_edit_session.assert_called_once()
    provider.reset_edit_session.assert_called_once()
    sidecar = json.loads((tmp_path / "chain" / "0002.png.json").read_text(encoding="utf-8"))
    assert sidecar["step"] == 2 and sidecar["of"] == 3 and sidecar["route"] == "image_edit_chain"
    assert sidecar["reference_images"][1].endswith("0001.png")


def test_edit_chain_openai_passes_size_and_default_model(tmp_path):
    provider = _openai()
    provider.edit_image.side_effect = [([], [r]) for r in _distinct_replies(2)]
    out = edit_chain(provider, _character(tmp_path), _action(), tmp_path / "chain", frames=2,
                     pose_instructions=["a", "b"], plate_color="#00FF00")
    assert len(out) == 2
    kwargs = provider.edit_image.call_args_list[0].kwargs
    assert kwargs["model"] == default_openai_edit_model()
    assert kwargs["size"] == openai_edit_size(default_openai_edit_model(), (16, 16)) and kwargs["n"] == 1
    provider.start_edit_session.assert_not_called()


def test_openai_edit_size_prefers_custom_when_legal_else_closest_preset():
    model = next(m for m, c in MODEL_CAPS.items() if c["supports_custom_size"])
    assert openai_edit_size(model, (1024, 1024)) == "1024x1024"
    assert openai_edit_size(model, (1000, 1010)) == "1008x1008"
    small = openai_edit_size(model, (200, 200))          # below the pixel floor -> preset
    assert small in MODEL_CAPS[model]["valid_sizes"]
    legacy = next(m for m, c in MODEL_CAPS.items() if not c["supports_custom_size"] and c["supports_mask"])
    assert openai_edit_size(legacy, (300, 100)) == max(
        (s for s in MODEL_CAPS[legacy]["valid_sizes"] if s != "auto"),
        key=lambda s: parse_size_string(s)[0] / parse_size_string(s)[1])


def test_edit_chain_matte_pairs(tmp_path, monkeypatch):
    provider = _google()
    provider.start_edit_session.return_value = True
    provider.edit_image.side_effect = [([], [r]) for r in _distinct_replies(4)]
    seen = []

    def fake_matte(on_white, on_black):
        seen.append((on_white.size, on_black.size))
        return Image.new("RGBA", on_white.size, (10, 20, 30, 128))

    monkeypatch.setattr("core.sprite.matting.difference_matte", fake_matte)
    out = edit_chain(provider, _character(tmp_path), _action(), tmp_path / "chain", frames=2,
                     pose_instructions=["a", "b"], plate_color="#00FF00", matte_pairs=True)
    assert len(out) == 2 and len(seen) == 2
    assert (tmp_path / "chain" / "0001.white.png").exists() and (tmp_path / "chain" / "0001.black.png").exists()
    assert Image.open(out[0]).getchannel("A").getextrema() == (128, 128)
    prompts = [c.args[1].lower() for c in provider.edit_image.call_args_list]
    assert "#ffffff" in prompts[0] and "#000000" in prompts[1]
    sidecar = json.loads((tmp_path / "chain" / "0001.png.json").read_text(encoding="utf-8"))
    assert sidecar["matte_pairs"] is True and len(sidecar["plates"]) == 2


def test_edit_chain_cancels_between_steps(tmp_path):
    provider = _google()
    provider.start_edit_session.return_value = True
    token = CancelToken()

    def first_then_cancel(*args, **kwargs):
        token.cancel()
        return ([], [png_bytes(w=16, h=16, squares=1)])

    provider.edit_image.side_effect = first_then_cancel
    with pytest.raises(Cancelled):
        edit_chain(provider, _character(tmp_path), _action(), tmp_path / "chain", frames=3,
                   pose_instructions=["a", "b", "c"], plate_color="#00FF00", token=token)
    assert sorted(p.name for p in (tmp_path / "chain").glob("*.png")) == ["0001.png"]
    provider.reset_edit_session.assert_called_once()


def test_edit_chain_length_mismatch(tmp_path):
    with pytest.raises(ValueError):
        edit_chain(_google(), _character(tmp_path), _action(), tmp_path / "chain", frames=3,
                   pose_instructions=["a"], plate_color="#00FF00")


def test_edit_chain_session_failure_is_logged_not_fatal(tmp_path):
    provider = _google()
    provider.start_edit_session.return_value = False
    provider.edit_image.side_effect = [([], [r]) for r in _distinct_replies(1)]
    logged = []
    out = edit_chain(provider, _character(tmp_path), _action(), tmp_path / "chain", frames=1,
                     pose_instructions=["a"], plate_color="#00FF00", log=logged.append)
    assert len(out) == 1 and any("session" in l for l in logged)
    provider.reset_edit_session.assert_not_called()
```

- [x] **Step 2: Run the tests to see them fail**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_image_route.py -v -k edit_chain` → `ImportError: cannot import name 'edit_chain'`.

- [x] **Step 3: Implement `edit_chain`**

Append to `core/sprite/generation/image_route.py`:

```python
# --------------------------------------------------------------------------- edit-chain route

MATTE_PLATES = ("#FFFFFF", "#000000")


def edit_chain(
    provider,
    character: Path,
    action: ActionCard,
    out_dir: Path,
    *,
    frames: int,
    pose_instructions: Sequence[str],
    plate_color: str,
    model: Optional[str] = None,
    log: LogFn = logger.info,
    token: Optional[CancelToken] = None,
    matte_pairs: bool = False,
) -> List[Path]:
    """Render ``frames`` PNGs where frame k is an edit of [character, frame k-1]."""
    if frames < 1:
        raise ValueError("frames must be >= 1")
    if len(pose_instructions) != frames:
        raise ValueError(f"pose_instructions has {len(pose_instructions)} entries; expected {frames}")
    character = Path(character)
    if not character.exists():
        raise FileNotFoundError(character)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    kind = provider_kind(provider)
    model = model or (default_openai_edit_model() if kind == "openai" else provider.get_default_model())
    character_bytes = character.read_bytes()
    with Image.open(character) as img:
        char_size: Size = img.size
    session_started = False
    if kind == "google":
        session_started = bool(provider.start_edit_session(
            character_bytes, style_context="sprite animation frames; keep the exact character", model=model))
        if not session_started:
            log("[image route] edit session did not start; continuing with single-shot edits")
            logger.warning("[image route] start_edit_session returned False")
    plates = list(MATTE_PLATES) if matte_pairs else [plate_color]
    outputs: List[Path] = []
    prev_bytes = character_bytes
    try:
        for k, instruction in enumerate(pose_instructions, start=1):
            if token is not None:
                token.raise_if_cancelled()
            what = f"edit-chain step {k}/{frames}"
            out_png = out_dir / f"{k:04d}.png"
            step_images: Dict[str, bytes] = {}
            prompts: Dict[str, str] = {}
            for color in plates:
                prompt = inject_chroma(STEP_PROMPT.format(instruction=instruction.strip()), color, loop=False)
                prompts[color] = prompt
                params: Dict = {"step": k, "plate": color}
                refs = [character_bytes, prev_bytes]
                if kind == "openai":
                    size = openai_edit_size(model, char_size)
                    params["size"] = size
                    log_request(log, what=what, provider=kind, model=model, prompt=prompt, params=params)
                    texts, images = call_provider(provider, "edit_image", refs, prompt, what=what,
                                                  model=model, size=size, n=1)
                else:
                    log_request(log, what=what, provider=kind, model=model, prompt=prompt, params=params)
                    texts, images = call_provider(provider, "edit_image", refs, prompt, what=what, model=model)
                log_response(log, what=what, texts=texts, images=images)
                step_images[color] = first_image(texts, images, what=what)
            plate_paths: List[str] = []
            if matte_pairs:
                from core.sprite.matting import difference_matte
                white = save_png(step_images[MATTE_PLATES[0]], out_dir / f"{k:04d}.white.png")
                black = save_png(step_images[MATTE_PLATES[1]], out_dir / f"{k:04d}.black.png")
                with Image.open(white) as w_img, Image.open(black) as b_img:
                    matted = difference_matte(w_img.convert("RGB"), b_img.convert("RGB"))
                matted.convert("RGBA").save(out_png, "PNG")
                plate_paths = [str(white), str(black)]
                next_bytes = step_images[MATTE_PLATES[0]]
            else:
                save_png(step_images[plate_color], out_png)
                next_bytes = step_images[plate_color]
            write_image_sidecar(out_png, {
                "prompt": prompts[plates[0]], "prompts": prompts, "provider": kind, "model": model,
                "timestamp": _timestamp(), "route": "image_edit_chain",
                "action": action.name, "action_id": action.id, "step": k, "of": frames,
                "pose": instruction, "plate_color": plate_color, "matte_pairs": matte_pairs,
                "plates": plate_paths,
                "reference_images": [str(character), str(outputs[-1]) if outputs else str(character)],
            })
            outputs.append(out_png)
            prev_bytes = next_bytes
            log(f"[image route] step {k}/{frames} saved: {out_png}")
    finally:
        if kind == "google" and session_started:
            provider.reset_edit_session()
    return outputs
```

- [x] **Step 4: Run the tests to see them pass**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_image_route.py -v` → 19 passed.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/image_route.py tests/sprite/test_image_route.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): image route edit-chain with optional white/black difference-matte pairs"
```

---

### Task 8: Retouch core

**Files:**
- Create: `core/sprite/generation/retouch.py`
- Test: `tests/sprite/test_retouch.py`

**Interfaces:**
- Consumes: `GoogleProvider.edit_image_region(image: bytes, region_bbox, prompt, model=None, ...)` (`providers/google.py:1907-2014`); `GoogleProvider.edit_image` list input; `OpenAIProvider.edit_image(..., mask=bytes, size=...)` (`providers/openai.py:821-940`, mask semantics: alpha 0 = editable, per `_create_alpha_mask` `:1070-1122`); validation pattern from `core/character_animator/ai_face_editor.py:561-617`; helpers from Task 6/7 (`provider_kind`, `call_provider`, `first_image`, `log_request`, `log_response`, `openai_edit_size`, `default_openai_edit_model`); `ProviderError`; `write_image_sidecar`.
- Produces: `next_retouch_path(frame: Path) -> Path`; `build_region_mask(size: Size, region: Rect, feather: int = 5) -> bytes`; `fit_to_size(image, size) -> Image`; `validate_retouch(original, edited, region) -> Tuple[bool, str]`; `retouch_prompt(instruction, *, neighbors: int) -> str`; `retouch_frame(provider, frame: Path, instruction: str, out_png: Optional[Path] = None, *, neighbors: Sequence[Path] = (), region: Optional[Rect] = None, model=None, log=logger.info, attempts: int = 2) -> Path`.

- [x] **Step 1: Write the failing test**

Create `tests/sprite/test_retouch.py`:

```python
# tests/sprite/test_retouch.py
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

from core.sprite.generation.errors import ProviderError
from core.sprite.generation.retouch import (
    build_region_mask, fit_to_size, next_retouch_path, retouch_frame, validate_retouch,
)
from providers.google import GoogleProvider
from providers.openai import MODEL_CAPS, OpenAIProvider


def _png(w=32, h=32, shade=100) -> bytes:
    arr = np.full((h, w, 4), (shade, shade, shade, 255), dtype=np.uint8)
    arr[8:24, 8:24] = (255, 0, 0, 255)
    buf = BytesIO()
    Image.fromarray(arr, "RGBA").save(buf, "PNG")
    return buf.getvalue()


def _frames(tmp_path: Path):
    paths = []
    for i in range(1, 4):
        p = tmp_path / f"{i:04d}.png"
        p.write_bytes(_png(shade=100))
        paths.append(p)
    return paths


def _google(reply: bytes):
    provider = MagicMock(spec=GoogleProvider)
    provider.get_default_model.return_value = "default-google-image-model"
    provider.edit_image.return_value = ([], [reply])
    provider.edit_image_region.return_value = ([], [reply])
    return provider


def _openai(reply: bytes):
    provider = MagicMock(spec=OpenAIProvider)
    provider.edit_image.return_value = ([], [reply])
    return provider


def test_next_retouch_path_never_collides(tmp_path):
    frame = tmp_path / "0003.png"
    frame.write_bytes(_png())
    first = next_retouch_path(frame)
    assert first.name == "0003.r1.png"
    first.write_bytes(_png())
    assert next_retouch_path(frame).name == "0003.r2.png"
    assert next_retouch_path(first).name == "0003.r2.png"     # retouch of a retouch keeps the base name


def test_google_whole_frame_uses_neighbors_as_references(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _google(_png(shade=180))
    out = retouch_frame(provider, f2, "fix the left hand", neighbors=[f1, f3])
    assert out == tmp_path / "0002.r1.png" and out.exists()
    assert f2.read_bytes() == _png(shade=100)                   # original untouched
    args, kwargs = provider.edit_image.call_args
    assert args[0] == [f2.read_bytes(), f1.read_bytes(), f3.read_bytes()]
    assert "fix the left hand" in args[1] and "neighboring" in args[1]
    assert kwargs["model"] == "default-google-image-model"
    provider.edit_image_region.assert_not_called()
    sidecar = json.loads((tmp_path / "0002.r1.png.json").read_text(encoding="utf-8"))
    assert sidecar["route"] == "retouch" and sidecar["source_frame"].endswith("0002.png")
    assert len(sidecar["reference_images"]) == 2 and sidecar["region"] is None


def test_google_region_uses_edit_image_region(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _google(_png(shade=180))
    retouch_frame(provider, f2, "add a glove", neighbors=[f1, f3], region=(8, 8, 16, 16))
    args, kwargs = provider.edit_image_region.call_args
    assert args[0] == f2.read_bytes() and args[1] == (8, 8, 16, 16) and "add a glove" in args[2]
    provider.edit_image.assert_not_called()


def test_openai_region_builds_alpha_mask(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _openai(_png(shade=180))
    model = next(m for m, c in MODEL_CAPS.items() if c["supports_mask"] and c["supports_multi_reference"])
    retouch_frame(provider, f2, "add a glove", neighbors=[f1], region=(8, 8, 16, 16), model=model)
    args, kwargs = provider.edit_image.call_args
    assert kwargs["model"] == model and kwargs["n"] == 1 and "size" in kwargs
    mask = Image.open(BytesIO(kwargs["mask"]))
    assert mask.size == (32, 32) and mask.mode == "RGBA"
    assert mask.getpixel((16, 16))[3] == 0            # inside region: editable
    assert mask.getpixel((0, 0))[3] == 255            # far outside: protected
    assert args[0] == [f2.read_bytes(), f1.read_bytes()]


def test_openai_without_region_sends_no_mask(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _openai(_png(shade=180))
    retouch_frame(provider, f2, "brighten the cape", neighbors=[])
    assert provider.edit_image.call_args.kwargs["mask"] is None


def test_build_region_mask_feathers_edge():
    mask = Image.open(BytesIO(build_region_mask((32, 32), (8, 8, 16, 16), feather=4)))
    assert mask.getpixel((7, 16))[3] < 255 and mask.getpixel((7, 16))[3] > 0
    assert mask.getpixel((2, 16))[3] == 255


def test_result_is_repadded_proportionally_when_size_differs(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _google(_png(w=64, h=32, shade=180))   # 2:1 reply for a 1:1 frame
    out = retouch_frame(provider, f2, "x")
    img = Image.open(out)
    assert img.size == (32, 32)
    alpha = np.asarray(img.getchannel("A"))
    assert alpha[0, 16] == 0 and alpha[31, 16] == 0 and alpha[16, 16] == 255   # letterboxed, not stretched


def test_fit_to_size_upscales_small_result():
    small = Image.new("RGBA", (16, 8), (1, 2, 3, 255))
    fitted = fit_to_size(small, (64, 64))
    assert fitted.size == (64, 64)
    assert fitted.getpixel((32, 32))[3] == 255 and fitted.getpixel((32, 2))[3] == 0


def test_validate_retouch_detects_unchanged():
    a = Image.open(BytesIO(_png(shade=100)))
    assert validate_retouch(a, a.copy(), None)[0] is False
    assert validate_retouch(a, Image.open(BytesIO(_png(shade=180))), (0, 0, 8, 8))[0] is True


def test_unchanged_result_retries_then_raises(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _google(_png(shade=100))               # identical to the source
    with pytest.raises(ProviderError):
        retouch_frame(provider, f2, "x", attempts=2)
    assert provider.edit_image.call_count == 2
    assert not (tmp_path / "0002.r1.png").exists()


def test_never_overwrites_existing_output(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    (tmp_path / "custom.png").write_bytes(_png())
    with pytest.raises(FileExistsError):
        retouch_frame(_google(_png(shade=180)), f2, "x", tmp_path / "custom.png")


def test_logs_request_and_response(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    lines = []
    retouch_frame(_google(_png(shade=180)), f2, "x", log=lines.append)
    assert any("request" in l and "prompt:" in l for l in lines)
    assert any("response" in l for l in lines) and any("validation" in l for l in lines)
```

- [x] **Step 2: Run the test to see it fail**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_retouch.py -v` → `ModuleNotFoundError`.

- [x] **Step 3: Implement the module**

Create `core/sprite/generation/retouch.py`:

```python
"""AI retouch of one sprite frame (Gemini or gpt-image) — non-destructive.

The output is a new file ``NNNN.r<k>.png`` beside the original; the original
is never overwritten, so undo is a pointer swap (design §1.4).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from core.sprite.generation.errors import ProviderError
from core.sprite.generation.image_route import (
    call_provider, default_openai_edit_model, first_image, log_request, log_response,
    openai_edit_size, provider_kind,
)
from core.sprite.models import Rect, Size
from core.utils import write_image_sidecar

logger = logging.getLogger(__name__)
LogFn = Callable[[str], None]

_RETOUCH_SUFFIX = re.compile(r"\.r(\d+)$")
MIN_CHANGE_MEAN_DIFF = 1.0     # same threshold as ai_face_editor._validate_edit


def next_retouch_path(frame: Path) -> Path:
    """``0003.png`` -> ``0003.r1.png`` (or the next free k); a retouch of a retouch keeps the base name."""
    frame = Path(frame)
    base = _RETOUCH_SUFFIX.sub("", frame.stem)
    k = 1
    while True:
        candidate = frame.with_name(f"{base}.r{k}{frame.suffix}")
        if not candidate.exists():
            return candidate
        k += 1


def build_region_mask(size: Size, region: Rect, feather: int = 5) -> bytes:
    """OpenAI edit mask: alpha 0 inside ``region`` (editable), 255 outside, feathered edge."""
    w, h = int(size[0]), int(size[1])
    x, y, rw, rh = region
    ys, xs = np.mgrid[0:h, 0:w]
    dx = np.maximum(0, np.maximum(x - xs, xs - (x + rw - 1)))
    dy = np.maximum(0, np.maximum(y - ys, ys - (y + rh - 1)))
    dist = np.sqrt(dx.astype(np.float32) ** 2 + dy.astype(np.float32) ** 2)
    if feather > 0:
        alpha = np.clip(dist / float(feather), 0.0, 1.0) * 255.0
    else:
        alpha = (dist > 0).astype(np.float32) * 255.0
    mask = np.zeros((h, w, 4), dtype=np.uint8)
    mask[..., 3] = alpha.astype(np.uint8)
    buf = BytesIO()
    Image.fromarray(mask, "RGBA").save(buf, "PNG")
    return buf.getvalue()


def fit_to_size(image: Image.Image, size: Size) -> Image.Image:
    """Return ``image`` at exactly ``size``: scaled proportionally and padded on a transparent canvas."""
    target = (int(size[0]), int(size[1]))
    image = image.convert("RGBA")
    if image.size == target:
        return image
    scale = min(target[0] / image.width, target[1] / image.height)
    new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.resize(new_size, Image.LANCZOS)
    canvas = Image.new("RGBA", target, (0, 0, 0, 0))
    canvas.paste(resized, ((target[0] - new_size[0]) // 2, (target[1] - new_size[1]) // 2))
    return canvas


def validate_retouch(original: Image.Image, edited: Image.Image, region: Optional[Rect]) -> Tuple[bool, str]:
    """The edited area must differ from the original (pattern: ai_face_editor._validate_edit)."""
    if region is None:
        box = (0, 0, original.width, original.height)
    else:
        x, y, w, h = region
        box = (x, y, x + w, y + h)
    a = np.asarray(original.convert("RGB").crop(box), dtype=np.float32)
    b = np.asarray(edited.convert("RGB").crop(box), dtype=np.float32)
    if a.shape != b.shape:
        return False, f"size mismatch {a.shape} vs {b.shape}"
    mean = float(np.mean(np.abs(a - b)))
    if mean < MIN_CHANGE_MEAN_DIFF:
        return False, f"edit region unchanged (mean diff {mean:.2f})"
    return True, f"mean diff {mean:.2f}"


def retouch_prompt(instruction: str, *, neighbors: int) -> str:
    parts = [instruction.strip().rstrip(".") + "."]
    if neighbors:
        parts.append(f"The other {neighbors} image(s) are the neighboring animation frames; "
                     "keep the character identical to them.")
    parts.append("Keep the same background color, framing, scale, and character position. Do not change anything else.")
    return " ".join(parts)


def retouch_frame(
    provider,
    frame: Path,
    instruction: str,
    out_png: Optional[Path] = None,
    *,
    neighbors: Sequence[Path] = (),
    region: Optional[Rect] = None,
    model: Optional[str] = None,
    log: LogFn = logger.info,
    attempts: int = 2,
) -> Path:
    """Retouch one frame; write ``NNNN.r<k>.png`` beside it (never overwrite) and return that path."""
    frame = Path(frame)
    if not frame.exists():
        raise FileNotFoundError(frame)
    if not instruction.strip():
        raise ValueError("instruction is empty")
    out = Path(out_png) if out_png else next_retouch_path(frame)
    if out.exists():
        raise FileExistsError(f"retouch output exists; never overwrite: {out}")
    kind = provider_kind(provider)
    model = model or (default_openai_edit_model() if kind == "openai" else provider.get_default_model())
    with Image.open(frame) as src:
        original = src.convert("RGBA")
    size: Size = original.size
    frame_bytes = frame.read_bytes()
    neighbor_paths = [Path(n) for n in neighbors if Path(n).exists()]
    neighbor_bytes = [p.read_bytes() for p in neighbor_paths]
    prompt = retouch_prompt(instruction, neighbors=len(neighbor_paths))
    params: Dict = {"region": list(region) if region else None, "neighbors": [str(p) for p in neighbor_paths]}
    last_reason = ""
    for attempt in range(1, attempts + 1):
        what = f"retouch {frame.name} attempt {attempt}/{attempts}"
        if kind == "google":
            log_request(log, what=what, provider=kind, model=model, prompt=prompt, params=params)
            if region is not None:
                texts, images = call_provider(provider, "edit_image_region", frame_bytes, tuple(region), prompt,
                                              what=what, model=model)
            else:
                texts, images = call_provider(provider, "edit_image", [frame_bytes, *neighbor_bytes], prompt,
                                              what=what, model=model)
        else:
            size_str = openai_edit_size(model, size)
            params["size"] = size_str
            mask = build_region_mask(size, region) if region is not None else None
            log_request(log, what=what, provider=kind, model=model, prompt=prompt, params=params)
            texts, images = call_provider(provider, "edit_image", [frame_bytes, *neighbor_bytes], prompt,
                                          what=what, model=model, mask=mask, size=size_str, n=1)
        log_response(log, what=what, texts=texts, images=images)
        data = first_image(texts, images, what=what)
        with Image.open(BytesIO(data)) as reply:
            edited = fit_to_size(reply, size)
        ok, last_reason = validate_retouch(original, edited, region)
        log(f"[retouch] validation: {last_reason}")
        if ok:
            out.parent.mkdir(parents=True, exist_ok=True)
            edited.save(out, "PNG")
            write_image_sidecar(out, {
                "prompt": prompt, "provider": kind, "model": model, "timestamp": datetime.now().isoformat(timespec="seconds"),
                "route": "retouch", "source_frame": str(frame), "instruction": instruction,
                "region": list(region) if region else None,
                "reference_images": [str(p) for p in neighbor_paths],
                "mask": "region alpha mask" if (kind == "openai" and region is not None) else None,
                "attempt": attempt,
            })
            log(f"[retouch] saved: {out}")
            return out
        logger.warning("[retouch] %s rejected: %s", what, last_reason)
    message = (f"Retouch produced no visible change after {attempts} attempt(s) ({last_reason}). "
               "Use a more specific instruction or the other provider.")
    logger.error("[retouch] %s", message)
    log(f"[retouch] {message}")
    raise ProviderError(message)
```

- [x] **Step 4: Run the test to see it pass**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_retouch.py -v` → 12 passed.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/retouch.py tests/sprite/test_retouch.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): non-destructive AI frame retouch (region or whole frame, Gemini/gpt-image)"
```

---

### Task 9: Retouch dialog + frame-strip wiring

**Files:**
- Create: `gui/sprite/retouch_dialog.py`
- Create: `gui/sprite/retouch_wiring.py`
- Modify: `gui/sprite/sprite_tab.py` (5a) — one call `install_retouch(self)` at the end of `SpriteTab.__init__`
- Test: `tests/sprite/gui/test_retouch_dialog.py`

**Interfaces:**
- Consumes: `retouch_frame` (Task 8); `DialogCleanupMixin`, `bind_primary_action`, `set_default_button` (`gui/common/dialog_conventions.py:77-141`); `DialogStatusConsole` (`gui/llm_utils.py:15-86`); `SpriteWorker(job, *, label="job", parent=None)` with `progress/finished/failed/cancelled` (5a); `SpriteTab.make_provider(name) -> ImageProvider` (5a; raises `ValueError` with a user-facing message when the key is missing — called inside the worker job so it surfaces through `failed(str)`); `ActionCard`; 5b `FrameStrip.retouchRequested(int)`, `PixelView.selection_rect() -> Optional[Rect]`, `FramesWorkspace.apply_frames(action_id, frames, label)` (snapshot + set frames + refresh); tab attributes `frame_strip`, `pixel_view`, `frames_workspace`, `current_action()`, `current_project`, `console`.
- Produces: `RetouchDialog(DialogCleanupMixin, QDialog)` with `retouched = Signal(object)`, `logLine = Signal(str)`, `build_job()`, `start_retouch()`, `cancel_retouch()`, `clear_region()`, `result_path`; `install_retouch(tab) -> None`; `open_retouch_dialog(tab, index, *, exec_dialog=True) -> Optional[RetouchDialog]`; `apply_retouch(tab, action, index, new_path) -> None`.

Mixin order is `(DialogCleanupMixin, QDialog)` — the mixin's `done()`/`closeEvent()` must precede `QDialog` in the MRO (docstring at `gui/common/dialog_conventions.py:103-141`). Console writes from the worker thread go through the `logLine` signal (queued connection), never directly.

- [x] **Step 1: Write the failing test**

Create `tests/sprite/gui/test_retouch_dialog.py`:

```python
# tests/sprite/gui/test_retouch_dialog.py
import copy
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("PySide6")
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from core.sprite.models import FrameMeta
from core.sprite.pipeline import CancelToken, no_progress
from core.sprite.project import ActionCard
from gui.sprite import retouch_dialog as rd
from gui.sprite.retouch_dialog import RetouchDialog
from gui.sprite.retouch_wiring import apply_retouch, install_retouch, open_retouch_dialog
from gui.sprite.workers import SpriteWorker


def _png(path: Path, shade=100) -> Path:
    arr = np.full((16, 16, 4), (shade, shade, shade, 255), dtype=np.uint8)
    Image.fromarray(arr, "RGBA").save(path)
    return path


def _frames(tmp_path):
    return [_png(tmp_path / f"{i:04d}.png") for i in range(1, 4)]


def _dialog(tmp_path, region=None):
    f1, f2, f3 = _frames(tmp_path)
    factory_calls = []

    def factory(name):
        factory_calls.append(name)
        return object()

    dialog = RetouchDialog(f2, [f1, f3], provider_factory=factory, region=region)
    return dialog, factory_calls


def test_dialog_builds_with_console_region_and_shortcut(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path, region=(2, 2, 8, 8))
    assert dialog.console is not None and dialog.region == (2, 2, 8, 8)
    assert "x=2" in dialog.region_label.text() and dialog.clear_region_btn.isEnabled()
    assert [dialog.provider_combo.itemData(i) for i in range(dialog.provider_combo.count())] == ["google", "openai"]
    dialog.clear_region()
    assert dialog.region is None and not dialog.clear_region_btn.isEnabled()


def test_build_job_passes_dialog_values_to_retouch_frame(qapp, tmp_path, monkeypatch):
    dialog, factory_calls = _dialog(tmp_path, region=(1, 1, 4, 4))
    seen = {}

    def fake_retouch(provider, frame, instruction, out_png=None, **kwargs):
        seen.update(kwargs, frame=frame, instruction=instruction)
        return tmp_path / "0002.r1.png"

    monkeypatch.setattr(rd, "retouch_frame", fake_retouch)
    dialog.instruction.setPlainText("fix the hand")
    dialog.provider_combo.setCurrentIndex(1)
    dialog.model_edit.setText("some-model")
    result = dialog.build_job()(no_progress, CancelToken())
    assert result == tmp_path / "0002.r1.png"
    assert factory_calls == ["openai"]
    assert seen["frame"].name == "0002.png" and seen["instruction"] == "fix the hand"
    assert [p.name for p in seen["neighbors"]] == ["0001.png", "0003.png"]
    assert seen["region"] == (1, 1, 4, 4) and seen["model"] == "some-model"


def test_start_retouch_runs_worker_and_emits(qapp, tmp_path, monkeypatch):
    dialog, _ = _dialog(tmp_path)
    out = tmp_path / "0002.r1.png"
    monkeypatch.setattr(rd, "retouch_frame", lambda *a, **k: out)
    monkeypatch.setattr(SpriteWorker, "start", SpriteWorker.run)     # synchronous in-test
    got = []
    dialog.retouched.connect(lambda p: got.append(Path(p)))
    dialog.instruction.setPlainText("x")
    dialog.start_retouch()
    assert got == [out] and dialog.result_path == out
    assert dialog.run_btn.isEnabled() and not dialog.cancel_btn.isEnabled()
    assert "saved" in dialog.console.console.toPlainText().lower()


def test_failure_is_logged_to_console(qapp, tmp_path, monkeypatch):
    dialog, _ = _dialog(tmp_path)

    def boom(*a, **k):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(rd, "retouch_frame", boom)
    monkeypatch.setattr(SpriteWorker, "start", SpriteWorker.run)
    dialog.instruction.setPlainText("x")
    dialog.start_retouch()
    assert "exploded" in dialog.console.console.toPlainText()
    assert dialog.run_btn.isEnabled()


def test_empty_instruction_blocks_run(qapp, tmp_path, monkeypatch):
    dialog, _ = _dialog(tmp_path)
    monkeypatch.setattr(rd, "retouch_frame", lambda *a, **k: pytest.fail("must not run"))
    dialog.start_retouch()
    assert "instruction" in dialog.console.console.toPlainText().lower()


class _Strip(QObject):
    retouchRequested = Signal(int)


class _FakeTab(QWidget):
    """The SpriteTab surface that retouch_wiring touches (5a/5b names)."""

    def __init__(self, action, region=None):
        super().__init__()
        self.frame_strip = _Strip()
        self.pixel_view = SimpleNamespace(selection_rect=lambda: region)
        self.frames_workspace = SimpleNamespace(apply_frames=self._apply_frames)
        self._action = action
        self.current_project = SimpleNamespace(project_dir=None, save=lambda: None)
        self.console = SimpleNamespace(log=lambda *a, **k: None)
        self.applied = []
        self.providers = []

    def _apply_frames(self, action_id, frames, label):
        assert action_id == self._action.id
        self._action.frames = list(frames)
        self.applied.append(label)

    def current_action(self):
        return self._action

    def make_provider(self, name="google"):
        self.providers.append(name)
        return object()


def _action(tmp_path):
    frames = [FrameMeta(name=f"hero_walk_{i:02d}", source_path=p, frame=(0, 0, 16, 16))
              for i, p in enumerate(_frames(tmp_path), start=1)]
    return ActionCard(id="a1", name="walk", prompt="walks", frames=frames)


def test_apply_retouch_repoints_a_copy_through_workspace(qapp, tmp_path):
    action = _action(tmp_path)
    tab = _FakeTab(action)
    original_frame = action.frames[1]
    before = copy.deepcopy(original_frame)
    new_path = tmp_path / "0002.r1.png"
    apply_retouch(tab, action, 1, new_path)
    assert action.frames[1].source_path == new_path
    assert original_frame.source_path == before.source_path      # the old list is untouched for the snapshot
    assert tab.applied == ["retouch 2"]


def test_open_retouch_dialog_collects_neighbors_region_and_provider_factory(qapp, tmp_path):
    action = _action(tmp_path)
    tab = _FakeTab(action, region=(3, 3, 5, 5))
    dialog = open_retouch_dialog(tab, 2, exec_dialog=False)
    assert dialog.frame.name == "0003.png"
    assert [p.name for p in dialog.neighbors] == ["0002.png"]
    assert dialog.region == (3, 3, 5, 5)
    dialog._provider_factory("openai")
    assert tab.providers == ["openai"]
    assert open_retouch_dialog(tab, 7, exec_dialog=False) is None


def test_install_retouch_connects_signal(qapp, tmp_path, monkeypatch):
    tab = _FakeTab(_action(tmp_path))
    calls = []
    monkeypatch.setattr("gui.sprite.retouch_wiring.open_retouch_dialog", lambda t, i, **k: calls.append(i))
    install_retouch(tab)
    tab.frame_strip.retouchRequested.emit(1)
    assert calls == [1]
```

- [x] **Step 2: Run the test to see it fail**

`QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_retouch_dialog.py -v` → `ModuleNotFoundError: gui.sprite.retouch_dialog`.

- [x] **Step 3: Implement the dialog**

Create `gui/sprite/retouch_dialog.py`:

```python
"""Retouch dialog: one frame, one instruction, one provider call in a SpriteWorker."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from core.sprite.generation.retouch import retouch_frame
from core.sprite.models import Rect
from core.sprite.pipeline import CancelToken, ProgressFn
from gui.common.dialog_conventions import DialogCleanupMixin, bind_primary_action, set_default_button
from gui.llm_utils import DialogStatusConsole
from gui.sprite.workers import SpriteWorker

logger = logging.getLogger(__name__)

PROVIDERS = (("google", "Google Gemini"), ("openai", "OpenAI gpt-image"))


class RetouchDialog(DialogCleanupMixin, QDialog):
    """Ctrl+Enter runs the retouch; Escape closes. Never overwrites the source frame."""

    retouched = Signal(object)   # Path of the new frame file
    logLine = Signal(str)        # worker-thread log lines -> console (queued)

    def __init__(self, frame: Path, neighbors: Sequence[Path], *,
                 provider_factory: Callable[[str], object], region: Optional[Rect] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.frame = Path(frame)
        self.neighbors: List[Path] = [Path(n) for n in neighbors]
        self.region: Optional[Rect] = tuple(region) if region else None
        self._provider_factory = provider_factory
        self._worker: Optional[SpriteWorker] = None
        self.result_path: Optional[Path] = None
        self.setWindowTitle(f"Retouch {self.frame.name}")
        self._build_ui()
        self.logLine.connect(self.console.log)

    # ----------------------------------------------------------------- ui
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Vertical, self)
        top = QWidget()
        form = QFormLayout(top)
        self.instruction = QPlainTextEdit()
        self.instruction.setPlaceholderText("What to change in this frame, e.g. 'fix the left hand: five fingers, same glove'")
        form.addRow("Instruction:", self.instruction)
        self.provider_combo = QComboBox()
        for pid, label in PROVIDERS:
            self.provider_combo.addItem(label, pid)
        form.addRow("Provider:", self.provider_combo)
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("provider default")
        form.addRow("Model:", self.model_edit)
        region_row = QHBoxLayout()
        self.region_label = QLabel(self._region_text())
        self.clear_region_btn = QPushButton("Clear region")
        self.clear_region_btn.setEnabled(self.region is not None)
        self.clear_region_btn.clicked.connect(self.clear_region)
        region_row.addWidget(self.region_label, 1)
        region_row.addWidget(self.clear_region_btn)
        form.addRow("Region:", region_row)
        form.addRow("Neighbors:", QLabel(", ".join(p.name for p in self.neighbors) or "(none)"))
        splitter.addWidget(top)
        self.console = DialogStatusConsole("Status Console", self)
        splitter.addWidget(self.console)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.run_btn = QPushButton("Retouch (Ctrl+Enter)")
        self.run_btn.clicked.connect(self.start_retouch)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_retouch)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        for button in (self.run_btn, self.cancel_btn, self.close_btn):
            buttons.addWidget(button)
        root.addLayout(buttons)
        self._primary = bind_primary_action(self, self.start_retouch)
        set_default_button(self, self.run_btn, focus=False)
        self.instruction.setFocus()
        self.resize(560, 480)

    def _region_text(self) -> str:
        if self.region is None:
            return "whole frame"
        x, y, w, h = self.region
        return f"x={x} y={y} w={w} h={h}"

    def clear_region(self) -> None:
        self.region = None
        self.region_label.setText(self._region_text())
        self.clear_region_btn.setEnabled(False)

    # ----------------------------------------------------------------- job
    def build_job(self) -> Callable[[ProgressFn, CancelToken], Path]:
        instruction = self.instruction.toPlainText().strip()
        provider_id = self.provider_combo.currentData()
        model = self.model_edit.text().strip() or None
        frame, neighbors, region = self.frame, list(self.neighbors), self.region
        factory = self._provider_factory
        console_log = self.logLine.emit

        def job(progress: ProgressFn, token: CancelToken) -> Path:
            progress("retouch", 0, 1, f"Retouching {frame.name} with {provider_id}")
            token.raise_if_cancelled()
            provider = factory(provider_id)
            out = retouch_frame(provider, frame, instruction, neighbors=neighbors, region=region,
                                model=model, log=console_log)
            progress("retouch", 1, 1, f"Saved {out.name}")
            return out

        return job

    def start_retouch(self) -> None:
        if self._worker is not None:
            self.console.log("A retouch is already running.", "WARNING")
            return
        if not self.instruction.toPlainText().strip():
            logger.warning("retouch: empty instruction")
            self.console.log("Enter an instruction first.", "WARNING")
            return
        self._worker = SpriteWorker(self.build_job(), parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.console.log(f"Retouch started: {self.frame.name}")
        self._worker.start()

    def cancel_retouch(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.console.log("Cancel requested", "WARNING")

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        self.console.log(f"[{stage}] {message}")

    def _on_finished(self, result) -> None:
        self.result_path = Path(result)
        self.console.log(f"Retouch saved: {self.result_path}", "SUCCESS")
        self._finish_worker()
        self.retouched.emit(self.result_path)

    def _on_failed(self, message: str) -> None:
        logger.error("retouch failed: %s", message)
        self.console.log(f"Retouch failed: {message}", "ERROR")
        self._finish_worker()

    def _on_cancelled(self) -> None:
        logger.info("retouch cancelled: %s", self.frame.name)
        self.console.log("Retouch cancelled.", "WARNING")
        self._finish_worker()

    def _finish_worker(self) -> None:
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._worker = None

    def on_dialog_close(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(2000)
            self._worker = None
```

- [x] **Step 4: Implement the wiring**

Create `gui/sprite/retouch_wiring.py`:

```python
"""Connect FrameStrip.retouchRequested to the RetouchDialog and apply the result with undo."""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Optional

from core.sprite.project import ActionCard
from gui.sprite.retouch_dialog import RetouchDialog

logger = logging.getLogger(__name__)


def apply_retouch(tab, action: ActionCard, index: int, new_path: Path) -> None:
    """Repoint one frame in a copied list through FramesWorkspace.apply_frames (snapshot + set + refresh).

    The copy matters: apply_frames snapshots the current list for undo before it installs the new one.
    """
    frames = copy.deepcopy(action.frames)
    frames[index].source_path = Path(new_path)
    tab.frames_workspace.apply_frames(action.id, frames, f"retouch {index + 1}")
    project = tab.current_project
    if project is not None and getattr(project, "project_dir", None) is not None:
        project.save()
    tab.console.log(f"Frame {index + 1} retouched -> {Path(new_path).name}", "SUCCESS")
    logger.info("retouch applied: action=%s frame=%d -> %s", action.name, index + 1, new_path)


def open_retouch_dialog(tab, index: int, *, exec_dialog: bool = True) -> Optional[RetouchDialog]:
    action = tab.current_action()
    if action is None or not (0 <= index < len(action.frames)) or action.frames[index].source_path is None:
        logger.warning("retouch: no frame at index %s", index)
        tab.console.log("Retouch: select a frame first.", "WARNING")
        return None
    frames = action.frames
    neighbors = [frames[i].source_path for i in (index - 1, index + 1)
                 if 0 <= i < len(frames) and frames[i].source_path is not None]
    region = tab.pixel_view.selection_rect()
    dialog = RetouchDialog(frames[index].source_path, neighbors, provider_factory=tab.make_provider,
                           region=region, parent=tab)
    dialog.retouched.connect(lambda path, a=action, i=index: apply_retouch(tab, a, i, Path(path)))
    if exec_dialog:
        dialog.exec()
    return dialog


def install_retouch(tab) -> None:
    """Call once from SpriteTab.__init__."""
    tab.frame_strip.retouchRequested.connect(lambda index: open_retouch_dialog(tab, index))
```

- [x] **Step 5: Wire the tab (5a file)**

Modify `gui/sprite/sprite_tab.py`: add `from gui.sprite.retouch_wiring import install_retouch` and, as the last statement of `SpriteTab.__init__` (after 5b's `FramesWorkspace` has set `frame_strip` / `pixel_view` / `frames_workspace` on the tab), `install_retouch(self)`. The region comes from 5b's `PixelView.selection_rect()`; sub-project 6 adds no selection UI.

- [x] **Step 6: Run the tests to see them pass**

`QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui -v` → 9 new tests pass; the 5a/5b tab, strip, and pixel-view tests still pass.

- [x] **Step 7: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/retouch_dialog.py gui/sprite/retouch_wiring.py gui/sprite/sprite_tab.py tests/sprite/gui/test_retouch_dialog.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): Retouch dialog (status console, Ctrl+Enter, SpriteWorker) wired to the frame strip with undo"
```

---

### Task 10: Action-cards "Render (image)" button + ImageRouteDialog

**Files:**
- Create: `gui/sprite/image_route_dialog.py`
- Modify: `gui/sprite/sprite_tab.py` — one call `install_image_route(self)` at the end of `SpriteTab.__init__`
- Test: `tests/sprite/gui/test_image_route_dialog.py`

**Interfaces:**
- Consumes: `generate_sheet`, `slice_generated_sheet`, `edit_chain`, `generate_pose_instructions`, `default_openai_edit_model` (Tasks 5-7); `run_pipeline(project, action, *, upto, progress, token)`, `stage_dir(project, action, stage)`, `CancelToken`, `ProgressFn`; `record_actual(project, action, usd, note="", *, provider, model, seconds, estimated_usd)` (sub-project 2); `FrameMeta`, `ActionCard`, `SpriteProject`; `SpriteWorker` (+ `cancelled`); 5a `ActionCardsPanel.add_card_action(label, callback)`, `ActionCardsPanel.llm_provider() -> str`, `ActionCardsPanel.refresh_status()`; `SpriteTab.{make_provider(name), config, console, action_cards_panel, current_project, current_action()}`; 5b `FramesWorkspace.apply_frames(action_id, frames, label)` via `tab.frames_workspace`; `config.get_api_key(provider)`, `config.get_auth_mode(provider)`.
- Produces: `ImageRouteDialog(DialogCleanupMixin, QDialog)` with `rendered = Signal(object)`, `logLine = Signal(str)`, `build_job()`, `start_render()`, `cancel_render()`, `generate_steps()`; `archive_existing_frames(extract_dir: Path) -> Optional[Path]`; `install_image_route(tab) -> None`; `open_image_route_dialog(tab, action, *, exec_dialog=True) -> Optional[ImageRouteDialog]`.

The dialog calls providers and an LLM, so it carries a `DialogStatusConsole` at the bottom (splitter), Ctrl+Enter = Render, Escape = close. The job writes frames into `stage_dir(project, action, "extract")` with `action.clip = None` (the G9 pre-extracted entry point), records a ledger row, then runs `run_pipeline(upto="stabilize")` like the video queue.

- [x] **Step 1: Write the failing test**

Create `tests/sprite/gui/test_image_route_dialog.py`:

```python
# tests/sprite/gui/test_image_route_dialog.py
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QWidget

from core.sprite.models import FrameMeta
from core.sprite.pipeline import CancelToken, no_progress
from core.sprite.project import ActionCard, SpriteProject
from gui.sprite import image_route_dialog as ird
from gui.sprite.image_route_dialog import ImageRouteDialog, archive_existing_frames, install_image_route
from gui.sprite.workers import SpriteWorker


def _png(path: Path) -> Path:
    Image.fromarray(np.zeros((16, 16, 4), dtype=np.uint8), "RGBA").save(path)
    return path


def _project(tmp_path):
    project = MagicMock(spec=SpriteProject)
    project.name = "hero"
    project.project_dir = tmp_path
    project.plate_path = None
    project.character_source = _png(tmp_path / "character.png")
    project.plate_color = "#00FF00"
    return project


def _action():
    return ActionCard(id="a1", name="walk", prompt="walks", duration_s=4, loop=True, target_frames=3, fps=12)


def _patch_core(monkeypatch, tmp_path, produced):
    extract_dir = tmp_path / "stages" / "a1" / "extracted"
    monkeypatch.setattr(ird, "stage_dir", lambda project, action, stage: extract_dir)
    monkeypatch.setattr(ird, "generate_sheet", lambda *a, **k: tmp_path / "sheet.png")
    monkeypatch.setattr(ird, "slice_generated_sheet", lambda *a, **k: produced)
    monkeypatch.setattr(ird, "edit_chain", MagicMock(return_value=produced))
    monkeypatch.setattr(ird, "run_pipeline", MagicMock(return_value={}))
    monkeypatch.setattr(ird, "record_actual", MagicMock())
    return extract_dir


def _fake_provider(name="google"):
    return SimpleNamespace(get_default_model=lambda: "default-image-model")


def _dialog(tmp_path, pose_fn=None):
    return ImageRouteDialog(_project(tmp_path), _action(), provider_factory=_fake_provider,
                            pose_fn=pose_fn or (lambda action, frames, log: [f"pose {k}" for k in range(1, frames + 1)]))


def test_dialog_defaults_and_mode_toggle(qapp, tmp_path):
    dialog = _dialog(tmp_path)
    assert dialog.frames_spin.value() == 3
    assert [dialog.mode_combo.itemData(i) for i in range(dialog.mode_combo.count())] == ["sheet", "edit_chain"]
    assert not dialog.matte_check.isEnabled() and not dialog.steps_edit.isEnabled()
    dialog.mode_combo.setCurrentIndex(1)
    assert dialog.matte_check.isEnabled() and dialog.steps_edit.isEnabled()
    assert dialog.console is not None


def test_sheet_job_fills_frames_and_runs_pipeline(qapp, tmp_path, monkeypatch):
    produced = [_png(tmp_path / f"{k:04d}.png") for k in (1, 2, 3)]
    _patch_core(monkeypatch, tmp_path, produced)
    dialog = _dialog(tmp_path)
    result = dialog.build_job()(no_progress, CancelToken())
    action = dialog.action
    assert result == produced
    assert [f.source_path for f in action.frames] == produced
    assert action.frames[0].duration_ms == round(1000 / 12)
    assert action.clip is None and action.status == "processed"
    ird.run_pipeline.assert_called_once()
    assert ird.run_pipeline.call_args.kwargs["upto"] == "stabilize"
    ird.record_actual.assert_called_once()
    ledger_kwargs = ird.record_actual.call_args.kwargs
    assert "image route sheet" in ledger_kwargs["note"]
    assert ledger_kwargs["provider"] == "google" and ledger_kwargs["model"] == "default-image-model"
    assert ledger_kwargs["seconds"] == 3.0                     # unit count = frames for the sheet route
    dialog.project.save.assert_called_once()


def test_edit_chain_job_uses_typed_steps_when_count_matches(qapp, tmp_path, monkeypatch):
    produced = [_png(tmp_path / f"{k:04d}.png") for k in (1, 2, 3)]
    _patch_core(monkeypatch, tmp_path, produced)
    pose_calls = []
    dialog = _dialog(tmp_path, pose_fn=lambda a, n, log: pose_calls.append(n) or ["x"] * n)
    dialog.mode_combo.setCurrentIndex(1)
    dialog.matte_check.setChecked(True)
    dialog.steps_edit.setPlainText("one\ntwo\nthree")
    dialog.build_job()(no_progress, CancelToken())
    assert pose_calls == []
    kwargs = ird.edit_chain.call_args.kwargs
    assert kwargs["pose_instructions"] == ["one", "two", "three"] and kwargs["matte_pairs"] is True
    assert kwargs["frames"] == 3 and kwargs["plate_color"] == "#00FF00"


def test_edit_chain_job_asks_llm_when_steps_missing(qapp, tmp_path, monkeypatch):
    produced = [_png(tmp_path / f"{k:04d}.png") for k in (1, 2, 3)]
    _patch_core(monkeypatch, tmp_path, produced)
    pose_calls = []
    dialog = _dialog(tmp_path, pose_fn=lambda a, n, log: pose_calls.append(n) or [f"p{k}" for k in range(n)])
    dialog.mode_combo.setCurrentIndex(1)
    dialog.build_job()(no_progress, CancelToken())
    assert pose_calls == [3]
    assert ird.edit_chain.call_args.kwargs["pose_instructions"] == ["p0", "p1", "p2"]


def test_generate_steps_button_fills_editor(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(SpriteWorker, "start", SpriteWorker.run)
    dialog = _dialog(tmp_path)
    dialog.mode_combo.setCurrentIndex(1)
    dialog.generate_steps()
    assert dialog.steps_edit.toPlainText().splitlines() == ["pose 1", "pose 2", "pose 3"]


def test_start_render_emits_rendered(qapp, tmp_path, monkeypatch):
    produced = [_png(tmp_path / f"{k:04d}.png") for k in (1, 2, 3)]
    _patch_core(monkeypatch, tmp_path, produced)
    monkeypatch.setattr(SpriteWorker, "start", SpriteWorker.run)
    dialog = _dialog(tmp_path)
    got = []
    dialog.rendered.connect(lambda paths: got.append(list(paths)))
    dialog.start_render()
    assert got == [produced] and dialog.render_btn.isEnabled()
    assert "3 frame" in dialog.console.console.toPlainText()


def test_missing_character_fails_cleanly(qapp, tmp_path, monkeypatch):
    produced = []
    _patch_core(monkeypatch, tmp_path, produced)
    monkeypatch.setattr(SpriteWorker, "start", SpriteWorker.run)
    dialog = _dialog(tmp_path)
    dialog.project.character_source = tmp_path / "missing.png"
    dialog.start_render()
    assert "character" in dialog.console.console.toPlainText().lower()
    assert dialog.render_btn.isEnabled()


def test_archive_existing_frames_moves_aside(tmp_path):
    extract = tmp_path / "extracted"
    extract.mkdir()
    _png(extract / "0001.png")
    archived = archive_existing_frames(extract)
    assert archived is not None and archived.parent == tmp_path and (archived / "0001.png").exists()
    assert not extract.exists()
    assert archive_existing_frames(tmp_path / "nope") is None


class _FakeConfig:
    """Mirror of 5a's FakeConfig: get/set/save/get_api_key/get_auth_mode."""

    def __init__(self):
        self.store = {}

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value):
        self.store[key] = value

    def save(self):
        return True

    def get_api_key(self, provider):
        return "test-key"

    def get_auth_mode(self, provider="google"):
        return "api-key"


class _FakeTab(QWidget):
    """The SpriteTab surface that image_route_dialog touches (5a/5b names)."""

    def __init__(self, tmp_path, action=None):
        super().__init__()
        self.actions = {}
        self.action_cards_panel = SimpleNamespace(
            add_card_action=lambda label, cb: self.actions.__setitem__(label, cb),
            llm_provider=lambda: "google",
            refresh_status=lambda: None)
        self.config = _FakeConfig()
        self.console = SimpleNamespace(log=lambda *a, **k: None)
        self.current_project = _project(tmp_path)
        self._action = action
        self.applied = []
        self.providers = []
        self.frames_workspace = SimpleNamespace(apply_frames=self._apply_frames)

    def _apply_frames(self, action_id, frames, label):
        # Record what the real FramesWorkspace.apply_frames would snapshot (current list) and install (new list).
        self.applied.append((action_id, label, len(self._action.frames), len(frames)))
        self._action.frames = list(frames)

    def current_action(self):
        return self._action

    def make_provider(self, name="google"):
        self.providers.append(name)
        return _fake_provider(name)


def test_install_image_route_registers_button_and_builds_dialog(qapp, tmp_path):
    action = _action()
    tab = _FakeTab(tmp_path, action)
    install_image_route(tab)
    assert "Render (image)" in tab.actions
    dialog = ird.open_image_route_dialog(tab, action, exec_dialog=False)
    assert isinstance(dialog, ImageRouteDialog)
    assert dialog._provider_factory == tab.make_provider
    # Simulate a finished job: the worker wrote the new frames onto the action; the dialog kept the old list.
    dialog.frames_before = []
    action.frames = [FrameMeta(name="hero_walk_01", source_path=_png(tmp_path / "0001.png"), frame=(0, 0, 0, 0))]
    dialog.rendered.emit([])
    assert tab.applied == [("a1", "Render (image)", 0, 1)]   # snapshot sees the pre-render list, new list installed
    assert len(action.frames) == 1


def test_rendered_for_another_action_only_refreshes_status(qapp, tmp_path):
    other = ActionCard(id="zz", name="idle", prompt="stands", duration_s=2, loop=True, target_frames=2, fps=12)
    tab = _FakeTab(tmp_path, _action())
    dialog = ird.open_image_route_dialog(tab, other, exec_dialog=False)
    dialog.rendered.emit([])
    assert tab.applied == []


def test_pose_fn_uses_panel_provider_and_config(qapp, tmp_path, monkeypatch):
    seen = {}

    def fake_generate(action, frames, **kwargs):
        seen.update(kwargs, frames=frames)
        return ["p"] * frames

    monkeypatch.setattr(ird, "generate_pose_instructions", fake_generate)
    tab = _FakeTab(tmp_path, _action())
    steps = ird._make_pose_fn(tab)(_action(), 3, lambda _m: None)
    assert steps == ["p", "p", "p"]
    assert seen["provider"] == "google" and seen["api_key"] == "test-key" and seen["auth_mode"] == "api-key"
    assert seen["model"] is None


```

- [x] **Step 2: Run the test to see it fail**

`QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_image_route_dialog.py -v` → `ModuleNotFoundError`.

- [x] **Step 3: Implement the dialog and install hook**

Create `gui/sprite/image_route_dialog.py`:

```python
"""Render one action card through the image route (sheet or edit-chain) in a SpriteWorker."""
from __future__ import annotations

import copy
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLineEdit, QPlainTextEdit,
    QPushButton, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from core.sprite.generation.cost import record_actual
from core.sprite.generation.errors import ProviderError
from core.sprite.generation.image_route import (
    default_openai_edit_model, edit_chain, generate_pose_instructions, generate_sheet,
    slice_generated_sheet,
)
from core.sprite.models import FrameMeta
from core.sprite.pipeline import CancelToken, ProgressFn, run_pipeline, stage_dir
from core.sprite.project import ActionCard, SpriteProject
from gui.common.dialog_conventions import DialogCleanupMixin, bind_primary_action, set_default_button
from gui.llm_utils import DialogStatusConsole
from gui.sprite.workers import SpriteWorker

logger = logging.getLogger(__name__)

PROVIDERS = (("google", "Google Gemini"), ("openai", "OpenAI gpt-image"))
MODES = (("sheet", "Sheet (one image, sliced)"), ("edit_chain", "Edit chain (one edit per frame)"))
PoseFn = Callable[[ActionCard, int, Callable[[str], None]], List[str]]


def archive_existing_frames(extract_dir: Path) -> Optional[Path]:
    """Move a populated extract directory aside instead of deleting it; return the archive path."""
    extract_dir = Path(extract_dir)
    if not extract_dir.exists() or not any(extract_dir.iterdir()):
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = extract_dir.with_name(f"{extract_dir.name}.prev-{stamp}")
    extract_dir.rename(archive)
    logger.info("archived previous frames: %s -> %s", extract_dir, archive)
    return archive


class ImageRouteDialog(DialogCleanupMixin, QDialog):
    rendered = Signal(object)   # List[Path]
    logLine = Signal(str)

    def __init__(self, project: SpriteProject, action: ActionCard, *,
                 provider_factory: Callable[[str], object], pose_fn: PoseFn,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.project = project
        self.action = action
        self._provider_factory = provider_factory
        self._pose_fn = pose_fn
        self._worker: Optional[SpriteWorker] = None
        self.frames_before: List[FrameMeta] = []     # pre-render frame list; restored before apply_frames snapshots
        self.setWindowTitle(f"Render (image) — {action.name}")
        self._build_ui()
        self.logLine.connect(self.console.log)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Vertical, self)
        top = QWidget()
        form = QFormLayout(top)
        self.mode_combo = QComboBox()
        for mid, label in MODES:
            self.mode_combo.addItem(label, mid)
        form.addRow("Mode:", self.mode_combo)
        self.provider_combo = QComboBox()
        for pid, label in PROVIDERS:
            self.provider_combo.addItem(label, pid)
        form.addRow("Provider:", self.provider_combo)
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("provider default")
        form.addRow("Model:", self.model_edit)
        self.frames_spin = QSpinBox()
        self.frames_spin.setRange(2, 24)
        self.frames_spin.setValue(max(2, min(24, self.action.target_frames)))
        form.addRow("Frames:", self.frames_spin)
        self.matte_check = QCheckBox("Render white + black plates and difference-matte (2x cost)")
        form.addRow("", self.matte_check)
        steps_row = QHBoxLayout()
        self.steps_edit = QPlainTextEdit()
        self.steps_edit.setPlaceholderText("One pose per line (edit-chain). Leave empty to ask the LLM.")
        self.steps_btn = QPushButton("Generate pose steps")
        self.steps_btn.clicked.connect(self.generate_steps)
        steps_row.addWidget(self.steps_edit, 1)
        steps_row.addWidget(self.steps_btn)
        form.addRow("Pose steps:", steps_row)
        splitter.addWidget(top)
        self.console = DialogStatusConsole("Status Console", self)
        splitter.addWidget(self.console)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.render_btn = QPushButton("Render (Ctrl+Enter)")
        self.render_btn.clicked.connect(self.start_render)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_render)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        for button in (self.render_btn, self.cancel_btn, self.close_btn):
            buttons.addWidget(button)
        root.addLayout(buttons)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._on_mode_changed(0)
        self._primary = bind_primary_action(self, self.start_render)
        set_default_button(self, self.render_btn)
        self.resize(640, 560)

    def _on_mode_changed(self, _index: int) -> None:
        chain = self.mode_combo.currentData() == "edit_chain"
        self.matte_check.setEnabled(chain)
        self.steps_edit.setEnabled(chain)
        self.steps_btn.setEnabled(chain)

    # ----------------------------------------------------------------- jobs
    def _typed_steps(self) -> List[str]:
        return [line.strip() for line in self.steps_edit.toPlainText().splitlines() if line.strip()]

    def generate_steps(self) -> None:
        """Fill the pose-step editor from the LLM contract (runs in a worker)."""
        if self._worker is not None:
            self.console.log("A job is already running.", "WARNING")
            return
        action, frames, pose_fn, log = self.action, self.frames_spin.value(), self._pose_fn, self.logLine.emit

        def job(progress: ProgressFn, token: CancelToken) -> List[str]:
            progress("pose_steps", 0, 1, f"Asking the LLM for {frames} pose steps")
            token.raise_if_cancelled()
            return pose_fn(action, frames, log)

        self._worker = SpriteWorker(job, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_steps_ready)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._set_running(True)
        self._worker.start()

    def _on_steps_ready(self, steps) -> None:
        self.steps_edit.setPlainText("\n".join(steps))
        self.console.log(f"{len(steps)} pose steps ready; edit them, then Render.", "SUCCESS")
        self._set_running(False)

    def build_job(self) -> Callable[[ProgressFn, CancelToken], List[Path]]:
        mode = self.mode_combo.currentData()
        provider_id = self.provider_combo.currentData()
        model = self.model_edit.text().strip() or None
        frames = self.frames_spin.value()
        matte = self.matte_check.isChecked() and mode == "edit_chain"
        typed_steps = self._typed_steps()
        project, action = self.project, self.action
        factory, pose_fn, log = self._provider_factory, self._pose_fn, self.logLine.emit

        def job(progress: ProgressFn, token: CancelToken) -> List[Path]:
            character = project.plate_path or project.character_source
            if character is None or not Path(character).exists():
                raise ProviderError("Import a character image first (Character panel).")
            provider = factory(provider_id)
            model_used = model or (default_openai_edit_model() if provider_id == "openai"
                                   else provider.get_default_model())
            extract_dir = stage_dir(project, action, "extract")
            archived = archive_existing_frames(extract_dir)
            if archived is not None:
                log(f"[image route] previous frames kept at {archived}")
            if mode == "sheet":
                progress("image_route", 0, 3, "Generating sheet")
                sheet_png = Path(project.project_dir) / "clips" / f"{action.id}_sheet.png"
                sheet = generate_sheet(provider, Path(character), action, sheet_png, frames=frames,
                                       plate_color=project.plate_color, model=model, log=log, token=token)
                progress("image_route", 1, 3, "Slicing sheet")
                paths = slice_generated_sheet(sheet, extract_dir, frames, project.plate_color, log=log)
            else:
                steps = typed_steps
                if len(steps) != frames:
                    progress("image_route", 0, 3, f"Generating {frames} pose steps")
                    steps = pose_fn(action, frames, log)
                progress("image_route", 1, 3, f"Edit chain: {frames} steps")
                paths = edit_chain(provider, Path(character), action, extract_dir, frames=frames,
                                   pose_instructions=steps, plate_color=project.plate_color, model=model,
                                   log=log, token=token, matte_pairs=matte)
            progress("image_route", 2, 3, "Running pipeline to stabilize")
            duration_ms = round(1000 / max(1, action.fps))
            action.frames = [
                FrameMeta(name=f"{project.name}_{action.name}_{i:02d}", source_path=p, frame=(0, 0, 0, 0),
                          duration_ms=duration_ms)
                for i, p in enumerate(paths, start=1)
            ]
            action.clip = None
            action.status = "rendered"
            action.error = None
            edits = len(paths) * (2 if matte else 1)
            record_actual(project, action, None,
                          note=f"image route {mode}: {len(paths)} frame(s), {edits} edit(s)",
                          provider=provider_id, model=model_used, seconds=float(edits))
            run_pipeline(project, action, upto="stabilize", progress=progress, token=token)
            action.status = "processed"
            project.save()
            progress("image_route", 3, 3, f"{len(paths)} frame(s) ready")
            return paths

        return job

    def start_render(self) -> None:
        if self._worker is not None:
            self.console.log("A job is already running.", "WARNING")
            return
        self.frames_before = copy.deepcopy(self.action.frames)
        self._worker = SpriteWorker(self.build_job(), parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_rendered)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._set_running(True)
        self.console.log(f"Image route started: {self.action.name} ({self.mode_combo.currentData()})")
        self._worker.start()

    def cancel_render(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.console.log("Cancel requested", "WARNING")

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        self.console.log(f"[{stage}] {done}/{total} {message}")

    def _on_rendered(self, paths) -> None:
        paths = list(paths)
        self.console.log(f"Rendered {len(paths)} frame(s) for {self.action.name}", "SUCCESS")
        self._set_running(False)
        self.rendered.emit(paths)

    def _on_failed(self, message: str) -> None:
        logger.error("image route failed: %s", message)
        self.console.log(f"Failed: {message}", "ERROR")
        self._set_running(False)

    def _on_cancelled(self) -> None:
        logger.info("image route cancelled: %s", self.action.name)
        self.console.log("Cancelled.", "WARNING")
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        self.render_btn.setEnabled(not running)
        self.steps_btn.setEnabled(not running and self.mode_combo.currentData() == "edit_chain")
        self.cancel_btn.setEnabled(running)
        if not running:
            self._worker = None

    def on_dialog_close(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(2000)
            self._worker = None


# --------------------------------------------------------------------- tab wiring

def _make_pose_fn(tab) -> PoseFn:
    """Pose steps use the chat provider chosen in the action-cards panel; the model comes from the registry."""
    def pose_fn(action: ActionCard, frames: int, log: Callable[[str], None]) -> List[str]:
        provider = tab.action_cards_panel.llm_provider()
        auth_mode = tab.config.get_auth_mode(provider) if provider in ("google", "gemini") else None
        return generate_pose_instructions(action, frames, provider=provider, model=None,
                                          api_key=tab.config.get_api_key(provider), auth_mode=auth_mode, log=log)
    return pose_fn


def _on_rendered(tab, action: ActionCard, dialog: ImageRouteDialog) -> None:
    """Refresh the card status; reload strip + player when the rendered action is the current one.

    The job already wrote ``action.frames``. ``apply_frames`` snapshots the current list for
    undo before it installs the new one, so restore the pre-render list first and hand the
    rendered list over as the new one.
    """
    tab.action_cards_panel.refresh_status()
    current = tab.current_action()
    if current is not None and current.id == action.id:
        rendered = list(action.frames)
        action.frames = list(dialog.frames_before)
        tab.frames_workspace.apply_frames(action.id, rendered, "Render (image)")
    tab.console.log(f"Image route: '{action.name}' has {len(action.frames)} frame(s)", "SUCCESS")


def open_image_route_dialog(tab, action: ActionCard, *, exec_dialog: bool = True) -> Optional[ImageRouteDialog]:
    project = tab.current_project
    if project is None:
        logger.warning("image route: no project open")
        tab.console.log("Open or create a sprite project first.", "WARNING")
        return None
    dialog = ImageRouteDialog(project, action, provider_factory=tab.make_provider,
                              pose_fn=_make_pose_fn(tab), parent=tab)
    dialog.rendered.connect(lambda _paths, a=action, d=dialog: _on_rendered(tab, a, d))
    if exec_dialog:
        dialog.exec()
    return dialog


def install_image_route(tab) -> None:
    """Call once from SpriteTab.__init__: adds "Render (image)" to every action card row."""
    tab.action_cards_panel.add_card_action("Render (image)", lambda action: open_image_route_dialog(tab, action))
```

- [x] **Step 4: Wire the tab (5a file)**

Modify `gui/sprite/sprite_tab.py`: add `from gui.sprite.image_route_dialog import install_image_route` and `install_image_route(self)` right after `install_retouch(self)` at the end of `SpriteTab.__init__`. 5a's `ActionCardsPanel.add_card_action` renders the button on existing and future rows.

- [x] **Step 5: Run the tests to see them pass**

`QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui -v` → 11 new tests pass; `tests/sprite/gui/test_action_cards_panel.py` (5a) still passes.

- [x] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/image_route_dialog.py gui/sprite/sprite_tab.py tests/sprite/gui/test_image_route_dialog.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): Render (image) card action with sheet/edit-chain dialog, pose steps, and pipeline hand-off"
```

---

### Task 11: Full-suite run, guard tests, plan bookkeeping

**Files:**
- Modify: `Plans/2026-08-29-sprite-image-route-exports-plan.md` (tick the boxes)

- [x] **Step 1: Run the guard and the whole suite**

```bash
QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -q
QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite -q
QT_QPA_PLATFORM=offscreen $PY -m pytest -q
```

All three must be green. Record the final pass count in the commit body.

- [x] **Step 2: Grep for forbidden literals in the new runtime code**

```bash
grep -rnE "gpt-image-[0-9]|gemini-[0-9]|claude-[0-9]" /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/generation/image_route.py /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/generation/retouch.py /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/generation/pose_steps.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/image_route_dialog.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/retouch_dialog.py
```

The only permitted hit is the `MODEL_CAPS["gpt-image-1"]` fallback key inside `openai_sheet_size`/`openai_edit_size`, which mirrors `providers/openai.py:173` (`_caps_for`). Replace any other hit with a capability lookup.

- [x] **Step 3: Tick every checkbox in this plan and commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add Plans/2026-08-29-sprite-image-route-exports-plan.md
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "docs(plans): sprite sub-project 6 complete (image route, retouch, engine exports)"
```

No version bump here; sub-project 7 bumps once for the whole feature.

---

## Self-review

- **Spec coverage (design §4.6):** `sheet_prompt`, `generate_sheet`, `edit_chain`, `generate_pose_instructions` (Tasks 5-7); `retouch_frame` with Gemini region/whole-frame and OpenAI mask paths (Task 8); `export_godot_tres` with `region`, `margin`, `speed`, `loop`, per-frame `duration` (Task 1); `EnginePreset`/`ENGINE_PRESETS` for the eight named engines, `export_with_preset`, `fps_reconciliation` (Task 2); `export_aseprite` with header `0xA5E0`, frame `0xF1FA`, Layer `0x2004`, Cel `0x2005` type 2 zlib, Tags `0x2018`, Palette `0x2019` when quantized, Color Profile `0x2007` sRGB, and the byte-level reader test (Task 3). GUI: format registration + preset combo with `how_to_import` and reconciliation notes (Task 4); `FrameStrip.retouchRequested` → `RetouchDialog` with snapshot-before-repoint (Task 9); action-card "Render (image)" with a sheet | edit-chain mode combo (Task 10). Golden `tests/sprite/golden/godot.tres` with whitespace-normalized comparison (Task 1). Every artifact gets a sidecar; every provider call is logged in full; token checks happen per frame in `edit_chain` and before the single call in `generate_sheet`.
- **Placeholders:** none. Every code block is complete; every symbol used is defined in this plan, in the design, or in an existing repo file with a verified line range.
- **Consistency:** helper names `provider_kind`, `call_provider`, `first_image`, `save_png`, `log_request`, `log_response`, `openai_sheet_size`, `openai_edit_size`, `default_openai_edit_model` are defined once in Task 6 and reused in Tasks 7-8 with the same signatures. Output naming (`<title>.png`, `.atlas.json`, `.tres`, `.aseprite`, `<title>_<tag>.gif`, `frames/`) is identical in Task 2 and Task 4. Mixin order `(DialogCleanupMixin, QDialog)` is used in both dialogs.
- **Order check:** Task 2 imports Task 3's writer lazily inside `_write_aseprite_native`, so Task 2 tests pass before Task 3 exists; the "aseprite_native" format is exercised only from Task 3 onward.
- **Rules:** no model-ID literals in runtime code except the `MODEL_CAPS["gpt-image-1"]` fallback key that mirrors the provider's own `_caps_for`; no dimensions/aspects in prompt text (tests assert it); no hand-built data paths; no `cd`; no version bump.

## Deviations from the design

1. **`generate_pose_instructions` lives in `core/sprite/generation/pose_steps.py`** and is re-exported from `image_route.py`. The design lists it under `image_route.py`; the split keeps the LLM contract (prompt text, schema, parser, fallback) in one focused module. The import path `core.sprite.generation.image_route.generate_pose_instructions` still works.
2. **`retouch_frame(..., out_png: Optional[Path] = None, ...)`.** The design signature has a required `out_png`. Here it is optional: when omitted, the function writes `NNNN.r<k>.png` beside the source (design §1.4 naming) via `next_retouch_path`, and it raises `FileExistsError` if the target exists. The dialog never passes `out_png`.
3. **`edit_chain` continuity uses two references, not the chat session.** `GoogleProvider.edit_image` (`providers/google.py:1832-1905`) is single-shot and does not consult `_last_chat_session`; only `edit_image_region(use_conversation=True)` does. The chain therefore passes `[character, previous frame]` as the edit inputs on both providers, and calls `start_edit_session`/`reset_edit_session` around the loop for style context, as the design names them. Extra keyword `matte_pairs: bool = False` per the sub-project brief.
4. **`EnginePreset` gains `json_layout: str = "hash"`** (Unreal/Paper2D needs the TexturePacker "array" layout). Everything else matches the design dataclass.
5. **Godot direction handling:** `SpriteFrames` has no direction field, so `ordered_frame_indices` unrolls reverse/ping-pong tags into explicit frame lists; `fps_reconciliation(meta, "godot")` reports it.
6. **`generate_sheet` grows `token: Optional[CancelToken] = None`** (one check before the provider call) so the dialog cancel button also covers the sheet mode. `slice_generated_sheet` is a new public function; the design folds slicing into the same step.
7. **"Render (image)" opens a dialog** (`ImageRouteDialog`) that holds the sheet | edit-chain mode combo, provider/model/frames fields, an editable pose-step list, and the required status console, instead of a bare combo on the card row. The button label the brief asked for is kept.
8. **Sibling-plan names follow the orchestrator's 2026-08-29 decision** (see "Names assumed from sibling plans"): 5b's `register_format(id, label, fn(meta, out_dir), *, needs_sheet, takes_template, checked)` + `sheet_png_path`, `options_layout`, `set_grid_options`, `pivot_x_spin` / `pivot_y_spin`, `name_template_edit`, `current_meta()`, `FramesWorkspace.apply_frames(action_id, frames, label)`, `PixelView.selection_rect()`; 5a's `SpriteTab.make_provider(name)`, `current_action()`, `ActionCardsPanel.add_card_action` / `llm_provider()`; core's G9 pre-extracted entry (`run_pipeline` accepts a populated extract dir with `action.clip is None`); sub-project 2's `record_actual` keyword overrides. Sub-project 6 edits no 5a/5b file except two one-line calls in `sprite_tab.py` and two in `export_dialog.py`. If an implementer finds a name that still differs, change it in the single adapter that touches it (`retouch_wiring.py`, `image_route_dialog._on_rendered` / `_make_pose_fn` / `open_image_route_dialog`, `engine_preset_box.install_engine_presets`, `export_formats.py`) and in the fake dialog/tab objects in the GUI tests.
9. **Aseprite header "Number of colors"** is written as the palette length when `meta.palette` is set and `0` otherwise; Aseprite falls back to its default palette for RGBA files without a Palette chunk. The file is verified byte-for-byte by the reader test; a manual open in Aseprite is an optional non-gating step in Task 3.
10. **Format ids are one vocabulary** across `EnginePreset.formats`, the export dialog, and the CLI: `grid`, `aseprite_json`, `texturepacker_json`, `png_sequence`, `gif`, `godot_tres`, `aseprite_native` (the CLI plan's `aseprite` becomes `aseprite_native`; plan-cli was told). The dialog applies the preset pivot through its `pivot_x_spin` / `pivot_y_spin`; `export_with_preset` applies it through `with_pivot` for the CLI.
11. **`core/sprite/timing.py` belongs to sub-project 2**, not 1 (design §4.2); the dependency line at the top of this plan already lists 2.
12. **Undo goes through `FramesWorkspace.apply_frames(action_id, frames, label)`** for both retouch and image-route renders; sub-project 6 never pushes a snapshot itself. `apply_retouch` repoints a deep-copied frame list so the snapshot inside `apply_frames` captures the pre-retouch path. The image-route job writes `action.frames` inside the worker, so `ImageRouteDialog.start_render` keeps `frames_before` and `_on_rendered` restores it right before `apply_frames` installs the rendered list — otherwise the snapshot would hold the new frames and undo would be a no-op.
13. **Preset notes use 5b's `ExportDialog.notes_label`** (`EnginePresetBox(notes_label=...)`); the box creates its own label only when used standalone. The box is inserted at `options_layout` index 1 (after the profiles box, above the formats box).
14. **Matte plates live in `<out_dir>/plates`, not beside the frames** (final review 2026-08-30, Important 6). `edit_chain` first wrote `NNNN.white.png` and `NNNN.black.png` into `out_dir`, which the GUI sets to the pipeline's extract stage directory. `pipeline.list_frames` is an unfiltered `glob("*.png")`, so a 3-frame matte render produced 9 `action.frames` ordered `0001.black, 0001, 0001.white, …`: the raw plates played as animation frames and keying plus stabilize were paid three times. The plates now go into a `plates` subdirectory. `list_frames` is unchanged, because it is a sub-project 1 contract every stage depends on. Each plate keeps its own `.json` sidecar and the composed frame's sidecar lists both plate paths.
15. **Pose-step chat models resolve through `action_cards.default_chat_model`** (final review 2026-08-30, Important 3). `resolve_model(provider, "chat")` passed `"chat"` as the registry *family*, and no `gemini/chat` or `anthropic/chat` family exists, so the resolver logged a warning and returned the family name itself. Every pose-step call asked the provider for a model named `"chat"`. `default_chat_model` normalizes the provider alias, picks the per-provider family, and carries an offline static default. The model-ID literals stay in `action_cards._CHAT_FAMILY`, which is their sanctioned home.
16. **The Gemini region retouch sends no neighbour frames, and says so** (final review 2026-08-30, Important 4). `GoogleProvider.edit_image_region` accepts exactly one image, so that one branch cannot carry the neighbours. The prompt, the request params and the sidecar `reference_images` now derive from the neighbours actually sent, which is an empty list on that branch. Every other path still sends and still reports them. `core/utils.py` defines `reference_images` as the inputs to the edit, so the record must match what the provider received.
17. **Both new card-row entry points refuse while the processing panel is busy** (final review 2026-08-30, Important 7 and 8). "Render (image)" and frame-strip "Retouch…" are writers: they rename the extract stage directory aside, clear the clip, rewrite `action.frames` and run a second pipeline. No lock guards `SpriteProject`, so a second writer against a running pipeline let the last writer win, and on Windows the rename raised `PermissionError`. Both entry points now refuse in the shape `FramesWorkspace.open_export_dialog` already ships, and log plus show the refusal. `apply_retouch` also re-validates its frame index, because `QDialog.exec()` still delivers queued events and a pipeline worker can shorten `action.frames` under a modal dialog.
18. **A render whose card the open project does not hold keeps its frames** (final review fix wave, 2026-08-30). Deviation 12's restore is destructive, and `apply_frames` returns early on an action id `_find_action` cannot resolve. Restoring before that call would leave the card with the pre-render list while the rendered PNGs sit on disk. `_on_rendered` now tests reachability first; an unknown card keeps the rendered frames and reports the missing undo snapshot as an ERROR, because a paid render is never discarded silently.
