# Fix wave D report — GUI busy guards (fix-ir-D)

**Date:** 2026-08-30
**Owner:** fix-ir-D
**Scope:** Important 7, Important 8, M9 (fix-now), Minor 5, Minor 6
**Files owned and touched:** `gui/sprite/image_route_dialog.py`, `gui/sprite/retouch_wiring.py`,
`tests/sprite/gui/test_image_route_dialog.py`, `tests/sprite/gui/test_retouch_dialog.py`.
No file outside that list was read for edit or modified. No git command ran.

---

## What changed per finding

### Important 7 — "Render (image)" has no busy guard (`gui/sprite/image_route_dialog.py`)

`open_image_route_dialog` now refuses while the processing panel runs, in the exact shape of
`gui/sprite/frames_workspace.py:322-327`. The guard sits directly after the `project is None`
check:

- `panel = tab.frames_workspace.panel`; `label = panel.busy_label or "processing"`.
- `logger.warning("Image route refused: the %r job is still running", label)` — the file logger.
- `tab.console.log(f"Wait for the running {label} job to finish before rendering", "WARNING")` —
  the console. The surrounding code in this module uses `tab.console.log`, so the guard matches it.
  A user-facing refusal is both logged and shown.
- `return None` — no dialog is constructed, so no worker can start.

A comment above the guard states the hazard (the render renames the extract directory aside,
clears the clip, rewrites `action.frames` and runs a second pipeline against a project no lock
guards; on Windows the rename raises `PermissionError`).

The real `FramesWorkspace` creates `self.panel = ProcessingPanel()` at
`gui/sprite/frames_workspace.py:56` and assigns itself to `tab.frames_workspace` at `:63`, so the
attribute the guard reads always exists on the real tab. The guard reads it at click time, not at
install time, so `install_image_route`'s registration order is irrelevant.

### Important 8 — frame-strip "Retouch…" (`gui/sprite/retouch_wiring.py`), both halves

**(a) busy guard.** `open_retouch_dialog` refuses while `tab.frames_workspace.panel.is_busy()`,
same shape, message "Wait for the running {label} job to finish before retouching", logged through
the module logger and written to `tab.console`. The guard runs *before* `tab.current_action()` and
the index validation on purpose: a pipeline that has already dropped the frame would otherwise
report "select a frame first", which names the wrong cause. The existing refusal messages and their
log lines are unchanged.

**(b) stale index.** `apply_retouch` re-validates `0 <= index < len(action.frames)` before it
copies the list. On a stale index it logs a WARNING through the module logger, writes
`"Retouch not applied: frame N no longer exists on '<action>'."` to the console, and returns.
`IndexError` can no longer escape the Qt slot. The docstring records why (`QDialog.exec()` blocks
user input but still delivers queued events, so the pipeline can shorten `action.frames` under a
modal dialog).

### M9 (fix-now) — no undo snapshot for a non-current action (`gui/sprite/image_route_dialog.py`)

The module-level `_on_rendered` no longer branches on `tab.current_action()`. Every render now
takes the same three steps, in the order deviation 12 requires:

1. `rendered = list(action.frames)` — the list the worker wrote.
2. `action.frames = list(dialog.frames_before)` — the pre-render list is restored **first**, so the
   snapshot `apply_frames` pushes holds the frames as they were before the render.
3. `tab.frames_workspace.apply_frames(action.id, rendered, "Render (image)")`.

The caller contract holds: `rendered` is a new list, and it shares no `FrameMeta` object with the
snapshotted list (`dialog.frames_before` is the deep copy `start_render` took), so nothing the
snapshot captures is mutated in place. `apply_frames` already handles the non-current case itself
with `reload=False` (`frames_workspace.py:290-291`), so the strip and the player still follow only
the selected card; the unselected path costs one extra save and one extra `projectChanged` emit.
The docstring records the reachability argument and that cost.

