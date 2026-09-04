# Sprite tab: revert of the 2026-09-01 crop work and the replacement plan

**Date:** 2026-09-02
**Branch:** `feat/sprite-tab`
**Status:** Tasks landed in the working tree. Not committed. The version bump and the PR
stay with sub-project 7 (`Plans/2026-08-29-sprite-cli-release-plan.md`). The working tree
also carries unrelated uncommitted provider, logging and main-window work; commit the sprite
files by path.

No file in `Plans/` tracks this fix work. `Plans/2026-08-29-sprite-tab-design.md` is the
feature design. `Plans/2026-08-29-sprite-cli-release-plan.md` is sub-project 7, not started.
This note is the tracker.

---

## What happened

On 2026-09-01 a session changed the sprite tab to solve four reported problems. The write-up is
`Notes/2026-09-01-sprite-export-crop-and-dialog-fixes.md`. The user tested the result and said:

> The main session was cropping the export to correct size, which is too over-zealous.

The sprite code from that session was reverted in the working tree on 2026-09-02. The full
reverted diff is kept as `Notes/sprite-tab-archive/2026-09-01-opus-crop-export-changes.patch`
for reference. It is not reapplied. The `README.md` help text from that session stays.

The four original problems are still real:

1. Exports must carry the target proportions.
2. The export dialog is partly unreadable until the window grows.
3. The sprite tab needs help text. Kept: the `README.md` edits stay.
4. Two of three test sprites came out with "strange palettes".

---

## Decision: drop the cell-aspect crop

Do not reintroduce `crop_to_cell_aspect`, `aspect_crop_box`, `aspect_crop_gain` or
`subject_bbox`. Do not add them as an opt-in profile field.

Honor the profile cell size only through the existing `hd` and `pixel` stages. Each stage
scales a frame with one factor and pads with transparent pixels
(`core/sprite/pipeline.py:470-501`, `core/sprite/stabilize.py:106-179`,
`core/sprite/pixelart.py:373-455`).

Reasons:

1. Measured on the three real projects, the protected crop gains 0% on `sprite-alpha` and
   `barry-guitar`, and 1.4% (8 rows) on `sprite-3`. The unprotected first version removed
   44% and 15% of the frame.
2. The padded fit already gives the cell proportions. Requirement 1 is met once the profile
   stages run.
3. The user rejected the crop in plain words.
4. An opt-in fill mode would still need a new alpha>=128 subject box. It stays a no-op on
   `barry-guitar` (soft plate) and `sprite-alpha` (opaque plate). It buys nothing today.

One guard stays: a test that a legacy `crop_to_cell_aspect` key in a saved project
(`sprite-alpha` carries one) is ignored on load and dropped on save
(`tests/sprite/test_project.py::test_legacy_crop_to_cell_aspect_key_is_ignored`,
`::test_project_round_trip_drops_legacy_crop_key`).

If the user later wants the target proportions at native resolution with no downscale, the
correct follow-up is Design C: pad the stabilize cell to a target aspect, opt-in, default
`None`. Not a crop.

---

## Root cause of "strange palettes" (confirmed)

`core/sprite/generation/queue.py` stopped the pipeline at `stabilize`, so
`stages/<action_id>/hd/` and `stages/<action_id>/pixel/` were never written after a render.
`SpriteProject.sheet_meta()` then fell back to the stabilize PNG without a message. The
`hd` and `pixel` exports were the same native-size, full-color files. The pixel quantize and
palette-lock pass never ran. The Processing panel path already used `upto="pixel"`, so the
result looked like it depended on settings.

---

## Tasks

The task numbers below come from the tags in the working-tree code and tests (`T3`, `T4`,
`T6`, `T9`). The other items carry no tag in the code; they are listed by content.

