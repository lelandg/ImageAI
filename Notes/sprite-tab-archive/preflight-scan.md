# Pre-flight conflict scan — sprite-image-route-exports-plan

Scanned 2026-08-30. Plan: `Plans/2026-08-29-sprite-image-route-exports-plan.md` (11 tasks, 4143 lines,
read in full). Spec: `Plans/2026-08-29-sprite-tab-design.md` §2/§3 row 6/§4.6/§5 (read in full).

## 1. Names assumed from sibling plans (summary section) vs. actual code/plans

Verified every symbol in the "Names assumed from sibling plans" block against the real
implementation for sub-projects 1/2/3 (all merged on this branch) and against the sibling
`-gui-a-plan.md` / `-gui-b-plan.md` text for 5a/5b (not yet implemented).

| Symbol | Assumed | Actual | Verdict |
|---|---|---|---|
| `core.sprite.models.{FrameMeta,TagMeta,SheetMeta,Rect,Size}` + `frames_for` | fields/sig as listed | `core/sprite/models.py:33-172` — identical fields, defaults, `frames_for` | MATCH |
| `exporters.grid.{GridOptions,export_grid}` | fields/sig as listed | `core/sprite/exporters/grid.py:30-38,118` — identical | MATCH |
| `exporters.aseprite_json/texturepacker_json/png_sequence/gif` exports | sigs as listed | `core/sprite/exporters/*.py` — identical kwargs | MATCH |
| `slicing.{guess_grid,slice_sheet}`, `import_png_sequence` | sigs + out_dir-clear behavior | `core/sprite/slicing.py:86-158` — `slice_sheet`/`import_png_sequence` call `_reset_dir(out_dir)`; plan's Task 6/10 always pass a `clips/…` or generated-sheet source outside the `stages/<id>/extract` out_dir, never a source living inside it | MATCH, hazard avoided (see §4) |
| `pipeline.{CancelToken,Cancelled,ProgressFn,no_progress,run_pipeline,stage_dir}` | sigs as listed | `core/sprite/pipeline.py:37-67,133,510` — identical; `run_pipeline` accepts a pre-populated extract dir w/ `action.clip is None` (G9), confirmed via `extract_runner` (`:340-357`) and `extract_stage_settings` (`:178-185`, hashes `external` frame identity so a re-render invalidates downstream cache) | MATCH |
| `project.{ActionCard,SpriteProject}`, `undo.{FrameListSnapshot,SnapshotStack}` | as listed | `core/sprite/project.py`, `core/sprite/undo.py` | MATCH |
| `generation.errors.{SpriteGenerationError,ProviderError,classify_provider_error}` | ctor sig, kwargs | `core/sprite/generation/errors.py` — exact ctor `(user_message,*,retryable=None,operation_id=None,original=None)`; plan never passes `operation_id` but that's an extra optional kwarg, not a break | MATCH |
| `generation.prompts.{inject_chroma,color_name,FORBIDDEN_WORDS}` | as listed | `core/sprite/generation/prompts.py` | MATCH |
| `generation.cost.record_actual(...)` | full kwarg signature | `core/sprite/generation/cost.py:125-128` — identical, including keyword-override semantics | MATCH |
| `generation.timing.ms_to_fps` | `(durations_ms) -> (fps, multipliers)` | `core/sprite/timing.py` — identical, GCD-based | MATCH |
| action-cards `completion_fn(**kwargs)` + `response.choices[0].message.content` | convention | `core/sprite/generation/action_cards.py:253-297` | MATCH |
| `matting.difference_matte(on_white, on_black) -> Image` | sig | `core/sprite/matting.py:144` | MATCH |
| Sub-project 5a: `SpriteWorker`, `ActionCardsPanel.add_card_action/llm_provider`, `SpriteTab.{make_provider,config,console,log,current_project,current_action,action_cards_panel,add_toolbar_action,projectChanged,actionSelected}` | sigs as listed | `gui/sprite/workers.py` (already implemented, exact match incl. `finished=Signal(object)` connected without `[object]` indexing, proven safe by existing `WorkerHost`); `-gui-a-plan.md:356-376,1915,3173` for the rest (not yet implemented) | MATCH |
| Sub-project 5b: `ExportDialog.register_format`, `sheet_png_path`, `FrameStrip.retouchRequested/frames/refresh`, `PixelView.{selection_rect,...}`, `FramesWorkspace.apply_frames` | sigs as listed | `-gui-b-plan.md:3559-4206 (register_format), 1813-2040 (FrameStrip), 643-797 (PixelView), 4923-5093 (FramesWorkspace)` — exact match including the `*, needs_sheet=False, takes_template=False, checked=False` keyword-only tail | MATCH |
| `providers/openai.py MODEL_CAPS`, `providers/google.py GoogleProvider.edit_image` | table + sig | `providers/openai.py:46-168`; `providers/google.py:1832` | MATCH |
| `core/llm_params.build_completion_kwargs`, `core/llm_models.resolve_model` | sigs | `core/llm_params.py:473-484`; `core/llm_models.py:63` | MATCH |
| `core/utils.write_image_sidecar/sidecar_path` | as listed | `core/utils.py:191,196` (plan cites `:193`, off by ~3 lines — stale citation only, not a functional issue) | MATCH (minor stale line cite, non-blocking) |
| `GoogleProvider.edit_image_region`, `start_edit_session`, `reset_edit_session`; `OpenAIProvider.edit_image` mask semantics | sigs used in Tasks 7/8 calls | `providers/google.py:1907-2095`; `providers/openai.py:821-877` | MATCH (positional/keyword args in plan code line up exactly) |
| `MODEL_CAPS["gpt-image-1"]` fallback literal | "only permitted hit," mirrors `providers/openai.py:173 _caps_for` | `providers/openai.py:171-173`: `return MODEL_CAPS.get(model) or MODEL_CAPS["gpt-image-1"]` | MATCH, citation verified verbatim |

