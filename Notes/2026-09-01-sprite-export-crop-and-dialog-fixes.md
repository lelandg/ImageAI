> **Status 2026-09-02: reverted.** The crop was dropped; the export-time profile-stage guarantee, the sheet_meta warning and the scroll-area dialog fix were reapplied in smaller form. See `Notes/2026-09-02-sprite-fix-plan.md`.

# Sprite export: crop to cell proportions, profile stages, dialog readability, README help

**Date:** 2026-09-01
**Branch:** `feat/sprite-tab`
**Scope:** Three reported problems plus one root cause found during the investigation.
**Status:** Complete. Not committed. The version bump and the PR stay with sub-project 7.

---

## What the user reported

1. Exports must be cropped to the target proportions.
2. The export dialog is partly unreadable until the window grows.
3. The sprite UI needs help text.
4. Two of three test sprites came out with "strange palettes".

---

## Root causes

### 1. Exports ignored the output profile

`SpriteProject.sheet_meta()` sets `cell_size` from the `OutputProfile` (hd 256x256, pixel
64x64). Every exporter then read `frame.source_path` and wrote the image at its **native**
size. `core/sprite/exporters/grid.py` even overwrote `filled.cell_size` with the largest
source image size. So `cell_size` had no effect at export time.

### 2. The profile stages never ran (this is the "strange palettes")

`core/sprite/generation/queue.py` stopped the pipeline at `stabilize`, so
`stages/<action_id>/hd/` and `stages/<action_id>/pixel/` were never written.
`sheet_meta()` falls back to the stabilize PNG when a profile stage directory is missing,
and it did so silently.

Measured in the three real projects under `G:\ImageAI\Images\sprites`:

| project | `exports/hd/` frame | `exports/pixel/` frame |
|---|---|---|
| sprite-alpha | 1280x720, 38764 colors | 1280x720, 38764 colors |
| sprite-3 | 498x588, 38798 colors | 498x588, 38798 colors |

The two profiles produced identical files. A real pixel profile is 64x64 with 32 colors.
The pixel profile's quantize and palette-lock pass had never run.

`gui/sprite/processing_panel.py` already used `upto="pixel"`, so the Processing panel path
was correct and the queue path was not. That is why the result appeared to depend on
settings.

### 3. The export dialog compressed its own options pane

`_build()` put the group boxes in a plain layout inside a vertical `QSplitter` with
`setStretchFactor(0, 0)` and no minimum. The splitter compressed the pane below its
`minimumSizeHint`, so the group boxes clipped their children. The Formats group was worst
hit, because `register_extra_formats()` and `install_engine_presets()` add rows **after**
`__init__` set a fixed 660x680 minimum.

### 4. The sprite tab had no help

`README.md` had zero matches for "sprite". The Help tab renders `README.md`, so the whole
tab was undocumented.

---

## What changed

### Crop to the cell proportions — `core/sprite/stabilize.py`

New `aspect_crop_box(content, cell, anchor, protect=None)` returns the largest box inside
the frame that carries the cell's aspect, positioned by the stabilize anchor. New
`aspect_crop_gain(...)` drops a crop that cannot cover more of the cell than the uncropped
frame, so a crop is never pure loss. New `subject_bbox(frames)` returns the union alpha box
of a whole action.

`crop_and_pad()` gained `crop_to_aspect` and `protect`. `hd_runner` and `run_pixel_stage`
pass the profile's setting and the action's subject box.

**The crop trims margin and never cuts the character.** The first implementation cropped
unconditionally. Review found that this decapitates a standing character, because the
stabilize stage hands the profile stages the content bounding box, not a letterboxed plate.
A square cell then trims the top. `subject_bbox` closes that: the crop box always contains
the union alpha box.

**A frame with no alpha is protected whole.** Alpha is the only signal that marks margin.
Without it an opaque 1280x720 plate whose keying failed and an opaque 400x650 character
look identical, so nothing is trimmed and the scale letterboxes. No pixel is lost.

