# Task 9 report: Retouch dialog + frame-strip wiring

## Implemented
- `gui/sprite/retouch_dialog.py` — `RetouchDialog(DialogCleanupMixin, QDialog)`: instruction text
  box, provider combo (google/openai), model line edit, region label + "Clear region" button,
  neighbor list, `DialogStatusConsole`. `build_job()` closes over the dialog's current field
  values and returns a `job(progress, token)` callable that calls `retouch_frame` through the
  dialog's `provider_factory`. `start_retouch()` refuses an empty instruction or a second
  concurrent run, then starts a `SpriteWorker` and wires progress/finished/failed/cancelled to
  the console and to `retouched = Signal(object)`. `on_dialog_close()` cancels and bound-waits
  (2000ms) any running worker — the dialog owns a single `SpriteWorker` directly (not the
  `WorkerHost` mixin), so this mirrors `export_dialog.py`'s cancel + bounded join without the
  orphan-tracking machinery that `WorkerHost` needs for multiple sequential jobs.
- `gui/sprite/retouch_wiring.py` — `open_retouch_dialog(tab, index, *, exec_dialog=True)` reads
  the current action and frame, collects existing neighbor frames (skipping missing indices/
  None source_path), reads the region from `tab.pixel_view.selection_rect()`, builds the dialog
  with `tab.make_provider` as the provider factory, and connects `retouched` to `apply_retouch`.
  `apply_retouch(tab, action, index, new_path)` deep-copies `action.frames`, repoints the one
  frame's `source_path`, and calls `tab.frames_workspace.apply_frames(action.id, frames, label)`.
  `install_retouch(tab)` connects `tab.frame_strip.retouchRequested` to `open_retouch_dialog`.
- `gui/sprite/sprite_tab.py` — added `from gui.sprite.retouch_wiring import install_retouch` and
  one call, `install_retouch(self)`, as the last statement of `SpriteTab.__init__` (after
  `FramesWorkspace` is built, so `frame_strip`/`pixel_view`/`frames_workspace` already exist).
- `tests/sprite/gui/test_retouch_dialog.py` — 8 tests per the brief (dialog build/region/
  shortcut state, `build_job()` argument passthrough, synchronous worker success/failure,
  empty-instruction guard, `apply_retouch` copy-and-repoint semantics, `open_retouch_dialog`
  neighbor/region/factory collection plus the out-of-range `None` case, `install_retouch` signal
  wiring).

## Deviations from the brief's prototype (both self-initiated, both verified against actual
callee behavior read at HEAD)

