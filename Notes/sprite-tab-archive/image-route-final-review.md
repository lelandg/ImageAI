# Final whole-branch review — sub-project 6 (image route, retouch, engine exports)

**Reviewer:** final-ir (senior code reviewer, read-only)
**Range:** `e83e39c..4567f8a` (21 commits, 24 files, +3946/-9)
**Date:** 2026-08-30
**Method:** read in passes — the review context, `global-constraints.md`, the plan header, the
global constraints, the per-task interface lists for Tasks 1–11, the Self-review and all 13 recorded
deviations; design spec §2, §3 row 6, §4.6 and §5; the controller ledger `progress.md` in full plus
`task-10-review.md` and `task-10-rereview.md`; then the whole source portion of
`review-e83e39c..4567f8a.diff` (godot_tres, engine_presets, aseprite_native, pose_steps, image_route,
retouch, export_formats, engine_preset_box, retouch_dialog, retouch_wiring, image_route_dialog, the
two touched 5a/5b files); then every consumed contract (`core/sprite/{models,pipeline,project,undo,
timing,matting}.py`, `core/sprite/exporters/*.py`, `core/sprite/generation/{_common,cost,errors,
prompts,action_cards}.py`, `core/{utils,llm_models,llm_params,llm_parsing}.py`,
`providers/{google,openai}.py`, `gui/sprite/{workers,frames_workspace,frame_strip,processing_panel,
action_cards_panel,export_dialog,sprite_tab}.py`, `gui/common/dialog_conventions.py`); then all ten
test modules and the golden `.tres`; then live offscreen probes. Five verification dimensions (spec,
providers, exporters, threading, seam, tests) each ran three independent votes per finding. A finding
survives only when a majority of votes confirm it against HEAD. The working tree, the index, HEAD and
the branches were not modified. Every scratch file lives under the session scratchpad. All line
numbers cite HEAD `4567f8a`.

**Verification actually run (not claimed):**

| Check | Command / probe | Result |
|---|---|---|
| Full suite (controller, 2026-08-30) | `pytest` on `4567f8a` | **1887 passed**, 19 skipped, 2 third-party warnings, 228.87 s |
| Guard grep, model-ID literals | six new runtime modules | only the two permitted `MODEL_CAPS["gpt-image-1"]` fallback keys (`image_route.py:100`, `:115`) |
| Core exporter + generation tests | `pytest test_{godot_tres,engine_presets,aseprite_native,pose_steps,image_route,retouch}.py` | 77 passed, 24.84 s, 0 warnings |
| GUI tests | `pytest gui/test_{export_dialog_engine_presets,image_route_dialog,retouch_dialog,export_dialog}.py` | 60 passed, 24.55 s, 0 warnings |
| Whole sprite directory | `pytest tests/sprite -q` | 809 passed, 125.21 s |
| Sprite GUI directory (traced) | `pytest tests/sprite/gui` under `sys.settrace` | 268 passed, 89.72 s |
| Preset manifest vs disk | `probe_manifest.py`, all eight presets, 4 frames / 2 tags | 7 presets exact; `web_preview` returns 8 paths, writes 12 |
| PNG-sequence sidecars | `probe_png_seq_manifest.py` | missing from manifest: 4 × `frames/*.png.json`; extra: 0 |
| GIF sidecar frame count | `probe_gif_sidecar.py`, ping-pong tag | GIF holds 6 frames, sidecar says `"frames": 4`; forward and reverse match |
| Chat-model resolution | `probe_pose.py`, live registry | `resolve_model('google'\|'gemini'\|'anthropic','chat')` → `'chat'`; provider receives `model='gemini/chat'` |
| Retouch neighbours (region path) | `probe_retouch_neighbors.py`, distinct frame shades | provider receives 1 image; prompt claims 2; sidecar records 2 |
| Retouch neighbours (control, no region) | same probe | provider receives 3 images in order `f2, f1, f3` |
| Retouch default-log duplication | `probe_retouch_doublelog.py`, no `log=` argument | full request and full response each logged twice, under two logger names |
| Cancel between matte plates | `probe_edit_chain_cancel.py` | 2 plate calls issued, 1 after Cancel landed; control `retouch_frame` stops after 1 |
| Busy guard, Render (image) | `probe_busy_guard.py`, real `ProcessingPanel` worker | `panel.is_busy()` True; dialog still opens; `is_busy()` consulted 0 times; extract dir renamed under the pipeline |
| Busy guard, Retouch | `probe_retouch_race.py`, real modal `exec()` + real `_sync_frames` | `IndexError` out of the Qt slot; `tab.applied == []`; the paid retouch is lost |
| Dialog lifetime | `probe_dialog_leak.py`, 5 opens each | 5/5 `ImageRouteDialog` and 5/5 `RetouchDialog` alive after `gc.collect()`, all tab children |
| Matte plates vs pipeline | `probe_matte_plates.py`, real `edit_chain` + real `run_pipeline` | 3 rendered frames become 9 `action.frames`, play order scrambled |
| Godot `.tres` structure | `probe_formats.py`, quote + backslash in tag name and atlas path | escaping correct; `load_steps` = ext + subs + 1; matches the golden |
| Aseprite container | `probe_formats.py`, hand-computed byte offsets | header size field == 512 actual; every frame chunk walk exact; 0 trailing bytes |
| Golden `.tres` sensitivity | `probe_regress.py`, three line-structure regressions | all 9 tests pass for every regression; a wrong field value is caught |
| `billed_units` coverage | `mutplugin.py`, inverted sheet read + no matte doubling | mutant survives `tests/sprite` (809 passed) |
| Archive collision loop | `probe_archive_collision.py` + traced GUI run | lines 50–51 never execute in 268 tests; 4 same-second archives stay distinct |
| Brief vs implementation test names | `def test_` diff over `task-{1..10}-brief.md` | 1 name absent, superseded by two stronger tests |
| Tree hygiene | `git status --porcelain`, `git rev-parse --short HEAD` | no change under `core/sprite`, `gui/sprite`, `tests/`; HEAD `4567f8a` |

---

## Plan/spec alignment — verdict + deviations

**Verdict: spec-complete on symbols and seams, with one unrecorded Important seam break (matte
plates in the extract stage directory), three unrecorded Important defects in the provider layer, and
two unrecorded Important gaps in the GUI busy-state contract.**

Every symbol design §4.6 and the plan's File Structure name exists with the stated behaviour:
`sheet_prompt`, `generate_sheet`, `slice_generated_sheet`, `edit_chain`, `generate_pose_instructions`,
`retouch_frame` with all three provider paths, `export_godot_tres`, `EnginePreset` / `ENGINE_PRESETS`
for the eight named engines, `export_with_preset`, `fps_reconciliation`, and `export_aseprite` with
`read_aseprite_summary`.

