# Final whole-branch review — sub-project 5b (GUI-B)

**Reviewer:** final-gb (senior code reviewer, read-only)
**Range:** `45f9796..157b282` (17 commits)
**Date:** 2026-08-30
**Method:** read in passes — the review context, global constraints, the plan header, the Task 6 and
Task 8 interface lists, the Self-review and the 12 recorded deviations; design spec §1.1, §1.3, §1.4,
§1.5, §1.6, §2, §4.5, §4.6 and §5; then the full source portion of `review-45f9796..157b282.diff`
(undo_controller, pixel_view, preview_player, frame_strip, ml_install_dialog, processing_panel,
export_dialog, shortcuts, frames_workspace, sprite_tab, workers); then the consumed core contracts
(`core/sprite/{project,undo,pipeline,extract,presets,keying,matting,ml_install,pixelart}.py`,
`core/sprite/exporters/*.py`, `core/recycle_bin.py`, `core/package_installer.py`); then all twelve
test modules; then live offscreen probes. Five parallel verification dimensions (spec, threading,
errors, seam, tests) each ran three independent votes per finding. A finding survives only when a
majority of votes confirm it against HEAD. The working tree, index, HEAD and branches were not
modified. All line numbers cite HEAD `157b282`.

**Verification actually run (not claimed):**

| Check | Command / probe | Result |
|---|---|---|
| Full suite (controller, 2026-08-30) | `pytest` on `157b282` | **1757 passed**, 19 skipped, 2 third-party warnings, 194.7 s |
| Guard greps | QMovie / SmoothPixmapTransform / PIL in view modules; QSettings outside `prefs.py` | clean (one docstring mention of "No QMovie"; `QSettings` only in `gui/sprite/prefs.py`) |
| Import isolation | fresh interpreter, `import gui.main_window` | `gui.sprite` not imported |
| Plan test-name parity | `def test_` names in the plan (91) vs `tests/sprite/gui/*.py` (215) | 0 missing |
| Sub-project-6 seam parity | grep of every seam name in the global-constraints list | all names and signatures match byte for byte |
| Core signature parity | read every core symbol the 5b GUI imports | all exist with the stated signature; `pick_key_color` consumed by nobody (documented below) |
| Shortcut scope | `probe_focus.py`, `probe_scope_real_tab.py` (real `SpriteTab`, focus on a button / the cards table) | Space on a focused button starts playback, `clicked` never fires; Delete on the cards table drops a frame (3 → 2); G and L toggle grid / loop mode |
| Worker lifetime | `verify_leak.py`, 50 sequential `start_job` runs, `gc.collect()` | 50/50 worker wrappers and 50/50 job closures alive; referrers are the `partial` arg tuples; run-id-bound control path frees 50/50; orphan path frees |
| Export vs pipeline | `probe_export_concurrent.py`, real `FramesWorkspace`, fake pipeline that resets the stage dir | panel `Export` disabled, toolbar `Export…` enabled; export starts while busy and writes 4 frames while the pipeline ends with 6 |
| Thumbnail decode | `probe_thumb.py`, 300 512×512 PNG cells | PNG handler `supportsOption(ScaledSize)=False`; scaled read 0.431 s vs full 0.435 s; `set_frames` cold 0.503 s, warm 0.005 s |
| Helper dialog accumulation | `probe_dialog_accumulate.py`, 5 `Overrides…` + 5 `Install…` clicks | 5 `FrameOverridesDialog` + 5 `SpriteMLInstallDialog` children remain after `gc.collect()` |
| Superseded probe busy | `probe_t6_supersede_busy.py`, gated `probe_video` | live probe: `busy=False`; superseded orphan: `busy=True`, Run/Preview/Export disabled until the gate releases |
| Scales field | `probe_scales.py`, `probe_dialog.py` (real export, grid format) | `1,2,4x` and `1,2,-4` → `(1,)`; no message box; console `Export complete: 6 file(s)`; no `@2x`/`@4x` files |
| Per-frame key colour | `probe_keycolor.py`, type `green`, OK | overrides `{}`; undo pushed; no message box; no console line; one file-log warning |
| Panel key colour | `probe_keycolor2.py`, type `1E90FF`, Run + Preview | `key.key_color=None`; pipeline keys on `#FF00FF` plate; no message box; console shows only INFO/SUCCESS |
| Purge with recycle failure | `test_probe_purge_false.py`, `send_to_recycle_bin` → False | `stages/` still on disk; console `Purged 0 intermediate item(s)`; no message box; `Export complete` |
| Strip decode failure | `probe_fs/probe.py`, missing + corrupt PNG | grey placeholders; 0 log records; tooltip has no hint |
| `openUrl` False | `probe_preview_done.py` | SUCCESS line only; no warning |
| Insert into read-only dir | `probe_insert_ro.py`, `chmod 0o500` | `PermissionError` escapes the slot; no `logMessage`, no message box |
| Double decode log | `probe_double_log.py` | one ERROR (`pixel_view`) + one WARNING (`frames_workspace`) for one path |
| QSettings test order | `pytest test_export_dialog.py::test_dialog_export_runs_worker_and_emits test_export_dialog.py::test_start_export_blocked_by_grid_padding_export_grid_rejects` | **1 failed** at `:220` (`assert False`); the second test alone passes; whole file in order passes 21 |
| Minor-4 mutant | `probe_m4/test_probe_m4.py`, `reload=True` forced | repo test still passes; strip held 7 frames before `projectChanged`, 4 after |
| Deferred-delete rationale | `probe_deferred_delete.py`, `plug_bad_shape.py` (deleteLater inside `exec()`) | dialog valid after `exec()` in both shapes; the contract test passes with the "bad" shape |
| Unasserted wait | `probe_wait.py`, `wait(100)` on a 600 ms fake | failure surfaces as `isVisible()` with the thread still running |
| fps assertion | `probe_fps.py` | `100.0 fps`, `210.0 fps`, `1000.0 fps` all satisfy the assertion at `:40` |
| Tree hygiene | `git status --short`, `git rev-parse HEAD` after all probes | no changes under `gui/` or `tests/`; HEAD `157b282` |