| Item | Change | Files | Tests |
|---|---|---|---|
| Queue stops at stabilize | `PIPELINE_UPTO` was flipped to `"pixel"`, then reverted to stabilize after review: the pixel stage locks the project palette on its first run, so a queue-driven run would lock it from the first card's untuned frames. The queue and an export must not both write `stages/<id>/hd` and `/pixel`. The success log names the stages that produced output. | `core/sprite/generation/queue.py` | `tests/sprite/generation/test_gen_queue.py::test_pipeline_upto_stops_before_the_profile_stages`, `::test_queue_never_runs_a_profile_stage` |
| Legal aspect ratios per provider | `legal_aspect_ratios(provider, model)` reads the Veo and Omni client constraints. `validate_generation_settings()` gives one user-facing message. The queue panel refuses an illegal ratio before a worker starts. The settings dialog offers only legal ratios and remaps a wrong one with a note and a log line. | `core/sprite/timing.py`, `core/sprite/generation/video_route.py`, `gui/sprite/queue_panel.py`, `gui/sprite/generation_settings_dialog.py` | `tests/sprite/test_sprite_timing.py`, `tests/sprite/generation/test_gen_video_route.py`, `tests/sprite/gui/test_queue_panel.py`, `tests/sprite/gui/test_generation_settings_dialog.py` |
| T3: export guarantees the profile stages | `ensure_profile_stages()` runs each missing or stale profile stage per action and returns profile -> reason. `run_export` calls it before `sheet_meta`, logs every reason, saves the project, and still writes. `sheet_meta()` logs one warning per action when an enabled profile falls back to the stabilize frames. | `core/sprite/pipeline.py`, `core/sprite/project.py`, `gui/sprite/export_dialog.py`, `core/sprite/__init__.py` | `tests/sprite/test_pipeline.py` (`ensure_profile_stages` block), `tests/sprite/gui/test_export_dialog.py` (T3 block), `tests/sprite/test_project.py` (sheet_meta warnings block) |
| T4: export dialog readability | The options pane sits in a `QScrollArea` with `setWidgetResizable(True)`. The dialog keeps a minimum width only. First open uses a size bounded to the screen; the geometry round-trips through `QSettings`. | `gui/sprite/export_dialog.py` | `tests/sprite/gui/test_export_dialog.py` (T4 block) |
| T6: chat model is a registry id | The action-card generator resolves `default_chat_model(provider)`; "chat" is not a registry family (see commit `0a655b4`). A resolver failure is logged and shown. | `gui/sprite/action_cards_panel.py` | `tests/sprite/gui/test_action_cards_panel.py`, `tests/sprite/gui/test_character_panel.py` |
| Pixel stage keeps every row | A portrait frame keeps every row through the pixel stage; `crop_and_pad` with a full-frame bbox drops no subject pixel. | `core/sprite/pipeline.py`, `core/sprite/stabilize.py` | `tests/sprite/test_pipeline_pixel.py::test_pixel_stage_keeps_every_row_of_a_portrait_frame`, `tests/sprite/test_stabilize.py::test_crop_and_pad_full_frame_bbox_never_drops_subject_pixels` |
| Legacy crop key guard | A saved `crop_to_cell_aspect` key loads inert and never saves back. | `core/sprite/project.py` | `tests/sprite/test_project.py::test_legacy_crop_to_cell_aspect_key_is_ignored`, `::test_project_round_trip_drops_legacy_crop_key` |
| T9: key self-check | The key stage warns when the key color removes less than 1% of the first frame. The warning names the sampled corner color. The alpha is not changed. | `core/sprite/pipeline.py` | `tests/sprite/test_pipeline_keying.py` |
| T10: notes | Banner on the 2026-09-01 note, archive row for the reverted patch, this plan. | `Notes/` | none (grep checks) |

Out of scope, per the decision above: any crop of the frame to the cell aspect.

---

## 2026-09-03: keying works out of the box

Question from Leland: an export still came out 16:9. Cause: the key stage removed nothing.
The plate Gemini made for "Rock out 2" was a muted green, Omni then rendered the clip on
plain white, and the key stage keyed on the requested `#00FF00`. Nothing was transparent, so
the stabilize box was the whole 1280x720 frame and the hd cell held a 16:9 strip.

Changes (`core/sprite/keying.py`, `core/sprite/pipeline.py`, `core/sprite/generation/plate.py`,
`gui/sprite/processing_panel.py`):

- `estimate_key_color()` samples the median border color of a frame and reports how uniform the
  border is. `auto_key_color()` chooses the key: the sampled color wins over the plate request;
  a border that is not one color falls back to the plate color with a warning.