1. **`apply_retouch` does not call `project.save()`.** The brief's Step 3/4 prototype text called
   `project.save()` after `apply_frames()`. Reading `gui/sprite/frames_workspace.py:273-293` at
   HEAD (5b, past the plan) shows `FramesWorkspace.apply_frames` already calls
   `self.tab.save_current_project()` (the public autosave, confirmed at `sprite_tab.py:325-332`)
   and emits `projectChanged()` internally. Calling `project.save()` a second time from the
   wiring layer would be a redundant direct call bypassing the tab's public autosave path for no
   benefit. I dropped it and documented why in `apply_retouch`'s docstring. No test exercises
   this path directly (the fake tab's `current_project.save` lambda is simply unused now); all
   dispatched facts and the read source agree this is correct.
2. **Test fixture PNG helper drops the deprecated `mode` argument.** The brief's test code used
   `Image.fromarray(arr, "RGBA").save(path)`, which raises `DeprecationWarning: 'mode' parameter
   is deprecated` (Pillow 13, 2026-10-15) — 24 warnings across the 8 tests, violating the
   contract's "test output pristine (no warnings)" self-review rule and the dispatch's own fact
   ("use `Image.fromarray(arr)` without the deprecated mode argument"). Changed to
   `Image.fromarray(arr).save(path)`; PIL infers `RGBA` correctly from the `(16,16,4)` uint8
   array (verified with a standalone interpreter check). Zero warnings after the fix.

Both are the only points where the transcribed code needed to diverge from the brief's literal
text; every interface name, signature, and file path matches the brief exactly.

## Note on brief text
Step 6 says "9 new tests pass"; the brief's own Step 1 code block contains 8 test functions. All
8 pass — this looks like an off-by-one in the brief's prose, not a missing test.

## Tests

```
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
  /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_retouch_dialog.py -v
```
```
8 passed in 10.06s
```
(no warnings)

```
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
  /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -q
```
```
3 passed in 3.18s
```

```
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
  tests/sprite/gui/test_sprite_tab_smoke.py tests/sprite/gui/test_sprite_tab_integration.py -v
```
```
40 passed in 12.86s
```

Full `tests/sprite` sweep (required: this task modified `sprite_tab.py`, which many other
`tests/sprite/` files exercise):
```
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
  tests/sprite -q
```
```
790 passed, 2 warnings in 119.61s (0:01:59)
```
The 2 warnings are pre-existing and unrelated to this task: `DeprecationWarning: Type
google._upb._message.{MessageMapContainer,ScalarMapContainer} uses PyType_Spec with a metaclass
that has custom tp_new` from the `google` protobuf import chain, not from any file this task
touched.

## Files changed
- `gui/sprite/retouch_dialog.py` (new)
- `gui/sprite/retouch_wiring.py` (new)
- `gui/sprite/sprite_tab.py` (modified: +2 lines — one import, one `install_retouch(self)` call
  at the end of `__init__`)
- `tests/sprite/gui/test_retouch_dialog.py` (new)

Working tree confirmed clean of the unrelated pre-existing changes (deleted root `*.md`,
untracked `Notes/*.md`, `feature-documenter.skill.zip`) before staging — `git status --short`
showed only these four files staged; nothing else was touched or committed.

Commit: `33050d1 feat(sprite): Retouch dialog (status console, Ctrl+Enter, SpriteWorker) wired to
the frame strip with undo`

## Self-review
- Names match the brief exactly: `RetouchDialog`, `retouched`, `logLine`, `build_job`,
  `start_retouch`, `cancel_retouch`, `clear_region`, `result_path`, `install_retouch`,
  `open_retouch_dialog`, `apply_retouch` — all present with the specified signatures.
- Mixin order is `(DialogCleanupMixin, QDialog)` as required.
- Console writes from the worker thread go only through `logLine.emit` (connected once, in
  `__init__`, to `self.console.log`) — never a direct `self.console.log` call from inside `job()`.
- No overbuilding: no extra buttons, no extra dialog state beyond what the brief's interfaces
  list requires.
- `retouch_frame`'s contract (never overwrites raw frames, writes `NNNN.r<k>.png`, writes its own
  `.json` sidecar via `write_image_sidecar`) is unchanged — this task calls it, does not
  reimplement it.
- No hardcoded model IDs, no dimensions/aspect/"transparent" text added to any prompt by this
  task's code (prompt text lives entirely inside `retouch_frame`, task 8's file).
- No hand-built data paths; `next_retouch_path`/`stage_dir`-style logic is entirely inside task
  8's `retouch.py`, untouched here.

## Concerns
None. Both deviations are narrow, justified by reading the actual callee source at HEAD (facts
given in the dispatch matched what the code does), and improve on the brief's literal prototype
without changing any documented interface, signature, or test expectation.

---

## Fix round (review finding: Important, FIX)

Review found one plan-mandated Important, three parts:

1. **`on_dialog_close` could drop a running worker.** The original implementation held a bare
   `self._worker: Optional[SpriteWorker]` and did `cancel(); wait(2000); self._worker = None`
   unconditionally on close — if the job hadn't finished within 2 seconds, that line drops the
   only reference to a still-running QThread parented to the dialog being torn down. A running
   QThread destroyed with its host aborts the process.
2. **`retouch_frame` never polled a cancel token**, so cancel could not take effect during a
   provider call or the retry loop.
3. Missing tests: a real close-while-busy test, and a pre-cancelled-token test for `retouch_frame`.

### Fix — chosen shape

**Converted `RetouchDialog` to mix in `WorkerHost`** (`class RetouchDialog(WorkerHost,
DialogCleanupMixin, QDialog)`), matching `gui/sprite/export_dialog.py`'s `ExportDialog` exactly,
rather than hand-rolling orphan tracking around the dialog's bare `SpriteWorker`. This was the
right shape because `WorkerHost`'s orphan machinery (`shutdown()` → `_adopt_orphan()` →
`_reap_orphan()` → `_on_worker_idle()`) already solves exactly this problem and is exercised by
`tests/sprite/gui/test_sprite_worker.py`; re-implementing a smaller version of it in the dialog
would duplicate logic the codebase already trusts.