`test_rendered_for_another_action_only_refreshes_status` encoded the old shape and is replaced by
`test_rendered_for_another_action_still_snapshots_that_action`, which asserts the snapshot is
pushed for the rendered card and that the selected card's own frames stay empty.

### Minor 5 — `billed_units` had no direct test

Three direct unit tests, no dialog and no Qt object involved:

- `test_billed_units_sheet_route_bills_only_a_returned_sheet` — the sheet branch, both readings of
  `sheet_done` (0 and 1).
- `test_billed_units_doubles_every_step_in_matte_mode` — the matte-doubling branch (4 for two
  finished steps).
- `test_billed_units_counts_only_finished_steps_after_a_partial_failure` — the partial-failure case:
  two `NNNN.png` steps beside a `.white.png`/`.black.png` plate pair count 2, and a directory that
  was never created counts 0.

A shared `_chain_dir` helper builds the extract directory these read. `billed_units` itself is
unchanged.

### Minor 6 — the archive same-second collision loop was unreachable

`test_archive_existing_frames_serializes_a_same_second_collision` freezes the clock
(`monkeypatch.setattr(ird, "datetime", SimpleNamespace(now=lambda: frozen))`), archives a populated
extract directory twice inside the frozen second, and asserts the two archive names are
`extracted.prev-20260830-120000` and `extracted.prev-20260830-120000-2`, that both archives keep
their PNG, and that the live directory is gone. `archive_existing_frames` itself is unchanged.

### Follow-up — `billed_units` docstring accuracy after fix-ir-C landed

The controller added one item after fix-ir-C committed the Important 6 fix
(`d51c164`). I verified the landed core code before I reworded anything:
`core/sprite/generation/image_route.py:324-326` builds `plates_dir = out_dir / "plates"` and
saves `NNNN.white.png` and `NNNN.black.png` there.

The old docstring claimed the plates keep a non-numeric stem *inside the extract directory*,
which is no longer the mechanism. The reworded docstring states the real one, in four short
sentences:

- `edit_chain` writes one `NNNN.png` per finished step into `extract_dir`.
- `edit_chain` writes the two matte plates into `extract_dir/plates` instead.
- The glob is not recursive, so it never reaches those plates.
- The `path.stem.isdigit()` filter stays as a defensive guard, and it keeps the count right
  for an older project directory whose plates still sit beside the frames.

`billed_units`' behaviour is unchanged: the `isdigit()` filter is still in the code, and no
statement in the function body was touched. No core file was read for edit or modified.
The `tests/sprite/gui` gate was re-run after this edit and after C's core commits (below).

### Follow-up 2 — the lost-render path is closed (controller item 1)

Concern 1 of the first report is now fixed in code. `_on_rendered` tests findability **before**
the destructive swap, mirroring `FramesWorkspace._find_action`
(`frames_workspace.py:133-137`) rather than calling into it:

```
rendered = list(action.frames)
project = tab.current_project
known = project is not None and any(a.id == action.id for a in project.actions)
```

- **Known card** — unchanged from the M9 fix: restore `dialog.frames_before`, then
  `apply_frames(action.id, rendered, "Render (image)")`. The snapshot still holds the
  pre-render list, so deviation 12's ordering is intact.
- **Unknown card** — no swap. `action.frames` keeps the list the job wrote, so the paid render
  stays on the card and matches the PNGs on disk. The module logger records an ERROR with the
  action id and name, and the console gets
  `"Rendered frames kept for '<name>', but no undo snapshot was recorded: the card is not in the
  open project."` at ERROR level. A paid render is never discarded silently.

`gui/sprite/frames_workspace.py` was not touched.

New test:
`test_rendered_for_an_action_the_project_does_not_hold_keeps_the_frames` renders a card whose id
is absent from `project.actions`, then asserts `apply_frames` is never reached, that
`action.frames` still holds the rendered frames, and that an ERROR line naming the missing undo
snapshot reaches the console.

