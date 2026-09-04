# Task 7 report: Image route — edit-chain (+ difference-matte pairs)

## What was implemented

- `core/sprite/generation/image_route.py`: appended `MATTE_PLATES = ("#FFFFFF", "#000000")`
  and `edit_chain(provider, character, action, out_dir, *, frames, pose_instructions,
  plate_color, model=None, log=logger.info, token=None, matte_pairs=False) -> List[Path]`.
  Frame k is an edit whose refs are `[character_bytes, prev_bytes]`; a Gemini chat session
  from `start_edit_session` (google only) establishes style context and is reset in a
  `finally`; the cancel token is checked at the top of each step; each frame gets a
  `.json` sidecar via `write_image_sidecar`; with `matte_pairs=True` each step renders
  white (`#FFFFFF`) and black (`#000000`) plates, keeps them on disk as
  `NNNN.white.png` / `NNNN.black.png`, and folds them through `difference_matte` into the
  RGBA output; the chain continues from the white plate's bytes.
  `default_openai_edit_model()` and `openai_edit_size()` already existed from Task 6 and
  needed no changes to their signatures.
- `tests/sprite/test_image_route.py`: appended the 7 chain tests plus `_distinct_replies`
  helper, per the brief.

## Deviations from the brief's prototype (both required to make the tests pass; report per contract §"Deviate only when a test fails")

1. **Threaded `log=log` through both `call_provider` calls in the plates loop.** The
   brief's Step 3 snippet omitted this kwarg, but at HEAD (post Task-6 fix rounds)
   `call_provider(..., log: LogFn = logger.info, ...)` routes full-content logging to the
   status console, and every other call site in this file (`generate_sheet`) already
   passes `log=log`. Omitting it would silently drop edit-chain request/response logging
   from the console. No test exercises this directly (it's a logging-completeness fix
   consistent with the file's established convention, not a required behavior for the
   given tests), but it was called out explicitly in the dispatch as a fact about the
   file's current state.
2. **Fixed a real half-up-rounding bug in `openai_edit_size`** (pre-existing, from
   Task 6, not part of this task's diff scope but exercised by this task's own test
   `test_openai_edit_size_prefers_custom_when_legal_else_closest_preset`). The old code
   used Python's `round()` (banker's / round-half-to-even), so `openai_edit_size(model,
   (1000, 1010))` computed `992x1008` instead of the expected `1008x1008` (1000/16 = 62.5
   rounds to even 62, not up to 63). Replaced `round(w / multiple) * multiple` with
   `int(w / multiple + 0.5) * multiple` (round half up) for both `cw` and `ch`. Verified
   all four sub-assertions in that test now pass, and re-ran the full sprite suite to
   confirm no other test depended on the old rounding behavior.
3. **Dropped `provider.start_edit_session.assert_not_called()`** from
   `test_edit_chain_openai_passes_size_and_default_model`. `OpenAIProvider` has no
   `start_edit_session`/`reset_edit_session` at all (only `GoogleProvider` does — grepped
   the whole repo to confirm), so `MagicMock(spec=OpenAIProvider)` doesn't expose that
   attribute; merely referencing `provider.start_edit_session` raises `AttributeError`
   before the assertion can run. `edit_chain`'s only touches of `start_edit_session` /
   `reset_edit_session` are inside `if kind == "google":` guards, so it is structurally
   impossible for the openai path to call them — the assertion was untestable as written
   given the spec, not a behavior gap. Replaced with an explanatory comment.

## Tests

Command: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_image_route.py -v`

```
tests/sprite/test_image_route.py::test_sheet_prompt_is_clean PASSED
tests/sprite/test_image_route.py::test_generate_sheet_google_uses_aspect_kwarg_not_prompt PASSED
tests/sprite/test_image_route.py::test_generate_sheet_openai_uses_custom_3to1_size PASSED
tests/sprite/test_image_route.py::test_openai_sheet_size_without_custom_size_picks_widest_preset PASSED
tests/sprite/test_image_route.py::test_generate_sheet_no_image_raises_provider_error PASSED
tests/sprite/test_image_route.py::test_generate_sheet_wraps_provider_exception PASSED
tests/sprite/test_image_route.py::test_generate_sheet_logs_request_and_response PASSED
tests/sprite/test_image_route.py::test_generate_sheet_default_log_writes_each_full_content_message_once PASSED
tests/sprite/test_image_route.py::test_generate_sheet_provider_failure_emits_error_to_log PASSED
tests/sprite/test_image_route.py::test_generate_sheet_honors_cancel_token PASSED
tests/sprite/test_image_route.py::test_generate_sheet_rejects_fewer_than_two_frames PASSED
tests/sprite/test_image_route.py::test_slice_uses_guess_when_confident PASSED
tests/sprite/test_image_route.py::test_slice_falls_back_to_one_row_when_guess_disagrees PASSED
tests/sprite/test_image_route.py::test_edit_chain_google_chains_previous_frame PASSED
tests/sprite/test_image_route.py::test_edit_chain_openai_passes_size_and_default_model PASSED
tests/sprite/test_image_route.py::test_openai_edit_size_prefers_custom_when_legal_else_closest_preset PASSED
tests/sprite/test_image_route.py::test_edit_chain_matte_pairs PASSED
tests/sprite/test_image_route.py::test_edit_chain_cancels_between_steps PASSED
tests/sprite/test_image_route.py::test_edit_chain_length_mismatch PASSED
tests/sprite/test_image_route.py::test_edit_chain_session_failure_is_logged_not_fatal PASSED

