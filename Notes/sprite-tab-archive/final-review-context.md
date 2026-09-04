# Final whole-branch review — sub-project 6 (image route, retouch, engine exports)

## What you review

**Range:** `e83e39c..4567f8a` — 21 commits, 24 files, +3946/-9.
`e83e39c` is the close of sub-project 5b (GUI-B). 5b already had its own final review and
re-review; **do not re-review 5b or 5a code**. The handoff text names `45f9796..` — that base is
wrong, it spans 5b as well. Use `e83e39c..4567f8a`.

**Primary input (read it in chunks; it is your main view):**
`/mnt/d/Documents/Code/GitHub/ImageAI/.superpowers/sdd/2026-08-29-sprite-image-route-exports-plan/review-e83e39c..4567f8a.diff`
(git log + `--stat` + `git diff -U5`).

**HEAD is `4567f8a`.** Every line number you cite must be a line number at HEAD.

## Inputs you must read

| Input | Path |
|---|---|
| Plan (goal, architecture, global constraints, per-task interface lists, Self-review, 13 Deviations) | `Plans/2026-08-29-sprite-image-route-exports-plan.md` |
| Design spec | `Plans/2026-08-29-sprite-tab-design.md` — §2 (data model), §3 row 6, §4.6 (image route, retouch, engine exports), §5 (testing) |
| Controller ledger — every ruling, every deferred minor | `.superpowers/sdd/2026-08-29-sprite-image-route-exports-plan/progress.md` |
| Global seam constraints | `.superpowers/sdd/2026-08-29-sprite-image-route-exports-plan/global-constraints.md` |
| Task briefs and implementer reports | same directory, `task-N-brief.md` / `task-N-report.md` (N = 1..11) |
| Task 10 review + re-review (the only task that needed two rounds) | `task-10-review.md`, `task-10-rereview.md` |
| Repo hard rules | `AGENTS.md` (repo root) |

Do **not** trust the task reports. Verify every claim against the diff and against HEAD.

## Files in scope (the whole sub-project)

Core:
- `core/sprite/exporters/godot_tres.py` (Task 1) — `export_godot_tres`, `render_godot_tres`, `ordered_frame_indices`
- `core/sprite/exporters/engine_presets.py` (Task 2) — `EnginePreset`, `ENGINE_PRESETS`, `export_with_preset`, `fps_reconciliation`, `FORMAT_IDS`
- `core/sprite/exporters/aseprite_native.py` (Task 3) — `export_aseprite`, `read_aseprite_summary`
- `core/sprite/generation/pose_steps.py` (Task 5) — LLM contract "Sprite Pose Steps — Strict v1.0"
- `core/sprite/generation/image_route.py` (Tasks 6+7) — `sheet_prompt`, `generate_sheet`, `slice_generated_sheet`, `edit_chain`, shared provider helpers
- `core/sprite/generation/retouch.py` (Task 8) — `retouch_frame`, `next_retouch_path`, `build_region_mask`, `fit_to_size`, `validate_retouch`

GUI:
- `gui/sprite/export_formats.py`, `gui/sprite/engine_preset_box.py` (Task 4)
- `gui/sprite/retouch_dialog.py`, `gui/sprite/retouch_wiring.py` (Task 9)
- `gui/sprite/image_route_dialog.py` (Task 10)
- `gui/sprite/export_dialog.py` (+4 lines), `gui/sprite/sprite_tab.py` (+6 lines) — the only 5a/5b files touched

Tests: `tests/sprite/test_{godot_tres,engine_presets,aseprite_native,pose_steps,image_route,retouch}.py`,
`tests/sprite/gui/test_{export_dialog_engine_presets,image_route_dialog,retouch_dialog}.py`,
`tests/sprite/gui/test_export_dialog.py` (3 pre-existing 5b tests re-idd),
`tests/sprite/golden/godot.tres`.

## Read-only rules — absolute

- Never mutate the working tree, the index, HEAD, branches, stashes, or tags. No `git add`,
  `commit`, `checkout`, `restore`, `stash`, `reset`.
- **Never write a file inside the repository.** Scratch files go only under
  `/home/leland/.claude/run/claude-1000/-mnt-d-Documents-Code-GitHub-ImageAI/142c578d-2b8c-4a99-9936-b57d066b736f/scratchpad/`.
  A stray `tests/sprite/gui/zzz_*.py` once broke other agents' directory runs.