Two `_FakeTab` changes support it: `current_project.actions` is now a real list seeded from the
tab's action (and `track()` appends to it as well as to `known`), and `_apply_frames` answers an
unknown id the way the real `apply_frames` does — it records the call and returns without
installing, instead of raising `KeyError`. The second change keeps the reversion check honest:
the reverted code fails on the frames assertion, not on an incidental `KeyError`.

**Reversion check.** Replacing the whole `known` branch with the unconditional
restore-then-`apply_frames` pair makes
`test_rendered_for_an_action_the_project_does_not_hold_keeps_the_frames` **FAIL** (the card is
left holding the empty pre-render list). The same mutation leaves
`test_rendered_for_another_action_still_snapshots_that_action` **passing**, which is the intended
control: the guard changes only the unknown-card path and leaves the M9 behaviour exactly as it
was. Script: `<scratchpad>/revert2.py`.

#### Note on the "item 1 is still open" round

The controller reported `_on_rendered` unchanged and a count of 275. The cause was a stale read of
**committed HEAD**, not a missing edit. The contract forbids me to commit, so my work lived only in
the working tree; at that moment HEAD was `d51c164` (fix-ir-C's core wave), which cannot contain it.
The guard and its test were already on disk and already verified.

Evidence gathered in that round, then re-verified from scratch:

- `gui/sprite/image_route_dialog.py:396-406` holds the `known` branch; the new test sits at
  `tests/sprite/gui/test_image_route_dialog.py:340`.
- Fresh reversion check (`<scratchpad>/revert3.py`), run in three steps against the live file:
  `guard present on disk: yes` → replace the whole `known` branch with the unconditional
  restore-then-`apply_frames` pair → `REVERTED -> FAILS (required) | 1 failed in 14.30 s` → restore
  the file byte for byte → `RESTORED -> PASSES (required) | 1 passed in 9.47 s`.
- Gate re-run: `tests/sprite/gui` **276 passed**, 2 warnings, 85.28 s;
  `tests/test_no_hardcoded_paths.py` **3 passed** in 2.63 s. The count is 276, not 275.

The controller committed all four owned files as **`dd48719`** ("fix(sprite-gui): busy guards for
the image route and retouch; undo snapshot for any card") during that verification run.
`git show HEAD:gui/sprite/image_route_dialog.py` carries the guard at line 399, so the committed
tree matches what this report describes. No further code change is needed for item 1.

### Follow-up 3 — `billed_units` docstring (controller item 2)

Already applied and still in place; see "Follow-up — `billed_units` docstring accuracy after
fix-ir-C landed" above. The current text at `gui/sprite/image_route_dialog.py:57-68` states that
`edit_chain` writes the plates into `extract_dir/plates`, that the glob is not recursive, and that
`path.stem.isdigit()` stays as a defensive guard. The `isdigit()` check is still in the code at
`:76` and no statement in the function body changed. Nothing further was needed for this item.

---

## Interaction with fix-ir-C's plates-directory move

`billed_units` counts finished edit-chain steps as `*.png` files in the extract directory whose
stem is all digits. fix-ir-C moved the `NNNN.white.png` and `NNNN.black.png` plates out of the
extract stage directory into a `plates` subdirectory (landed as `d51c164`), so the non-recursive
glob no longer reaches them at all. The section below was written before that commit landed and is
unchanged; the docstring now states the post-C mechanism (see the follow-up above).

- **Nothing in this wave depends on where the plates land.** I did not change the digit-stem filter,
  and the guards, the M9 fix and the archive test never look at plate files.
- After C lands, the digit-stem filter becomes *redundant in production* — the extract directory
  will hold only `NNNN.png` — but it stays **correct**, and it stays the only thing that keeps the
  count right for any older project directory that still holds plates from a render made before C's
  change. It also stays correct if `glob("*.png")` ever sees a non-frame artifact again. My
  recommendation is to keep it; simplifying it would drop a guard that costs nothing.
- My test `_chain_dir` deliberately puts a `.white.png`/`.black.png` pair in the directory. After
  C's change that layout no longer occurs on a fresh render, so the test reads as a regression guard
  on the filter rather than as a model of the current on-disk layout. It passes either way, and it
  does not constrain C's choice of directory. The pre-existing
  `test_partial_edit_chain_failure_records_the_paid_steps` writes a `0002.white.png` for the same
  reason and is likewise unaffected.
- Deferred triage row (a) — `billed_units` under-counts a matte step that dies between its two plate
  calls — is unchanged by either wave and stays deferred.

---

## Reversion check per new test

Each check mutated exactly one source construct, ran only the covering test, and restored the file
byte for byte. Script: `<scratchpad>/revert_check.py` (outside the repo).

| Test | Source mutation | Result |
|---|---|---|
| `test_image_route_is_refused_while_the_processing_panel_runs` | busy guard block deleted from `open_image_route_dialog` | FAILED as required |
| `test_retouch_is_refused_while_the_processing_panel_runs` | busy guard block deleted from `open_retouch_dialog` | FAILED as required |
| `test_apply_retouch_ignores_an_index_the_pipeline_dropped` | bounds check deleted from `apply_retouch` | FAILED as required (`IndexError`) |
| `test_rendered_for_another_action_still_snapshots_that_action` | `_on_rendered` restored to the old current-action-only branch | FAILED as required |
| `test_billed_units_sheet_route_bills_only_a_returned_sheet` | `return 1 if sheet_done else 0` → `return 0 if sheet_done else 1` | FAILED as required |
| `test_billed_units_doubles_every_step_in_matte_mode` | `return steps * (2 if matte else 1)` → `return steps` | FAILED as required |
| `test_billed_units_counts_only_finished_steps_after_a_partial_failure` | `if path.stem.isdigit()` filter dropped | FAILED as required |
| `test_archive_existing_frames_serializes_a_same_second_collision` | `serial = 2` + `while archive.exists():` loop deleted | FAILED as required |

Script tail: `ALL DISCRIMINATING`. Both source files were verified restored, and the full gate below
ran against the restored tree.

---

## Test-shape notes

- **Real gated worker, no fixed sleep.** `_gated_panel` (one copy per test module, they must not
  import each other) builds a **real `ProcessingPanel`** and starts a **real `SpriteWorker`** on it
  through `WorkerHost.start_job`. The job sets an `entered` `threading.Event`, then blocks on a
  `gate` `threading.Event` with a 10 s bound. `available_backends` is monkeypatched so the panel's
  constructor does not probe the ML backends. `panel.is_busy()` and `panel.busy_label` are the real
  `WorkerHost` implementations, never stubs.
- **No thread survives a test.** Each busy test releases the gate in a `finally`, asserts
  `worker.wait(10000)`, pumps `qapp.processEvents()` five times so the queued release event is
  delivered, and asserts `panel.shutdown()` returns True. Each then asserts the guard *lifts*
  (`open_*` returns a dialog once the panel is idle), so the tests cannot pass on a blanket refusal.
- **No `MainWindow`.** Both test modules keep their existing `_FakeTab(QWidget)` surfaces. Each grew
  a `panel` keyword (default: a tiny `_IdlePanel` that answers `is_busy() is False`) and a
  `log_calls` list so the console line can be asserted; the previously silent
  `console.log` lambda is now a recording method.
- `test_image_route_dialog._FakeTab` also grew `known` + `track(action)`, because the M9 fix routes
  an unselected card through `apply_frames` and the old `_apply_frames` stub assumed the current
  action was always the target.
- `Image.fromarray(arr)` is called without a mode argument everywhere in both files (unchanged).

---

## Gate

```
QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/sprite/gui -q -p no:cacheprovider
........................................................................ [ 26%]
........................................................................ [ 52%]
........................................................................ [ 78%]
...........................................................              [100%]
=============================== warnings summary ===============================
tests/sprite/gui/test_main_window_sprite_wiring.py::test_video_tab_declares_and_main_window_connects_the_signal
  <frozen importlib._bootstrap>:488: DeprecationWarning: Type google._upb._message.MessageMapContainer uses PyType_Spec with a metaclass that has custom tp_new. This is deprecated and will no longer be allowed in Python 3.14.
tests/sprite/gui/test_main_window_sprite_wiring.py::test_video_tab_declares_and_main_window_connects_the_signal
  <frozen importlib._bootstrap>:488: DeprecationWarning: Type google._upb._message.ScalarMapContainer uses PyType_Spec with a metaclass that has custom tp_new. This is deprecated and will no longer be allowed in Python 3.14.
275 passed, 2 warnings in 80.31s (0:01:20)
```

```
QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/test_no_hardcoded_paths.py -q -p no:cacheprovider
3 passed in 2.78s
```

268 → 275 tests: 7 added, 1 flipped in place, 0 removed.

**Re-run after fix-ir-C's core commits and the docstring follow-up** (HEAD `d51c164`):
`tests/sprite/gui` **275 passed, 2 warnings in 83.26 s**. The counts and the warnings are
identical, so C's plates move breaks nothing in this slice.

**Re-run after the lost-render guard** (follow-up 2): `tests/sprite/gui` **276 passed, 2 warnings
in 81.61 s** (one test added), and `tests/test_no_hardcoded_paths.py` **3 passed in 2.76 s**. The
two warnings are the same pre-existing third-party protobuf ones.

**The two warnings are pre-existing and third party.** They come from the protobuf C extension
imported by `tests/sprite/gui/test_main_window_sprite_wiring.py`, a file this wave does not touch,
and the final review recorded the same two warnings for the full suite at HEAD `4567f8a`. No test in
either file I own emits a warning: the two owned modules run clean
(`test_image_route_dialog.py` + `test_retouch_dialog.py`: **33 passed in 11.16 s**, 0 warnings).

---

## Files changed

- `/mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/image_route_dialog.py`
- `/mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/retouch_wiring.py`
- `/mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_image_route_dialog.py`
- `/mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_retouch_dialog.py`

Nothing was staged or committed. Leland's unrelated working-tree items (deleted root `*.md`,
untracked `Notes/*.md`, modified `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`) were not touched.

---

## Concerns

1. ~~**`_on_rendered` now depends on `apply_frames` finding the action.**~~ **CLOSED** by
   follow-up 2 above: `_on_rendered` tests findability before the destructive swap, keeps the
   rendered frames when the project does not hold the card, and reports the missing undo snapshot
   as an ERROR on both sinks. Covered by
   `test_rendered_for_an_action_the_project_does_not_hold_keeps_the_frames`.
2. **`deleteLater` is still absent from both dialogs (5b Minor 4 / Minor 3).** Left deliberately, per
   the triage `defer` ruling and the brief. Minor 1 (the four bare `log()` progress lines in
   `core/sprite/generation/image_route.py`) must be fixed in the same wave as any future
   `deleteLater`, or an orphan's bare `log()` raises `RuntimeError` on a deleted QObject.
3. **Two `_gated_panel` copies and two `_IdlePanel` copies**, one per test module. Test modules in
   `tests/sprite/gui/` do not import each other, and moving either helper into `conftest.py` would
   change a shared file I do not own. If the controller wants them shared, that is a conftest edit
   for a later wave.
4. **Both busy guards read `tab.frames_workspace.panel` without a `getattr` fallback.** That is
   deliberate — it matches `FramesWorkspace.open_export_dialog`, and the attribute is created in
   `FramesWorkspace.__init__` — but it means any future tab double that omits `frames_workspace` or
   `panel` fails with `AttributeError` instead of silently skipping the guard. A silent skip would
   be worse.
5. **Sub-project 7's CLI does not go through either entry point**, so neither busy guard protects a
   CLI render that runs while the GUI pipeline runs. Nothing in this wave can close that; it belongs
   with sub-project 7's own concurrency story.