**0 mismatches** in this section.

## 2. Task-pair producer/consumer checks (within this plan)

| Producer → Consumer | Interface | Verdict |
|---|---|---|
| Task 1 `export_godot_tres`/`ordered_frame_indices` → Task 2 `_write_godot_tres`/`fps_reconciliation` | same signatures, same import path | MATCH |
| Task 2 `ENGINE_PRESETS`/`FORMAT_IDS`/`fps_reconciliation` → Task 4 `engine_preset_box.py` | same names, same import path; Task 2's lazy `_write_aseprite_native` import of Task 3's `export_aseprite` explicitly deferred so Task 2's own tests pass before Task 3 exists (stated in plan's own "Order check") | MATCH |
| Task 3 `export_aseprite` → Task 4 `write_aseprite_native` | same sig | MATCH |
| Task 5 `generate_pose_instructions` → Task 6 `image_route.py` (re-export) → Task 10 `image_route_dialog.py` import | re-export chain intact, all three modules import consistently | MATCH |
| Task 6 `provider_kind, call_provider, first_image, save_png, log_request, log_response, openai_sheet_size` → Task 7 `edit_chain`, Task 8 `retouch.py` | identical helper names/signatures reused verbatim (plan's own self-review confirms and code matches) | MATCH |
| Task 7 `edit_chain` matte pairs → `difference_matte` (sub-project 3) | `core/sprite/matting.py:144` sig `(on_white, on_black) -> Image` matches test's `fake_matte(on_white, on_black)` monkeypatch target `core.sprite.matting.difference_matte` | MATCH |
| Task 8 `retouch_frame` → Task 9 `retouch_dialog.build_job()` | same kwargs (`neighbors=`, `region=`, `model=`, `log=`) | MATCH |
| Task 9 `FrameStrip.retouchRequested(int)` (5b) → `install_retouch` | consumer wires `tab.frame_strip.retouchRequested.connect(...)`; matches 5b `Signal(int)` | MATCH |
| Task 9 `apply_retouch` → 5b `FramesWorkspace.apply_frames(action_id, frames, label)` | snapshot-then-install ordering documented and matches 5b's own docstring behavior ("pushes the undo snapshot of the CURRENT action.frames") | MATCH |
| Task 10 `ImageRouteDialog` → Tasks 5-7 (`generate_sheet`, `slice_generated_sheet`, `edit_chain`, `generate_pose_instructions`, `default_openai_edit_model`) and sub-project 2 `record_actual` | all call sites match the real/assumed signatures, including `seconds=` = edit-count semantics called out in the Names-assumed note | MATCH |
| Task 10 `archive_existing_frames` → `stage_dir`'s extract directory | archives (renames) instead of deleting; new content then written by `slice_generated_sheet`/`edit_chain` into a distinct directory — no path collision with `slice_sheet`'s "clears out_dir" behavior since the sheet PNG source always lives under `clips/`, never under `stages/<id>/extract/` | MATCH |

**0 mismatches** in this section.

## 3. Self-consistency (tests vs. code, per task)

Checked names/signatures/literals used in each task's test file against that task's own
implementation code, golden-file expectations against the renderer, "Files" lists against
files actually created/modified, and commit file lists against files created:

- Task 1: golden `.tres` content vs. `render_godot_tres` output logic (Rect2 margin formula,
  `speed`/`loop`/`duration` fields, `load_steps` arithmetic) — consistent. Commit list matches
  File Structure table. MATCH.
- Task 2: preset formats reference only ids in `FORMAT_IDS`; `test_every_preset_is_well_formed`
  checks constraints (`formats ⊆ FORMAT_IDS`, `0≤pivot≤1`, `how_to_import` sentence count,
  `json_layout ∈ {hash,array}`) that the literal `ENGINE_PRESETS` dict actually satisfies for
  all 8 entries (checked unreal → `json_layout="array"`, others default `"hash"`). MATCH.
- Task 3: byte-layout struct formats (`_HEADER`, `_FRAME_HEADER`, etc.) match the documented
  Aseprite spec table sizes (128/16/6 bytes), and `read_aseprite_summary` decodes exactly the
  chunks `export_aseprite` writes (order: color-profile, [palette], layer, [tags], cel on frame
  0; cel-only on later frames) — matches `test_chunk_layout_first_frame_carries_metadata`. MATCH.
- Task 4: `_FakeDialog` test double exposes exactly the 5b surface `register_extra_formats`/
  `install_engine_presets` touch (`options_layout`, `format_checks`, `notes_label`, `grid`,
  `pivot_x_spin/y_spin`, `name_template_edit`, `register_format`, `set_grid_options`,
  `grid_options`, `current_meta`) — all present in the real `-gui-b-plan.md` `ExportDialog`.
  MATCH.
- Task 5: contract schema (`POSE_STEPS_SCHEMA`) vs. `parse_pose_steps` validation logic (version,
  count, order, non-empty, forbidden-word strip) — every rejection path has a matching test.
  MATCH.
- Task 6: `sheet_prompt`/`generate_sheet` never place aspect or pixel size in prompt text —
  `test_sheet_prompt_is_clean` asserts this and the implementation only puts `aspect_ratio=`/
  `size=` in kwargs. MATCH.
- Task 7: `edit_chain` reference-image ordering (`[character, prev]`) matches
  `test_edit_chain_google_chains_previous_frame`'s asserted `calls[k].args[0]`. Matte-pair
  plates written as `NNNN.white.png`/`NNNN.black.png` before the merged `NNNN.png` — sidecar
  `plates` list and `matte_pairs` flag match `test_edit_chain_matte_pairs`. MATCH.
- Task 8: `next_retouch_path` numbering (`.rN`) matches `retouch_frame`'s use of it as the
  default `out_png`, and `FileExistsError` is raised before any provider call in the
  "never overwrite" test. `validate_retouch`/retry-then-raise loop matches
  `test_unchanged_result_retries_then_raises` (`attempts=2` → `edit_image.call_count == 2`,
  no `.r1.png` written). MATCH.
- Task 9: `RetouchDialog` MRO `(DialogCleanupMixin, QDialog)` matches the dialog-conventions
  docstring requirement; `SpriteWorker.finished.connect` (no `[object]` indexing) matches the
  real `gui/sprite/workers.py` implementation, not just the "known risk" caveat in
  `-gui-a-plan.md`. MATCH.
- Task 10: `record_actual` call's `seconds=float(edits)` where `edits = len(paths) * (2 if
  matte else 1)` matches `test_sheet_job_fills_frames_and_runs_pipeline`'s
  `ledger_kwargs["seconds"] == 3.0` (3 frames, no matte) and the design's "seconds is the unit
  count — edits — for this route" note. `frames_before`/`_on_rendered` restore-then-apply
  ordering matches `test_install_image_route_registers_button_and_builds_dialog`'s asserted
  `tab.applied == [("a1","Render (image)",0,1)]`. MATCH.
- Task 11: guard commands (`test_no_hardcoded_paths.py`, full `tests/sprite`, full suite) and
  the forbidden-literal grep target exactly the files this plan creates. MATCH.

**0 mismatches** in this section.

## 4. Constraint/spec conflict checks

| Constraint | Finding | Verdict |
|---|---|---|
| No `claude-*`/`gpt-*`/`gemini-*` literal outside `static_default=`/`MODEL_CAPS` lookup | Only hit is `MODEL_CAPS.get(model) or MODEL_CAPS["gpt-image-1"]` in `openai_sheet_size`/`openai_edit_size` — a capability-table key lookup, verbatim-mirrors `providers/openai.py:173 _caps_for`. Plan's own Task 11 Step 2 greps for this and calls it out as the only permitted hit. | OK, no conflict |
| No "transparent"/aspect/dimensions in prompt text | `sheet_prompt`, `STEP_PROMPT`, `retouch_prompt` never embed aspect/px; `inject_chroma`/`strip_render_terms` (already merged, confirmed) strip them; `SHEET_ASPECT_GEMINI`/`size=` only ever go into kwargs, never string-interpolated into a prompt. Tests assert this (`test_sheet_prompt_is_clean`, `test_messages_name_contract_and_frames`). | OK, no conflict |
| Provider calls never on the UI thread | Every provider call in Tasks 6-10 happens inside a `job(progress, token)` closure run through `SpriteWorker`/`WorkerHost`; dialogs never call `retouch_frame`/`generate_sheet`/`edit_chain`/`generate_pose_instructions` directly from a button slot. | OK, no conflict |
| Dialogs calling LLMs need status console / Ctrl+Enter / Escape | `RetouchDialog` and `ImageRouteDialog` both build a `DialogStatusConsole`, call `bind_primary_action` (Ctrl+Enter) and use `DialogCleanupMixin` (Escape/close) — confirmed against real `gui/llm_utils.py:15-83` and `gui/common/dialog_conventions.py` signatures. | OK, no conflict |
| Unlogged user-facing errors | `classify_provider_error` logs via `logger.error(..., exc_info=exc)` before returning; both dialogs' `_on_failed` log to `logger.error` and the status console. | OK, no conflict |
| No hand-built data paths | `stage_dir()`/`project.project_dir` composition follows the same pattern already used by sub-project 1's own `stage_dir()`; no absolute-root path is built by hand (the `tests/test_no_hardcoded_paths.py` guard target). | OK, no conflict |
| Every written artifact gets a `.json` sidecar | `.tres` (Task 1 `write_image_sidecar`), `.aseprite` (Task 3), retouched PNG (Task 8), sheet/edit-chain frames (Tasks 6-7 `write_image_sidecar`/`slice_generated_sheet`) all call it. | OK, no conflict |
| Raw frames never overwritten; retouch writes `NNNN.r<k>.png` | `next_retouch_path` + `FileExistsError` guard in `retouch_frame`; original frame bytes read but never re-saved to the same path. | OK, no conflict |
| Re-render archives, not deletes, the previous extract dir | Task 10 `archive_existing_frames` renames `stages/<id>/extract` to `extract.prev-<timestamp>` before writing new frames, rather than deleting it (as `_reset_dir`/`slice_sheet` do internally for a *fresh* target dir). | OK, no conflict |
| `slice_sheet`/`import_png_sequence` clear `out_dir` before writing — caller must never pass a source living inside `out_dir` | Every call site in this plan (Task 6 `slice_generated_sheet`, Task 10's dialog) passes a sheet PNG under `project_dir/clips/...` as source and `stages/<id>/extract` as `out_dir` — always distinct directories. | OK, hazard not triggered |

**0 conflicts** in this section.

## 5. Rubric-defect checks (vacuous tests, duplicated logic)

Scanned all ~90 test functions across the plan's 11 tasks for assertion-free bodies and
scanned the produced modules for copy-pasted logic blocks that should be shared helpers.

- No test function found with zero assertions or a body that can't fail.
- No duplicated logic block found: shared helpers (`provider_kind`, `call_provider`,
  `first_image`, `save_png`, `log_request`, `log_response`, `openai_sheet_size`,
  `openai_edit_size`, `default_openai_edit_model`) are defined once in Task 6 and imported
  (not re-implemented) by Tasks 7, 8, and 10.

**0 defects** in this section.

## Summary

**Total rows checked:** ~55 across all five categories (18 names-assumed rows, 10 task-pair
rows, 11 self-consistency rows, 9 constraint rows, 2 hazard/defect-sweep rows).
**MISMATCH / CONFLICT rows: 0.**

The only note worth carrying forward (not a mismatch): two `core/utils.py` line citations in
the plan (`:14` for `sanitize_filename`, `:193` for `write_image_sidecar`) are stale by ~3
lines against the current file (actual: `:17`, `:196`) — cosmetic only, does not affect any
import or behavior.
