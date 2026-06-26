# Phase 5b — AI content handoff — Completion Summary ✅
**Last Updated:** 2026-06-25 19:10

Second slice of **Phase 5** (after 5a, PR #24). Delivers the cross-tab AI-content
features on one new seam — **LayoutTab ↔ MainWindow wiring** (the tab was built
with only `config`, no MainWindow ref). Branch: `feat/layout-ai-designer-phase5b`.
Plan: `Plans/2026-06-25-layout-ai-designer-phase5b-content.md`.

> **GUI-runtime note:** the LayoutTab side + both pure core modules are unit-tested
> headless (166 layout tests). The MainWindow cross-tab handlers can't run in
> headless WSL, so they're written defensively and need **live verification in the
> PowerShell `.venv`** (see "Verify in PowerShell" below).

## What shipped

### 1. Send to Image tab handoff (`232cb21`)
Select an image region → **Send to Image →** opens the Generate tab pre-filled
with the region's prompt and a size derived from its pixel bbox; the result is
routed back into that region by id.
- `ContentInspector`: "Send to Image →" + `regionSendToImageRequested(region_id,
  current_prompt)` (honors an unsaved prompt edit).
- `LayoutTab`: `sendToImageRequested(payload)` decouples it from MainWindow;
  `_on_region_send_to_image` persists the prompt + emits `{region_id, prompt,
  width, height}`.
- `MainWindow`: connects the signal (guarded for the QWidget fallback);
  `_configure_image_for_region` sets `prompt_edit` + `resolution_selector` and
  switches tab; `_maybe_place_image_in_layout` (called after
  `self.current_saved_paths = saved_paths` in `_on_generation_finished`) places
  `saved_paths[0]` via `set_region_content`. Every step wrapped so a handoff can
  never destabilize generation.

### 2. Layout-complete mode (`8e9b681`)
**Fill all regions →** drives the Image tab through every prompted image region
in sequence.
- `core/layout/fill_plan.py` (NEW, pure): `FillPlan` (current/advance/progress/
  done) — sequencing state, unit-tested without a GUI.
- `LayoutTab`: `fillAllRequested(list)` + toolbar button; `_collect_fill_payloads`
  gathers ordered payloads for prompted image regions; empty → helpful status.
- `MainWindow`: single-send and fill-all share one path — `_begin_layout_fill`
  builds a `FillPlan` (1 vs many), and `_maybe_place_image_in_layout` places each
  result then advances ("region k of N"); a failed `set_region_content` still
  advances the queue; the final placement returns to the Layout tab.

### 3. Batch-fill core (`c120dd1`)
- `core/layout/batch_fill.py` (NEW, pure): `build_requests` → keyed `BatchRequest`
  per prompted image region (key = region id, so results map back order-
  independently); `nearest_supported_ratio` snaps the region aspect to a Google-
  supported ratio (never a pixel token); `parse_result_jsonl` maps a downloaded
  result file's keys → image bytes; `results_to_placements` keeps only keys that
  match a doc image region.
- **Deferred (next PR): live batch submission/polling/placement.** It's async
  (up to 24h), Google-only, needs a keyed-results accessor on `BatchManager`
  (`get_job_results` currently returns flat `(images, errors)` without pairing the
  key to the bytes) and a persistent region↔job map across sessions, and must be
  GUI-verified. The pure core above is the reusable foundation for it.

## Tests
`QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q`
→ **166 passed** (151 → **+15**):
- `test_layout_tab_send_to_image.py` (4): payload incl. unsaved-edit prompt;
  text/unknown-region no-ops.
- `test_fill_plan.py` (3) + `test_layout_tab_fill_all.py` (3): sequencing/progress;
  prompted-images-only collection; fill-all emit / no-emit.
- `test_batch_fill.py` (5): request keys/filtering/only-empty; nearest-ratio;
  JSONL parsing; placement filtering.

## Review
Opus structured review over the branch diff: **no Critical issues.** One Important
issue fixed (`a465719`): the layout handoff state (`_pending_layout_region_id` /
`_layout_fill_plan`) was cleared only on a *successful* placement, so a failed or
image-less generation could misroute the next normal generation into a region —
now cleared on every failure path via `_clear_layout_handoff()` (and the
empty-`saved_paths` case consumes the pending id). One Minor fixed
(`batch_fill` recovers past a malformed image part). Review confirmed the routing
hook is fully guarded (can't break generation), single-send/fill-all share one
path, and a failed `set_region_content` still advances the queue.

## Verify in PowerShell (`.venv`)
1. Layout tab → design a page with image regions → on an image region click
   **Suggest with AI**, then **Send to Image →**. The Image tab opens with the
   prompt + size. Generate → the image lands back in the region; the tab returns
   to Layout.
2. Give 2+ image regions prompts → **Fill all regions →**. Generate repeatedly;
   each result fills the next region ("region k of N"); finishes on the Layout tab.
3. Confirm a *normal* Image-tab generation (not from Layout) is unaffected (no
   stray placement).

## Out of scope / next
- Live batch async flow (above); non-Google batch; multi-page fill (`pages[0]`
  only); auto-regenerate loops.