- The key stage samples the first frame when no key color is set, keys every frame on that one
  color, and writes `stages/<id>/key/key.json`. The alpha stage reads the same color. Stage
  code versions for `key` and `alpha` are 3, so existing projects re-key on the next run.
- Neutral keys (white, gray, black plates) add luminance to the distance and skip despill.
- `detect_edge_bands()` finds letterbox and pillarbox bars (flat rows of one color that end on a
  flat row of another color) and the key stage clears them. The sampler reads inside the bars.
- Muted keys (chroma below 0.35) get a clamped tolerance and softness so grays and whites in
  the subject stay opaque. An explicit per-frame override bypasses the clamp.
- The plate step measures the real plate background, writes it to the sidecar, and warns on
  drift.

Measured on the real first frames with the final code (key sampled, then `key_frame`):

| clip | sampled key | removed | subject box |
|---|---|---|---|
| Rock out 2 (white background) | `#FFFFFF` | 75% | (304, 30, 969, 720) |
| sprite-alpha, pillarboxed 1:1 | `#75BB65` | 86% | (448, 104, 802, 632) |
| sprite-alpha, 16:9 | `#76B965` | 76% | (404, 46, 873, 720) |
| barry-guitar | `#28C238` | 84% | (432, 80, 924, 658) |
| sprite-3 | `#06CD1C` | 86% | (483, 102, 942, 666) |

Before the change every one of these except sprite-3 removed 0%.

Follow-up the same day: `rock_3_20260903_100335` showed an opaque black block on the right in
three of nine frames. The clip is 1:1 inside black bars; the right bar carried compression
noise and the sound glyphs touched it, so the first bar rule (flat rows, then a flat row of
another color) missed it. `detect_edge_bands()` now counts a run of rows that are mostly the
edge color and checks the strip just inside the run for another color. All nine frames detect
both bars (275 / 274 px). The `key` stage is code version 4 so existing projects re-key.

Known limit: colors in the character that match the plate (the green in a tie-dye shirt on a
green plate) are keyed with the plate. Pick a plate color that is absent from the character.

## Facts and hypotheses

Confirmed by code and tests:

- The queue stopped at `stabilize` before this work (`PIPELINE_UPTO` in
  `core/sprite/generation/queue.py`). It still does; the export runs the missing profile
  stages itself (T3), and the export is refused while the queue runs.
- The 2026-09-01 crop symbols are gone from `core/` and `gui/`. A grep for
  `crop_to_cell_aspect`, `aspect_crop_box` and `subject_bbox` hits only the two guard tests.
- Today's app log was restored from the Windows logs directory (1511 lines, started
  07:03:06).

Hypothesis, not verified in this session:

- The keying failed outright on `sprite-alpha` and `barry-guitar` (stabilize frames 100%
  opaque). The T9 self-check warns on that case; it does not fix the key color.

---

## Results

Run on 2026-09-02 from the repo directory with
`QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest <paths> -q -p no:cacheprovider`.

| Test paths | Result |
|---|---|
| `tests/sprite`, `tests/test_*.py` (root level) | 1144 passed, 19 skipped, 1 deselected, 205 s |
| `tests/gui`, `tests/layout`, `tests/migration`, `tests/styles`, `tests/video` | 877 passed, 145 s |

The deselected test is `tests/sprite/gui/test_main_window_sprite_wiring.py::test_init_ui_adds_sprite_placeholder_after_layout`.
It is the known issue from the 2026-09-01 note: an uncommitted `gui/main_window.py` edit
moves the Sprite tab ahead of Layout, and the test asserts the old order. It is not part of
this work. Decide the tab order, then update the test or the code to match.

Review round (2026-09-02, after the first implementation): the repairs from that review are in
the tree. They cover the queue revert to `stabilize`, the export refusal while the queue runs,
the broad exception handling in `ensure_profile_stages`, the provider auth-mode normalization,
the log filter that keeps `record.exc_info`, and the pytest guard on `copy_log_on_exit`.

Commit ids: none. Nothing from this work is committed. The commit, the version bump and the
single PR stay with sub-project 7.