---

## Plan/spec alignment — verdict + deviations

**Verdict: aligned on architecture and seams, with one unrecorded Important deviation (§1.5 scope), one unrecorded Minor reinterpretation (§4.5 live re-run), and one Important threading gap that the branch claims to have closed but did not.**

All nine 5b modules exist with the interfaces the plan lists. The `sprite_tab.py` seam grew only by
the Task 9 rulings (workspace-aware `shutdown`/`join_orphans`/`_worker_panels`, `save_current_project`).
`gui/main_window.py` has no commit in the range; its lazy load and close path are unchanged.

**Design §1.4 (undo)** is met end to end. Every destructive list edit in `FrameStrip` (`delete_selected`,
`duplicate_selected`, `insert_from_file`, `move_frame`, drop reorder via `aboutToReorder`,
`apply_duration`, `apply_overrides`) calls `_snapshot()` before the mutation. `FramesWorkspace.apply_frames`
snapshots before `_replace_frames`. `UndoController` defaults to depth 50, keeps one `SnapshotStack`
per action id, and reuses `FrameListSnapshot.capture`. Undo and redo use the private no-snapshot path.

**Design §1.5 (shortcuts)** is complete on keys: Space, `,`, `.`, Home, End, Delete, Ctrl+D,
Ctrl+Z/Ctrl+Y (+Ctrl+Shift+Z), `+`/`-`/`=`/Ctrl+0, G, L, Ctrl+Enter through `bind_primary_action`
on `ProcessingPanel`, `ExportDialog`, `FrameOverridesDialog`, `SpriteMLInstallDialog`, and Escape
through `DialogCleanupMixin`. The "Where" column is not met: every row binds to the tab (Important 1).

**Design §1.6 (storage, purge)** is met. The purge checkbox mirrors `prefs.purge_after_export_enabled()`,
enabling it goes through `prefs.confirm_purge`, and the purge delegates to
`SpriteProject.purge_intermediates()` only after a non-empty export. All 5b QSettings keys live under
`sprite/…` via `prefs.get_pref`/`set_pref`; splitters persist through `persist_splitter(prefs.sprite_settings(), …)`;
paths come from `get_data_paths()` or are project-relative.

**Design §4.5 (GUI rows)** are present: IconMode strip with InternalMove reorder, duplicate / delete /
insert, duration spin, per-frame overrides dialog; QTimer + QPixmap player with per-frame ms,
forward / reverse / pingpong, tag combo, slider scrub, loop-seam meter; QGraphicsView pixel view with
FastTransformation, integer zoom 1–16, grid, checkerboard; processing groups + Run pipeline in a
`SpriteWorker`; export dialog with profiles × formats, output directory, sticky confirmed purge.

**Sub-project-6 seam list** matches the contract byte for byte: `ExportDialog.register_format(id, label, fn, *,
needs_sheet, takes_template, checked)`, `format_checks`, `profile_checks`, `options_layout`, `notes_label`,
`name_template_edit`, `pivot_x_spin`/`pivot_y_spin`, `grid_options`/`set_grid_options`, `current_meta()`,
`request()`, `sheet_png_path`, `FormatFn`, the five `BUILTIN_FORMATS` ids; `FrameStrip.retouchRequested(int)`;
`PixelView.selection_rect()`; `SpriteTab.{undo_stack, frame_strip, pixel_view, preview_player,
processing_panel, frames_workspace, undo_controller, refresh_frames}`; `FramesWorkspace.apply_frames`.
The `needs_sheet` contract holds in `run_export`: `export_grid` runs once per profile before any
format callable when a selected format needs the sheet.

**All 12 recorded deviations match the code:** PixelView inside the player, `FramesWorkspace` module,
`WorkerHost` mixin, `fn(meta, out_dir)` plugin signature, region selection, `apply_frames`,
rebuild-palette = clear lock + re-run (deviation 11), toolbar `Export…` as a second entry point
(deviation 3), and the rest.

**Deviations that landed but are NOT recorded:**

1. §1.5 scopes Space/`,`/`.`/Home/End/L to the preview player, Delete/Ctrl+D to the strip, and
   `+`/`-`/Ctrl+0/G to the pixel view. `install_shortcuts` binds every row on the tab with
   `Qt.WidgetWithChildrenShortcut` (Important 1). The plan's Task 8 text states the tab-wide scope;
   the Deviations section does not.
2. §4.5 lists "live re-run of changed stages" for `processing_panel.py`. Settings edits only write
   back and emit `settingsChanged`; nothing runs until Run pipeline (Minor 1). The Self-review maps
   the line to the stage cache; the Deviations section does not record the reinterpretation.
3. The cross-plan contract table lists `core.sprite.keying.pick_key_color` as consumed by 5b. The
   eyedropper reads one pixel (`PixelView.color_at`). The plan's own Task 2 spec and tests require
   the single-pixel read, so this is a plan-internal inconsistency, not a code defect (see Refuted).

**Threading contract (§1.1):** one `SpriteWorker(QThread)` per job, worker-owned `CancelToken`,
`Cancelled → cancelled()`, no PIL/ffmpeg on the GUI thread, late events dropped by `_guarded`, panels
shut down before the project repoints, orphans pinned in `_LIVE_ORPHANS`, export dialog parented +
held + `deleteLater` after `exec()`. No path was found on which a running `QThread` is destroyed.
The gap is the opposite: a finished worker is never freed at all (Important 2), and the toolbar
`Export…` lets an export run against a project the pipeline is still mutating (Important 3).

**Repo hard rules:** every worker terminal path, purge, ML install, ffprobe, insert / export-frame
and preview decode failure is logged AND shown. Three input-validation paths break the rule at a
commit point (Important 4–6). No hand-built path. `get_data_paths()` only.

**5a carry-forwards:** 5b touched none of them. `CharacterPanel` still has no Ctrl+Enter
(`shortcuts.py:6` leaves Ctrl+Enter to each panel), queue log levels, the GUI-only-writer save
redesign, positional current-tab persistence, `getsource` wiring tests, `analyze_source` on the GUI
thread and the `_on_send_to_sprite` TypeError branch remain for 6/7. The "deleteLater on normally
finished workers" item is superseded by `fee96b5` (detach instead of delete) but the replacement has
the leak described in Important 2.

