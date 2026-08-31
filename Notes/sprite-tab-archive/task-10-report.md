# Task 10 report — Action-cards "Render (image)" button + ImageRouteDialog

**Status:** DONE
**Commit:** `5c6bc95` — feat(sprite): Render (image) card action with sheet/edit-chain dialog, pose steps, and pipeline hand-off
**Branch:** `feat/sprite-tab`

## What I implemented

### `gui/sprite/image_route_dialog.py` (new)

Transcribed from the brief's verified prototype, with no code deviations.

- `ImageRouteDialog(DialogCleanupMixin, QDialog)` — `rendered = Signal(object)`, `logLine = Signal(str)`.
  Form rows: Mode (`sheet` / `edit_chain`), Provider (`google` / `openai`), Model (blank = provider
  default), Frames spin (2..24, seeded from `action.target_frames`), matte checkbox, pose-steps editor
  plus a "Generate pose steps" button. A `DialogStatusConsole` sits at the bottom of a vertical
  `QSplitter`. `bind_primary_action` maps Ctrl+Enter to `start_render`; `set_default_button` makes
  Render the default; the Close button calls `reject()` (Escape closes).
- Mode gating: `_on_mode_changed` enables the matte checkbox, the steps editor, and the steps button
  only for `edit_chain`.
- `build_job()` returns the closure the worker runs. It resolves the character from
  `project.plate_path or project.character_source` and raises `ProviderError` with a user-facing
  message when the file is missing; builds the provider through the injected factory; archives any
  prior extract directory; then either `generate_sheet` + `slice_generated_sheet`, or `edit_chain`
  with typed pose steps (falling back to `pose_fn` when the typed count does not match the frame
  count). It writes `action.frames` (`FrameMeta` per path, `duration_ms = round(1000 / fps)`), sets
  `action.clip = None` (the G9 pre-extracted entry point), records the ledger row through
  `record_actual(..., provider=, model=, seconds=)`, runs `run_pipeline(upto="stabilize")`, sets
  `action.status = "processed"`, and saves the project.
- Worker plumbing mirrors `gui/sprite/retouch_dialog.py`: a plain `self._worker: Optional[SpriteWorker]`
  (the dialog does **not** subclass `WorkerHost`, so the "never write `self._worker`" rule does not
  apply), signals connected to bound methods, and `logLine` as the only worker-thread path to the
  console (queued).
- **Close-while-busy — which pattern:** I used **`retouch_dialog.py`'s pattern**, exactly as the brief
  specifies: `on_dialog_close` cancels the worker, joins it with `wait(2000)`, and clears the slot.
  The `export_dialog.py` `shutdown()` + `join_orphans()` fallback belongs to `WorkerHost` subclasses;
  this dialog owns a single bare `SpriteWorker`, so it has no orphan list to join.
- `archive_existing_frames(extract_dir)` renames a populated directory to
  `<name>.prev-YYYYmmdd-HHMMSS` (a move, never a delete) and returns the archive path; returns `None`
  for a missing or empty directory.
- Tab wiring: `_make_pose_fn(tab)` builds the pose callable from the action-cards panel's chat
  provider plus `config.get_api_key` / `config.get_auth_mode` (auth mode only for google/gemini);
  `_on_rendered` refreshes the card status and, for the current action, restores the pre-render frame
  list before handing the rendered list to `FramesWorkspace.apply_frames` so the undo snapshot
  captures the pre-render state; `open_image_route_dialog(tab, action, *, exec_dialog=True)` guards on
  "no project open"; `install_image_route(tab)` registers the "Render (image)" card action.

### `gui/sprite/sprite_tab.py` (modified — 2 lines)

One import (`from gui.sprite.image_route_dialog import install_image_route`) and one call
`install_image_route(self)` at the end of `SpriteTab.__init__`, immediately after `install_retouch(self)`.
Nothing else in the file changed (diff verified before staging).

### `tests/sprite/gui/test_image_route_dialog.py` (new) — 11 tests

