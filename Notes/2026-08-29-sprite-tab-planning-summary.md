# Sprite Tab — Planning Summary

**Date:** 2026-08-29
**Branch:** `feat/sprite-tab` (cut from `origin/main`; carries the 2026-08-24 research commit)
**Status:** Design + 8 sub-project plans complete. Implementation not started.

## What happened

1. Leland selected 39 features, 10 critic gaps, and answered 10 open
   questions in `Plans/sprite-tab-feature-selector.md`.
2. The design spec `Plans/2026-08-29-sprite-tab-design.md` locks the
   architecture: `core/sprite/` (pure Python), `gui/sprite/` (PySide6),
   `cli/commands/sprite.py`; two generation routes (video first, image
   later) over one cached processing spine; two output profiles (`hd`,
   `pixel`, both on by default); `FrameMeta`/`SheetMeta`/`SpriteProject`
   data model; cancel/progress contract; stage-runner registry;
   storage under `<Images root>/sprites/`.
3. Eight plan-writing agents ran in parallel, one per sub-project. Each
   agent prototyped its code, assembled the plan's code blocks into a
   scratch tree, and ran the plan's own tests before reporting. The
   orchestrator reconciled every cross-plan seam (stage-runner registry,
   `SpriteProjectManager` API, export-dialog plugin surface, worker API,
   `apply_frames`, format ids) and re-checked the eight files with a
   symbol cross-reference script.

## Plan files (execute in this order)

| # | Plan | Tasks | Depends on |
|---|---|---|---|
| 1 | `Plans/2026-08-29-sprite-core-spine-plan.md` | 15 | — |
| 2 | `Plans/2026-08-29-sprite-video-route-plan.md` | 13 | 1 |
| 3 | `Plans/2026-08-29-sprite-keying-plan.md` | 11 | 1 (parallel with 2) |
| 4 | `Plans/2026-08-29-sprite-pixel-art-plan.md` | 8 | 1, 3 |
| 5a | `Plans/2026-08-29-sprite-gui-a-plan.md` | 10 | 1, 2 |
| 5b | `Plans/2026-08-29-sprite-gui-b-plan.md` | 10 | 1, 3, 4, 5a |
| 6 | `Plans/2026-08-29-sprite-image-route-exports-plan.md` | 11 | 1, 2, 3, 5a, 5b |
| 7 | `Plans/2026-08-29-sprite-cli-release-plan.md` | 15 | 1–6 (PR gate) |

93 tasks total. Sub-project 7 owns the version bump (version-manager,
minor), docs, CodeMap, local review, push, and the single PR.

## Decisions recorded during planning

- Stage directories are `stages/<action_id>/<stage>/` named after `STAGES`.
- `register_stage(stage, runner, settings_fn, code_version)` is the hook
  sub-projects 3 and 4 use to replace identity stages; settings callables
  take `(project, action)`.
- `default_profiles()` enables both `hd` (256×256) and `pixel` (64×64).
- `OutputProfile` gains `upscale_small` and `upscale_method` (owned by 1,
  read by 4).
- `SpriteProjectManager` lives in `core/sprite/project.py` with
  `create_project / list_projects / find_project / load_project /
  save_project / delete_project`.
- Export plugins: `fn(meta, out_dir) -> List[Path]`, underscore ids.
- `FramesWorkspace.apply_frames(action_id, frames, label)` is the retouch
  seam; callers pass a new deep-copied list.
- The Omni per-second price must be verified on the pricing page on the day
  of implementation; unverified → estimator shows "unknown".

## Next step

Execute sub-project 1 with `superpowers:subagent-driven-development`
(fresh subagent per task, review between tasks). Commit per task. Update
the plan file's checkboxes as tasks finish.
