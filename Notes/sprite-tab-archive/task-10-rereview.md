# Task 10 re-review — fix round 1 (`4567f8a`)

Scope: the five Important findings of `task-10-review.md`, the declared extra fix, and
the disposition of the nine Minors. Diff reviewed:
`review-84f0bff..4567f8a.diff` (1 commit, 2 files, +309/-70).

Test run (mine, once):

```
QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest \
  tests/sprite/gui/test_image_route_dialog.py tests/sprite/gui/test_sprite_tab_smoke.py \
  tests/sprite/gui/test_retouch_dialog.py -q -p no:cacheprovider
42 passed in 12.66s
```

No warnings, no errors. `test_image_route_dialog.py` grew from 11 to 18 tests.

## Verdict per finding

**Addressed: 5 of 5 Important. Open: 0 Important.**

### Important 1 — close-while-busy → **addressed**

The dialog now inherits `WorkerHost`
(`gui/sprite/image_route_dialog.py:90`), and the class base order
`(WorkerHost, DialogCleanupMixin, QDialog)` is identical to `ExportDialog`
(`gui/sprite/export_dialog.py:268`) and to Task 9's `RetouchDialog`
(`gui/sprite/retouch_dialog.py:27`), so all three dialogs share one shape.

- `on_dialog_close` (`:335-341`) is a character-for-character mirror of
  `export_dialog.py:639-646`: `shutdown(timeout_ms=CLOSE_SHUTDOWN_TIMEOUT_MS)`, a
  `logger.warning` on the False return, then the unbounded `join_orphans()`.
- **No `self._worker` writes remain** — verified by grep over the whole file: zero
  occurrences. Every lifecycle transition goes through `start_job` / `is_busy` /
  `cancel_running` / `shutdown`. `_set_running` (`:325-329`) no longer clears the slot;
  the `if not running: self._worker = None` line is gone.
- `_on_worker_idle` is overridden (`:331-333`) to call `_set_running(False)`, which is
  the piece that re-enables the buttons after an orphan is reaped — without it the
  timeout path would leave Render disabled forever.
- The original crash is genuinely gone. `shutdown` on a timeout does
  `worker.setParent(None)` and keeps a strong reference in `_orphan_list()` +
  `_LIVE_ORPHANS` (`gui/sprite/workers.py:296-320`), so the dialog can be destroyed
  while the thread runs — the `workers.py:30-34` hazard no longer applies.

**Close-while-busy tests are race-free.** Both use a `threading.Event` gate, not a
sleep, and both establish the ordering with an event, not with timing:

- `test_close_while_a_render_runs_joins_the_worker` waits on `entered` (job is
  provably inside the provider call) before `reject()`, then releases the gate at
  +0.2 s against a 5000 ms shutdown bound — a 25x margin, and `worker.wait()` is
  correct in either order. The assertions `not dialog.is_busy()` and
  `worker.isFinished()` are deterministic consequences of `shutdown()` returning
  True, not of event delivery.
- `test_shutdown_timeout_keeps_the_worker_as_an_orphan` is the stronger test:
  the job is blocked on `gate.wait(10)`, so `shutdown(timeout_ms=1)` **cannot**
  succeed — the timeout branch is forced, not raced. It then asserts the two
  properties that matter: `dialog.is_busy()` (orphan counts as busy) and
  `worker.parent() is None` (detached, so destroying the dialog cannot destroy a
  running thread), and after `join_orphans` + `processEvents` that `is_busy()` goes
  False — which also proves the `_on_worker_idle` hook fires.
- Both clean up in `finally` with `gate.set()`, a bounded `join_orphans(10000)` and
  `worker.wait(10000)`. No thread is left running at test exit.

One consequence worth recording, correct as written: after a close, `shutdown` clears
`_worker`, so the queued `finished` event is dropped by `WorkerHost._guarded`
(`workers.py:223-234`). `_on_rendered` never runs and `rendered` never fires into a
closed dialog — no `apply_frames` against a dead widget.

### Important 2 — `gemini` → `google` config key → **addressed**

`_config_key_for` (`:346-353`) delegates to `CONFIG_KEY_BY_PROVIDER_ID`, **imported
from `action_cards_panel`** rather than re-declared, so the two cannot drift. Both
lookups now use the mapped key: `get_api_key(config_key)` (`:365`) and
`get_auth_mode(config_key)` (`:366`). The old `provider in ("google", "gemini")`
guard is gone; `auth_mode` is now fetched unconditionally, which is right — the
mapping, not a provider allowlist, is what makes the lookup correct. The panel's own
id (`"gemini"`) is still what reaches `generate_pose_instructions`, which is correct:
that is an `llm_models` provider id, not a config key.