Defaults + mode toggle; sheet job (frames, durations, `clip=None`, `status="processed"`, pipeline
`upto="stabilize"`, ledger note/provider/model/unit-count, project save); edit-chain with typed steps
(matte on, plate colour, frame count); edit-chain LLM fallback when steps are missing; the
"Generate pose steps" button; `start_render` emitting `rendered` with the console line; a missing
character failing cleanly with the button re-enabled; `archive_existing_frames` moving aside;
`install_image_route` registering the button and the undo-snapshot hand-off; a render for a
different action only refreshing status; and `_make_pose_fn` passing provider/api_key/auth_mode/model.

## Deviations from the brief

One, in the test file only:

- `_png()` calls `Image.fromarray(arr)` **without** the `"RGBA"` mode argument. The brief's snippet
  passed `"RGBA"`; the dispatch's conftest facts state the mode argument must be omitted (Pillow
  removed it). Behaviour is identical — a 16x16 zero-filled RGBA array still yields an RGBA image.

No deviations in the implementation file; it is the brief's prototype verbatim.

## Surface checks done before writing code (all confirmed at HEAD `33050d1`)

- `core/sprite/generation/image_route.py` re-exports `generate_pose_instructions` from `pose_steps`
  (line 21, `# noqa: F401`), so the brief's single import block is correct.
- `record_actual` signature matches the brief: `(project, action, usd, note="", *, provider=None,
  model=None, seconds=None, estimated_usd=None)`.
- `generate_sheet` / `slice_generated_sheet` / `edit_chain` keyword names match the call sites.
- `ActionCard` has `status` (`draft | queued | rendering | rendered | failed | processed`), `error`,
  `clip`, `frames`; `FrameMeta(name, source_path, frame, ..., duration_ms)` matches.
- `ActionCardsPanel.add_card_action` / `llm_provider` / `refresh_status` exist as described.
- `Path(project.project_dir) / "clips"` follows the existing convention
  (`core/sprite/generation/queue.py:85`, `gui/sprite/queue_panel.py:241`); `clips` is a declared
  `PROJECT_SUBDIRS` entry, and `save_png` creates the parent directory.
- `ProviderError("...")` takes the user message positionally; `SpriteWorker.run` converts it to
  `failed(user_message)`.

## Tests + results

All runs in the foreground, `QT_QPA_PLATFORM=offscreen`, with
`PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python`.

**1. Task tests (Step 2 — before the implementation existed):**

```
$PY -m pytest tests/sprite/gui/test_image_route_dialog.py -q
E   ImportError: cannot import name 'image_route_dialog' from 'gui.sprite'
ERROR tests/sprite/gui/test_image_route_dialog.py
1 error in 14.24s
```

**2. Task tests (Step 5 — after the implementation):**

```
$PY -m pytest tests/sprite/gui/test_image_route_dialog.py -v
... 11 items, all PASSED
11 passed in 9.27s
```

**3. Whole sprite GUI directory** (covers the dispatch's required extras —
`test_sprite_tab_smoke.py`, `test_sprite_tab_integration.py`, `test_retouch_dialog.py`,
`test_action_cards_panel.py`):

```
$PY -m pytest tests/sprite/gui -q
261 passed, 2 warnings in 78.06s
```

The 2 warnings are pre-existing protobuf `DeprecationWarning`s raised by the google import inside
`tests/sprite/gui/test_main_window_sprite_wiring.py`; they are unrelated to this task. My own test
file's output is pristine.

**4. Path guard:**

```
$PY -m pytest tests/test_no_hardcoded_paths.py -q
3 passed in 2.62s
```

**5. Full `tests/sprite` (contract: shared module touched):**

```
$PY -m pytest tests/sprite -q
FAILED tests/sprite/test_retouch.py::test_retouch_frame_honors_pre_cancelled_token
1 failed, 801 passed, 2 warnings in 135.27s
```

The single failure is **not** mine and **not** caused by my change. It is Task 9's concurrent,
uncommitted fix round: `git status` shows `tests/sprite/test_retouch.py`,
`core/sprite/generation/retouch.py`, `gui/sprite/retouch_dialog.py` and
`tests/sprite/gui/test_retouch_dialog.py` all modified in the working tree, and the failure is a
half-written assertion in their working copy:

```
>       assert any("response" in l for l in lines) and any("validation" in l for l in lines)
E       NameError: name 'lines' is not defined
tests/sprite/test_retouch.py:171
```