**All 13 recorded deviations match the code.** Deviation 1 (pose_steps split out and re-exported),
2 (optional `out_png` on `retouch_frame`), 3 (two-reference edit-chain continuity with
`start_edit_session` / `reset_edit_session` in a `finally`), 4 (`EnginePreset.json_layout`, `"array"`
for Unreal only), 5 (Godot direction unrolling reported by `fps_reconciliation`), 6 (the `token`
kwarg on `generate_sheet` and the new `slice_generated_sheet`), 7 (`ImageRouteDialog` instead of a
bare card combo), 8 (the sibling-plan names), 9 (the palette-length `ncolors` header field),
10 (one format-id vocabulary), 11 (`timing.py` ownership), 12 (undo through
`FramesWorkspace.apply_frames` with `frames_before` restored before the snapshot), and 13 (the preset
box reuses 5b's `notes_label` at `options_layout` index 1) are all implemented as written.

**Hard rules hold on every path I could reach.** No dimension, aspect ratio or forbidden word reaches
prompt text: `sheet_prompt` and the edit-chain `STEP_PROMPT` pass through `inject_chroma` →
`strip_render_terms`, `parse_pose_steps` strips `FORBIDDEN_WORDS` from LLM-authored sentences, the
Gemini aspect goes through the `aspect_ratio=` kwarg (`providers/google.py:1856-1875`) and the OpenAI
size through `size=`. Raw frames are never overwritten: `retouch_frame` writes `NNNN.r<k>.png` and
raises `FileExistsError` rather than overwrite, and `archive_existing_frames` renames a populated
extract directory aside. No data path is built by hand; `project_dir` and `stage_dir` own every
location. Every artifact carries a `write_image_sidecar` sidecar, including the matte plates that
Task 7 once missed.

**Deviations that landed but are NOT recorded:**

1. `edit_chain` writes `NNNN.white.png` and `NNNN.black.png` into the same directory the pipeline
   reads as its extract stage, and `pipeline.list_frames` globs `*.png` without a filter. The design
   never states that the plates share the frame directory (Important 6).
2. `pose_steps.generate_pose_instructions` resolves its default chat model with the registry family
   `"chat"`. The registry has no `gemini/chat` or `anthropic/chat` family, so the default model
   becomes the literal string `"chat"` (Important 3). The plan text prescribes the call at line 20,
   but the plan does not record the resulting failure, and the sprite package already owns the
   correct helper.
3. The Gemini region-retouch branch drops the neighbour frames while the prompt, the request log and
   the sidecar all state that the neighbours were sent (Important 4).
4. Neither new card-row entry point checks `ProcessingPanel.is_busy()`, although
   `FramesWorkspace.open_export_dialog` fences exactly the same hazard for the export path
   (Important 7, Important 8).

**Recurring finding classes — the fifth-instance sweep.** Class 1 (an incomplete manifest) has a
fifth instance: `_write_png_sequence` returns the PNGs and drops every per-frame sidecar
(Important 1). Class 2 (a module that bypasses `_common.emit`) has a fifth instance: `retouch.py`
imports the three log helpers from `image_route`, so `emit`'s same-logger guard misses and the
default path double-logs (Important 5). Class 3 (a `gemini` id used as a config key) is closed:
`_config_key_for` imports `action_cards_panel.CONFIG_KEY_BY_PROVIDER_ID` instead of copying it, and
two tests pin the mapping. Class 4 (close-while-busy dropping a running QThread) is closed: both new
dialogs mix in `WorkerHost`, override `_on_worker_idle`, never write `self._worker`, and mirror
`ExportDialog.on_dialog_close`. No path destroys a running `QThread`.

---

## Strengths

- **The Godot exporter is correct field for field.** `_escape` replaces the backslash first and the
  quote second, so both metacharacters survive in a tag name and in an atlas path.
  `ordered_frame_indices` unrolls all four directions without a duplicated endpoint, `load_steps`
  equals one ext plus N subs plus one, `margin = Rect2(ox, oy, sw-w, sh-h)` matches Godot's
  `AtlasTexture` semantics, and the render matches the golden byte for byte after normalization.
- **The Aseprite writer matches the published byte layout.** An independent hand-offset parse (no
  module struct used) confirmed the container reconciles exactly: the header size field equals the
  real file length, every frame chunk walk consumes exactly the declared frame size, the reserved
  tail is zero, and no trailing byte remains. The 1.3 additions (cel z-index, tag repeat) are present.
- **Full-content LLM logging is real.** `log_request` prints provider, model, params and the complete
  prompt. `log_response` prints the image count, the per-image byte sizes and the model text.
  `pose_steps` logs the complete system and user messages and the complete raw reply, and strips
  `api_key` and `messages` from the params echo.
- **Every artifact gets its sidecar.** The sheet, each sliced cell, both matte plates with their own
  prompt and plate colour, the composed frame, and the retouch output all call
  `core.utils.write_image_sidecar`. `test_image_route.py:268-283` pins the plate provenance chain.
- **The partial-spend ledger is honest about direction.** `record_actual` runs before `run_pipeline`
  with `recorded = True`, so a pipeline failure cannot double-bill. The failure path and the cancel
  path both restore `action.frames`, `action.clip` and the status, then save the project.
- **Both new dialogs satisfy the worker-lifetime contract.** Each mixes in `WorkerHost`, overrides
  `_on_worker_idle`, never assigns `self._worker`, and closes with a bounded `shutdown()` followed by
  `join_orphans()`. `retouch_frame` polls its cancel token immediately before and immediately after
  each attempt's provider call, so the unbounded join returns after one call instead of the whole
  retry loop.
- **Every job closure snapshots its widget values on the GUI thread.** `build_job` in both dialogs,
  the pose-step job, and `_make_pose_fn` bind mode, provider, model, frame count, matte flag, typed
  steps, instruction, region, neighbours, api key and auth mode by value. No closure holds `self` or
  a widget.
- **The undo contract in deviation 12 is met end to end.** `start_render` deep-copies
  `action.frames` before the job, the module-level `_on_rendered` restores that list before
  `apply_frames` installs the rendered one, and `apply_retouch` repoints a deep copy. The snapshot
  therefore holds the pre-render frames, so undo is a real undo.
- **The format vocabulary is genuinely single.** `FORMAT_IDS` equals the five `BUILTIN_FORMATS` ids
  plus the two ids `register_extra_formats` adds, so `install_engine_presets.apply` can never
  mis-key a checkbox. `_grid_output_paths` models `export_grid` exactly, and the two
  manifest-equals-disk tests use a recursive listing rather than a subset check.
- **The 5a/5b footprint is four and six lines of pure addition.** No shutdown path, no
  `join_orphans` path, no `closeEvent` and no lazy-tab-load path changes. The three re-idd 5b tests
  were forced by a real registration collision, and no assertion was weakened; the builtin-order test
  was strengthened to pin all seven ids.

---

## Issues

### Critical

None.

### Important

**Important 1 — `export_with_preset`'s PNG-sequence manifest omits every per-frame sidecar it writes**
`core/sprite/exporters/engine_presets.py:168-169` (`_write_png_sequence` returns only
`export_png_sequence`'s PNGs); `core/sprite/exporters/png_sequence.py:66-67` (each frame gets
`write_image_sidecar`), `:100-105` (the return list holds PNG paths only); the sibling writers at
`engine_presets.py:165`, `:181`, `:188` and `:216` all return their sidecars.
*Failure:* `export_with_preset(meta, "web_preview", out)` on a 4-frame, 2-tag sheet returns 8 paths
while 12 files land on disk. The four missing entries are `frames/hero_walk_01.png.json`,
`frames/hero_walk_02.png.json`, `frames/hero_idle_01.png.json` and `frames/hero_idle_02.png.json`.
Sub-project 7 consumes `export_with_preset` as its one-call export seam, so a CLI that zips, copies
or reports the returned list drops every frame sidecar and the bundle loses the frame provenance the
repo hard rule requires. This is the fifth instance of class 1, which the controller ruled Important
for Task 2 and Task 4 under the rule "every writer's return list must equal what lands on disk". The
two manifest-equals-disk tests both use `phaser3` (grid + texturepacker_json), and the `web_preview`
test asserts only `any(p.parent.name == "frames" for p in written)`, so no test can catch it.
*Fix:* return the sidecars beside the PNGs —
`pngs = list(export_png_sequence(meta, out_dir / "frames", template=preset.name_template))`, then
`return [p for png in pngs for p in (png, sidecar_path(png))]`. Add the recursive disk-versus-manifest
assertion to a `web_preview` export in `tests/sprite/test_engine_presets.py`.

**Important 2 — the GIF sidecar states a frame count the GIF does not have for a ping-pong tag**
`core/sprite/exporters/engine_presets.py:176-181` (`_write_gif` writes
`"frames": tag.to_index - tag.from_index + 1`); `core/sprite/exporters/gif.py:65-69` (`pingpong`
writes `frames + reversed(frames[1:-1])`, `pingpong_reverse` likewise); `gif.py:113-125`
(`export_gif` already wrote a richer, correct sidecar at the same path, with `"frames": len(frames)`,
`durations_ms`, `loop` and `warnings`).
*Failure:* export `web_preview` for a tag `TagMeta(name="walk", from_index=0, to_index=3,
direction="pingpong")`. `hero_walk.gif` holds 6 frames; `hero_walk.gif.json` says `"frames": 4`.
`write_image_sidecar` targets the identical path, so the preset writer also discards
`durations_ms`, `loop`, `warnings` and `timestamp` that `export_gif` recorded. A reader who sizes a
playback loop from the sidecar, or who verifies the export, gets the wrong number. A `reverse` tag is
unaffected, because a reverse only reorders the frames. No test pins the sidecar body.
*Fix:* compute the count from the same unrolled order the exporter uses. `ordered_frame_indices` is
already imported at `engine_presets.py:11`, so write `"frames": len(ordered_frame_indices(tag))`.
Better still, merge the preset fields into `export_gif`'s sidecar instead of overwriting the file.

**Important 3 — pose-step model resolution asks the registry for a family that does not exist, so the default model becomes the literal string `"chat"`**
`core/sprite/generation/pose_steps.py:156` (`model = model or resolve_model(provider, "chat")`);
`core/llm_models.py:71-76` (`resolve_model` catches the `LookupError`, logs a warning and returns
`static_default or family`, which is `"chat"` here); the correct helper already exists at
`core/sprite/generation/action_cards.py:232-245` (`_CHAT_FAMILY` maps gemini → `flash`, anthropic →
`sonnet`, openai → `chat`, and `default_chat_model` normalizes the provider alias first).
*Failure:* a user opens Render (image), picks Edit chain and clicks "Generate pose steps", or leaves
the pose box empty so `build_job` calls `pose_fn` at `gui/sprite/image_route_dialog.py:239`.
`_make_pose_fn` passes `model=None` and the panel id `google` or `gemini`. Verified end to end at
HEAD: the registry warns `no family gemini/chat in registry (known: ['flash', 'flash-lite', 'pro'])`,
`resolve_model` returns `'chat'`, `build_completion_kwargs` sends `model='gemini/chat'`, and the
provider rejects it. `classify_provider_error` turns the rejection into a `ProviderError` and the
dialog shows "Failed: … models/gemini/chat is not found for API version v1beta". The LLM pose-step
path — the whole reason Task 5 exists — never works for Google, Gemini or Anthropic on the default
path, and the GUI offers no other path. Every test either passes an explicit `model=` or
monkeypatches `resolve_model`, so no test exercises real resolution.
*Fix:* use the package's own helper. Import `default_chat_model` from
`core.sprite.generation.action_cards` and write `model = model or default_chat_model(provider)`. Add
a test that does not monkeypatch `resolve_model` and asserts the resolved model is not the family
name.

**Important 4 — the Gemini region retouch never sends the neighbour frames, but the prompt, the request log and the sidecar all state that it did**
`core/sprite/generation/retouch.py:142` (`prompt = retouch_prompt(instruction,
neighbors=len(neighbor_paths))`, which appends "The other N image(s) are the neighboring animation
frames"); `:143` (`params["neighbors"]` carries the paths into `log_request`); `:152-153` (the region
branch passes `frame_bytes` only, while `:155` and `:162` do pass `neighbor_bytes`); `:179` (the
sidecar records `"reference_images": [str(p) for p in neighbor_paths]`); `core/utils.py:212` defines
`reference_images` as "paths or names of inputs to /edits".
*Failure:* a user drags a selection rectangle on frame 2, opens Retouch with Google Gemini selected
(the default) and types "fix the left hand". `open_retouch_dialog` always supplies frames 1 and 3 as
neighbours and always supplies the rectangle. Probe result at HEAD: the provider receives exactly one
image, while the prompt claims two neighbours, the request log lists two neighbour paths and the
persisted `.json` records two reference images. The continuity instruction therefore points at images
the model never saw, and the sidecar is false, so nobody can reproduce that frame from its
provenance. The control run without a region sends all three frames, which proves the wiring is
correct everywhere else. `providers/google.py:1907-1916` shows `edit_image_region` takes a single
image, so the branch itself is by design; the prompt and the provenance are not.
*Fix:* build the prompt and the provenance from what the code actually sends. Compute
`sent_neighbors = [] if (kind == "google" and region is not None) else neighbor_paths`, then use
`retouch_prompt(instruction, neighbors=len(sent_neighbors))`, set
`params["neighbors"] = [str(p) for p in sent_neighbors]`, and write the same list into the sidecar.
Extend `tests/sprite/test_retouch.py:80` to assert the prompt omits "neighboring" when none are sent.

**Important 5 — `retouch.py` double-logs every provider request and response on the default log path**
`core/sprite/generation/retouch.py:115` (`log: LogFn = logger.info`, bound to the *retouch* module
logger); `:20-23` (`log_request`, `log_response` and `call_provider` are imported from `image_route`);
`core/sprite/generation/image_route.py:77`, `:83`, `:92` (each helper calls `emit(logger, log, …)`
with *image_route's* module logger); `core/sprite/generation/_common.py:21` (the guard skips the sink
only when `getattr(log, "__self__", None) is logger`).
*Failure:* the sink's `__self__` is `core.sprite.generation.retouch` while the emitting logger is
`core.sprite.generation.image_route`, so the identity guard misses and both sinks fire. Probe at
HEAD, calling `retouch_frame(provider, frame, instruction)` with no `log=` argument: the full request
line (which carries the whole prompt) and the full response line each appear twice, under two
different logger names. `retouch`'s own emit-routed lines appear once, which isolates the cause to
the three imported helpers. Sub-project 7's CLI calls `retouch_frame` without a `log=` argument, so
`imageai_current.log` doubles for the retouch route and a duplicated response reads as two provider
calls. The controller ruled this identical class Important for Task 5 and for Task 6.
*Fix:* give the shared helpers the caller's logger. Add a `logger` keyword to `log_request`,
`log_response` and `call_provider` in `image_route.py`, default it to image_route's logger, and pass
`logger=logger` from retouch's three call sites (`:150`, `:161`, `:166`). Add a once-only caplog test
like `tests/sprite/test_image_route.py:131`.

**Important 6 — matte plates land in the pipeline's extract stage directory, so `run_pipeline` treats them as animation frames**
`gui/sprite/image_route_dialog.py:214` (`extract_dir = stage_dir(project, action, "extract")`), `:241`
(`edit_chain(..., extract_dir, ..., matte_pairs=matte)`), `:259` (`run_pipeline(..., upto="stabilize")`
on the very next statement); `core/sprite/generation/image_route.py:298-299` (the plates are saved as
`NNNN.white.png` and `NNNN.black.png` in that same directory); `core/sprite/pipeline.py:145`
(`list_frames` is an unfiltered `directory.glob("*.png")`), `:351` (the extract runner returns it),
`:553` (`_sync_frames` rebuilds `action.frames` from the stabilize output). The module's own
`billed_units` guards against exactly this collision with `path.stem.isdigit()`
(`image_route_dialog.py:70`), so the hazard is known at one call site and unguarded at the other.
*Failure:* the user picks Edit chain, ticks "Render white + black plates and difference-matte (2x
cost)", sets Frames = 3, and renders. Verified end to end at HEAD with the real `edit_chain` and the
real `run_pipeline`: `edit_chain` returns 3 paths, the console says "Rendered 3 frame(s)", and
`action.frames` ends with 9 entries ordered `0001.black, 0001, 0001.white, 0002.black, …`. The frame
strip, the preview player and every later export therefore show the raw white and black plates
interleaved with the matted frames, in the wrong order, and every keying and stabilize cost is paid
three times. No recorded deviation and no ruling covers this seam; the Task 7 ruling covers only the
plates' missing sidecars. The test cannot catch it because `run_pipeline` is a `MagicMock`.
*Fix:* keep non-frame artifacts out of the extract stage directory. Write the plates into a sibling
directory (`out_dir / "plates"`) and keep recording their paths in the composed frame's sidecar
`plates` list, so `list_frames` still sees only `NNNN.png`. Do not filter `list_frames` instead —
that changes a sub-project 1 contract every stage depends on. Add a test that renders a 2-step matte
chain into a real extract directory and asserts `pipeline.list_frames(extract_dir)` returns exactly
the composed frames in order.