- Never dispatch subagents.
- The working tree carries Leland's own unrelated items (deleted root `*.md`, untracked
  `Notes/*.md`, `feature-documenter.skill.zip`, modified `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`).
  Ignore them. They are not findings and you never touch them.
- Run tests with `QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest … -q -p no:cacheprovider`.
  Run them in the **foreground** with a 600000 ms timeout. Background runs never wake you.
- Report only what you can cite as `file:line` at HEAD. A clean dimension returns an empty
  findings list. Do not pad.

## Severity calibration

| Severity | Meaning |
|---|---|
| **Critical** | Data loss, a crash on a reachable path, a security or credential leak, or a corrupt artifact a user ships. |
| **Important** | A user-visible defect on a reachable path, a broken seam that sub-project 7 consumes, a violated repo hard rule (unlogged user-facing error, hand-built data path, missing sidecar, model-ID literal, prompt-text dimension), a spec requirement that is missing without a recorded deviation, or a test that cannot fail. |
| **Minor** | Style, naming, a coverage gap on obviously-correct code, an unused import, a docstring that overstates. |

A **recorded deviation** in the plan's "Deviations from the design" section (13 of them) or a
**controller ruling** in `progress.md` is NOT a finding — unless the implementation deviates from
the deviation itself. Read both lists before you raise a spec finding.

## State of the branch

- Full suite at `4567f8a`: **1887 passed, 19 skipped, 2 warnings, 228.87 s**, exit 0
  (controller-run 2026-08-30 18:35).
- Guard grep for model-ID literals in the six new runtime modules: only the two permitted
  `MODEL_CAPS["gpt-image-1"]` fallback keys at `core/sprite/generation/image_route.py:100` and `:115`,
  which mirror `providers/openai.py` `_caps_for`.
- All ten implementation tasks are closed. Task 10 needed one fix round plus a re-review; every
  other task closed in one round or one fix round.

## Environment facts — do not relearn these

- **Worker lifetime contract (`gui/sprite/workers.py`).** `WorkerHost` binds WEAK references into
  signal partials and disconnects after release. `shutdown() -> bool`. A timed-out worker becomes an
  orphan in the module-level `_LIVE_ORPHANS`; `join_orphans()` is the unbounded fallback. Every
  `WorkerHost` subclass overrides `_on_worker_idle` and never writes `self._worker`. A dialog that
  holds a worker mixes in `WorkerHost` and mirrors `ExportDialog.on_dialog_close`.
  `RetouchDialog` (Task 9 fix) and `ImageRouteDialog` (Task 10 fix) both follow this shape.
- `tests/sprite/gui/conftest.py` has an autouse teardown `gc.collect()`.
- `Image.fromarray(arr, "RGBA")` is deprecated — the mode arg was removed everywhere. Zero
  Pillow warnings is the standard; the 2 remaining warnings are third-party.
- `FramesWorkspace.apply_frames(action_id, frames, label)` pushes the undo snapshot itself. A
  caller passes a NEW deep-copied list and never mutates live `FrameMeta` objects first.
- Config keys: a `gemini` combo id must map to `google` before `config.get_api_key` /
  `config.get_auth_mode`. `action_cards_panel._config_key_for` owns the table.

## Recurring finding classes on this branch — check each one

These four classes each bit two or more tasks. Sweep for a fifth instance.

1. **A function that writes files but returns an incomplete manifest.** Bit Task 2
   (`_grid_output_paths` stopped at the first missing candidate), Task 4
   (`write_godot_tres`/`write_aseprite_native` returned `[primary]` while also writing `.json`
   sidecars), and 5b Task 7. Every writer's return list must equal what lands on disk.
2. **A module that bypasses `core/sprite/generation/_common.emit` and double-logs.** Bit Task 5
   (`pose_steps`) and Task 6 (`log_request`/`log_response`). Every log site in the generation
   package routes through `emit(logger, log, message, level=…)`.
3. **A `gemini` combo id used directly as a config key instead of mapping to `google`.** Bit
   Task 10 and, earlier, 5a.
