# Phase 4 — Content MVP — Completion Summary ✅
**Last Updated:** 2026-06-24 17:25

Part of the AI Layout Designer redesign. Implements **F-MVP** (spec §9 Subsystem
F): fill the placeholders the designer/canvas produce, yielding a finished,
exportable page — with **no** AI content features.

Branch: `feat/layout-ai-designer-phase4` (stacked on
`feat/layout-ai-designer-phase3`). Plan:
`Plans/2026-06-24-layout-ai-designer-phase4-content.md`.

## What shipped
1. **Renderer fix** (`core/layout/qt_renderer.py`): a *filled* image region's
   pixmap is drawn on top of the placeholder rect; it now receives the same
   selectable flags (`_apply_flags`) instead of bare `setData`, so clicking a
   filled image re-selects its region (prerequisite for changing an existing
   image).
2. **`ContentInspector`** (`gui/layout/content_inspector.py`, NEW): a compact
   per-region editor.
   - Image region → **Import image…** (`QFileDialog`) and **From history…**
     (reuses the existing `ImageHistoryDialog`) + a current-ref label.
   - Text region → `QPlainTextEdit` + **Apply text**.
   - Emits `regionContentChanged(region_id, value)`; the inspector only
     *displays* the region — it never mutates the document.
3. **LayoutTab wiring** (`gui/layout/layout_tab.py`): `canvas.regionSelected` →
   `inspector.set_region`; `regionContentChanged` → `set_region_content(id,
   value)` which sets `image_ref`/`text` on the region and re-renders. The
   inspector resets on every `_adopt_document`. `set_region_content` is the
   programmatic hook Phase 5 will reuse to place images by region id.

## Design decisions
- **Single-mutator pattern**: `LayoutTab` owns all document mutation (mirrors
  `apply_style` / `apply_designer_result`). The inspector is display-only +
  signals.
- **Reused** `ImageHistoryDialog` (clean API: `(config, parent)` →
  `get_selected_image()`); did **not** revive the retired template-era
  `inspector_widget.py` (legacy block model, zero live references).

## Tests
- `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q`
  → **88 passed, 0 warnings** (75 before Phase 4 → +13).
- New: `test_qt_renderer.py::test_filled_image_region_is_selectable`;
  `test_content_inspector.py` (5: editor switching, import emit, cancel no-op,
  from-history emit, apply-text emit); `test_layout_tab_content.py` (7: selection
  routing, **real canvas-selection→inspector wiring**, image/text content change,
  unknown-id no-op, reset-on-new-document, and the **F-MVP E2E acceptance** —
  design → fill image+text → export valid PDF).

## Whole-branch review
opus structured review over `feat/layout-ai-designer-phase3..HEAD`.
**Verdict: APPROVE** — no Critical or Important issues. It confirmed the key
design point (the single-mutator path re-fetches the region by id in
`set_region_content`, so the inspector's held reference can never cause a
wrong-region edit after `_refresh` rebuilds the scene) and that the renderer's
two same-id selectable items are unambiguous for `selected_region_id()`.

One consolidated fix wave applied the optional Minor items (`ad40a27`):
- pixmap overlay is selectable but **not** movable (`_apply_flags(..., movable=
  False)`) — can't drag a filled image off its placeholder.
- `ContentInspector._set_image_ref` guards a null region.
- `set_region_content` skips the re-render when the value is unchanged.
- `_find_region` documents the single-page (pages[0]) MVP assumption.
- added a test that a real scene selection drives the inspector.

## Out of scope (Phase 5 / later)
- Per-region AI prompt help, "Send to Image tab", batch placement,
  layout-complete mode, `.iaibundle` (F-AI / bundles).
- Multi-page content editing (only page 0 is wired — matches the rest of the tab,
  which operates on `pages[0]`).
- PNG transparency / image-path page backgrounds (renderer deferrals).
- Per-region role picker / custom-role editor (Phase 3 deferral).
