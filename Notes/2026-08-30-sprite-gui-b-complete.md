# Sprite tab — sub-project 5b (GUI-B) complete — 2026-08-30

**Branch:** `feat/sprite-tab` (not pushed; one PR after sub-project 7). **Range:** `45f9796..9898946` (24 commits).
**Suite:** 1775 passed / 19 skipped / 0 failures (`pytest -q`, offscreen). 5b added ~150 tests.

## What shipped
- `gui/sprite/`: `undo_controller.py` (per-action snapshot stacks), `pixel_view.py` (integer zoom, grid, pick, region select for sub-project 6), `preview_player.py` (QTimer playback, loop modes, seam meter), `frame_strip.py` (reorder/duplicate/delete/insert with undo, cached proportional thumbnails, per-frame overrides), `ml_install_dialog.py`, `processing_panel.py` (per-profile settings, worker-run pipeline, chroma preview, rebuild palette), `export_dialog.py` (pluggable formats, grid/pivot options, per-project export dir, purge-after-export), `shortcuts.py` (§1.5 table, owner-scoped), `frames_workspace.py` (assembly + `apply_frames` retouch seam); `sprite_tab.py` integration.
- `gui/sprite/workers.py` hardening: weak-reference signal binding (no per-job leak), orphan handling with module-level strong refs, finished workers joined and detached.

## Review process
- Task-by-task SDD (10 tasks, each reviewed; fix rounds on Tasks 4, 6, 7, 9).
- Whole-branch final review as a dynamic Workflow (88 agents: 5 dimensions + triage → 3-lens adversarial verification): 0 Critical, 7 Important, 13 Minor, 4 refuted.
- One fix wave (three parallel implementers, disjoint files) closed every Important + 8 fix-now Minors; scoped re-review (18 agents): all closure groups closed, 0 new findings.

## Owed / deferred
- **Leland (manual, Windows PowerShell):** the 5a click-through of the three "Send to Sprite" surfaces and lazy tab load is still owed; 5b adds the frames workspace to check while you are there.
- Deferred to 6/7 (listed in the image-route SDD ledger): helper-dialog deleteLater, probe-orphan Run gating, purge failure reporting + off-GUI purge, double decode log, export_grid returning its paths, plus the open 5a carry-forwards.

## Next
Sub-project 6 (image route + engine exports): `.superpowers/sdd/2026-08-29-sprite-image-route-exports-plan/`, then 7 (CLI, version bump, docs, ONE PR). Resume via `.superpowers/sdd/HANDOFF.md`.