---

## Strengths

- **Undo is complete and cheap to reason about.** Snapshot-before-mutate is applied at every list
  edit, per-action stacks are keyed by id, and `apply_frames` is the single documented edit path for
  sub-project 6 ("do not push a snapshot yourself").
- **Late-event guard is closed at the source.** `WorkerHost._guarded` (`workers.py:178-188`) drops
  every signal from a worker that is no longer `self._worker`; `SpriteTab._apply_project` shuts every
  panel down BEFORE repointing (`sprite_tab.py:299-307`, `_worker_panels` includes the 5b panel).
- **The probe worker shows the correct lifetime pattern.** `processing_panel.py:811-819` binds ints
  (`probe_id`, `action_id`) into its partials; 80/80 probe workers freed under supersede-while-running
  with `gc.collect()` each round and no crash.
- **Orphan lifecycle is sound.** `_adopt_orphan` detaches, pins, wires the reaper to all three terminal
  signals and handles the already-finished race; `_reap_orphan` is idempotent.
- **Export dialog ownership is correct after Task 9.** Parented to the tab, held in `_export_dialog`
  while modal, released in `finally`, `deleteLater()` after `exec()`; `on_dialog_close` cancels and joins
  with a bounded shutdown then `join_orphans`; `FramesWorkspace.shutdown/join_orphans` reach both the
  panel and an open dialog from `SpriteTab.shutdown` and from `aboutToQuit`.
- **Every worker terminal path is logged and shown.** `_on_failed`/`_on_cancelled` in the export
  dialog and the processing panel, the ML install failure branch, `_probe_failed`; `Cancelled` maps to
  `cancelled`, never `failed`.
- **No QSettings off the GUI thread; no QSettings outside `prefs.py`.** `run_export` emits only
  `logMessage`/`progress` from the worker.
- **No double connections across project switches.** `ProfileEditor`s are rebuilt and `deleteLater`'d
  per `set_project`; `attach_pixel_view` disconnects the previous view; workspace wiring is done once.
- **Tests join real threads with bounded waits**, verify exports on disk (including `@2x` and sidecars),
  use real widgets and QTest, sandbox QSettings and data paths, and build no `MainWindow`.
  `test_close_during_export_joins_running_worker` is a genuinely discriminating join test.

---

## Issues

### Critical

None.

### Important

**Important 1 — §1.5 keys are tab-wide; Space steals every button, Delete on the cards table deletes frames**
`gui/sprite/shortcuts.py:63-64` (`QShortcut(QKeySequence(key), tab)` + `setContext(Qt.WidgetWithChildrenShortcut)`
for every row of `SHORTCUT_TABLE` at `:26-43`); `gui/sprite/frames_workspace.py:71`.
*Failure:* the user tabs to `Run pipeline` (or any of ~40 buttons and checkboxes) and presses Space:
the preview toggles play and the button never activates. The user selects a row in
`ActionCardsPanel.table` (`action_cards_panel.py:94`, a `QTableWidget`) and presses Delete:
`FrameStrip.delete_selected` (`frame_strip.py:286-295`) removes the current frame of the current action
with no feedback. G and L on the cards table toggle the grid and cycle the loop mode. Probe on the real
`SpriteTab`: button focused + Space → playing; table focused + Delete → 3 frames become 2.
*Fix:* give each `SHORTCUT_TABLE` row an owner and create the `QShortcut` on that owner with
`Qt.WidgetWithChildrenShortcut`: strip rows on `tab.frame_strip`, player rows on `tab.preview_player`,
view rows on the player + view container (deviation 2 places the view inside the player). Keep only
Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z on the tab. Add a test that a focused `QPushButton` receives Space and
that Delete on a focused table does not call `delete_selected`. `tests/sprite/gui/test_shortcuts.py`
asserts only `context()` and `parent()`, so it cannot catch this.