One crop box serves the whole action, so the character does not shift between frames and
the pixel profile keeps one shared integer reduce factor.

`OutputProfile.crop_to_cell_aspect` defaults to **True**. The Processing panel exposes it
as "Crop to the cell proportions (fills the cell)".

Effect on the three real projects:

| project | subject box | hd 256x256 result |
|---|---|---|
| sprite-alpha | full frame (opaque) | no margin to trim; 256x144 in the cell, every pixel kept |
| barry-guitar | full frame (opaque) | no margin to trim; 256x144 in the cell, every pixel kept |
| sprite-3 | (0, 8, 492, 580) | crop 498x580 at (0,8); 220x256 in the cell, subject intact |

Bars that survive mean the subject itself does not match the cell proportions. A 498x588
character fills a 216x256 `hd` cell exactly.

### Profile stages run — `core/sprite/generation/queue.py`

`PIPELINE_UPTO` moved from `"stabilize"` to `"pixel"`. `_post_process` now names the stages
that actually produced frames, because `run_pipeline` skips a disabled profile.
`gui/sprite/queue_panel.py` and `gui/sprite/image_route_dialog.py` moved to `upto="pixel"`
as well.

`SpriteProject.sheet_meta()` keeps its fallback but now logs one warning per action, naming
the project, the action, the profile and the missing directory. A disabled profile is named
as the cause instead of advising a pipeline run that would skip the stage.

### Export dialog readability — `gui/sprite/export_dialog.py`

The options pane sits in a `QScrollArea` with `setWidgetResizable(True)`. The splitter is
non-collapsible and both panes carry a minimum height. `_apply_minimum_size()` measures the
real content after every format registers and caps the result at 90% of the available
screen; `showEvent` re-measures once, because Qt settles size hints only at polish time.

A `WheelGuard` event filter sends a wheel over an unfocused spin box, combo box or slider to
the scroll area instead of editing an export parameter. A field the user clicked into keeps
its wheel.

### Help — `README.md`

New `#### Sprite Tab` section under GUI Features, with a Table of Contents entry. It covers
the project toolbar, character panel, action cards, generation settings, render queue, frame
strip, preview player, processing panel, retouch, image route, the pipeline stage by stage,
the on-disk layout, the export dialog, the output profiles, and the keyboard shortcuts.
`tests/test_readme_help_anchors.py` checks that every Table of Contents link resolves under
both the app's slug rule and GitHub's.

---

## Review

Three adversarial lenses (correctness geometry, regression sweep, contracts and UX) produced
12 findings; 11 were confirmed by execution and 1 of 1 plausible survived refutation. All 12
were fixed. The most important were the head-loss defect above, a `resolution_check` that
measured the cropped frame instead of the source (which would have routed frames into the
paid `stability_api` upscale path), and the wheel-over-spin-box defect.

---

## Known issue, not from this work

`tests/gui/test_main_window_sprite_wiring.py::test_init_ui_adds_sprite_placeholder_after_layout`
fails. It asserts that `"📖 Layout"` appears before `"🎮 Sprite"` in the source of
`MainWindow._init_ui`. The working tree carries an uncommitted `gui/main_window.py` edit
that moves the Sprite tab ahead of Layout, alongside uncommitted provider/model sync work
and `tests/gui/test_provider_model_sync.py`. Decide whether the tab order or the test is
right, then update the loser.

---

## Follow-ups

- Sub-project 7 owns the CLI verbs, the CodeMap refresh, the version bump and the single PR.
- `core/sprite/exporters/grid.py` still overwrites `cell_size` from the largest source
  image. That is correct for a sheet built from already-fitted profile frames, but it means
  the sheet's cell size is derived, not declared. Worth a look during sub-project 7.
- The keying failed outright on sprite-alpha and barry-guitar: their stabilize frames are
  100% opaque, so the green plate was never removed. That is a separate defect and it is
  why those two exports cannot be cropped at all.