**Important 7 — "Render (image)" has no busy guard against the processing panel's pipeline worker**
`gui/sprite/image_route_dialog.py:390-399` (`open_image_route_dialog` checks only `project is None`);
contrast `gui/sprite/frames_workspace.py:322-327`, which refuses the export for exactly this reason
("`run_pipeline` rewrites `action.frames`, the locked palette and the stage directories that the
export reads, and no lock guards `SpriteProject`");
`gui/sprite/processing_panel.py:623-627` (`_sync_enabled` disables only `run_btn`, `preview_btn` and
`export_btn`, never the cards table); `gui/sprite/action_cards_panel.py:127-130` (the table is gated
on the *cards* panel's own busy state).
*Failure:* the user presses Run for action `walk`, then clicks "Render (image)" on the same row and
presses Render. The image-route job is a writer: it renames `stages/walk/extract/` aside
(`:215`), sets `action.clip = None` (`:223`), rewrites `action.frames` (`:246`) and runs a second
`run_pipeline` (`:259`), while the first worker is still writing that same stage directory and will
call `_sync_frames` itself. Probe at HEAD: `panel.is_busy()` is True, the dialog opens anyway,
`is_busy()` is consulted zero times, the pipeline's `0001.png` is moved into
`extract.prev-<stamp>` while its manifest still names `extract/0001.png`, the live directory ends up
holding both workers' files, both workers write `action.frames` and call `project.save()`, and the
last writer wins. On Windows the rename raises `PermissionError` instead and the render fails.
*Fix:* mirror `FramesWorkspace.open_export_dialog`. After the `project is None` check, refuse when
`tab.frames_workspace.panel.is_busy()` — log the warning, write
`tab.console.log(f"Wait for the running {label} job to finish before rendering", "WARNING")` and
return `None`. Add a GUI test that puts a gated worker on the processing panel and asserts the dialog
is not created.

**Important 8 — frame-strip "Retouch…" has the same missing busy guard, and `apply_retouch` indexes a frame list the pipeline worker can shorten under it**
`gui/sprite/retouch_wiring.py:29-31` (`open_retouch_dialog` validates `0 <= index <
len(action.frames)` once, then holds `index` for the life of the dialog), `:41` (the lambda binds the
stale index), `:22-23` (`apply_retouch` does `frames[index].source_path = …` with no bounds check);
`gui/sprite/frame_strip.py:450-453`, `:558-571` (the context-menu entry is never disabled);
`core/sprite/pipeline.py:479-506`, `:553` (`_sync_frames` drops old entries beyond the new count and
replaces `action.frames`).
*Failure:* the user presses Run for the current action (12 frames), right-clicks frame 11 and chooses
"Retouch…", so `index` is 10. `QDialog.exec()` blocks user input but still delivers queued events, so
the pipeline's stabilize stage can drop two duplicate frames and set `action.frames` to a 10-item
list while the modal dialog is up. Probe at HEAD, with the real modal `exec()`, a real `SpriteWorker`
and the real `_sync_frames` on a background thread: `IndexError: list index out of range` escapes the
Qt slot at `retouch_wiring.py:23`, `FramesWorkspace.apply_frames` is never reached, and `tab.applied`
stays empty — the retouch the user paid a provider call for is lost. In the equal-length variant no
error appears at all; the retouch is applied and then overwritten by the pipeline's own write.
*Fix:* refuse in `open_retouch_dialog` while `tab.frames_workspace.panel.is_busy()`, in the same
shape as `frames_workspace.py:322-327`. Additionally re-validate `0 <= index < len(action.frames)` at
the top of `apply_retouch` and return with a logged console WARNING when it no longer holds, so a
stale index can never raise out of a slot.

### Minor

**Minor 1 — four progress lines in `image_route` bypass `emit`, so they reach one sink only and a raising sink can abort the render**
`core/sprite/generation/image_route.py:193` (`log(f"[image route] sheet saved: {out}")`), `:212` and
`:214-215` (grid detected / grid rejected), `:328` (`log(f"[image route] step {k}/{frames} saved:
…")`); `core/sprite/generation/_common.py:18-26` (`emit` writes the module logger first and swallows
a sink that raises).
*Failure:* with the GUI's `self.logLine.emit` sink these four lines never reach the file logger, so
`imageai_current.log` cannot tell which frames landed on disk after a mid-chain failure. Probe: an
8-step chain logged every request and response but zero "step k/n saved" lines to the file logger,
and a sink that raises aborted `edit_chain` after step 1 while the emit-routed lines survived. This
is the Task 7 deferred minor; the triage row below rules **defer**, because no hard rule breaks today
and the sink cannot raise while `on_dialog_close` joins the worker.
*Fix:* replace the four bare calls with `emit(logger, log, …)`, matching every other log site in the
generation package. Fix this in the same wave as any `deleteLater` on the two dialogs.

**Minor 2 — `edit_chain` never polls the cancel token between the two matte plate calls, so Cancel still buys the second plate**
`core/sprite/generation/image_route.py:272-273` (the only poll, once per step), `:278`
(`for color in plates:`), `:287` and `:291` (one provider call per plate, with no poll between them
and none after); contrast `core/sprite/generation/retouch.py:121-124`, `:147` and `:165`, which
document and implement the opposite convention, as do `make_chroma_plate` and
`generate_action_cards`.
*Failure:* the user starts an 8-step chain with the matte checkbox ticked and presses Cancel while
step 3's white-plate call is in flight. Probe at HEAD: the white call returns, the black call is
issued and paid, and only step 4's poll raises `Cancelled`. The control run of `retouch_frame` under
the same probe stops after one call. The user pays for one image call they cancelled, and
`on_dialog_close` waits an extra provider round trip. The plan's brief places the check only in the
step loop, and Deviation 6 covers `generate_sheet` alone, so the shape is spec-matching but the
convention in the same package is stricter.
*Fix:* add `if token is not None: token.raise_if_cancelled()` at the top of the `for color in plates:`
body and again right after `log_response`, matching the retouch convention.

**Minor 3 — neither new modal dialog is deleted after `exec()`**
`gui/sprite/image_route_dialog.py:398-401` and `gui/sprite/retouch_wiring.py:41-44` (both connect a
result lambda, call `dialog.exec()` and return without `deleteLater()`); contrast
`gui/sprite/frames_workspace.py:341-345`, which deletes the export dialog in a `finally`.
*Failure:* probe at HEAD — five opens of each dialog leave 5/5 Python objects and 5/5 C++ objects
alive after `gc.collect()` and `processEvents()`, all still children of the tab, each holding roughly
50 (image route) or 39 (retouch) child widgets, and each `ImageRouteDialog` still holding its
deep-copied `frames_before` list. A session with eight renders and twenty retouches keeps 28 dialog
trees for the life of the process. The connect at `image_route_dialog.py:398` binds the dialog into
its own C++ connection storage, so even an unparented dialog could not be collected. This is the 5b
Minor 4 carry-forward; the triage row rules **defer**, because `DialogCleanupMixin` deletes nothing
by design and every sprite dialog shares the pattern.
*Fix:* wrap both `exec()` calls in `try/finally: dialog.deleteLater()` the way `open_export_dialog`
does, and bind the result handler with `functools.partial` on a module-level function instead of a
lambda that closes over the dialog. Fix Minor 1 in the same wave.

**Minor 4 — the golden `.tres` comparison collapses every newline, so it cannot detect a line-structure regression**
`tests/sprite/test_godot_tres.py:30-31` (`_norm` is `" ".join(text.split())`), `:37` (the golden
comparison); the only other line-aware guard is `:49`, which checks line 1 only.
*Failure:* Godot's text-resource parser is line-oriented — each `[sub_resource …]` header and each
`key = value` must start its own line. Probe at HEAD with three regressions (whole file joined with
spaces, atlas block joined with spaces, blank separators dropped): all nine tests pass every time,
and the rendered resource drops from 38 lines to 27 in the worst case. A wrong field value and a
dropped comma-space are still caught, so the gap is narrower than it sounds, but a `.tres` that Godot
refuses to import ships green. This is the Task 1 deferred minor; the triage row rules **defer**.
*Fix:* compare line by line —
`assert [l.rstrip() for l in out.read_text().splitlines()] == [l.rstrip() for l in
GOLDEN.read_text().splitlines()]`. That keeps the trailing-whitespace tolerance and restores newline
sensitivity.

**Minor 5 — `billed_units`' sheet branch and matte doubling have no test at all**
`gui/sprite/image_route_dialog.py:66` (`return 1 if sheet_done else 0`), `:71`
(`return steps * (2 if matte else 1)`); a grep of `tests/` for `billed_units` or
`record_partial_spend` returns nothing. The helper is reached only through two tests
(`test_image_route_dialog.py:295` and `:320`), and both run `mode="edit_chain"` with the matte
checkbox unticked. The sheet-mode failure tests never reach it: one fails after `recorded = True` and
the other raises outside the `try`.
*Failure:* a mutation probe that inverts the `sheet_done` read and removes the matte doubling
survives the whole sprite suite (809 passed). A behaviour probe shows the slip is real: with the
inverted read, a provider failure inside `generate_sheet` bills 1 unit for a call that never
completed, and a failure during slicing bills 0 for a sheet the user paid for. This function decides
what the user is billed, and the commonest real failure on the sheet route is the untested branch.
*Fix:* add two direct unit tests on the helper. `billed_units("sheet", False, tmp_path,
sheet_done=False) == 0` and `… sheet_done=True) == 1`, plus `billed_units("edit_chain", True,
dir_with_two_digit_pngs, False) == 4`. They need no dialog and no Qt.

**Minor 6 — the archive same-second collision loop is unreachable from any test**
`gui/sprite/image_route_dialog.py:48-51` (`serial = 2` then `while archive.exists():`);
`tests/sprite/gui/test_image_route_dialog.py:149-156` (`test_archive_existing_frames_moves_aside`
calls the function once on a populated directory and once on a missing one).
*Failure:* the first call renames the directory away, so the second call returns at `:42` without
entering the loop. A `sys.settrace` run over the whole GUI test directory (268 passed) shows lines 50
and 51 never execute. A later simplification that drops the counter, or one that starts it at 1,
raises `OSError`/`FileExistsError` inside the worker when a user re-renders an action twice within
one second, and the suite stays green. A four-archive probe inside one second confirms the loop works
today. This is Task 10 re-review item (b); the triage row rules **defer**.
*Fix:* freeze the clock and call twice. Monkeypatch `ird.datetime` so both calls get the same stamp,
re-create `extract` with a PNG between them, and assert the two archive names are `…prev-<stamp>` and
`…prev-<stamp>-2`.

---

## Deferred-minor triage

| Minor | Verdict | Why | Cost if wrong |
|---|---|---|---|
| T1: golden `.tres` comparison is whitespace-normalized (`tests/sprite/test_godot_tres.py:31`) | defer | The normalization is the brief's own test shape, and `test_load_steps_is_ext_plus_subs_plus_resource` plus four substring assertions still pin token order. | A `.tres` that keeps every token in order but loses its line breaks ships, and Godot refuses to parse the resource. |
| T3: Aseprite tags chunk packs `from_index`/`to_index` unclamped (`core/sprite/exporters/aseprite_native.py:109`) | defer | The unclamped write matches the `aseprite_json` convention, and no producer emits a negative index — `project.py:543` and `frames_workspace.py:170` both build tags from `0..len-1`. | A hand-edited project with a negative or >65535 index raises `struct.error` out of the export worker instead of a user-facing message. |
| T2: fps drift note has no magnitude gate (`core/sprite/exporters/engine_presets.py:263`) | defer | The controller already recorded this as a plan-owner note, because the brief's verbatim test pins the note shape; an over-eager warning is noise, not a wrong export. | The notes label shows sub-millisecond warnings a user learns to ignore, which hides a real drift note later. |
| T2: degenerate-duration note text (`engine_presets.py:268`) | defer | `duration_ms` is only ever produced as `round(1000 / max(1, fps))`, so a 0 ms frame needs a hand-edited project, and the fallout is one nonsensical advisory line. | A user who hand-edits a duration to 0 reads a self-contradictory note and cannot tell what the exporter did. |
| T2: `repeat == 1` is unnoted (`engine_presets.py:276`) | drop | False positive: `godot_tres.py:80` writes `loop=true` only for `repeat == 0`, so `repeat == 1` maps to `loop=false`, which is exactly "play once". Nothing is unrepresentable, so nothing needs a note. | Nothing — a note would describe behaviour the target already reproduces exactly. |
| T6: `default_openai_edit_model` / `openai_edit_size` unused (`core/sprite/generation/retouch.py:135`) | already-resolved | Both are consumed now — `retouch.py:135` and `:158` (Task 8, `22618af`), `image_route.py:255` and `:284` (Task 7, `e7d3b16`), `image_route_dialog.py:212` (Task 10, `5c6bc95`); `test_image_route.py:236-243` covers `openai_edit_size` directly. | None. Dead code would remain, which the check shows is no longer the case. |
| T4: unused `SimpleNamespace` import (`tests/sprite/gui/test_export_dialog_engine_presets.py:3`) | defer | The import is genuinely unused, but the repo carries no flake8, ruff or pyproject lint config, so nothing gates on it. | A future lint gate turns one dead test import into a build failure. |
| T7: bare single-sink `log()` progress lines (`core/sprite/generation/image_route.py:328`, `:193`, `:212`, `:214`) | defer | No hard rule breaks — every LLM request and response already routes through `emit` — and the sink cannot raise today, because `on_dialog_close` keeps the dialog alive through an unbounded `join_orphans`. | If Minor 3 is fixed by adding `deleteLater`, a still-running orphan's bare `log()` raises `RuntimeError` on the deleted QObject and aborts the render. Fix both items in one wave. |
| T8: unused `List` import (`core/sprite/generation/retouch.py:13`) | defer | `List` appears only on the typing import line, and no lint gate exists. | A future lint gate fails on one dead import in a runtime module. |
| T8: nonexistent neighbour paths dropped silently (`core/sprite/generation/retouch.py:140`) | defer | The drop is not silent in the record that matters: `params["neighbors"]` at `:143` carries the surviving list into `log_request`, so the full request log states which neighbours reached the provider. | A user whose neighbour file is missing gets a weaker retouch with only an implicit warning in the request log. |
| M1: `test_sheet_job_fills_frames_and_runs_pipeline` asserts overwritten `source_path`s (`tests/sprite/gui/test_image_route_dialog.py:79`) | defer | The assertion pins the dialog's own frame construction, which the dialog really performs, so the test can still fail on a real regression; only pipeline-seam fidelity is missing, and sub-project 7 exercises that seam. | A change to the `FrameMeta` the dialog hands `run_pipeline` passes this test while breaking the real stabilize hand-off. |
| M2: `FrameMeta.name` is discarded by `_sync_frames` (`gui/sprite/image_route_dialog.py:247`) | defer | Only the name is dead. `duration_ms` and the list length are load-bearing, because `_sync_frames` carries them forward by index, and the surviving name is the pipeline-wide convention. | On the rare cache-hit path frames keep the project-prefixed name while every other action uses the short one — a cosmetic naming inconsistency in exported sidecars. |
| M6: module-level `_on_rendered` shares its name with the method (`gui/sprite/image_route_dialog.py:374`) | defer | The two live in different namespaces and neither shadows the other; the collision costs reader attention, and the plan names the module function in deviation 8, so a rename needs a plan-owner ruling. | A maintainer edits the wrong `_on_rendered` and the mistake surfaces only at runtime. |
| M7: `frames_spin` never writes back to `action.target_frames` (`gui/sprite/image_route_dialog.py:125`) | defer | A write-back is not obviously right: the spin clamps to 2..24 while a card may carry up to 64, so a blind write-back silently truncates a 40-frame card, and the Frames column is already user-editable. | After a 5-frame render the cards table shows the old count, and `suggest_clip_duration` sizes a later video clip from the stale number. |
| M9: no undo snapshot when the rendered action is not the current one (`gui/sprite/image_route_dialog.py:383`) | **fix-now** | "Render (image)" sits on every card row, so rendering a non-selected card is fully reachable. Skipping `apply_frames` leaves that action's undo stack without a snapshot, so a later Ctrl+Z pops an older snapshot and discards the render. Global constraint 12 requires undo to go through `apply_frames` for image-route renders, and `apply_frames` already handles the non-current case with `reload=False`. | If the guard is intentional, dropping it costs one extra `projectChanged` emit and one extra save on a path that already saved. The wave must also flip `test_rendered_for_another_action_only_refreshes_status` and the plan prototype, which both encode the current shape. |
| (a): `billed_units` under-counts a matte step that dies between its two plate calls (`gui/sprite/image_route_dialog.py:70`) | defer | The under-count is capped at one provider call, on a render that already failed, and only in matte mode. Every completed step bills exactly, because the count runs against a directory `archive_existing_frames` has just emptied. | The cost panel understates a failed matte render by one edit, and the docstring reads as an exact rule when it is optimistic. A one-line docstring caveat is the cheap fix if a wave runs anyway. |
| (b): archive same-second collision loop has no test (`gui/sprite/image_route_dialog.py:49`) | defer | The loop is three lines whose only branch is "the name exists, so try the next serial", and a traced 268-test run confirms the code is correct today; a test needs a frozen clock. | A regression that reintroduces the same-second collision raises `OSError` out of the render worker on the second render of a second, with no test to catch it. |
| (c): `cancel_render` is a silent no-op against an unreaped orphan (`gui/sprite/image_route_dialog.py:304`) | defer | The orphan state is entered only from `on_dialog_close`, which then blocks on an unbounded `join_orphans`, so the Cancel button is unreachable while an orphan exists. The gap lives in the shared `WorkerHost` layer that `ExportDialog` and `RetouchDialog` also use. | In a future path that shuts down without joining, a user clicks Cancel, reads "Cancel requested", and nothing is cancelled. |
| (d): the failure path overwrites a good `"processed"` status (`gui/sprite/image_route_dialog.py:278`) | defer | The asymmetry is deliberate and defensible — the render did fail, `action.error` carries the message, and frames plus clip are restored — so any change is a plan-owner ruling about what a card badge means. | A card holding good restored frames shows a "failed" badge until the user re-renders, which can read as data loss when none occurred. |
| 5b Minor 4: the two new dialogs are never deleted after `exec()` (`gui/sprite/image_route_dialog.py:400`, `gui/sprite/retouch_wiring.py:43`) | defer | `DialogCleanupMixin` deletes nothing by design and every sprite dialog including 5b's `ExportDialog` shares the pattern, so fixing only the two new ones diverges from the family. No crash is possible, because `on_dialog_close` shuts down and joins every worker first. | Each Render (image) or Retouch open leaks one dialog, with its console and its deep-copied `frames_before` list, for the life of the app. Pair any `deleteLater` with the T7 bare-log item. |
| 5b Minor 6 + T7: a recycle-bin failure during purge-after-export reads as success (`gui/sprite/export_dialog.py:576`) | defer | Sub-project 6 did not touch this surface: the whole diff to `export_dialog.py` is two imports and two install calls, and the purge block is unchanged 5b code. | A per-item recycle failure that raises nothing still reads as a clean purge, and a slow recycle bin freezes the GUI — both unchanged from the 5b handover. |
| 5b T7: `_grid_output_paths` re-derives `grid.py`'s naming (`core/sprite/exporters/engine_presets.py:201`) | defer | Sub-project 6 added a second copy, but the duplication is guarded: `test_manifest_matches_every_file_on_disk_for_atlas_preset` compares the manifest against a recursive disk listing, so any drift from `grid.py:168-181` fails the suite. Changing `export_grid`'s return type touches every 5b caller. | If `grid.py`'s `@Nx` or sidecar naming changes while that test is weakened, the preset manifest lists files that do not exist and omits ones that do. |

---

## Refuted findings

- **`aseprite_json` and `aseprite_native` output names collide** (`engine_presets.py:152` vs `:187`) — the two names do resolve to the same `<title>.aseprite.json`, but `FORMAT_WRITERS` has one consumer, `export_with_preset`, which iterates a shipped preset's fixed `formats` tuple; no preset lists `aseprite_native` at all, the GUI path uses `<title>_<profile>` stems, and the CLI plan stems its own files differently. The collision needs code that does not exist.
- **The sheet route's success ledger row bills one provider call as N edits** (`image_route_dialog.py:253`) — the line, the note text and `seconds=float(edits)` are prescribed verbatim by the Task 10 brief, and the plan's own test pins `seconds == 3.0` with the comment "unit count = frames for the sheet route". Nothing aggregates `seconds`: `SpriteProject.total_cost` sums only `estimated_usd` and `actual_usd`, both `None` on image-route rows, so no panel overstates anything.
- **The Gemini edit-session priming call is logged on neither sink on success** (`image_route.py:261`) — `GoogleProvider.start_edit_session` logs its own outcome on both branches, returns `bool` and swallows every exception, so the console's warning at `:263-265` distinguishes primed from unprimed unambiguously; the call carries no caller-authored prompt and returns no images or text, so `log_request`/`log_response` have nothing of their shape to record. The block matches the brief verbatim and the controller reviewed and closed it.
- **`retouch_prompt` sends the raw user instruction without `strip_render_terms`** (`retouch.py:97`) — the plan supplies this function body verbatim, `FORBIDDEN_WORDS` exists to protect a machine-authored chroma-plate prompt rather than a user's own words, the retouch operates on an already-extracted RGBA frame, and stripping would mangle intent ("make the cape less transparent" → "make the cape less"). The result is written to a new `.r<k>.png` and is one undo away.
- **`RetouchDialog`'s docstring rationale for the unbounded `join_orphans()` is withdrawn** (`retouch_dialog.py:35`) — the sentence states the mechanism it relies on ("polls its `token` **around** the provider call"), and a probe confirms the polling converts an N-call worst case into a one-call worst case; `retouch_frame`'s own docstring states the exact semantics, and the in-place comment on the close path makes only the unambiguously true claim.
- **`export_with_preset` names its output without the profile, so a per-profile CLI export overwrites itself** (`engine_presets.py:227`) — the naming is the plan's own Task 2 convention and keeps the `.tres` `res://<title>.png` reference consistent, `export_with_preset` has no non-test caller at HEAD, and the sub-project 7 plan computes `out_dir = base / profile / preset_id` inside its profile loop, so hd and pixel land in disjoint directories by construction.
- **The sheet-route test pins frame state that the real pipeline overwrites** (`test_image_route_dialog.py:79`) — the test is prescribed verbatim by the Task 10 brief, it can and does fail if the dialog stops writing `source_path` (both mutations were run), the dialog's list count and order are load-bearing because `_sync_frames` carries `duration_ms`, `pivot` and `overrides` forward by index, and `tests/sprite/test_pipeline.py:171-173` asserts the post-pipeline truth directly. It is already tracked as deferred minor M1.
- **Aseprite byte-level tests round-trip through the writer's own structs** (`test_aseprite_native.py:80`) — `aseprite_native.py:52` asserts the two largest struct sizes at import, the tests pin frame and chunk sizes with independent arithmetic and round-trip cel pixels against the raw numpy source, the named mutation changes field arity and fails loudly, and Deviation 9 records the byte-level test as the gate with a manual Aseprite open as the optional independent oracle.

---

## Assessment

**Needs fixes.** The branch implements every symbol design §4.6 names, all 13 recorded deviations,
and every seam sub-project 7 consumes. The full suite is green (1887 passed), no model-ID literal
escapes the two permitted fallback keys, no data path is hand-built, every artifact carries its
sidecar, and no path destroys a running `QThread`. Eight Important findings block the gate: two
export-metadata defects that a sub-project 7 consumer reads (an incomplete manifest and a wrong GIF
frame count), one provider defect that makes the LLM pose-step path fail on every provider the GUI
offers, one false provenance record plus one double-log in the retouch route, one seam break that
turns 3 rendered frames into 9 pipeline frames, and two missing busy guards that let a second writer
run against a project the pipeline is mutating. Every fix is small and local. Apply them in the waves
below, then run the whole suite once.

**Fix wave 1 — core exporters and generation (disjoint files, run in parallel):**

1. `core/sprite/exporters/engine_presets.py` — return the per-frame sidecars from
   `_write_png_sequence` (Important 1); compute the GIF sidecar's `"frames"` from
   `ordered_frame_indices(tag)`, or merge the preset fields into `export_gif`'s own sidecar instead
   of overwriting it (Important 2).
2. `core/sprite/generation/pose_steps.py` — replace `resolve_model(provider, "chat")` with
   `default_chat_model(provider)` from `core.sprite.generation.action_cards` (Important 3).
3. `core/sprite/generation/retouch.py` — build the prompt, the request params and the sidecar
   `reference_images` from the neighbours actually sent on the Gemini region branch (Important 4);
   pass the caller's logger to the three imported helpers, or set the default sink to `None`
   (Important 5).
4. `core/sprite/generation/image_route.py` — write the matte plates into a sibling `plates`
   directory so `list_frames` sees only `NNNN.png` (Important 6); add a `logger` keyword to
   `log_request`, `log_response` and `call_provider` for item 3 above (Important 5); poll the cancel
   token inside the `for color in plates:` body and after `log_response` (Minor 2); route the four
   bare `log()` progress lines through `emit` (Minor 1).

**Fix wave 2 — GUI (disjoint files, run in parallel, after wave 1):**

5. `gui/sprite/image_route_dialog.py` — refuse to open while
   `tab.frames_workspace.panel.is_busy()`, with a logged and shown message (Important 7); call
   `apply_frames` for a non-current action so the undo snapshot is pushed (triage M9, fix-now); wrap
   `exec()` in `try/finally: dialog.deleteLater()` and bind the result handler with
   `functools.partial` (Minor 3).
6. `gui/sprite/retouch_wiring.py` — refuse to open while the processing panel is busy, and
   re-validate `0 <= index < len(action.frames)` at the top of `apply_retouch` (Important 8); apply
   the same `try/finally: dialog.deleteLater()` shape (Minor 3).

**Fix wave 3 — tests (one implementer per file, after waves 1 and 2):**

7. `tests/sprite/test_engine_presets.py` — add the recursive disk-versus-manifest assertion for
   `web_preview`; pin the GIF sidecar body for a ping-pong tag (Important 1, Important 2).
8. `tests/sprite/test_pose_steps.py` — add a test that does not monkeypatch `resolve_model` and
   asserts the resolved model is not the family name (Important 3).
9. `tests/sprite/test_retouch.py` — assert the region-path prompt omits "neighboring" and that the
   sidecar records no reference image; add a once-only caplog test for the default log path
   (Important 4, Important 5).
10. `tests/sprite/test_image_route.py` — render a 2-step matte chain into a real extract directory
    and assert `pipeline.list_frames(extract_dir)` returns exactly the composed frames in order; add
    a cancel test that counts provider calls across the two plates (Important 6, Minor 2).
11. `tests/sprite/gui/test_image_route_dialog.py` — add the busy-guard refusal test; flip
    `test_rendered_for_another_action_only_refreshes_status` for the M9 fix; add the three direct
    `billed_units` unit tests; add the frozen-clock archive collision test (Important 7, M9,
    Minor 5, Minor 6).
12. `tests/sprite/gui/test_retouch_dialog.py` — add the busy-guard refusal test and a stale-index
    test that asserts `apply_retouch` returns without raising (Important 8).
13. `tests/sprite/test_godot_tres.py` — compare the golden line by line instead of collapsing
    whitespace (Minor 4).

**Record in the plan's Deviations section:** the matte-plate directory (after wave 1 the plates leave
the extract stage, so the entry can note the correction), the pose-step chat-family resolution, the
Gemini region-retouch neighbour semantics, and the busy-guard contract for the two new card-row entry
points.

**Carry to the sub-project 7 brief:** every "defer" row in the triage table, and the note that
`export_with_preset` requires a unique `out_dir` per profile and per preset.
