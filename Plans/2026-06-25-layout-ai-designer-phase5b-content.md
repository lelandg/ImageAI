# Phase 5b — AI content handoff (Send-to-Image, batch, layout-complete) ✅ shipped
**Last Updated:** 2026-06-25 19:10
**Author:** Leland Green + Claude (Opus 4.8)
**Design source:** `Plans/2026-06-24-layout-ai-designer-design.md` §9 (F-AI)
**Branch:** `feat/layout-ai-designer-phase5b`
**Predecessor:** Phase 5a (PR #24, merged) — prompt-help writes `region.prompt`,
the field this phase consumes.

Phase 5b delivers the cross-tab AI-content features. All three share one new
seam: **LayoutTab ↔ MainWindow wiring** (LayoutTab is built with only `config`
at `main_window.py:554`, no MainWindow ref). They land as sequenced commits on
one branch, foundation first.

> **GUI-runtime note:** the cross-tab flow can't be exercised in headless WSL
> (MainWindow needs the full app). The LayoutTab side (signal/payload/queue
> logic) is unit-tested headless; the MainWindow handlers are kept minimal and
> heavily guarded, and Leland verifies the live flow in the PowerShell `.venv`.

---

## Integration map (confirmed in code)
| Need | Symbol | Location |
|---|---|---|
| Generate-tab prompt | `prompt_edit` (QTextEdit) | `main_window.py` |
| Target size | `resolution_selector.set_resolution("WxH")` | `settings_widgets.py:1108` |
| Switch to Image tab | `tabs.setCurrentWidget(tab_generate)` | `main_window.py:561` |
| Generation result paths | `saved_paths` → `self.current_saved_paths` | `main_window.py:6324` |
| Place into region | `tab_layout.set_region_content(id, path)` | `layout_tab.py:237` |
| Batch | `BatchManager`, `BatchRequest(key=…)`, `get_job_results` | `core/batch_manager.py` |

---

## Feature 1 — "Send to Image tab" (foundation)

### Flow
Select an image region → **Send to Image →** → the Generate tab opens with the
region's prompt + a target size derived from the region's pixel bbox; the region
id is remembered as *pending*. When the user generates, the saved image is routed
back into that region by id.

### LayoutTab side (headless-testable)
- `ContentInspector`: image page gains **"Send to Image →"**; emits
  `regionSendToImageRequested(region_id, current_prompt_text)` (carries the box's
  current text so an unsaved edit is honored).
- `LayoutTab`: new signal `sendToImageRequested(object)`. `_on_region_send_to_image`
  persists the prompt onto the region, then emits the payload
  `{region_id, prompt, width, height}` (width/height = region bbox w,h).

### MainWindow side (guarded; manual-verified)
- After creating `tab_layout`: if it exposes `sendToImageRequested`, connect it to
  `_on_layout_send_to_image`; init `self._pending_layout_region_id = None`.
- `_on_layout_send_to_image(payload)`: set `prompt_edit`; set size via
  `resolution_selector.set_resolution(f"{w}x{h}")` (defensive `hasattr`/try);
  store pending id; `tabs.setCurrentWidget(tab_generate)`; status message.
- `_on_generation_finished`: after `self.current_saved_paths = saved_paths`, call
  `_maybe_place_image_in_layout(saved_paths)` — if a pending id is set, route
  `saved_paths[0]` via `tab_layout.set_region_content`, switch back to the Layout
  tab, clear pending. Fully wrapped so it can never break generation.

### Tests
- LayoutTab emits `sendToImageRequested` with the right payload (region id,
  prompt incl. unsaved edit, width/height from bbox); text/unknown region → no-op.
- The placement leg reuses `set_region_content` (already covered).

---

## Feature 2 — Batch placement by region id (Google-only)

### Flow
**Generate all (batch)** → every image region with a prompt becomes a
`BatchRequest(key=region_id, prompt, width, height)` → submit via `BatchManager`
→ on completion map each result image back to its region by `key` and
`set_region_content`.

### Modules
- `core/layout/batch_fill.py` (NEW, pure/testable):
  - `build_requests(document) -> List[BatchRequest]` — one per image region with a
    non-empty prompt; `key=region.id`, size from bbox. Skips empty-prompt regions
    (records which were skipped).
  - `results_to_placements(requests, images) -> List[(region_id, bytes)]` — maps
    results back by request order/key (BatchManager returns images in request
    order; key carries the region id).
- LayoutTab: **Generate all (batch)** button → emits `batchFillRequested(object)`
  (the request list + a save callback contract), or calls a host hook. MainWindow
  owns the Google client (`BatchManager.set_client`), submits, polls on a worker,
  saves each image to disk, and calls `set_region_content` per region.

### Notes / risks
- Batch is **Google genai only** (the manager wraps that client). The button is
  enabled only when the Google client is available; otherwise it explains why.
- Polling runs off the GUI thread; progress + errors surface in a status console
  and the log (repo LLM-logging/error rules).
- This leg is largely MainWindow-side (client + polling), so it is verified
  manually; `batch_fill.py` carries the unit-tested logic.

---

## Feature 3 — Layout-complete mode (region queue)

### Flow
**Fill all regions** → queue every image region (optionally only empty ones) and
drive the Image tab one region at a time: configure prompt+size, switch, and on
each generation-finished, place the result and advance to the next region until
the queue drains. A small status shows "filling region k of N".

### Design
- Reuses Feature 1's pending-region mechanism, generalized to a **queue**:
  `self._layout_fill_queue: List[str]`. `_maybe_place_image_in_layout` places the
  current result, pops the queue, and if non-empty configures the next region and
  stays on the Image tab; when empty, returns to the Layout tab.
- LayoutTab emits the ordered region payloads; MainWindow holds the queue.
- A **Cancel** clears the queue.

### Tests
- Queue advance logic (pure): given a queue and a placement, the next region is
  configured and the queue shrinks; last placement returns to layout. Modeled in
  a small pure helper so it's testable without MainWindow.

---

## Cross-cutting compliance (design §11)
- All LLM/batch requests + responses logged (file + console); model IDs
  registry-resolved; every error logged **and** surfaced; images scaled-not-
  cropped (placement only sets `image_ref`; the renderer's fit modes are
  unchanged); no size/ratio tokens injected into prompts.

## Out of scope
- Non-Google batch providers; multi-page fill (tab still operates on `pages[0]`);
  auto-regenerate loops. `.iaibundle` already shipped in 5a.

## Task checklist
1. ✅ Plan doc (this file) — committed `b7ff0b8`.
2. ✅ Feature 1 — Send to Image tab handoff + result routing (`232cb21`).
3. ✅ Feature 3 — layout-complete mode (`FillPlan` + queue) (`8e9b681`).
4. ✅ Feature 2 — **batch-fill core** (`batch_fill.py`, `c120dd1`); **live async
   submission/polling/placement deferred** (needs a Google client, a keyed-results
   accessor on `BatchManager`, and GUI verification — see completion summary).
5. ✅ Full `tests/layout/` green — **166 passed** (151 → +15); completion summary
   in `Plans/2026-06-25-layout-ai-designer-phase5b-completion.md`.
