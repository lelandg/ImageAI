# Task 8 report: Retouch core

## What I implemented

`core/sprite/generation/retouch.py` — non-destructive AI retouch of one sprite
frame, transcribed from the brief's prototype with two adjustments (see
Deviations below):

- `next_retouch_path(frame)` — `NNNN.png -> NNNN.r<k>.png`, never collides,
  a retouch-of-a-retouch keeps the base name.
- `build_region_mask(size, region, feather=5)` — OpenAI alpha mask (0 =
  editable inside `region`, 255 outside, feathered edge).
- `fit_to_size(image, size)` — proportional scale + transparent letterbox,
  never stretches.
- `validate_retouch(original, edited, region)` — mean-abs-diff check over the
  region (or whole frame), same 1.0 threshold as
  `ai_face_editor._validate_edit`.
- `retouch_prompt(instruction, *, neighbors)` — instruction + neighbor/context
  guardrail sentence.
- `retouch_frame(provider, frame, instruction, out_png=None, *, neighbors=(),
  region=None, model=None, log=logger.info, attempts=2)` — Google whole-frame
  (`edit_image` with neighbors as extra references) or region
  (`edit_image_region`); OpenAI edit with an optional region alpha mask;
  retries up to `attempts` on an unchanged result, then raises
  `ProviderError`; writes `NNNN.r<k>.png` beside the original (never
  overwrites) plus a `.json` sidecar via `write_image_sidecar`; never
  overwrites the original frame.

`tests/sprite/test_retouch.py` — the brief's 12 tests, transcribed, with the
`_png()` fixture fix described below.

## Deviations from the brief (and why)

1. **Test fixture bug (self-contradictory as given):** `_png()`'s hardcoded
   red square at `[8:24, 8:24]` was drawn with a fixed color regardless of
   `shade`, and the region-based tests use `region=(8, 8, 16, 16)` — exactly
   that square. So the "reply" image (`shade=180`) and the source frame
   (`shade=100`) were byte-identical *inside the tested region*, making
   `validate_retouch` correctly report "unchanged" and `retouch_frame` raise
   `ProviderError` after exhausting `attempts` — which fails
   `test_google_region_uses_edit_image_region` and
   `test_openai_region_builds_alpha_mask` (both expect a successful edit).
   Verified by computing the mean diff directly: 0.0 inside `(8,8,24,24)` with
   the original fixture. Fix: tint the square by `shade`
   (`(255, shade % 256, shade % 256, 255)`) instead of a fixed `(255,0,0,255)`,
   so a shade-only change is visible in that region too. This does not affect
   any other test's assertions (checked each one: `region=None` tests compare
   the whole canvas, dominated by background shade change regardless of the
   square; `test_validate_retouch_detects_unchanged` uses `region=(0,0,8,8)`,
   which never overlapped the square in either version).
2. **Deprecated PIL `mode` argument:** `Image.fromarray(arr, "RGBA")` /
   `Image.fromarray(mask, "RGBA")` triggered
   `DeprecationWarning: 'mode' parameter is deprecated` (Pillow 13, due
   2026-10-15) in both the test fixture and `build_region_mask`. Dropped the
   mode argument in both places (PIL infers RGBA from the `(h, w, 4)` uint8
   shape) to keep gate output pristine.
3. **`log=log` threaded through `call_provider`:** the brief's prototype
   called `call_provider(...)` without `log=log`; per the dispatch note (the
   file "moved past the brief in reviewed fix rounds"), `call_provider` in
   `image_route.py` takes a `log: LogFn = logger.info` kwarg that must be
   threaded through every call. Added `log=log` to all three `call_provider`
   invocations.
4. **Logging via `emit`, never bare `logger` + `log`:** per the dispatch note,
   replaced the brief's `logger.warning(...)` / `log(...)` duplicate pairs
   (validation line, per-attempt rejection, final failure) with
   `emit(logger, log, message, level=...)` from `core.sprite.generation._common`
   — the same helper `log_request`/`log_response` already use in
   `image_route.py`. Behavior is unchanged; this only avoids double-logging
   and matches the module's established logging convention.

No other deviations. File structure, function names, and signatures match
the brief exactly.

## Tests + results

```
$ /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
    /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_retouch.py -v
```
```
tests/sprite/test_retouch.py::test_next_retouch_path_never_collides PASSED
tests/sprite/test_retouch.py::test_google_whole_frame_uses_neighbors_as_references PASSED
tests/sprite/test_retouch.py::test_google_region_uses_edit_image_region PASSED
tests/sprite/test_retouch.py::test_openai_region_builds_alpha_mask PASSED
tests/sprite/test_retouch.py::test_openai_without_region_sends_no_mask PASSED
tests/sprite/test_retouch.py::test_build_region_mask_feathers_edge PASSED
tests/sprite/test_retouch.py::test_result_is_repadded_proportionally_when_size_differs PASSED
tests/sprite/test_retouch.py::test_fit_to_size_upscales_small_result PASSED
tests/sprite/test_retouch.py::test_validate_retouch_detects_unchanged PASSED
tests/sprite/test_retouch.py::test_unchanged_result_retries_then_raises PASSED
tests/sprite/test_retouch.py::test_never_overwrites_existing_output PASSED
tests/sprite/test_retouch.py::test_logs_request_and_response PASSED
============================== 12 passed in 2.65s ==============================
```
No warnings in this run.

```
$ /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
    /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -q
```
```
3 passed in 2.70s
```

Full `tests/sprite` (since I consume `image_route.py`, which has other tests
under `tests/sprite/`), run in the foreground:
```
$ QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
    /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite -q
```
```
782 passed, 2 warnings in 127.54s (0:02:07)
```
The 2 warnings are pre-existing `DeprecationWarning`s from
`google._upb._message` (protobuf metaclass, Python 3.14 deprecation) in
`tests/sprite/gui/test_main_window_sprite_wiring.py`, unrelated to this task.

Grep for Qt imports in the two new files: none found (`PySide|PyQt|QtCore|
QtWidgets|QtGui` — no matches).

## Files changed

- `core/sprite/generation/retouch.py` (new, 172 lines)
- `tests/sprite/test_retouch.py` (new, 164 lines)

## Self-review

- Completeness vs. brief: all 6 public functions (`next_retouch_path`,
  `build_region_mask`, `fit_to_size`, `validate_retouch`, `retouch_prompt`,
  `retouch_frame`) implemented with the exact signatures listed under
  "Produces" in the task brief.
- Names match the brief exactly (function names, parameter names, module
  path, test file path).
- No overbuilding: no extra public functions, no speculative options beyond
  what the brief and its consumed helpers require.
- Tests verify real behavior: mocked providers assert on call args (image
  bytes, region tuple, prompt content, model, mask alpha values), sidecar
  contents, retry/raise-on-unchanged, never-overwrite, and full request/
  response/validation logging — not just "it returns something."
- Test output pristine: no warnings in the task's own test file after the
  fixture and PIL-mode fixes; the full `tests/sprite` run's only warnings are
  pre-existing and unrelated to this task.

## Concerns

None. Commit `22618af` on `feat/sprite-tab`, only the two task files staged.