I did not touch those files, as instructed. Every file in my gate is green.

## Self-review

- **Completeness vs. brief:** every produced name exists — `ImageRouteDialog` (`rendered`, `logLine`,
  `build_job`, `start_render`, `cancel_render`, `generate_steps`), `archive_existing_frames`,
  `install_image_route`, `open_image_route_dialog`. All six brief steps are done.
- **Names match the brief exactly.** Widget attribute names (`mode_combo`, `provider_combo`,
  `model_edit`, `frames_spin`, `matte_check`, `steps_edit`, `steps_btn`, `render_btn`, `cancel_btn`,
  `close_btn`, `console`, `frames_before`) are the ones the tests and the plan use.
- **No overbuilding:** the dialog file is the prototype; I added no extra features, options, or
  helpers.
- **Global constraints honoured:** no `claude-*`/`gpt-*`/`gemini-*` literal anywhere (the OpenAI model
  comes from `default_openai_edit_model()`, the Google one from `provider.get_default_model()`); no
  aspect ratio, dimensions, or "transparent" in any prompt text (this file writes no prompt text at
  all — `generate_sheet` / `edit_chain` own that); no hand-built data paths (`stage_dir` plus the
  established `project_dir / "clips"` convention); every provider/LLM call logs through the `log`
  callable into the status console; every user-facing failure is logged (`logger.error` in
  `_on_failed`); no version bump, no CHANGELOG entry.
- **Tests verify real behaviour**, not mocks of the code under test: the job closure is executed for
  real (with the *collaborator* functions patched), the widgets are exercised, and the undo
  hand-off is asserted through the recorded `apply_frames` arguments.
- **Working-tree hygiene:** staged exactly three files by explicit path; the unrelated deleted root
  `*.md`, untracked `Notes/`, `feature-documenter.skill.zip`, `.superpowers/` and Task 9's in-flight
  edits are untouched and unstaged (`3 files changed, 559 insertions(+)`).

## Concerns

None blocking. Two notes for the reviewer:

1. `tests/sprite/test_retouch.py::test_retouch_frame_honors_pre_cancelled_token` fails on the shared
   working tree right now because of Task 9's in-flight edit. It must be green again once that fix
   round commits; it is outside my task and I left it alone.
2. `_make_pose_fn` passes `auth_mode` only when the panel's provider is `google`/`gemini`, matching
   the brief. Providers that also honour an auth mode would need the same mapping the
   `ActionCardsPanel._config_key_for` helper already does; that is 5a's surface, not this task's.

---

# Fix round 1 — review rulings 1-5

**Commit:** `4567f8a` — fix(sprite-gui): image-route dialog close safety, key mapping, honest failure state, paid-step ledger
**Files:** `gui/sprite/image_route_dialog.py`, `tests/sprite/gui/test_image_route_dialog.py` (2 files, +309/-70)
`gui/sprite/sprite_tab.py` was NOT touched again; its one import + one call stand unchanged.

## What changed, ruling by ruling

### Ruling 1 — close-while-busy must never drop a running QThread

`ImageRouteDialog` now **adopts `WorkerHost`**: `class ImageRouteDialog(WorkerHost,
DialogCleanupMixin, QDialog)`, the same base order `ExportDialog` uses
(`gui/sprite/export_dialog.py:268`). Consequences:

- Every direct `self._worker` write is gone. `generate_steps` and `start_render` call
  `self.start_job(job, label=…, on_finished=…, on_failed=…, on_cancelled=…,
  on_progress=…)`; busy tests use `self.is_busy()`; `cancel_render` calls
  `self.cancel_running()`.
- `_on_worker_idle()` is overridden to re-enable the buttons when the last orphan reaps.
- `on_dialog_close` now mirrors `export_dialog.py:639-646` exactly:
  `shutdown(timeout_ms=CLOSE_SHUTDOWN_TIMEOUT_MS)`, and on a timeout it logs a warning
  and falls back to `join_orphans()`. A timed-out worker is therefore handed to the
  orphan machinery (`setParent(None)` + `_LIVE_ORPHANS` + reap on its terminal signal)
  instead of being dropped while its thread runs.
- `CLOSE_SHUTDOWN_TIMEOUT_MS = 5000`, named as in `export_dialog.py:48`.

