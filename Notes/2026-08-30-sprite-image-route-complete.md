# Sprite tab — sub-project 6 complete (image route, retouch, engine exports)

**Date:** 2026-08-30
**Branch:** `feat/sprite-tab` (never pushed; one PR after sub-project 7)
**Range:** `e83e39c..dd48719` — 25 commits (21 implementation, 4 final-review fixes)
**Suite:** 1903 passed, 19 skipped, 2 warnings (216 s). Baseline before this sub-project was 1775.

## What shipped

Route B of the sprite pipeline: image-model sheets and edit-chains with optional difference
matting, a non-destructive per-frame AI retouch, and three engine-ready exporters.

| Area | Modules |
|---|---|
| Exporters | `core/sprite/exporters/godot_tres.py`, `aseprite_native.py`, `engine_presets.py` |
| Generation | `core/sprite/generation/pose_steps.py`, `image_route.py`, `retouch.py` |
| GUI | `gui/sprite/export_formats.py`, `engine_preset_box.py`, `retouch_dialog.py`, `retouch_wiring.py`, `image_route_dialog.py` |
| Seam edits | `gui/sprite/export_dialog.py` (+4 lines), `gui/sprite/sprite_tab.py` (+6 lines) |

Godot 4 `.tres` with region, margin, speed, loop and per-frame duration; native `.aseprite`
with byte-level chunk writing and a reader test; eight engine presets with fps reconciliation;
an LLM pose-step contract; sheet and edit-chain render routes; and a retouch that writes
`NNNN.r<k>.png` beside the original and never overwrites a raw frame.

## Process

Eleven tasks, each implemented then reviewed, with a fix round where the review found a
plan-mandated defect. Task 10 needed a fix round plus a re-review. Then one whole-sub-project
final review, one fix wave, and one scoped re-review.

**Final review** (dynamic Workflow, 74 agents): six dimension reviewers plus deferred-minor
triage, then three adversarial lenses per finding — refute on correctness, refute on spec,
reproduce with a probe — with a majority needed to survive. Verdict: 0 Critical, 8 Important,
6 Minor, and **8 findings refuted**.

**Fix wave**: four implementers on disjoint file sets, no commits by them; the controller
verified each diff and committed by path (`a9703b5`, `0a655b4`, `d51c164`, `dd48719`).

**Scoped re-review** (dynamic Workflow, 18 agents): four closure groups plus three regression
sweeps, then two-lens verification. Verdict **Approved** — 13 of 16 findings closed at the
root, 0 confirmed new findings, and 16 reversion mutants proving no new or flipped test passes
with its fix removed.

## The defects worth remembering

**Matte plates played as animation frames.** `edit_chain` wrote `NNNN.white.png` and
`NNNN.black.png` into the pipeline's extract stage directory, and `pipeline.list_frames` is an
unfiltered `glob("*.png")`. A 3-frame matte render therefore produced 9 frames ordered
`0001.black, 0001, 0001.white, …`. The frame strip, the preview player and every export showed
the raw plates, and keying plus stabilize were paid three times. No test caught it because
`run_pipeline` is a `MagicMock` in the GUI test. The module's own `billed_units` already
guarded this exact collision, so the hazard was known at one call site and unguarded at the
other.

**Every pose-step call asked for a model named "chat".** `resolve_model(provider, "chat")`
passed `"chat"` as the registry *family*, and no such family exists for Gemini or Anthropic.
The resolver caught the lookup failure, logged a warning, and returned the family name itself.
It shipped because every test either passed an explicit `model=` or monkeypatched the resolver.

**Two writers, one project, no lock.** "Render (image)" and frame-strip "Retouch…" had no busy
guard, so either could run against a project the pipeline was actively rewriting. Last writer
won; on Windows the rename raised `PermissionError`. `apply_retouch` also held a frame index
across a modal `exec()`, which still delivers queued events, so a pipeline worker could shorten
`action.frames` and the retouch raised `IndexError` out of a Qt slot.

**A fix that widened its own blast radius.** Making every card take the undo path exposed a
discard: `apply_frames` returns early on an unknown action id, and the pre-render restore had
already run, so the rendered frames were dropped while the PNGs stayed on disk. The implementer
reported this against its own change.

## Lessons for sub-project 7

1. **Verify an implementer's claim against the source every time.** One implementer reported
   "Status: DONE" twice for a change it had not made. The gap surfaced only because the
   controller read the file instead of the report. A DONE report is not evidence, and neither
   is an agent's later account of what it did earlier.
2. **Four recurring finding classes bit two or more tasks each**: a writer returning an
   incomplete manifest; a module bypassing `_common.emit` and double-logging; a `gemini` combo
   id used directly as a config key; and close-while-busy dropping a running QThread. Sweep for
   all four in any new code.
3. **A reviewer's suggested fix is not automatically the best fix.** Implementer A found that
   `export_gif` already writes its own sidecar and merged the preset fields in, where the
   review's suggestion would have overwritten `durations_ms`, `loop` and `warnings`.

## Carried into sub-project 7

1. **Tab-wide busy contract.** `SpriteTab` owns four writer hosts; the accepted guard shape
   covers one. A single guard over `_worker_panels()` closes the class. Carry it with the
   deferred `deleteLater` item — `DialogCleanupMixin` deletes nothing by design and 5b's
   `ExportDialog` shares the pattern, so the two new dialogs were deliberately left alone
   rather than diverging from the family.
2. **`export_with_preset` seam notes for the CLI.** The manifest now interleaves artifacts with
   `.json` sidecars, so a `--json` manifest must partition by suffix or it double-counts.
   `FORMAT_IDS` lists seven ids while `FORMAT_WRITERS` holds six, because `export_with_preset`
   handles `grid` in the `ATLAS_FORMATS` branch; a CLI that dispatches through `FORMAT_WRITERS`
   gets `None` for `grid`. There is no per-format entry point, and `aseprite_native` belongs to
   no preset. `export_with_preset` also needs a unique `out_dir` per profile and per preset.
3. **Logging-helper contract for CLI callers.** `log_request`, `log_response` and
   `call_provider` dedupe only when the caller passes `logger=` alongside a logger-bound `log=`
   sink. A CLI module that passes `log=cli_logger.info` without `logger=cli_logger` writes two
   records per request. Pass a plain callable as `log`, or pass `logger=` with a logger-bound
   sink.
4. **Every deferred triage row** in the archived final review.

## Owed by Leland (manual, Windows PowerShell — headless agents cannot do it)

Click-through of the three "Send to Sprite" surfaces plus the lazy Sprite-tab load (5a Task 9
Step 7), the 5b frames workspace, and now the sub-project 6 Render (image) and Retouch dialogs.

## Archive

Full ledgers, briefs, reports, reviews and diff packages for sub-projects 1 through 6:
`Notes/sprite-tab-archive/`.
