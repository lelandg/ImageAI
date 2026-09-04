# Task 6 report: Image route — sheet generation and slicing

## Implemented

- `core/sprite/generation/image_route.py` — transcribed verbatim from the brief's Step 3 prototype:
  - Shared helpers: `provider_kind`, `default_openai_edit_model`, `first_image`, `save_png`,
    `log_request`, `log_response`, `call_provider`, `openai_sheet_size`, `openai_edit_size`.
  - Sheet route: `sheet_prompt`, `generate_sheet`, `slice_generated_sheet`.
  - Re-exports `generate_pose_instructions` from `core.sprite.generation.pose_steps` (imported,
    not edited — that module's implementer is concurrently applying a logging-only fix).
  - Constants: `SHEET_ASPECT_GEMINI = "21:9"`, `SHEET_SIZE_CUSTOM = "3072x1024"`,
    `MIN_GRID_CONFIDENCE = 0.6`, `STEP_PROMPT`.
- `tests/sprite/test_image_route.py` — transcribed verbatim from the brief's Step 1.

Before writing, I verified every consumed signature against the real source (not just the
brief's line-number claims):
- `GoogleProvider.edit_image` (`providers/google.py:1832-1905`) — accepts `image` as
  bytes/str/Path/list via `_edit_input_parts`; honors `aspect_ratio=` through `image_config`.
- `OpenAIProvider.edit_image` (`providers/openai.py:821-940`) — signature
  `(image, prompt, model=None, mask=None, size="1024x1024", n=1, **kwargs)`.
- `MODEL_CAPS` (`providers/openai.py:46-168`) — capability keys match
  (`supports_custom_size`, `valid_sizes`, `custom_size_edge_multiple`, etc.).
- `validate_custom_size`, `parse_size_string` (`core/image_size.py:12, 61`).
- `core.sprite.slicing.guess_grid` / `slice_sheet` — `slice_sheet` calls `_reset_dir(out_dir)`
  first (the core-spine hazard); my module never passes a source living inside `out_dir`.
- `core.sprite.pipeline.CancelToken` / `Cancelled` — `raise_if_cancelled()`.
- `core.sprite.generation.errors.ProviderError` / `classify_provider_error`.
- `core.sprite.generation.prompts.inject_chroma` / `FORBIDDEN_WORDS`.
- `core.sprite.project.ActionCard` field names (`id, name, prompt, duration_s, loop,
  target_frames, fps, ...`).
- `core.utils.write_image_sidecar` (`core/utils.py:193`).
- `core.sprite.generation.pose_steps.generate_pose_instructions` — imported only, signature
  unchanged, no edits made.

No deviations from the brief's prototype were needed; all consumed signatures matched exactly.

## Tests

Module tests:
```
$PY -m pytest tests/sprite/test_image_route.py -v
```
Result: 11 passed (the brief's Step 4 says "12 passed" — the actual verbatim test file has 11
test functions; this is a brief-count discrepancy, not a missing test or implementation gap).
One benign warning: `DeprecationWarning: 'mode' parameter is deprecated` from the test's own
verbatim `png_bytes()` fixture helper (`Image.fromarray(arr, "RGBA")`) — not from implementation
code; left as specified since the brief instructs verbatim transcription and the test passes.

Gate — no-hardcoded-paths:
```
QT_QPA_PLATFORM=offscreen $PY -m pytest tests/test_no_hardcoded_paths.py -q
```
Result: 3 passed.

Gate — full `tests/sprite` suite (run once, in the foreground; auto-moved to background by the
harness after the 120s timeout, awaited via completion notification, never polled):
```
QT_QPA_PLATFORM=offscreen $PY -m pytest tests/sprite -q
```
Result: 751 passed, 18 warnings in 123.31s. Warnings: 2 pre-existing `DeprecationWarning`s from
`google._upb._message` in an unrelated GUI wiring test, plus the 16 Pillow-mode warnings above.
No failures, no Qt import in my two files (confirmed via grep for `PySide`/`PyQt`).

## Files changed

- `core/sprite/generation/image_route.py` (new)
- `tests/sprite/test_image_route.py` (new)

## Self-review

- Completeness vs. brief: all "Produces" symbols present (`provider_kind`, `call_provider`,
  `first_image`, `save_png`, `log_request`, `log_response`, `openai_sheet_size`, `sheet_prompt`,
  `generate_sheet`, `slice_generated_sheet`, re-exported `generate_pose_instructions`).
- Names match the brief exactly.
- No overbuilding: file matches the brief's prototype exactly, including the two extra helpers
  (`default_openai_edit_model`, `openai_edit_size`) already present in the verified prototype —
  these are follow-on-route helpers the plan author included, not scope creep I added.
- Tests verify real behavior: mocked providers only (`MagicMock(spec=...)`), no network calls;
  each test asserts on actual kwargs passed to `edit_image`, actual sidecar JSON contents, actual
  sliced frame sizes/paths.
- Test output is pristine except the one benign, brief-specified Pillow deprecation warning noted
  above.
- Only my two files were staged; the working tree's unrelated changes (root `*.md` deletions,
  `Notes/*.md`, `feature-documenter.skill.zip`, concurrent `gui/sprite/export_dialog.py` and
  `engine_preset_box.py`/`export_formats.py` work) were left untouched.

## Concerns

None. The one item worth flagging is cosmetic: the brief's Step 4 expects "12 passed" but the
verbatim test file contains 11 test functions — no functionality is missing, just a count typo
in the brief text.

## Commit

`66233b8` — `feat(sprite): image route sheet generation (Gemini aspect kwarg, gpt-image 3:1
custom size) and slicing`

## Fix report (team-lead review finding)

**Finding:** `tests/sprite/test_image_route.py:34` used `Image.fromarray(arr, "RGBA")` — the
`mode` argument is deprecated in this Pillow and produced 16 `DeprecationWarning`s (one per
`png_bytes()` call across the suite), which the pristine-output self-review rule counts against.
Team lead noted the same fix already landed in `test_aseprite_native.py` and
`test_engine_presets.py`.

**Fix:** Changed line 34 to `Image.fromarray(arr).save(buf, "PNG")`. RGBA is inferred from the
array's `(H, W, 4)` uint8 shape, so output is byte-for-byte identical — zero behavior change.

**Covering tests + command + output:**
```
$PY -m pytest tests/sprite/test_image_route.py -v
```
Result: 11 passed, 0 warnings (previously 11 passed, 16 warnings).

```
QT_QPA_PLATFORM=offscreen $PY -m pytest tests/test_no_hardcoded_paths.py -q
```
Result: 3 passed (unaffected by this change; re-run for completeness).

**Commit:** `a3ec539` — `test(sprite): drop deprecated fromarray mode arg in image_route test
helper` (new commit, not an amend, per the implementer contract).

## Fix report (team-lead review round 2)

**Finding 1 (Important, ruled FIX):** `log_request`/`log_response` called `logger.info(message)`
and `log(message)` separately — the same double-logging bug Task 5 fixed in `pose_steps.py`
(`66c7c88`). `generate_sheet`'s default `log=logger.info` made every default-log call double-log
too.

**Finding 2 (Minor, ruled FIX in the same round):** `call_provider`'s exception path called
`logger.error(...)` only, so a provider failure never reached the status-console `log` sink.

**Fix:**
- Imported `emit` from `core.sprite.generation._common`.
- `log_request`/`log_response` now call `emit(logger, log, message)` instead of the two direct
  calls — message content unchanged.
- `call_provider` gained a keyword-only `log: LogFn = logger.info` parameter (not in the brief's
  original signature; added because the brief authorized "an added optional `log=logger.info`
  kwarg" for this exact case) and its exception handler now calls
  `emit(logger, log, f"[image route] {what} failed: {exc}", level="error")` instead of
  `logger.error(...)` alone.
- `generate_sheet`'s two `call_provider(...)` call sites now pass `log=log` so failures reach
  whatever sink the caller passed in.
- This matches `pose_steps.py`'s post-fix shape exactly (`emit(logger, log, message)` for
  info-level, `emit(logger, log, message, level="error")` for the failure path).

**New tests** (mirroring Task 5's pattern in `test_pose_steps.py`):
- `test_generate_sheet_default_log_writes_each_full_content_message_once` — with `log` left at
  its default and `caplog` capturing `core.sprite.generation.image_route` at INFO, asserts the
  `"[image route] sheet request:"` and `"[image route] sheet response:"` lines each appear
  exactly once (previously would have been logged twice via the direct `logger.info` + `log`
  calls, except the default case only doubled inside `emit` before the fix's dedup check existed
  — this test locks in the dedup behavior going forward).
- `test_generate_sheet_provider_failure_emits_error_to_log` — forces `provider.edit_image` to
  raise, passes a recording `log` sink, and asserts both that the sink receives a `"failed"`
  line containing the original exception text, and that `caplog` recorded it at `ERROR` level on
  the module logger.

**Covering tests + command + output (team lead's exact gate):**
```
$PY -m pytest tests/sprite/test_image_route.py tests/sprite/test_pose_steps.py \
  tests/test_no_hardcoded_paths.py -q -p no:cacheprovider
```
Result: 27 passed in 28.05s, 0 warnings (pristine).

Also confirmed no `PySide`/`PyQt` import was introduced (grep on both changed files, no hits).

**Files changed:** `core/sprite/generation/image_route.py`, `tests/sprite/test_image_route.py`
(only these two staged and committed).

**Commit:** `a97e969` — `fix(sprite): route image-route logging through the shared emit helper`.