One ordering detail the switch forced: `_set_running(True)` now runs **before**
`start_job`. With the tests' synchronous `SpriteWorker.start = SpriteWorker.run`, the
terminal signal is delivered inside `start_job`, so a `_set_running(True)` afterwards
would undo the `_set_running(False)` the finished slot already ran. `_set_running` no
longer clears `_worker` (WorkerHost owns that slot); it only sets button state.

**Tests (2, both Event-gated, release + join in `finally`):**
`test_close_while_a_render_runs_joins_the_worker` starts a real worker whose sheet call
blocks on a `threading.Event`, then closes the dialog through `reject()` (the Close
button / Escape path, which `DialogCleanupMixin.done` routes to `on_dialog_close`) and
asserts the dialog is idle and the thread finished — no crash.
`test_shutdown_timeout_keeps_the_worker_as_an_orphan` forces the timeout branch with
`shutdown(timeout_ms=1)` while the job is blocked, and asserts `shutdown` returns
`False`, the host still reports busy, and `worker.parent() is None` — the worker was
detached, not dropped. Both release the gate and `join_orphans(10000)` in `finally`.

### Ruling 2 — the `gemini` → `google` config-key mapping

`gui/sprite/image_route_dialog.py` now imports 5a's own table —
`from gui.sprite.action_cards_panel import CONFIG_KEY_BY_PROVIDER_ID` — and adds a local
`_config_key_for(provider_id)` over it, so the two cannot drift. `_make_pose_fn` maps the
panel id once and uses the mapped key for **both** `get_api_key` and `get_auth_mode`.
The generator still receives the panel's raw id (`provider="gemini"`), matching 5a's
precedent at `action_cards_panel.py:420-434`. The old
`provider in ("google", "gemini")` guard on `get_auth_mode` is gone; 5a calls it
unconditionally on the mapped key.

Import-cycle check: `action_cards_panel` imports neither `sprite_tab` nor
`image_route_dialog`, so the new import is acyclic. `tests/sprite/gui` confirms it.

**Test:** `_FakeConfig` is now key-sensitive — `get_api_key`/`get_auth_mode` return the
credentials **only** for `"google"` and `None` for anything else, and both record the key
they were asked for in `key_reads`. `_FakeTab.llm_provider` now returns `"gemini"`, the
id `get_all_provider_ids()` actually yields. `test_pose_fn_maps_the_gemini_id_to_the_google_config_key`
asserts `provider == "gemini"`, `api_key == "test-key"`, `auth_mode == "api-key"` and
`key_reads == ["google", "google"]`.

**Verified it fails on the old code.** I restored the previous `_make_pose_fn` body in
place, ran the two pose tests, and put the file back:

```
=== OLD CODE RESULT ===
FAILED …::test_pose_fn_maps_the_gemini_id_to_the_google_config_key
FAILED …::test_pose_fn_snapshots_the_provider_combo_on_the_gui_thread
2 failed in 15.32s
```

### Ruling 3 — no live-widget read from the worker thread

`_make_pose_fn` now resolves `provider`, the mapped `config_key`, `api_key` and
`auth_mode` in its **outer** scope — on the GUI thread, at dialog-construction time — and
the returned closure captures those plain values. It touches no Qt object.

**Test:** `test_pose_fn_snapshots_the_provider_combo_on_the_gui_thread` counts combo
reads. After `_make_pose_fn(tab)` the count is 1; after calling the returned `pose_fn`
twice it is still 1, and `key_reads` is still the single mapped pair.

### Ruling 4 — honest state on failure and cancel

The job body from the first generation call through `run_pipeline` is now inside one
`try`. Before it runs, the job records restore points (`frames_before`, `status_before`,
`clip_before`) and sets `action.clip = None` up front (the G9 entry point, and it also
keeps video figures off any ledger row written on the failure path).

- `except Cancelled:` restores frames, the **previous** status and the clip, clears
  `error`, saves, and re-raises — a cancel is never recorded as a failure.
- `except Exception:` restores frames and the clip, sets `status = "failed"` and
  `action.error` to the exception's `user_message` (or `str`), saves, and re-raises.