**The reversion check holds.** `_FakeConfig` is now key-sensitive — `get_api_key` /
`get_auth_mode` return the credential only for `"google"` and `None` otherwise, and
both record into `key_reads`; `_FakeTab._llm_provider` now returns `"gemini"`, the id
`get_all_provider_ids()` actually yields. Against the pre-fix code the new test fails
three ways at once: `api_key` would be `None`, `auth_mode` would be `None`, and
`key_reads` would read `["gemini", ...]` instead of `["google", "google"]`. This is a
real regression guard, not a restatement. No import-time module swap was needed to
confirm it — the assertions are pinned to the mapped key, which the old code never
produced.

### Important 3 — live widget read on the worker thread → **addressed**

`_make_pose_fn` now reads `llm_provider()`, the mapped key, the api key and the auth
mode in its **outer** scope (`:363-366`), on the GUI thread at dialog-construction
time, and the inner `pose_fn` closes over four plain values. This matches 5a's own
precedent (`action_cards_panel.py:420-434`).

**Traced every attribute the job closure touches** — all are widget-free:

| Captured | What it is | Verdict |
|---|---|---|
| `mode`, `provider_id`, `model`, `frames`, `matte`, `typed_steps` | plain str/int/bool/list, read in `build_job` on the GUI thread | ✅ |
| `project`, `action` | `SpriteProject` / `ActionCard` data objects | ✅ |
| `factory` = `tab.make_provider` | reads `self.config` only, no widget (`gui/sprite/sprite_tab.py:253-262`); the constraints explicitly sanction calling it inside a worker | ✅ |
| `pose_fn` | now four captured values | ✅ (was the defect) |
| `log` = `self.logLine.emit` | signal emit, thread-safe, queued | ✅ |

`test_pose_fn_snapshots_the_provider_combo_on_the_gui_thread` pins it: after two
`pose_fn` calls, `tab.provider_reads` is still 1 and `key_reads` is still
`["google", "google"]`. That assertion fails on the old code (it would read 3 and 3).

### Important 4 — honest failure state → **addressed**

The generation block is wrapped in `try` with restore points captured first:
`frames_before = list(action.frames)`, `status_before = action.status`,
`clip_before = action.clip` (`:220-222`), and `action.clip = None` moved **above** the
try (`:223`).

- `except Cancelled` (`:260-270`): frames, status and clip restored, `error = None`,
  `project.save()`, re-raise. A cancel is not a failure — `status_before` is put back.
- `except Exception` (`:271-281`): frames and clip restored, `status = "failed"`,
  `error = message` (from `user_message` when present, so the card carries the same
  text the console shows), `project.save()`, re-raise. The re-raise keeps
  `SpriteWorker.run`'s `failed(user_message)` conversion intact — nothing is
  swallowed.
- The shallow `list(action.frames)` is sufficient here: the job replaces the list, it
  never mutates a `FrameMeta`, so the restored objects are the originals.
- Moving `action.clip = None` earlier is safe: `core/sprite/generation/image_route.py`
  never reads `action.clip` (grep: zero hits), and `record_actual` still sees
  `clip is None`, so no video figures reach the ledger row.

**Success path unchanged.** Frames still enter the project through the workspace:
`_on_rendered` (`:378-391`) is untouched by this diff — it restores
`dialog.frames_before` (the `copy.deepcopy` taken in `start_render`, `:294`) and calls
`tab.frames_workspace.apply_frames(action.id, rendered, "Render (image)")`, exactly
one snapshot. `test_install_image_route_registers_button_and_builds_dialog` still
asserts `tab.applied == [("a1", "Render (image)", 0, 1)]`, and
`test_sheet_job_fills_frames_and_runs_pipeline` still asserts one `record_actual` and
`upto="stabilize"`.

Two new tests cover the branches:
`test_failed_pipeline_restores_frames_and_marks_the_action_failed` (frames rolled
back, `status == "failed"`, message in `action.error`, one save) and
`test_cancelled_render_restores_status_and_bills_finished_steps`
(`status == "draft"`, `error is None`).

### Important 5 — partial-spend ledger → **addressed**

`billed_units` (`:57-71`) and `record_partial_spend` (`:74-87`) are new, small, and
correct against the real `edit_chain`:

- **The stem filter is right.** `edit_chain` writes the composed frame as
  `f"{k:04d}.png"` and the matte plates as `f"{k:04d}.white.png"` /
  `f"{k:04d}.black.png"` (`core/sprite/generation/image_route.py:275`, `:298-299`,
  `:309`). `"0002.white".isdigit()` is False, so plates are excluded and only
  completed steps are counted — which is what
  `test_partial_edit_chain_failure_records_the_paid_steps` pins by writing a
  `0002.white.png` decoy and asserting `seconds == 2.0`.
- **The count cannot include a previous run's frames**, because
  `archive_existing_frames` has already moved the whole extract directory aside
  before generation starts (`:230-233` order). This is the dependency that makes a
  directory-listing count safe; it holds.
- **Sheet route:** `1 if sheet_done else 0`, with `sheet_done = True` set only after
  `generate_sheet` returns (`:238`), so a failure inside `slice_generated_sheet` still
  bills the one call that was made.
