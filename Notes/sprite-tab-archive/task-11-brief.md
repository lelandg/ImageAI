### Task 11: Full-suite run, guard tests, plan bookkeeping

**Files:**
- Modify: `Plans/2026-08-29-sprite-image-route-exports-plan.md` (tick the boxes)

- [ ] **Step 1: Run the guard and the whole suite**

```bash
QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -q
QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite -q
QT_QPA_PLATFORM=offscreen $PY -m pytest -q
```

All three must be green. Record the final pass count in the commit body.

- [ ] **Step 2: Grep for forbidden literals in the new runtime code**

```bash
grep -rnE "gpt-image-[0-9]|gemini-[0-9]|claude-[0-9]" /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/generation/image_route.py /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/generation/retouch.py /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/generation/pose_steps.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/image_route_dialog.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/retouch_dialog.py
```

The only permitted hit is the `MODEL_CAPS["gpt-image-1"]` fallback key inside `openai_sheet_size`/`openai_edit_size`, which mirrors `providers/openai.py:173` (`_caps_for`). Replace any other hit with a capability lookup.

- [ ] **Step 3: Tick every checkbox in this plan and commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add Plans/2026-08-29-sprite-image-route-exports-plan.md
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "docs(plans): sprite sub-project 6 complete (image route, retouch, engine exports)"
```

No version bump here; sub-project 7 bumps once for the whole feature.

---

## Self-review

- **Spec coverage (design §4.6):** `sheet_prompt`, `generate_sheet`, `edit_chain`, `generate_pose_instructions` (Tasks 5-7); `retouch_frame` with Gemini region/whole-frame and OpenAI mask paths (Task 8); `export_godot_tres` with `region`, `margin`, `speed`, `loop`, per-frame `duration` (Task 1); `EnginePreset`/`ENGINE_PRESETS` for the eight named engines, `export_with_preset`, `fps_reconciliation` (Task 2); `export_aseprite` with header `0xA5E0`, frame `0xF1FA`, Layer `0x2004`, Cel `0x2005` type 2 zlib, Tags `0x2018`, Palette `0x2019` when quantized, Color Profile `0x2007` sRGB, and the byte-level reader test (Task 3). GUI: format registration + preset combo with `how_to_import` and reconciliation notes (Task 4); `FrameStrip.retouchRequested` → `RetouchDialog` with snapshot-before-repoint (Task 9); action-card "Render (image)" with a sheet | edit-chain mode combo (Task 10). Golden `tests/sprite/golden/godot.tres` with whitespace-normalized comparison (Task 1). Every artifact gets a sidecar; every provider call is logged in full; token checks happen per frame in `edit_chain` and before the single call in `generate_sheet`.
- **Placeholders:** none. Every code block is complete; every symbol used is defined in this plan, in the design, or in an existing repo file with a verified line range.
- **Consistency:** helper names `provider_kind`, `call_provider`, `first_image`, `save_png`, `log_request`, `log_response`, `openai_sheet_size`, `openai_edit_size`, `default_openai_edit_model` are defined once in Task 6 and reused in Tasks 7-8 with the same signatures. Output naming (`<title>.png`, `.atlas.json`, `.tres`, `.aseprite`, `<title>_<tag>.gif`, `frames/`) is identical in Task 2 and Task 4. Mixin order `(DialogCleanupMixin, QDialog)` is used in both dialogs.
- **Order check:** Task 2 imports Task 3's writer lazily inside `_write_aseprite_native`, so Task 2 tests pass before Task 3 exists; the "aseprite_native" format is exercised only from Task 3 onward.
- **Rules:** no model-ID literals in runtime code except the `MODEL_CAPS["gpt-image-1"]` fallback key that mirrors the provider's own `_caps_for`; no dimensions/aspects in prompt text (tests assert it); no hand-built data paths; no `cd`; no version bump.

## Deviations from the design

1. **`generate_pose_instructions` lives in `core/sprite/generation/pose_steps.py`** and is re-exported from `image_route.py`. The design lists it under `image_route.py`; the split keeps the LLM contract (prompt text, schema, parser, fallback) in one focused module. The import path `core.sprite.generation.image_route.generate_pose_instructions` still works.
2. **`retouch_frame(..., out_png: Optional[Path] = None, ...)`.** The design signature has a required `out_png`. Here it is optional: when omitted, the function writes `NNNN.r<k>.png` beside the source (design §1.4 naming) via `next_retouch_path`, and it raises `FileExistsError` if the target exists. The dialog never passes `out_png`.
3. **`edit_chain` continuity uses two references, not the chat session.** `GoogleProvider.edit_image` (`providers/google.py:1832-1905`) is single-shot and does not consult `_last_chat_session`; only `edit_image_region(use_conversation=True)` does. The chain therefore passes `[character, previous frame]` as the edit inputs on both providers, and calls `start_edit_session`/`reset_edit_session` around the loop for style context, as the design names them. Extra keyword `matte_pairs: bool = False` per the sub-project brief.
4. **`EnginePreset` gains `json_layout: str = "hash"`** (Unreal/Paper2D needs the TexturePacker "array" layout). Everything else matches the design dataclass.
5. **Godot direction handling:** `SpriteFrames` has no direction field, so `ordered_frame_indices` unrolls reverse/ping-pong tags into explicit frame lists; `fps_reconciliation(meta, "godot")` reports it.
6. **`generate_sheet` grows `token: Optional[CancelToken] = None`** (one check before the provider call) so the dialog cancel button also covers the sheet mode. `slice_generated_sheet` is a new public function; the design folds slicing into the same step.
7. **"Render (image)" opens a dialog** (`ImageRouteDialog`) that holds the sheet | edit-chain mode combo, provider/model/frames fields, an editable pose-step list, and the required status console, instead of a bare combo on the card row. The button label the brief asked for is kept.
8. **Sibling-plan names follow the orchestrator's 2026-08-29 decision** (see "Names assumed from sibling plans"): 5b's `register_format(id, label, fn(meta, out_dir), *, needs_sheet, takes_template, checked)` + `sheet_png_path`, `options_layout`, `set_grid_options`, `pivot_x_spin` / `pivot_y_spin`, `name_template_edit`, `current_meta()`, `FramesWorkspace.apply_frames(action_id, frames, label)`, `PixelView.selection_rect()`; 5a's `SpriteTab.make_provider(name)`, `current_action()`, `ActionCardsPanel.add_card_action` / `llm_provider()`; core's G9 pre-extracted entry (`run_pipeline` accepts a populated extract dir with `action.clip is None`); sub-project 2's `record_actual` keyword overrides. Sub-project 6 edits no 5a/5b file except two one-line calls in `sprite_tab.py` and two in `export_dialog.py`. If an implementer finds a name that still differs, change it in the single adapter that touches it (`retouch_wiring.py`, `image_route_dialog._on_rendered` / `_make_pose_fn` / `open_image_route_dialog`, `engine_preset_box.install_engine_presets`, `export_formats.py`) and in the fake dialog/tab objects in the GUI tests.
9. **Aseprite header "Number of colors"** is written as the palette length when `meta.palette` is set and `0` otherwise; Aseprite falls back to its default palette for RGBA files without a Palette chunk. The file is verified byte-for-byte by the reader test; a manual open in Aseprite is an optional non-gating step in Task 3.
10. **Format ids are one vocabulary** across `EnginePreset.formats`, the export dialog, and the CLI: `grid`, `aseprite_json`, `texturepacker_json`, `png_sequence`, `gif`, `godot_tres`, `aseprite_native` (the CLI plan's `aseprite` becomes `aseprite_native`; plan-cli was told). The dialog applies the preset pivot through its `pivot_x_spin` / `pivot_y_spin`; `export_with_preset` applies it through `with_pivot` for the CLI.
11. **`core/sprite/timing.py` belongs to sub-project 2**, not 1 (design §4.2); the dependency line at the top of this plan already lists 2.
12. **Undo goes through `FramesWorkspace.apply_frames(action_id, frames, label)`** for both retouch and image-route renders; sub-project 6 never pushes a snapshot itself. `apply_retouch` repoints a deep-copied frame list so the snapshot inside `apply_frames` captures the pre-retouch path. The image-route job writes `action.frames` inside the worker, so `ImageRouteDialog.start_render` keeps `frames_before` and `_on_rendered` restores it right before `apply_frames` installs the rendered list — otherwise the snapshot would hold the new frames and undo would be a no-op.
13. **Preset notes use 5b's `ExportDialog.notes_label`** (`EnginePresetBox(notes_label=...)`); the box creates its own label only when used standalone. The box is inserted at `options_layout` index 1 (after the profiles box, above the formats box).