**Important 2 — Finished workers are never freed; the partial-in-connection cycle is invisible to the GC**
`gui/sprite/workers.py:147-173` (`partial(self._mark_terminal, worker)`, `partial(self._guarded, worker, …)`,
`partial(self._release_worker, worker)` connected to the worker's own signals); `:325-343`
(`_release_worker` joins + `setParent(None)`; the comment at `:339-341` says the worker "is freed by
Python when its last reference drops"); mirrored comment at `processing_panel.py:887-894`.
*Failure:* PySide stores the partials in C++ connection storage. The cyclic collector cannot traverse
that storage, so the cycle worker → connection → `partial.args` → worker is permanent. Probe: 50
sequential jobs, `gc.collect()`, 50/50 wrappers alive, `gc.get_referrers` shows only the partial arg
tuples. Each job leaks the finished `QThread`, the job closure (which holds `provider_cfg` /
`credentials["api_key"]` at `character_panel.py:195-204` and `queue_panel.py:198-201`, and the project),
and for exports the whole `ExportDialog` Python graph via the `log` closure and bound callbacks
(`export_dialog.py:504-512`) after `frames_workspace.py:317` has already `deleteLater()`'d its C++ side.
Commit `fee96b5` claims to close this; `test_sprite_worker.py:329-344` checks only
`findChildren(QThread) == []`, which passes. The `_reap_orphan` path (`:298`, `deleteLater` from inside
the worker's own signal delivery) does free the worker and ran 120 rounds without a crash, which
contradicts the comment at `:340-341`. Sub-project 6 adds more `WorkerHost` subclasses on this pattern.
*Fix (~20 lines in `workers.py`):* bind a per-job integer run id instead of the worker into every
partial (`self._run_id += 1`; keep `self._worker` and `self._worker_run_id`); make `_mark_terminal`,
`_guarded` and `_release_worker` resolve the worker as `self._worker if self._worker_run_id == run_id else None`.
This is the pattern `processing_panel.py:811-819` already uses. Keep `worker.wait()` + `setParent(None)`.
Disconnect the worker's signals after the release as a belt. Correct both comments. Add a weakref test:
start a job, deliver, drop references, `gc.collect()`, assert the weakref is dead.
This overrides the SYSTEMIC triage row below: the exposure is not "a self-cycle freed only by the
collector", it is a leak per job, and the fix is small and local.

**Important 3 — Export can run concurrently with a running pipeline on the same project**
`gui/sprite/frames_workspace.py:72` (`self.export_btn = tab.add_toolbar_action("Export…", …)`, never
disabled); `:294-311` (`open_export_dialog` checks only `project is None` and an already-open dialog);
contrast `processing_panel.py:613` (the panel's own button is gated on `is_busy()`).
*Failure:* the user clicks Run pipeline, then the toolbar `Export…` while the progress bar is live,
then Export. `run_pipeline` mutates `action.frames` (`pipeline.py:507`), `profile.locked_palette`
(`pixelart.py:306`) and `rmtree`s stage directories (`pipeline.py:314-318`) on the panel's worker,
while `run_export` calls `project.sheet_meta(profile)` (`export_dialog.py:221`, `project.py:519-528`
with a silent stabilize fallback) on the dialog's worker. No lock guards `SpriteProject`. Probe: the
export succeeded with 4 frames while the pipeline's final output is 6. `_on_finished` then
`purge_intermediates()` (`project.py:574-583`) recycles `stages/` and clears `stage_fingerprints`
while the pipeline may still write there.
*Fix:* in `open_export_dialog`, when `self.panel.is_busy()` log + show "Wait for the running
<busy_label> job to finish before exporting" and return `None`; or drive `self.export_btn.setEnabled`
from the same running-state hook that `processing_panel.py:613` uses.

**Important 4 — `parse_scales` silently collapses an invalid scale list to `(1,)`**
`gui/sprite/export_dialog.py:162-176` (`ValueError` branch logs a warning and returns `(1,)`;
`value <= 0` returns `(1,)` with no log); `:424` (`grid_options` uses it); `:491-492`
(`validate_grid_options` then passes); `:185-190` (docstring claims "refuses … rather than silently
overriding").
*Failure:* the user types `1,2,4x` (or `1,2,-4`) and clicks Export. Only the 1× sheet is written; the
console says `Export complete: 6 file(s)`; no message box; for `-4` nothing is logged at all. Probe
with the real grid export confirms no `@2x`/`@4x` files. `test_parse_scales`
(`tests/sprite/gui/test_export_dialog.py:69`) pins the silent behaviour. One vote refuted on the
ground that the plan prescribes the branch verbatim (`plan:3982-3994`); the majority holds that the
plan text does not lift the repo rule "every user-facing error logged AND shown", so the finding stands.
*Fix:* make `parse_scales` raise `ValueError` (or return `None`) on a bad token and have `start_export`
add the message to `problems` so the existing QMessageBox path shows it. Update `test_parse_scales`
to assert the refusal.

**Important 5 — Invalid per-frame key colour is dropped on OK with a log-only warning**
`gui/sprite/frame_strip.py:113-122` (`values()`: `else: logger.warning(...)`); `:390-396`
(`edit_overrides_for_selected` applies `dialog.values()` on Accept); `:381-388` (`apply_overrides`
pushes a snapshot and writes the remaining keys).
*Failure:* the user checks Key color, types `green`, clicks OK. The override holds tolerance and
softness only; the tooltip shows `overrides: none` for the colour; no message box; no console line;
an undo step is pushed. The next run keys that frame with the action colour. This is a commit point,
not the per-keystroke case the T6 ledger deferred (`progress.md:58` covers
`processing_panel.py:531-538`). `test_frame_strip.py:139-140` asserts only that the key is absent.
*Fix:* validate in `accept()`: when `key_color_on` is checked and `HEX_RE` does not match, log +
`QMessageBox.warning` on the dialog and return without accepting.

**Important 6 — Invalid key colour in the processing panel is replaced by the plate colour at run time**
`gui/sprite/processing_panel.py:531-538` (`_key_color_value` → `None` + `logger.warning`); `:555`
(write-back); `:651-663` (`run_pipeline`) and `:694-716` (`preview_key_on_clip`, `color = key.key_color
or project.plate_color` at `:705`) call `_write_back` then start the job with no check; `:921-924`
(`_warn` exists and is unused here); `core/sprite/pipeline.py:189` resolves `None` to the plate.
*Failure:* the user pastes `00FF00` (no `#`) and presses Ctrl+Enter. The pipeline keys on the plate
colour; the console says `Run pipeline: action 'walk'` then `Pipeline finished`; no message box.
Probe: typed `1E90FF`, plate `#FF00FF`, pipeline received `None` → `#FF00FF`. One vote refuted on
the ground that the field's placeholder says "plate color" and the ledger deferred the item; the
majority holds that the deferral covered only the per-keystroke path and that the two commit points
are new.
*Fix:* in `run_pipeline` and `preview_key_on_clip`, after `_write_back`, read
`self.key_color_edit.text().strip()`; if non-empty and `HEX_RE` does not match, `self._warn("Key color",
f"{text!r} is not #RRGGBB")` and return. Leave `_key_color_value` log-only per keystroke.

**Important 7 — ExportDialog tests share QSettings state; test order decides pass/fail**
`tests/sprite/gui/test_export_dialog.py:18-30` (`_close` → `done(0)` → `_save_settings`); `:189-203`
(persists `formats=png_sequence`); `:206-214` (persists `""`); `:217-220`
(`assert dialog.format_checks["grid"].isChecked()`); `gui/sprite/export_dialog.py:579-583`
(`if formats:` applies the persisted set); `tests/conftest.py:7-30` (session-scoped sandbox, no reset);
`tests/sprite/gui/conftest.py:97-111` (autouse fixture only collects garbage).
*Failure:* `pytest …::test_dialog_export_runs_worker_and_emits …::test_start_export_blocked_by_grid_padding_export_grid_rejects`
→ 1 failed at `:220`. The file passes only because `test_dialog_validates_selection` sits between
them and persists an empty string that `if formats:` ignores. Any reorder, `-k` filter or
`pytest-randomly` run breaks it, and a dialog that fails to restore defaults cannot be detected while
earlier tests pre-seed the store.
*Fix:* add an autouse fixture in `test_export_dialog.py` (or extend the `project` fixture) that removes
the `sprite/export` group from `prefs.sprite_settings()` before each test, or monkeypatch
`get_pref`/`set_pref` onto a per-test dict. Keep `test_settings_round_trip` (`:387`) as the only test
that exercises persistence across two dialogs.

### Minor

**Minor 1 — No "live re-run of changed stages"; settings edits only write back**
`gui/sprite/processing_panel.py:576-581` (`_on_changed`: `_write_back` + `settingsChanged.emit` +
`_update_estimate`); `run_pipeline` is bound only to `run_btn` (`:420`) and Ctrl+Enter (`:224`).
*Failure:* the user drags the tolerance slider and expects the key stage to re-run (§1.2); nothing
happens until Run pipeline. Probe: two settings edits, 500 ms of event pumping, zero `run_pipeline` calls.
*Fix:* record the reinterpretation under "Deviations from the design" (manual Run + stage cache), or
add an opt-in "Auto re-run" checkbox that debounces `settingsChanged` (~500 ms) into `run_pipeline`
when the panel is idle.

**Minor 2 — `open_export_dialog` docstring and a test comment cite the withdrawn DeferredDelete rationale**
`gui/sprite/frames_workspace.py:288-293`; `tests/sprite/gui/test_sprite_tab_integration.py:325-327`.
*Failure:* the docstring says a `deleteLater()` posted inside the modal loop "would destroy the dialog
before `exec()` returns". Probe: the dialog is valid after `exec()` in both shapes, and the contract
test passes with the "bad" shape. A maintainer tests the claim, finds it false, and removes the
`try/finally` release as cargo cult, which reintroduces the held-forever dialog. The ledger marks
this "must be corrected" (`progress.md:82`).
*Fix:* rewrite both: the reference is released in `finally` so a dialog that closes without emitting
`finished` (or raises out of `exec`) is not held for the life of the tab; `deleteLater` after `exec()`
keeps the returned object readable by the caller (sub-project 6 registers formats on it). Point at
`test_export_dialog_reference_is_released_even_without_a_finished_signal`.

**Minor 3 — Thumbnail docstring overstates `QImageReader`; PNG cells are decoded at full size on the GUI thread**
`gui/sprite/frame_strip.py:465-469` (docstring), `:484-488` (`setScaledSize` + `read`), `:439-447`
(`_rebuild` decodes every frame); callers `frames_workspace.py:129,199`.
*Failure:* Qt's PNG handler reports `supportsOption(ScaledSize)=False`; it decodes the full image and
then calls `QImage::scaled`. A 300-frame 512×512 action freezes the GUI ~0.5 s on first select.
Inside the design letter (no PIL/ffmpeg) but not its intent. The plan self-review lists the limit
(`plan:5237-5238`).
*Fix:* correct the docstring now. If measured to matter in 6/7, decode lazily per visible row or in a
`QThreadPool` with a queued result signal; keep the mtime cache.

**Minor 4 — Modal helper dialogs parented to long-lived widgets are never deleted after `exec()`**
`gui/sprite/processing_panel.py:642-646` (`SpriteMLInstallDialog(self)`); `gui/sprite/frame_strip.py:390-396`
(`FrameOverridesDialog(…, self)`); contrast `frames_workspace.py:313-317`.
*Failure:* each `Overrides…` and each `Install…` click adds one hidden dialog (with its console,
splitter and, for install, a finished `PackageInstaller` reference) to the parent's child tree for
the session. Probe: 5 clicks → 5 children each. Qt-owned, so not a GC-crash trigger; accumulation only.
*Fix:* `dialog.deleteLater()` after `exec()` returns, or `setAttribute(Qt.WA_DeleteOnClose)` before `exec()`.

**Minor 5 — A superseded probe orphan keeps the panel busy until the old ffprobe returns**
`gui/sprite/processing_panel.py:868-880` (`_supersede_probe` adopts a running probe as an orphan);
`workers.py:205-216` (`is_busy` counts orphans); `processing_panel.py:609-616` (`_sync_enabled`).
*Failure:* the user clicks through several cards quickly on a slow disk; Run / Preview / Export and
Ctrl+Enter stay disabled until the oldest ffprobe exits (normally < 1 s). Correct and safe (120
supersede/reap rounds, no crash, all workers freed); over-conservative.
*Fix:* defer. If wanted, track probe orphans in a list that `is_busy()` ignores, or document it.

**Minor 6 — Recycle-bin failure during purge-after-export is reported as success**
`gui/sprite/export_dialog.py:536-547` (`_on_finished` logs `Purged {count}` for any non-raising call);
`core/sprite/project.py:574-584` (`send_to_recycle_bin` False → `logger.warning`, count skipped);
`core/recycle_bin.py:213-222` (returns False on "No trash utility found"); `send2trash` is not installed
in `.venv_linux`.
*Failure:* WSL without a trash backend: `stages/` stays on disk; the console shows `Purged 0
intermediate item(s) to the recycle bin` then `Export complete`; no message box.
*Fix:* defer with the T7 "purge on GUI thread" item: return `(removed, failed_dirs)` or raise on a
False recycle, and route a non-empty failure list through the existing `QMessageBox.warning` path.

**Minor 7 — Frame-strip thumbnail decode/stat failures are silent**
`gui/sprite/frame_strip.py:477-480` (`except OSError: return None`), `:491-493` (`isNull` → `None`),
`:457-462` (grey placeholder), `:449-455` (tooltip without hint).
*Failure:* a stabilize PNG is deleted outside the app. The strip shows a grey cell, the file log has
no entry, and the console stays quiet until the player reaches that index. Probe: missing + corrupt
files → 0 log records.
*Fix:* log once per `(path, mtime)` miss at WARNING and emit `logMessage` with the path; dedupe with a
set so `refresh()` does not spam. Fix now (a few lines).

**Minor 8 — `_preview_done` ignores `QDesktopServices.openUrl` returning False**
`gui/sprite/processing_panel.py:717-720`.
*Failure:* no default `.mp4` handler: the console says `Chroma preview written: <path>` and nothing
else; no log line. Same house pattern in `midjourney_dialog.py` and `storage_settings_widget.py`.
*Fix:* `if not QDesktopServices.openUrl(...): self._warn("Chroma preview", f"Could not open {path}; open it manually.")`. Fix now.

**Minor 9 — `insert_from_file` `mkdir` of `inserted/` is outside the error handler**
`gui/sprite/frame_strip.py:315-316` (`dest_dir.mkdir(...)` before the `try` at `:326-332`); slots at
`:201` and `:522` have no guard.
*Failure:* the anchor frame lives under a read-only stage directory; the user clicks Insert…, picks
files; a `PermissionError` traceback goes to stderr; no `logMessage`, no message box. Probe confirms.
*Fix:* wrap the `mkdir` in the same `except OSError` → `logger.error` + `logMessage` +
`QMessageBox.critical` pattern used for `shutil.copy2` and return 0. Fix now.

**Minor 10 — PixelView decode failures are logged twice on the workspace path**
`gui/sprite/pixel_view.py:91-93` (`logger.error`); `gui/sprite/frames_workspace.py:215-219`
(`logger.warning` + `tab.log`). `set_view_image` has no production caller.
*Failure:* one ERROR and one WARNING file-log line per bad path; noise only.
*Fix:* defer to sub-project 6 when the retouch preview becomes the first caller; drop the
`logger.warning` and keep the console line.

**Minor 11 — Minor-4 widget assertions cannot fail; the `projectChanged` fast path heals the strip first**
`tests/sprite/gui/test_sprite_tab_integration.py:158-175`; `gui/sprite/frames_workspace.py:271-276`
(`apply_frames` then `projectChanged.emit()`), `:106-108` (same-project fast path → `refresh_frames`).
*Failure:* with `reload=True` forced, the test still passes (probe: strip held 7 frames before the
emit, 4 after). The Minor-4 fix has no regression guard; only `other.frames`, `can_undo(other.id)` and
`tab.saved` discriminate.
*Fix:* monkeypatch `workspace.strip.set_frames` / `workspace._reload_player` to record calls and assert
neither is called with the other action's replacement; or wrap `_replace_frames` and assert the strip
never held a 7-frame list.

**Minor 12 — Unasserted bounded wait in the ML-install reject test**
`tests/sprite/gui/test_ml_install_dialog.py:85` (`dialog._installer.wait(5000)` return discarded);
contrast `conftest.py:80-89` (`assert worker.wait(...)`).
*Failure:* on a loaded CI box the 150 ms fake does not finish in 5 s; `reject()` refuses; the failure
reads as "reject did not close the dialog" with a thread still running at exit. 3/3 real runs green.
*Fix:* `assert dialog._installer.wait(5000), "fake installer did not finish"`.

**Minor 13 — fps readout assertion accepts two values; the `12` branch is dead**
`tests/sprite/gui/test_preview_player.py:40`; `gui/sprite/preview_player.py:277-285` returns `"10.0 fps"`.
*Failure:* `"100.0 fps"`, `"210.0 fps"` and `"1000.0 fps"` all satisfy `"10" in readout`; a mis-scaled
regression passes.
*Fix:* `assert player.fps_readout() == "10.0 fps"`; add a variable-duration case asserting the
`(variable)` suffix.

---

## Deferred-minor triage

| Minor | Verdict | Why | Cost if wrong |
|---|---|---|---|
| T1: unused `Path` import (`test_undo_controller.py:1`) | defer | Lint nit in a test file; nothing builds on it. | None. |
| T1: undo()/redo() deep-copy twice (`undo_controller.py:79`) | drop | `FrameListSnapshot.capture` (`undo.py:26`) copies `current`; `_copy` at `:79/:90` copies the popped snapshot that `SnapshotStack` keeps on the redo stack. Each copy protects a different live object. | Removing either lets a caller mutate a stored snapshot and corrupt redo. |
| T2: `fit_zoom()` untested (`pixel_view.py:128`) | defer | No test references it; sub-project 6 consumes `PixelView` and is the natural place. | A wrong initial zoom goes unnoticed. |
| T3: `loop_seam_score` mismatched-size branch untested (`preview_player.py:55`) | defer | Pure numpy pad path; no later dependency. | A wrong seam readout for mixed sizes. |
| T3: no `hideEvent` pause (`preview_player.py:241`) | defer | `pause()` is called only from workspace shutdown; QTimer decodes while the tab is hidden; polish for 7. | Idle CPU while another tab is active. |
| T3: reverse non-wrap step untested (`preview_player.py:208`) | drop | No non-wrap branch exists; `step()` wraps modulo both ways and the reverse edge is asserted at `test_preview_player.py:13`. | None. |
| T4: `FrameOverridesDialog` hardcodes the three `OVERRIDE_KEYS` (`frame_strip.py:57`) | defer | The tuple is unchanged since sub-project 3; no later sub-project adds a key. | A new core key is unreachable from the dialog. |
| T4: `_finish_reorder` defensive branch leaves a no-op snapshot (`frame_strip.py:505`) | defer | Logged internal-error path that Qt's internal move does not reach. | One extra no-op Ctrl+Z step. |
| T5: title-bar close persists the splitter before the `reject()` guard (`ml_install_dialog.py:169`) | drop | Documented mixin behaviour (`dialog_conventions.py:110-113`); the write is idempotent; the guard still refuses the close. | None. |
| T6: duplicated pipeline job closure (`processing_panel.py:659` / `:740`) | defer | Identical 3-line closure; nothing in 6/7 changes the call. | An argument change must be made twice. |
| T6: `open_install_dialog` no error handling (`processing_panel.py:642`) | defer | `sprite_ml_packages` / `python_supports_rembg` cannot raise; only the constructor path is exposed. | One unlogged stderr traceback. |
| T6: invalid key colour logged not shown (`processing_panel.py:531`) | **fix-now** | Promoted to Important 6: the two commit points (Run / Preview) silently key on the plate colour; ~6 lines. | User keys on the wrong colour and does not know why. |
| T6: superseded probe orphan keeps `is_busy()` True (`processing_panel.py:610`) | defer | Minor 5; confirmed, safe, sub-second. | Run greyed briefly after a fast card switch. |
| T7: unbounded `join_orphans` on close (`export_dialog.py:607`) | defer | House pattern shared with `sprite_tab.closeEvent`; first join bounded at 5 s; the job polls the token between profiles/formats. | A close stalls for one exporter call. |
| T7: `_grid_output_paths` duplicates `grid.py` naming (`export_dialog.py:76`) | defer | Changing `export_grid`'s return type is sub-project 7 core API work; names are exercised by `test_export_dialog.py:144-150`. | A `grid.py` naming change silently drops files from the reported list. |
| T7: dead `format_grid` fallback (`export_dialog.py:99`) | defer | `needs_sheet=True` means `run_export` always writes the sheet first; the docstring says so; 6 decides whether standalone calls exist. | A standalone call uses default padding/scales. |
| T7: saved formats never applied to sub-project-6 registrations (`export_dialog.py:579`) | **fix-now** | 6 would build on broken ground: `_load_settings` applies the persisted set only to checkboxes present at `__init__` (`:323`), so every format 6 registers starts unchecked on every open. Keep the parsed wanted-set on the instance and apply it in `register_format` (`:443-460`); ~5 lines. | 6's formats never restore, or 6 must work around the dialog. |
| T7: export settings global, not per project (`export_dialog.py:566`) | **fix-now** | `sprite/export/out_dir` carries no project identity, so project A's directory overrides `default_export_dir(project)` for project B and B's files land in A's tree; persist under a project-keyed suffix or stop restoring `out_dir` across projects. | One project's exports written into another project's tree. |
| T7: purge on the GUI thread (`export_dialog.py:541`) | defer | `rglob` + recycle bin after the worker finished; moving it changes the `confirm_purge` flow; belongs with 7's polish and Minor 6. | Dialog freezes for seconds on a large tree. |
| T7: test-name/assertion mismatch `sheet_written_once` (`test_export_dialog.py:144`) | defer | Asserts the output set only, so a triple write would pass; the assertions still guard the set. | A per-format sheet rewrite goes unnoticed (time only). |
| T7: JSON outputs never parsed (`test_export_dialog.py:144`) | defer | Core exporter tests own JSON shape; 6 adds engine formats where parsing is natural. | A malformed document from the GUI path passes the GUI suite. |
| T9: `set_view_image` no production caller (`frames_workspace.py:207`) | defer | Docstring names 6's retouch preview as the caller; the `Path` union gap is fixed. | None until 6 lands. |
| T9: decode failures logged at two levels (`frames_workspace.py:203`) | defer | Minor 10; logged-AND-shown is met, severities differ. | Two file-log lines per bad frame. |
| T9: single-action fixture coverage (`test_sprite_tab_integration.py:158`) | defer | Partly closed by the two-card test; per-action undo isolation, `_on_action_selected('')` and `shutdown()==False` remain for 6's cross-action tests. | A cross-action `undo_stack` regression goes unnoticed. |
| T9: annotation-only `QImage`/`QPixmap` imports (`frames_workspace.py:14`) | drop | Used in the `set_view_image` signature; lazy under `from __future__ import annotations`. | None. |
| T9: withdrawn DeferredDelete rationale in docstring + test comment (`frames_workspace.py:287`, `test_sprite_tab_integration.py:325`) | **fix-now** | Minor 2; the ledger marks it must-correct; probe shows the stated Qt rule is false. | A reader in 6/7 "fixes" the working shape against a false rule. |
| T9: Minor-4 reload test does not discriminate (`test_sprite_tab_integration.py:158`) | **fix-now** | Minor 11; mutant confirmed. | A regression that pushes another action's frames into the shown strip passes. |
| T9: double strip/player reload per `apply_frames` (`frames_workspace.py:276`) | defer | The second pass is served by the mtime cache; the emit is what refreshes the 5a panels. | One redundant rebuild per retouch. |
| T9: two divergent worker-host lists (`sprite_tab.py:258` vs `:436-446`) | defer | Harmless while the export dialog is modal; a host added in 6 must go in both. Note it in the 6 brief. | A 6 host in one list only is not joined on switch or close. |
| SYSTEMIC: `start_job` partials bind the worker to its own signals (`workers.py:156`) | **fix-now** (overrides the dimension triage "defer") | Promoted to Important 2: the probe shows the worker is never freed, not "freed only by the collector"; the run-id pattern already exists at `processing_panel.py:811-819`; ~20 lines in one file before 6 adds more hosts. The GC-crash exposure itself is closed (export dialog parented/held/deleted; workers joined before detach; autouse teardown collect in tests). | Per-job leak of a QThread, an API-key-holding closure and, for exports, the dialog graph; multiplied by 6's hosts. |
| 5a: `CharacterPanel` no Ctrl+Enter (deviation 16) | defer | Untouched by 5b; `shortcuts.py:6` leaves Ctrl+Enter to each panel. | Ctrl+Enter does nothing on that panel. |
| 5a: queue log levels (`queue_panel.py`) | defer | Untouched by 5b; the file logger keeps the true level. | Queue warnings show as INFO in the console. |
| 5a: GUI-only-writer save redesign (`project.py:438`) | defer | 5b added one GUI-thread writer (`apply_frames` → `save_current_project`), consistent with the interim RLock. | Saves serialize on the lock; no corruption. |
| 5a: positional current-tab persistence (`main_window.py:9226`) | defer | Untouched; one-time misrestore after the Sprite insert. | One wrong restored tab once. |
| 5a: `getsource` wiring tests (`test_main_window_sprite_wiring.py:72`) | defer | Untouched; a headless `MainWindow` construction test is 7 (PR gate) work. | A refactor that keeps the text but breaks the wiring passes. |
| 5a: `deleteLater` on normally finished workers (`workers.py:342`) | already-resolved / superseded | `fee96b5` detaches instead; the replacement's leak is Important 2. | None beyond Important 2. |
| 5a: `analyze_source` on the GUI thread (`character_panel.py:156`) | defer | Untouched (~10 ms). | Brief stall on a very large character PNG. |
| 5a: `_on_send_to_sprite` TypeError branch (`main_window.py:8269`) | defer | Untouched; unreachable with the shipped callers. | Silent no-op for a future non-path caller. |

---

## Refuted findings

- **Fallback export directory uses `project.name` instead of the slug** (`export_dialog.py:181`) — the branch is unreachable from the GUI (every project the tab hands over has `project_dir` set by `create_project` / `load`), the plan prescribes the line verbatim, the manager layout is `<slug>_<stamp>` so the slug alone matches nothing either, and the field is user-editable.
- **Signals connected to lambdas in `FrameStrip`** (`frame_strip.py:225`) — the lambdas discard Qt's `checked` bool for slots with optional first parameters (`insert_from_file(paths=None)`, `export_selected_frame(out_png=None)`) and bind the `"reorder"` label; connecting bound methods would introduce real bugs; the plan mandates the lines; sender and receiver share the strip's child tree.
- **`PackageInstaller` thread has no app-exit join path** (`ml_install_dialog.py:135`) — the dialog is application-modal and blocking; `QApplication.quit()` under Qt 6.11.1 routes through `closeEvent → reject()`, which refuses while `is_running()`, so the quit is cancelled (reproduced headless); no repo code calls `QApplication.exit()`; same house pattern as `gui/install_dialog.py`.
- **Eyedropper reimplements `pick_key_color` as a single-pixel read** (`pixel_view.py:169`) — the plan's Task 2 spec and tests require single-pixel `color_at` (`plan:437, 526-531, 757-763`); §4.5 places the picker on `character_panel.py`; keying output was identical for the stated scenario and diverged only at noise ±20 with tolerance 0.06; the contract-table row is a plan-internal inconsistency at most.
- **`SpriteTab.undo_stack` rebinding per action is undocumented** (`frames_workspace.py:126`) — the rebinding is documented at `plan:4609-4610`, the inline comment at `frames_workspace.py:69` and the integration test at `test_sprite_tab_integration.py:101`; sub-project 6's plan lists `tab.undo_stack` as "not used here" and routes edits through `apply_frames(action_id, …)`; per-action stacks looked up by id are the §1.4 design.
- **Stale per-file `gc.collect()` in `_close()` duplicates the conftest fixture** (`test_export_dialog.py:30`) — `progress.md:61` rules that the per-file collect stays; the two mechanisms are redundant and harmless; the neighbouring test docstring at `:257-258` already points at the conftest fixture; the file passes 5/5 with either alone.

---

## Assessment

**Needs fixes.** The branch implements every 5b module, every recorded deviation and every
sub-project-6 seam as specified, the full suite is green (1757 passed), and no path destroys a
running thread. Seven Important findings block the gate: one missed requirement (§1.5 scope) that
breaks Space on every button and Delete on the cards table; one per-job resource leak that the
branch claims to have closed and that sub-project 6 would multiply; one unsynchronised export against
a running pipeline; three swallowed input errors at commit points; and one order-dependent test file.
All fixes are small and local. Apply them in this order, then re-run the whole suite once.

**Fix wave 1 — behaviour (Important 1–6 + two promoted triage items):**
1. `gui/sprite/workers.py` — bind an integer run id into the `start_job` partials; resolve the worker
   in `_mark_terminal` / `_guarded` / `_release_worker`; disconnect after release; correct the comments
   at `workers.py:339-341` and `processing_panel.py:887-894`; add the weakref test (Important 2).
2. `gui/sprite/shortcuts.py` — per-owner `QShortcut` creation (strip / player / view container);
   tab keeps only undo/redo; add the focused-button and focused-table tests (Important 1).
3. `gui/sprite/frames_workspace.py` — gate `open_export_dialog` on `panel.is_busy()` with a logged +
   shown message, or drive `export_btn.setEnabled` from the panel's running state (Important 3).
4. `gui/sprite/export_dialog.py` — `parse_scales` refuses bad tokens; `start_export` shows the
   message; update `test_parse_scales` (Important 4). In the same file: apply the persisted formats set
   inside `register_format` (T7 fix-now) and key `out_dir` by project or stop restoring it across
   projects (T7 fix-now).
5. `gui/sprite/frame_strip.py` — `FrameOverridesDialog.accept()` refuses an invalid checked key colour
   with a shown message (Important 5).
6. `gui/sprite/processing_panel.py` — `run_pipeline` and `preview_key_on_clip` refuse a non-empty
   invalid key colour through `_warn` (Important 6).

**Fix wave 2 — tests (Important 7 + Minors 11–13):**
7. `tests/sprite/gui/test_export_dialog.py` — autouse fixture that clears the `sprite/export` group
   before each test (Important 7).
8. `tests/sprite/gui/test_sprite_tab_integration.py:158` — record `strip.set_frames` /
   `_reload_player` calls and assert on them (Minor 11).
9. `tests/sprite/gui/test_ml_install_dialog.py:85` — assert the `wait()` return (Minor 12).
10. `tests/sprite/gui/test_preview_player.py:40` — exact `"10.0 fps"` assertion plus a variable case (Minor 13).

**Fix wave 3 — small fix-now Minors:**
11. Rewrite the withdrawn-rationale docstring at `frames_workspace.py:288-293` and the comment at
    `test_sprite_tab_integration.py:325-327` (Minor 2).
12. Correct the thumbnail docstring at `frame_strip.py:465-469` (Minor 3).
13. Wrap the `mkdir` at `frame_strip.py:316` in the existing log + show pattern (Minor 9).
14. Log + `logMessage` once per thumbnail miss at `frame_strip.py:479` / `:491` (Minor 7).
15. Check the `openUrl` return at `processing_panel.py:720` (Minor 8).
16. `deleteLater()` the two helper dialogs after `exec()` (Minor 4).

**Record in the plan's Deviations section:** the §1.5 scope (after wave 1 it matches the design and
the entry can note the correction), and the §4.5 "live re-run" reinterpretation (Minor 1).

**Carry to the sub-project 6 brief:** Minor 5, Minor 6 with the T7 GUI-thread purge, Minor 10, the
divergent worker-host lists, and every "defer" row above.
