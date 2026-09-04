# Sprite tab: de-jitter cropped the character (rock_3 export)

Date: 2026-09-04 07:29. Branch: `feat/sprite-tab`. Nothing is committed.

## Symptom

The exports of `G:\ImageAI\Images\sprites\rock_3_20260903_100335` show frames with
the character cut off. Frame 7 of `rock_out` lost the top of the head and the feet.

## Root cause

The `stabilize` stage does two things:

1. `crop_and_pad` crops every frame to the same union alpha box (275,0)-(1006,720)
   of the 1280x720 clip. Every frame keeps a fixed 731x720 window. This part is
   correct.
2. `dejitter` (project default `True`, method `phase`) then registers every frame
   to frame 1 by phase correlation of the alpha mask and translates the frame.
   The tool is for camera jitter. On pose animation the mask changes shape every
   frame, the correlation locks onto different body parts, and the shift is
   large and wrong. The translation pushes subject pixels off the fixed canvas.

Shifts recomputed from the stage files on disk:

| Frame | Phase shift (dy, dx) px | Opaque pixels before → after | Lost |
|---|---|---|---|
| 3 | +88, -52 | 220,025 → 210,264 | 4 % |
| 6 | +40, +42 | 214,812 → 211,321 | 2 % |
| 7 | -100, -208 (clamped to -183) | 225,303 → 179,955 | 20 % |
| 9 | +28, 0 | 227,051 → 221,501 | 2 % |

The 25 % clamp (`MAX_SHIFT_FRACTION`) is 180 px on this frame and does not protect
the subject. The clip prompt asks for "no camera movement, character stays
centered", so there is no jitter to remove.

## Fix

- `core/sprite/project.py`: `StabilizeSettings.dejitter` defaults to `False`.
  Saved projects keep their stored value.
- `core/sprite/stabilize.py`: new `limit_shift_to_canvas(alpha, dy, dx)` clamps
  each axis to the room between the alpha bbox and the canvas edge. `dejitter`
  applies it after the fraction clamp and logs a warning when it limits a shift.
- `core/sprite/pipeline.py`: `stabilize` stage `code_version` 2 → 3, so cached
  stabilize output from the old code is stale.
- `gui/sprite/processing_panel.py`: tooltip on the De-jitter checkbox. Also adds
  the missing `from PIL import Image` (ruff F821 at the key-color estimate).
- `README.md`: Stabilize row and pipeline step 5 describe the new default.
- Tests: `tests/sprite/test_dejitter.py` gains three tests (helper, refused
  shift, limited shift). `tests/sprite/test_project.py` and
  `tests/sprite/test_pipeline_keying.py` assert the new default.

## Verification

Stabilize rerun on a copy of the rock_3 `alpha` frames (scratch directory, the
project on `G:` is untouched):

| Mode | Result |
|---|---|
| New default (de-jitter off) | 9 frames, all 731x720, 0 % opaque pixels lost |
| De-jitter on, phase, with the guard | 0 % lost; frame 7 moves up 16 px (the room it had) |

## Open

- Every `alpha` frame has a 1-px keying artifact at column 275 (88 rows). It pins
  the left edge of the union box and shows as a stray line. Not fixed here.
- `tests/sprite/gui/test_main_window_sprite_wiring.py::test_init_ui_adds_sprite_placeholder_after_layout`
  still fails on the uncommitted tab-order change in `gui/main_window.py` (known
  since 2026-09-01; decision pending).
- To fix the rock_3 project itself: open it, untick De-jitter in the Processing
  panel, run the pipeline, export again.