- **No double-billing.** `recorded = True` (`:258`) is set immediately after the full
  `record_actual` and before `run_pipeline`; both except blocks are guarded by
  `if not recorded`. A pipeline failure after a successful generation therefore
  produces exactly one row — the full one. Verified both ways:
  `test_failed_pipeline_restores_frames_and_marks_the_action_failed` asserts
  `record_actual.assert_called_once()`, and the two partial tests assert the partial
  row's `seconds` and `note`.
- **Ordering detail, correct:** `record_partial_spend` runs *before*
  `action.clip = clip_before`, so the partial row is also written with `clip is None`
  and cannot inherit video provider/model/estimate defaults
  (`core/sprite/generation/cost.py:135-152`).
- `units <= 0` returns without writing a row, so a failure before any provider call
  adds no noise to the ledger.

### Declared extra fix — archive same-second collision → **minimal, but untested**

`archive_existing_frames` gained four lines: a `serial = 2` counter and a
`while archive.exists()` loop appending `-2`, `-3`, … (`:44-50`). Minimal, in scope,
and it fixes exactly the Minor 4 I raised. **It has no test** — no test in the file
references `prev-`, a serial, or a same-second re-archive;
`test_archive_existing_frames_moves_aside` is unchanged and never exercises the loop.
The loop is three lines and obviously correct by inspection, so this is a coverage
gap rather than a risk. Recorded as a Minor for final-review triage.

## Minors from the first review — disposition

**Resolved (4 of 9):**

- **M3 — no `label=` on the workers:** fixed. `label="pose steps"` (`:187`) and
  `label="image route"` (`:297`), so `WorkerHost`'s refusal warnings and
  `SpriteWorker.run`'s error lines now name the job.
- **M4 — same-second archive collision:** fixed in code (`:44-50`); see above,
  untested.
- **M5 — workers accumulate on the dialog:** fixed by the `WorkerHost` adoption.
  `_release_worker` joins, `setParent(None)`s and disconnects each finished worker
  (`workers.py:378-408`), and `_reap_orphan` calls `deleteLater()` (`:352`), so
  nothing piles up as a child of the dialog.
- **M8 — cancel/close/cancelled paths untested:** substantially fixed — three new
  tests cover the `Cancelled` job path, the close-and-join path and the
  shutdown-timeout orphan path. The `cancel_render()` slot itself is still not called
  by any test.

**Still open (5 of 9), for final-review triage:**

- **M1** — `test_sheet_job_fills_frames_and_runs_pipeline` still asserts
  `source_path`s that the real `_sync_frames` overwrites; `run_pipeline` is still a
  `MagicMock`.
- **M2** — `FrameMeta.name = f"{project.name}_{action.name}_{i:02d}"` (`:246`) is
  still discarded by `_sync_frames` (`core/sprite/pipeline.py:498`).
- **M6** — the module-level `_on_rendered` still shares its name with
  `ImageRouteDialog._on_rendered`.
- **M7** — `frames_spin` still never writes back to `action.target_frames`.
- **M9** — still no undo snapshot when the rendered action is not the current one.

## New Minor findings from this round

1. **`billed_units` under-counts a matte step that dies between its two plate calls.**
   The white plate is saved at `image_route.py:298` and the black at `:299`, but the
   composed `NNNN.png` only at `:309`. A provider failure on the black plate leaves a
   paid white-plate call with no digit-stemmed file, so that step bills 0 instead of 1.
   Worst case one uncounted call per failed render; the docstring's "finished files
   count the steps the provider already billed" is accurate for the common case and
   optimistic for this one.
2. **The archive-collision loop has no test** (see above).
3. **`cancel_render` is a silent no-op when the busy state is an orphan.**
   `is_busy()` is True for an unreaped orphan, but `cancel_running()` only touches
   `self._worker`, which `shutdown` already cleared (`workers.py:277-296`). The
   console still logs "Cancel requested" (`:302-305`). Reachable only after a
   timed-out close, so cosmetic.
4. **The failure path discards the previous status.** `status = "failed"` (`:278`)
   overwrites whatever the card had — including a good `"processed"` from an earlier
   video render — while the cancel path restores `status_before`. Defensible (the
   render did fail, and `clip` is restored so the card is recoverable), but the
   asymmetry is deliberate enough to be worth a line in the plan.

## Assessment

**Task quality:** Approved — **Reasoning:** All five Important findings are fixed at
the root rather than patched at the symptom — `WorkerHost` adoption removes every
`self._worker` write and mirrors `export_dialog`'s close path, the config key is
mapped through the panel's own imported table, the pose closure snapshots on the GUI
thread, and the failure/cancel paths restore state, mark the card honestly and record
the spend already incurred — and the new tests are genuine regression guards that fail
against the pre-fix code, with the orphan path forced rather than raced. What remains
is nine Minors (five carried over, four new), none of which affects correctness of the
success or failure paths.