============================== 20 passed in 3.35s ==============================
```
(No warnings — pristine output. 20 = the brief's 13 pre-existing + 7 new; the brief's Step 4
estimate said "19 passed", off by one from actual pre-existing count, immaterial.)

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -q` → `3 passed in 3.07s`.

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite -q` (module touched has other
tests under `tests/sprite/`, so ran the sub-tree once before committing, per the gate) →
`769 passed, 2 warnings in 121.55s`. The 2 warnings are pre-existing
`DeprecationWarning`s from `google._upb._message` inside
`tests/sprite/gui/test_main_window_sprite_wiring.py::test_video_tab_declares_and_main_window_connects_the_signal`
— a file this task never touched.

`grep -n "PySide6\|PyQt" core/sprite/generation/image_route.py tests/sprite/test_image_route.py`
→ no matches (exit 1). No Qt import introduced.

## Files changed

- `core/sprite/generation/image_route.py` (append `MATTE_PLATES` + `edit_chain`; fix
  `openai_edit_size` rounding)
- `tests/sprite/test_image_route.py` (append the 7 chain tests + `_distinct_replies`
  helper; one assertion dropped per deviation #3 above)

Commit: `e7d3b16` — "feat(sprite): image route edit-chain with optional white/black
difference-matte pairs"

## Self-review

- Completeness vs. brief: `edit_chain` matches the brief's interface signature exactly
  (`provider, character, action, out_dir, *, frames, pose_instructions, plate_color,
  model=None, log=logger.info, token=None, matte_pairs=False) -> List[Path]`). All 7
  brief-specified tests present and passing, verbatim except the one dropped assertion
  (documented above).
- Names match the brief exactly: `edit_chain`, `MATTE_PLATES`, no renames.
- No overbuilding: only appended what the brief asked for, plus the two documented
  bugfixes required to make the brief's own tests pass.
- Tests verify real behavior: reference-chaining across steps, google session
  start/reset in `finally`, openai size/model kwargs, matte-pair plate persistence +
  alpha recovery, cancel-between-steps (only step-1 artifact survives, session still
  reset), length-mismatch `ValueError`, non-fatal session-start failure with a logged
  message.
- Verified against real provider signatures (not guessed): `providers/google.py:1832`
  `edit_image` list input, `:2016` `start_edit_session`, `:2087` `reset_edit_session`;
  `providers/openai.py:855` `edit_image` bytes/path normalization;
  `core/sprite/matting.py:144` `difference_matte`.
- Working tree hygiene: confirmed via `git status --porcelain` before and after `git add`
  that only `core/sprite/generation/image_route.py` and `tests/sprite/test_image_route.py`
  were staged; the unrelated deleted root `*.md` files, untracked `Notes/*.md`,
  `feature-documenter.skill.zip`, and another implementer's in-progress
  `gui/sprite/{export_formats,engine_preset_box,export_dialog}.py` + GUI test were left
  untouched throughout.

## Concerns

None blocking. The two deviations (log threading, rounding fix) are both small, scoped,
and necessary for the brief's own tests to pass — flagged per contract rather than
silently patched.

---

## Fix round (review findings, all accepted)

Reviewer re-derived all three of the deviations above and accepted them; three fix items
in `core/sprite/generation/image_route.py`:

1. **Matte-plate sidecars.** The `matte_pairs` branch saved `NNNN.white.png` /
   `NNNN.black.png` via `save_png` but never wrote a `.json` sidecar for either — the
   AGENTS.md hard rule ("every generated image gets a `.json` metadata sidecar") covers
   every written artifact, not just the merged frame. Added a `write_image_sidecar` call
   for each plate (route `"image_edit_chain_plate"`), mirroring the merged frame's fields:
   `prompt`, `provider`, `model`, `timestamp`, `action`/`action_id`, `step`/`of`, `pose`,
   and `plate_color` (the plate's own colour, `#FFFFFF` or `#000000`).
2. **Session-start-failure line routed through `emit`.** Previously called `log(...)`
   directly, then `logger.warning(...)` separately — a raising console sink there would
   propagate and abort `edit_chain` before any frame was rendered. Replaced both calls
   with one `emit(logger, log, "...", level="warning")`, matching `_common.emit`'s
   documented contract ("a sink that raises never breaks generation; the failure goes to
   DEBUG") and the file's `log_request`/`log_response` convention.
3. **Honest matte provenance.** In matte mode the merged frame's sidecar
   `reference_images[1]` previously cited `outputs[-1]` (the previous step's *merged*
   RGBA), but the chain actually feeds the previous step's *white plate* bytes into the
   next step's `edit_image` refs (`next_bytes = step_images[MATTE_PLATES[0]]`). Added a
   `prev_reference_path` variable, seeded to `character` and updated each step to the
   white plate's path in matte mode (`out_png` in non-matte mode, where it was already
   correct — `next_bytes` there equals the merged frame's own bytes). The sidecar now
   cites the true source.

### Tests added/extended

- `test_edit_chain_matte_pairs`: extended to assert both plate `.json` sidecars exist,
  assert their `plate_color`/`step`/`of`/`provider`/`model`/`prompt` fields, and assert
  frame 2's sidecar `reference_images[1]` ends with `0001.white.png` (not the merged
  `0001.png`).
- `test_edit_chain_session_failure_survives_raising_log_sink` (new): a `log` sink that
  raises specifically on the session-start-failure message text must not abort the chain
  (`len(out) == 1`, `reset_edit_session` still not called since the session never
  started). First draft matched on the substring `"session"`, which coincidentally also
  matched the unrelated raw `log("...step 1/1 saved: .../<tmp_path>/chain/0001.png")`
  call at the end of the loop — pytest derives `tmp_path` from the test's own function
  name (`test_edit_chain_session_failur1`), which itself contains "session". Fixed by
  matching the exact message string instead of a substring; documented here rather than
  silently reworked, since it briefly surfaced that the loop's per-step `log(...)` call
  is *also* a bare (non-`emit`) sink call — out of this fix round's declared scope
  (limited to the session-start-failure line), left as-is, flagged for awareness.

### Gate

Command: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_image_route.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -q -p no:cacheprovider`

```
........................                                                 [100%]
24 passed in 5.40s
```
Pristine, no warnings.

Also re-ran the sibling suite (module has other tests under `tests/sprite/`):
`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite -q` →
`782 passed, 2 warnings in 126.68s` (782 vs. the prior round's 769 — the concurrent
`retouch.py` implementer's tests landed in between; the same 2 pre-existing
`google._upb._message` `DeprecationWarning`s in
`tests/sprite/gui/test_main_window_sprite_wiring.py`, a file this task never touched).

`grep -n "PySide6\|PyQt" core/sprite/generation/image_route.py tests/sprite/test_image_route.py`
→ no matches (exit 1).

### Files changed (fix round)

- `core/sprite/generation/image_route.py`
- `tests/sprite/test_image_route.py`

Commit: `b2a76c2` — "fix(sprite): matte-plate sidecars, emit-routed session warning,
honest matte provenance"

### Working tree hygiene

`git status --porcelain` before and after `git add` confirmed only the two files above
were staged; the unrelated deleted root `*.md` files, untracked `Notes/*.md`,
`feature-documenter.skill.zip` were left untouched. No `gui/sprite/*` files from the
concurrent `retouch.py` implementer appeared as pending changes at commit time (that work
had already landed separately) — nothing of theirs was touched or staged by this round
either way.

### Concerns

None blocking. The single flagged-but-out-of-scope item: the per-step `log(...)` call
inside the main loop (`"[image route] step {k}/{frames} saved: ..."`) is still a bare,
non-`emit`-routed sink call, same as it was before this fix round and same as several
other bare `log(...)` calls elsewhere in the file (`generate_sheet`,
`slice_generated_sheet`) that predate this task entirely. A raising console sink there
would still abort `edit_chain` after the session-start-failure path. This was outside the
three declared fix items; noting it for a future pass rather than expanding scope
unilaterally.