4. **Close-while-busy dropping a running QThread.** Bit Task 9 and Task 10. A dialog that closes
   while a worker runs must never let the QThread be destroyed under it.

Also sweep: **every artifact this sub-project writes gets a `.json` sidecar** through
`core.utils.write_image_sidecar` (repo hard rule). Task 7's matte plates missed theirs once.

## Deferred minors — the triage agent owns this list

Triage every item. For each: locate it at HEAD (`file:line`), say whether it still exists or a
later commit resolved it (name the commit), and rule **fix-now / defer / drop / already-resolved**
with a one-sentence why and the cost if you are wrong.

Rule **fix-now** only when leaving the item makes sub-project 7 build on broken ground, misleads a
reader (a withdrawn-rationale docstring or comment qualifies), or is a real user-visible defect.
Rule **defer** when sub-project 7 owns the surface. Rule **drop** for false positives.

### From the per-task reviews (`progress.md`)

- **Task 1** — the golden `.tres` comparison is whitespace-normalized (the brief's own test shape).
- **Task 3** — the Aseprite tags chunk writes `from`/`to` unclamped (matches the `aseprite_json`
  convention).
- **Task 2** — the fps drift note has no magnitude gate (the brief's verbatim test pins the shape);
  degenerate-duration text; `repeat == 1` is unnoted.
- **Task 6** — `default_openai_edit_model` / `openai_edit_size` were unused until Task 8 landed
  (the brief's own forward helpers). Confirm they are used now.
- **Task 4** — an unused `SimpleNamespace` import (a brief artifact).
- **Task 7** — bare single-sink `log()` progress lines remain in the `edit_chain` main loop and in
  `generate_sheet` / `slice_generated_sheet`. No double-log; only the `emit` raising-sink safety net
  is missing.
- **Task 8** — an unused `List` import; nonexistent neighbour paths are dropped silently with no log
  line.

### Open from the Task 10 first review (5 of 9)

- **M1** — `test_sheet_job_fills_frames_and_runs_pipeline` still asserts `source_path`s that the real
  `_sync_frames` overwrites, and `run_pipeline` is still a `MagicMock`.
- **M2** — `FrameMeta.name = f"{project.name}_{action.name}_{i:02d}"` (`image_route_dialog.py:246`)
  is discarded by `_sync_frames` (`core/sprite/pipeline.py:498`).
- **M6** — the module-level `_on_rendered` shares its name with `ImageRouteDialog._on_rendered`.
- **M7** — `frames_spin` never writes back to `action.target_frames`.
- **M9** — no undo snapshot when the rendered action is not the current one.

### New from the Task 10 re-review (4)

- **(a)** `billed_units` under-counts a matte step that dies between its two plate calls. The white
  plate is saved at `image_route.py:298` and the black at `:299`, but the composed `NNNN.png` only at
  `:309`. A provider failure on the black plate leaves a paid white-plate call with no digit-stemmed
  file, so that step bills 0 instead of 1.
- **(b)** The archive same-second collision loop (`image_route_dialog.py:44-50`) has no test.
  `test_archive_existing_frames_moves_aside` never exercises the loop.
- **(c)** `cancel_render` is a silent no-op when the busy state is an orphan. `is_busy()` is True for
  an unreaped orphan, but `cancel_running()` only touches `self._worker`, which `shutdown` already
  cleared. The console still logs "Cancel requested".
- **(d)** The failure path discards the previous status. `status = "failed"`
  (`image_route_dialog.py:278`) overwrites a good `"processed"` from an earlier video render, while
  the cancel path restores `status_before`.

### Carried forward from the 5b final review — 6 owns them only where 6 touched the surface

- 5b Minor 4: modal helper dialogs parented to long-lived widgets are never deleted after `exec()`.
  **6 added two such dialogs** (`RetouchDialog`, `ImageRouteDialog`) — judge those two.
- 5b Minor 6 + T7: a recycle-bin failure during purge-after-export is reported as success.
- 5b T7 note: `_grid_output_paths` duplicates `grid.py` naming; `export_grid` should return the paths
  it wrote.

Anything else on the 5a/5b carry-forward list belongs to sub-project 7. Rule it **defer**.

## Output

Return structured findings only. Do not write the final document unless you are the synthesizer.
