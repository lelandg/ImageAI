# Comic Layout — Manual Editor: Region Geometry (sub-project #5a of 5)

**Status:** Design approved 2026-06-27. Ready for implementation plan.
**Branch:** `feat/comic-layout-geometry-core` (all comic-layout sub-projects share one branch).
**PR gate:** Do NOT open a PR — the single PR comes only after the whole comic-layout feature (the last #5 phase) is done.

## 1. Goal

Give the Layout tab a **manual region-geometry editor** so a user can refine the
panels that the AI designer (#4) or a tiling preset (#2) produced — without
re-running the AI. #5a delivers the smallest useful editor plus the interactive-
editing **foundation** that later phases build on:

- **Move-only vertex & curve-handle drag** on existing `path` and `polygon`
  panels — reshape a corner, bend a curved edge.
- **Per-panel bleed / borderless toggles** (model-ready today; just needs UI).
- **Editing foundation**: edit handles that survive the full-scene rebuild,
  segment write-back, undo hooks, and a geometry inspector.

Sub-project #5 is **phased**. This spec is **#5a (region geometry)**. Split/knife,
merge, and delete are **#5b**; all overlay editing (balloon placement,
tail→region snapping, SFX rotation, contour-aware wrapping) is **#5c**.

## 2. Scope decisions (user-approved)

| Decision | Choice |
|----------|--------|
| #5 decomposition | **Phase it — region geometry first** (#5a); overlay editing later (#5c) |
| #5a workflow | **Refine existing layouts** — edit panels that already exist; no hand-drawing of new panels |
| Vertex editing depth | **Move only** — drag existing anchor points and bezier control handles; segment count/types unchanged (no insert/delete, no line↔curve convert) |
| Panel ops in #5a | **Bleed/borderless toggle only**; split/knife, merge, delete → **#5b** |
| Live-editing model | **Editor-overlay controller** — a `GeometryEditor` layered on `CanvasWidget`; the pure renderer stays display-only |

## 3. Current architecture (verified, with anchors)

- **Scene is fully rebuilt on every change.** `LayoutTab._refresh` (`gui/layout/layout_tab.py:129`) → `CanvasWidget.load_page` (`gui/layout/canvas_widget.py:23`) → `qt_renderer.build_scene` (`core/layout/qt_renderer.py:359`). `load_page` calls `old.deleteLater()`, so **any handle item attached to the scene is destroyed on every refresh** — the central constraint #5a designs around.
- **Coordinates: scene == page pixels.** `build_scene` creates `QGraphicsScene(0,0,pw,ph)`; `Region.bbox`/`points`/`segments` are page pixels. `CanvasWidget` applies a view transform via `fitInView` (`canvas_widget.py:37`), called **only on load** (not on resize). Mouse↔scene via `QGraphicsView.mapToScene`/`mapFromScene`.
- **What is draggable today:** only text-region guide boxes (`_RegionRectItem`) when `selectable and not locked`. Image frames are `movable=False`. Overlays are not even selectable.
- **Write-back gap (the deferred #5 carry-forward):** `_writeback_move` (`core/layout/qt_renderer.py:107`) persists a drag delta into `region.bbox` and (for polygons) `region.points`, but **never touches `region.segments`**. So translating a `path` region visually reverts on the next refresh (`region_to_painter_path` re-reads `segments`). The code comment tags this as #5's job.
- **Reusable, Qt-free geometry:** `core/layout/geometry.py` — `segments_bbox(segments)`, `validate_segments(segments)`. `core/layout/qt_renderer.py` — `segments_to_painter_path`, `region_to_painter_path` (used to rebuild a panel's `QPainterPath` from the model). `PathSegment` point semantics: `move`/`line` = 1 anchor; `quad` = [control, end]; `cubic` = [c1, c2, end]; `close` = [].
- **Undo:** `core/layout/history.py` — `History.append(prompt)` snapshots the current document; `LayoutTab.restore_snapshot` (`gui/layout/layout_tab.py:422`) restores + `_refresh`. The editor only needs to snapshot at the right moments.
- **Model fields already present:** `Region.bbox/points/segments/shape/bleed/z/image_style` (`core/layout/models.py:116`); `ImageStyle.stroke_px` (`models.py:66`, `0` = borderless). No new model fields are needed for #5a.

## 4. Architecture — `GeometryEditor` controller

A new controller **`gui/layout/geometry_editor.py`**, owned by `LayoutTab`, layered
on `CanvasWidget`. The renderer (`qt_renderer.py`) stays **display-only** — it gains
no interaction logic. The controller owns all edit handles and drag handling.

**Why a controller (not renderer-baked or incremental-scene):** keeps the pure
renderer pure, isolates editing in one testable unit, and survives the full-scene
rebuild by **regenerating handles from the model** after each build rather than
trying to preserve scene state.

**Lifecycle:**
1. **Selection / activation.** Selecting a `path` or `polygon` region surfaces an
   **"Edit shape"** toggle in the geometry inspector (§6). Toggling it on sets the
   controller's `edit_region_id` and shows handles.
2. **Handle (re)generation.** After every scene build (`_refresh` → `load_page`),
   `LayoutTab` calls `geometry_editor.rebuild_handles()`. If an `edit_region_id`
   is active, the controller looks up that region's `_RegionPathItem` (items carry
   `setData(0, region_id)`), builds an **edit-point list** from the model, and adds
   one `QGraphicsEllipseItem` handle per edit point (plus thin connector lines for
   curve control points). Because handles are rebuilt from the model, they **survive
   the rebuild**.
3. **Drag (live).** On handle drag, the controller mutates the bound model point
   (`region.segments[i].pts[j]` or `region.points[i]`) and updates the panel's path
   item **in place** via `region_to_painter_path(region)` — **without** a full
   `_refresh()`. A re-entrancy guard (`LayoutTab._suspend_refresh`, §7) blocks any
   `_refresh` triggered mid-drag.
4. **Commit (release).** On mouse-release: recompute `region.bbox`
   (`geometry.segments_bbox` for path; bbox-of-points for polygon), run
   `geometry.validate_segments` (path) and skip the commit + log if it returns
   errors (degrade, never corrupt), **snapshot undo** (`history.append("edit shape:
   <region>")`), then one `_refresh()` (which calls `rebuild_handles()` and so
   re-lays the handles at their new positions).

**Edit-point model.** The controller maps handles to model writes via a small list
of edit-point descriptors `{scene_xy, kind, write(new_xy)}`:
- **polygon** region → one anchor handle per `points[i]`.
- **path** region → per segment: `move`/`line` → 1 anchor handle (`pts[0]`);
  `quad` → anchor handle (`pts[1]` end) + 1 control handle (`pts[0]`); `cubic` →
  anchor handle (`pts[2]` end) + 2 control handles (`pts[0]`, `pts[1]`). Control
  handles render with a thin connector line to their associated anchor and are
  visually distinct (e.g. hollow vs filled). `close` contributes no handle.
Move-only: the list length and segment types never change during a #5a edit.

## 5. Segment write-back foundation

Close the deferred gap so a **whole-panel translate** drag of a `path` region also
moves its `segments` (today only `bbox`/`points` are written, so path drags revert).

- Add a pure, Qt-free helper to `core/layout/geometry.py`:
  `translate_segments(segments, dx, dy) -> List[PathSegment]` (offsets every point
  of every segment).
- Extend `_writeback_move` (`qt_renderer.py:107`): when `region.shape == "path"` and
  `region.segments`, set `region.segments = translate_segments(item._base_segments,
  dx, dy)`. `_bind_region` captures `_base_segments` alongside `_base_bbox`/
  `_base_points`. `bbox` continues to be updated from the translated geometry.

This makes path panels translatable and gives the vertex tool a tested mutation
primitive. (Whole-panel translate of a path region remains gated by the existing
lock/`movable` rules — unchanged here.)

## 6. Geometry inspector + bleed/borderless

A new small widget **`gui/layout/geometry_inspector.py`**, shown when a region is
selected (near the existing `ContentInspector`, which stays content/text-style only
— clean separation). It exposes, for the selected region:
- **Shape** (read-only label: rect / polygon / path).
- **Bleed** checkbox → `Region.bleed`.
- **Borderless** checkbox → `ImageStyle.stroke_px` (`0` when checked, a sensible
  default when unchecked; creates a default `ImageStyle` if the region has none).
- **Z-order** spin → `Region.z`.
- **"Edit shape"** toggle (path/polygon only) → drives the `GeometryEditor`.

Each control change writes the model, **snapshots undo** (`history.append`), and
`_refresh()`es. The widget emits signals; `LayoutTab` performs the model writes
(so the widget stays Qt-only UI with no model-mutation logic baked in).

## 7. Coordinate / refresh handling

- **Mouse↔model**: `QGraphicsView.mapToScene` / `mapFromScene` (scene == page px).
- **Resize re-fit**: add a `resizeEvent` override to `CanvasWidget` that re-runs
  `fitInView(scene.sceneRect(), Qt.KeepAspectRatio)` so handles stay aligned when
  the widget resizes.
- **Mid-drag refresh suppression**: a `LayoutTab._suspend_refresh` flag; `_refresh`
  early-returns while set. The controller sets it on drag-start, clears it on
  release (after the commit `_refresh`).

## 8. Error handling / edge cases

- **Invalid edit** — if a committed segment edit fails `validate_segments`, skip the
  write-back, log via `logging.getLogger(__name__)`, and leave the model unchanged
  (the live preview reverts on the commit `_refresh`). Never persist invalid
  geometry; never crash.
- **Stale `edit_region_id`** — if the active edit region is gone after a rebuild
  (deleted by another path, snapshot restore), `rebuild_handles()` clears edit mode
  and adds no handles.
- **Non-path/polygon selection** — the "Edit shape" toggle is hidden/disabled for
  `rect` regions (they keep their existing translate-drag; bbox is shown read-only).
- **Empty / degenerate region** — a region whose `segments` produce an empty bbox is
  left untouched and logged.

## 9. Testing (headless, `QT_QPA_PLATFORM=offscreen`)

Interaction logic lives in **directly-callable controller methods** (not synthetic
Qt mouse events), so tests drive the model transitions, not the event loop:
- `geometry.translate_segments` — pure unit tests (offsets all point types; round-trip).
- `_writeback_move` for a `path` region — a translate updates `segments` (regression
  for the deferred gap) and recomputes `bbox`.
- `GeometryEditor` edit-point generation — a `path` region yields the right handle
  count/positions (anchors + controls); a `polygon` yields one per vertex.
- A handle-move method mutates the correct `segments[i].pts[j]` / `points[i]` and the
  commit recomputes `bbox`; an edit that fails `validate_segments` is rejected.
- `GeometryInspector` signals flip `Region.bleed` / `ImageStyle.stroke_px` / `Region.z`.
- Undo: a committed edit appends exactly one `History` snapshot; restore returns the
  pre-edit geometry.
- Full layout suite stays green (baseline **276**; +N).

## 10. Out of scope (deferred, not gaps)

- **Split/knife, merge, delete** → **#5b** (reuses `polygon.clip_halfplane` /
  `union_polygons`; the editor foundation from #5a carries over).
- **Overlay editing** — balloon placement/drag, tail→region snapping, SFX rotation
  (needs a new `Overlay.rotation` field), contour-aware wrapping → **#5c**.
- **Stranded pixel-anchored overlays on a regions-only redesign** (carried from #4)
  → lands with #5c overlay editing.
- **PIL export still bypasses the Qt renderer/overlays** (carried from #1–#3) — the
  biggest cross-cutting follow-up, after the editor phases.
- **Vertex insert/delete, line↔curve conversion, rect-corner resize** — possible
  #5b additions; not in #5a.

## 11. Self-review (completed by author)

- **Placeholder scan:** no TBD/TODO; every component names a concrete file, interface,
  and the existing helper it reuses.
- **Internal consistency:** the editor-overlay-controller choice (§4) is the answer to
  the full-rebuild constraint (§3); handles regenerate from the model after each
  rebuild, so "survive rebuild" is achieved by reconstruction, not preservation —
  consistent throughout. Undo (§6/§9) reuses `History`; no second undo system.
- **Scope check:** focused on one phase (region geometry, move-only, no split/merge/
  delete); decomposition into #5a/#5b/#5c is explicit. Sized for a single plan.
- **Ambiguity check:** vertex tool targets `path` + `polygon` only (rect keeps
  translate-drag) — stated explicitly; "move only" defined as no insert/delete/convert;
  borderless defined as `stroke_px == 0`.