- The success path is unchanged in effect: frames are still seeded **before**
  `run_pipeline` (which the review confirmed is what makes `duration_ms` survive
  `_sync_frames`), then `status = "processed"` and one `project.save()`.

**Tests:** `test_failed_pipeline_restores_frames_and_marks_the_action_failed` makes
`run_pipeline` raise and asserts the pre-render frame list is intact, `status == "failed"`,
`error` carries the message, and the project was saved.
`test_cancelled_render_restores_status_and_bills_finished_steps` asserts
`status == "draft"` (the pre-render value) and `error is None`.

### Ruling 5 — a ledger row for provider steps already billed

Two new module-level helpers:

- `billed_units(mode, matte, extract_dir, sheet_done) -> int` — for the edit chain it
  counts the finished `NNNN.png` files in the extract directory (a matte plate's stem
  `0002.white` is not a digit, so plates never inflate the count) and multiplies by 2 when
  `matte_pairs` is on; for the sheet route it returns 1 once `generate_sheet` has returned.
- `record_partial_spend(project, action, *, mode, provider, model, units, outcome, log)` —
  writes one `record_actual` row (`seconds = units`) with a note naming the outcome, and
  echoes it to the console. It no-ops at 0 units.

Both `except` branches call it, guarded by a `recorded` flag so a `run_pipeline` failure
**after** the full row was written does not double-bill the ledger.

**Test:** `test_partial_edit_chain_failure_records_the_paid_steps` has `edit_chain` write
`0001.png`, `0002.png` and a `0002.white.png` plate before raising at step 3, then asserts
exactly one ledger row with `seconds == 2.0`, `"failed"` in the note, and the right
provider/model.

## Also fixed (declared, not requested)

Review **Minor 4** — `archive_existing_frames` used a one-second stamp, so a second render
inside the same second renamed onto an existing directory and raised a bare `OSError`
(always on Windows). It now appends `-2`, `-3`, … until the destination is free. Two lines,
on the exact path this fix round makes more robust. Review Minor 3 (worker `label=`) is
also resolved, because `WorkerHost.start_job` requires the keyword: the labels are
`"image route"` and `"pose steps"`. No other Minor was touched.

## Tests + results

All foreground, `QT_QPA_PLATFORM=offscreen`.

**The review's gate:**

```
$PY -m pytest tests/sprite/gui/test_image_route_dialog.py \
              tests/sprite/gui/test_sprite_tab_smoke.py \
              tests/test_no_hardcoded_paths.py -q -p no:cacheprovider
36 passed in 15.31s
```

Pristine — no warnings, no errors.

**Task file in detail:** 17 passed in 10.13s (11 original, all still passing; 6 new).

**Safety net, whole GUI directory** (the file is shared with sprite_tab and the new
`action_cards_panel` import could have introduced a cycle):

```
$PY -m pytest tests/sprite/gui -q -p no:cacheprovider
268 passed, 2 warnings in 82.21s
```

268 = the previous 261 plus my 7 net new tests. The 2 warnings are the same pre-existing
protobuf `DeprecationWarning`s from `test_main_window_sprite_wiring.py`.

## Self-review

- All five rulings are implemented and each has a test that exercises the real behaviour.
  Ruling 2's test is proven to fail on the old code by an actual run, not by inspection.
- No `self._worker` write survives in the dialog; `_on_worker_idle` is overridden, as the
  dispatch required for a `WorkerHost` subclass.
- Worker-thread console writes still go only through the queued `logLine` signal.
- `record_actual` is still called with the verified signature, and never with a live
  `action.clip` attached.
- Staged exactly the two files named in the dispatch. Task 9's in-flight edits to
  `retouch_dialog.py`, `retouch.py` and their tests are untouched and unstaged; the
  unrelated deleted root `*.md`, `Notes/`, the zip and `.superpowers/` are untouched.

## Concerns

None blocking. One judgement call worth flagging: `on_dialog_close` falls back to an
**unbounded** `join_orphans()`, exactly as `ExportDialog` does. If a provider HTTP call
hangs past the 5-second shutdown bound, closing the dialog blocks the GUI until that call
returns. That is the sanctioned trade in this codebase — the alternative is destroying a
running `QThread`, which aborts the process — but it is a real blocking close, and both
dialogs would need the same treatment if it is ever revisited.