- `gui/sprite/retouch_dialog.py`: `start_retouch()` now calls `self.start_job(...)` (was: manual
  `SpriteWorker(...)` construction + four manual `.connect()` calls); `cancel_retouch()` calls
  `self.cancel_running()`; `is_busy()` replaces the `self._worker is not None` check.
  `on_dialog_close()` mirrors `ExportDialog.on_dialog_close` exactly: bounded
  `shutdown(timeout_ms=CLOSE_SHUTDOWN_TIMEOUT_MS)` (5000ms, same constant name/value as
  `export_dialog.py`), falling back to unbounded `join_orphans()` only if that times out — never
  drops the worker either way. Added the `_on_worker_idle()` hook (per the original task-9
  dispatch's own guidance: "If you subclass WorkerHost, override `_on_worker_idle` and never write
  `self._worker`") to reset the run/cancel button state if an orphan finishes after the dialog
  would otherwise have looked idle-but-stuck.
- `core/sprite/generation/retouch.py`: added `token: Optional[CancelToken] = None` to
  `retouch_frame`, checked immediately before each attempt and immediately after that attempt's
  provider call — same convention and wording as `make_chroma_plate`
  (`core/sprite/generation/plate.py:33-35`) and `generate_action_cards`
  (`core/sprite/generation/action_cards.py:277`). Backward compatible (keyword-only, defaults to
  `None`, existing callers unaffected). `RetouchDialog.build_job()`'s `job()` closure now passes
  `token=token` through to `retouch_frame`.

### Tests added

- `tests/sprite/test_retouch.py::test_retouch_frame_honors_pre_cancelled_token` — a pre-cancelled
  `CancelToken` raises `Cancelled` before any provider call (mirrors
  `tests/sprite/test_image_route.py::test_generate_sheet_honors_cancel_token`); asserts both
  `provider.edit_image` and `provider.edit_image_region` were never called.
- `tests/sprite/gui/test_retouch_dialog.py::test_close_while_busy_joins_running_worker` — a real
  threaded `SpriteWorker` (no `SpriteWorker.start` monkeypatch) gated on a `threading.Event`;
  closes the dialog while the job is genuinely blocked mid-call and asserts the worker is not
  dropped. This test is copied structurally from
  `tests/sprite/gui/test_export_dialog.py::test_close_during_export_joins_running_worker`,
  including both of its documented race fixes: an `entered` Event so the assertions only run once
  the worker thread has genuinely reached the gated mock (otherwise `shutdown()`'s
  `worker.cancel()` can race a not-yet-scheduled QThread into finishing near-instantly, passing
  for the wrong reason since `job()` checks the cancel token before calling `retouch_frame`), and
  scheduling `release.set()` from a `threading.Timer` started BEFORE the blocking
  `dialog.reject()` call, so the elapsed-time assertion (`>= 140ms`) actually measures
  `on_dialog_close()`'s `join_orphans()` fallback rather than the gated job's own timing
  coincidentally winning the race. Verified this test is discriminating: reverted
  `retouch_dialog.py` to the pre-fix version and confirmed the test fails (in that revision it
  fails immediately on `monkeypatch.setattr(rd, "CLOSE_SHUTDOWN_TIMEOUT_MS", ...)` because that
  attribute — and the whole `WorkerHost` surface the test exercises — did not exist yet).

### Self-inflicted bug caught before commit

My first `Edit` to `tests/sprite/test_retouch.py` used an `old_string` that (due to an earlier
`Read` call whose `limit` cut off one line I never saw) matched only the first of
`test_logs_request_and_response`'s two assert lines. The edit correctly replaced the matched
substring but left the second assert line (`assert any("response" in l for l in lines) and
any("validation" in l for l in lines)`) orphaned immediately after my newly inserted test
function, referencing an undefined `lines` name and silently truncating the original test's
coverage. Caught by running the full gate (`NameError: name 'lines' is not defined`) before
committing; fixed by restoring both assert lines to `test_logs_request_and_response` and moving
the new test cleanly after it. Final diff for that file is minimal and correct (verified with
`git diff`).

### Gate

```
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
  tests/sprite/gui/test_retouch_dialog.py tests/sprite/test_retouch.py \
  tests/sprite/gui/test_sprite_worker.py -v
```
```
42 passed in 12.05s
```
(no warnings)

```
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest \
  tests/test_no_hardcoded_paths.py -q
```
```
3 passed in 2.85s
```

### Files changed (this round)
- `gui/sprite/retouch_dialog.py`
- `core/sprite/generation/retouch.py`
- `tests/sprite/gui/test_retouch_dialog.py`
- `tests/sprite/test_retouch.py`

Working tree confirmed to contain only these four staged files before commit (`git status
--short`); Task 10's concurrently-edited `gui/sprite/sprite_tab.py` and new
`gui/sprite/image_route_dialog.py` were not touched.

Commit: `84f0bff fix(sprite): retouch close path never drops a running worker; cancellable
retouch`

### Concerns
None. Both source deviations from the original brief in the initial Task 9 pass stand as
previously documented; this round only adds the reviewed fix and its tests, with no further
deviations from the review's instructions.
