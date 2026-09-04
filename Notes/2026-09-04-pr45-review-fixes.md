# PR #45 review round 1: fixes

Date: 2026-09-04. Branch: `feat/sprite-tab`. PR: https://github.com/lelandg/ImageAI/pull/45

The CL PR Reviewer (Claude Opus) returned "request changes" with five blocking
items and three security items. Every item was checked against the PR-head
source before a change was made. All eight were real. Each fix has a
regression test that failed before the fix and passes after it.

## Blocking

| # | Finding | Fix | Test |
|---|---|---|---|
| 1 | Cancel during a re-render stranded the card at `rendering`; the cancel branch read the stale `action.clip`. | `ActionQueue.run` tracks a local `produced` flag. | `test_gen_queue.py::test_cancel_during_a_re_render_requeues_the_card` |
| 2 | Veo loop conditioning ignored `action.loop`; one-shot cards got `image=last_frame=plate` and 8 s. | `build_veo_config` gates on `settings.loop_conditioning and action.loop`; the record stores the applied value. | `test_gen_video_route.py::test_veo_loop_conditioning_is_skipped_for_a_non_looping_action` |
| 3 | `delete_project` rmtree'd the parent of any opened project file. | Containment check against `base_dir` (resolved, never the base itself); recycle bin first, rmtree fallback. | `test_project.py::test_delete_project_refuses_a_directory_outside_the_manager_base`, `::test_delete_project_prefers_the_recycle_bin_and_falls_back_to_rmtree` |
| 4 | Frame-strip edits never saved; close did not autosave. | `FramesWorkspace._on_frames_changed` calls `tab.save_current_project()`; `SpriteTab.shutdown()` calls `_autosave()`. | `test_sprite_tab_integration.py::test_strip_edit_saves_the_project`, `::test_real_sprite_tab_shutdown_autosaves` |
| 5 | Run pipeline and the image route did not check the render queue. | `ProcessingPanel.set_busy_guard()`; the workspace installs a guard on `tab.queue_panel.is_busy()`; `open_image_route_dialog` checks the queue too. | `test_processing_panel.py::test_run_pipeline_is_refused_while_an_external_job_runs`, `test_sprite_tab_integration.py::test_run_pipeline_is_refused_while_the_render_queue_runs`, `test_image_route_dialog.py::test_image_route_is_refused_while_the_render_queue_runs` |

## Security

| Finding | Fix | Test |
|---|---|---|
| `action.id` was an unsanitised path component under `_reset_dir`'s rmtree. | `validate_action_id` (`[A-Za-z0-9_-]{1,64}`) in `ActionCard.from_dict` and in `pipeline.stage_dir`. | `test_project.py::test_action_card_rejects_an_id_that_is_not_a_single_path_segment`, `test_pipeline.py::test_stage_dir_refuses_an_action_id_that_escapes_the_project` |
| Raw tag name in the engine-preset GIF file name. | `sanitize_filename(tag.name)` in `_write_gif`. | `test_engine_presets.py::test_gif_filename_sanitizes_the_tag_name` |
| Repo `AGENTS.md` had dropped the repo-level security rules. | Four bullets restored under Hard rules. | none |

## Not changed, and why

- "The PR body says the branch carries a sprite CLI": the PR body does not
  mention a CLI. No change.
- The non-blocking suggestions (plate colour in the key fingerprint, purge
  behaviour, numeric frame sort, `null` tolerance in `from_dict`, edit-chain
  resume, retry after timeout, gcloud project id, `_ensure_client` return,
  settings-dialog model text, refine cancel token, duplicate `redact_secrets`,
  optional scikit-image) are deferred to follow-up issues or the next round.
- Ruff reports 14 pre-existing findings in three touched files (E402 in
  `test_gen_video_route.py`, F401 in `test_gen_queue.py` and
  `video_route.py`). They pre-date this round and are left alone.
