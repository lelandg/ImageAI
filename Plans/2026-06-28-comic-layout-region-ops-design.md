# Comic Layout — Manual Editor: Region Operations (sub-project #5b of 5)

**Status:** Design 2026-06-28. Scope user-approved (core ops; two-click free-line knife).
**Branch:** `feat/comic-layout-geometry-core` (all comic-layout sub-projects share one branch).
**PR gate:** Do NOT open a PR — the single PR comes only after the whole comic-layout feature (#5c) is done.

## 1. Goal

Add **panel-level operations** to the Layout-tab manual editor, on top of the
#5a `GeometryEditor` foundation and the pure polygon primitives from #2:

- **Split / knife** — a **two-click free line** across a panel cuts it into two
  panels (any angle), via `polygon.clip_halfplane`.
- **Merge** — combine two adjacent panels into one, via `polygon.union_polygons`.
- **Delete** — remove a panel.

**Out of scope (user-approved "core ops only"):** vertex insert/delete,
line↔curve conversion, rect-corner resize (possible later); all overlay editing
and export unification are **#5c**.

## 2. Scope decisions (user-approved)

| Decision | Choice |
|----------|--------|
| #5b depth | **Core ops only** — split, merge, delete |
| Knife UX | **Two-click free line** — click two points; both sides become panels |
| Result shape | **`polygon`** regions (renderer + #5a vertex editor both support them) |
| Operable shapes | rect, polygon, and **straight-edged** `path` (move/line/close only); curved paths are rejected with a logged status message (never crash) |

## 3. Current architecture (verified, with anchors)

- **Pure polygon toolkit (Qt-free):** `core/layout/polygon.py` — `signed_area`,
  `ensure_orientation`, `clip_halfplane(poly, a, b)` (Sutherland–Hodgman half-plane
  clip; keeps the side left of a→b), `union_polygons(polys) -> List[Poly]`
  (index-based ring chaining + `_remove_colinear`; scoped to edge-sharing cells),
  `polygon_to_segments(poly)`. `Poly = List[Point]`, `Point = Tuple[float,float]`.
- **Region model:** `core/layout/models.py:117` — `Region.shape ∈ {rect,polygon,path}`,
  `bbox`, `points` (polygon vertices, int page px), `segments` (path), `kind`,
  `z`, `bleed`, `image_style`, `role`, `name`. Rect geometry lives in `bbox`.
- **Editor foundation (#5a):** `gui/layout/geometry_editor.py` (`GeometryEditor`,
  handle regeneration after rebuild), `gui/layout/geometry_inspector.py`
  (emit-signals-only widget; `LayoutTab` owns mutation), `gui/layout/layout_tab.py`
  (`_find_region:214`, `_refresh:129` rebuilds whole scene + `rebuild_handles`,
  `snapshot_and_refresh`, `set_refresh_suspended`, `history`).
- **Canvas:** `gui/layout/canvas_widget.py` — `QGraphicsView`; emits
  `regionSelected(str)` from scene selection; `selected_region_id()`; scene ==
  page px; `mapToScene` for mouse→scene. No tool-mode concept yet.
- **Undo:** `History.append(prompt)` snapshots the document; the editor snapshots
  at commit time only.

## 4. Architecture

### 4.1 Pure module `core/layout/region_ops.py` (Qt-free, fully unit-tested)

The geometry/model transforms live here so they test headless and stay out of Qt.

- `region_to_polygon(region) -> Optional[Poly]`
  - `rect` → the 4 bbox corners (CW from top-left).
  - `polygon` → `[(float,float)] from region.points`.
  - `path` with only `move`/`line`/`close` segments → the ordered anchor points.
  - `path` containing `quad`/`cubic` → **None** (curved; unsupported this phase).
- `split_region(region, a, b) -> Optional[Tuple[Region, Region]]`
  - `poly = region_to_polygon(region)`; if `None` → `None`.
  - `left = clip_halfplane(poly, a, b)`, `right = clip_halfplane(poly, b, a)`
    (reversing the cut direction selects the opposite half).
  - If either side has `< 3` vertices (cut missed / grazed) → `None`.
  - Build two `polygon` regions copying `kind/z/bleed/image_style/role/name` from
    the original, ids `f"{region.id}_a"` / `f"{region.id}_b"`, `points` = rounded
    int tuples, `bbox` recomputed from points. Return `(r_a, r_b)`.
- `merge_regions(base, other) -> Optional[Region]`
  - `p1, p2 = region_to_polygon(base), region_to_polygon(other)`; either `None` → `None`.
  - `rings = union_polygons([p1, p2])`; if `len(rings) != 1` → `None`
    (panels are disjoint / share no edge — not mergeable into one ring).
  - Build one `polygon` region from `base`'s `id/kind/z/bleed/image_style/role/name`,
    `points` from the single ring, `bbox` recomputed. Return it.
- Helpers: `_poly_bbox(poly) -> Rect`, `_region_from_polygon(template, poly, *, id)`.
- **Determinism:** no `Math.random`/time; results depend only on inputs.

### 4.2 Canvas tool modes (`canvas_widget.py`)

Add a minimal **tool-mode** state so the canvas can collect knife clicks / a merge
target without disturbing normal selection:

- `set_tool_mode(mode: str)` where `mode ∈ {"none","knife","merge"}` (default `"none"`).
- New signals: `knifeLine(float,float,float,float)` (p1x,p1y,p2x,p2y in scene px)
  and `mergeTarget(str)` (the clicked region id).
- `mousePressEvent` override:
  - `"none"` → `super()` (unchanged selection/rubber-band behavior).
  - `"knife"` → record `mapToScene(pos)`; on the **second** click emit
    `knifeLine(...)`, then auto-reset to `"none"`. (First click stashed on the widget.)
  - `"merge"` → resolve the region id under the cursor (`itemAt`→`data(0)`); if found
    emit `mergeTarget(id)` then reset to `"none"`; if empty space, ignore.
- Switching tool mode clears any half-entered knife state.

### 4.3 Inspector controls (`geometry_inspector.py`)

Add a button row (emit-signals-only, consistent with #5a):

- **"Delete panel"** → `deleteRequested(str)`.
- **"Knife (split)"** (checkable) → `knifeToggled(str, bool)`.
- **"Merge…"** (checkable) → `mergeToggled(str, bool)`.

`set_region` enables Delete for any region; Knife/Merge for rect/polygon/path
(the op itself fail-safes on curved paths). The two checkable tools are mutually
exclusive and reset (unchecked) on every `set_region` (selection change), exactly
like the existing `edit_shape_chk`.

### 4.4 Controller wiring (`layout_tab.py`)

`LayoutTab` owns all model mutation (same split as #5a). Handlers:

- `_on_region_delete(region_id)`: drop the region from `page.regions`; if it was the
  `geometry_editor` edit region, exit edit mode; `snapshot_and_refresh("delete panel: …")`.
- `_on_region_knife_toggled(region_id, on)`: on → remember `region_id`, set canvas
  tool mode `"knife"`; off → tool mode `"none"`. On `canvas.knifeLine(p1,p2)`:
  `split_region(region, p1, p2)`; if `None` → status message + log, reset; else
  replace the region **in place** (same list index) with the two results,
  `snapshot_and_refresh`, reset tool mode + uncheck the inspector toggle.
- `_on_region_merge_toggled(region_id, on)`: on → remember base `region_id`, set
  tool mode `"merge"`. On `canvas.mergeTarget(other_id)`: if `other_id == base` →
  ignore; else `merge_regions(base, other)`; if `None` → status + log; else replace
  base in place with the merged region, remove `other`, `snapshot_and_refresh`, reset.
- All mutations go through `snapshot_and_refresh` (one undo snapshot each; `_refresh`
  rebuilds the scene and `rebuild_handles`).

## 5. Error handling / edge cases

- **Cut misses the panel** (`split_region` → None): no model change; status
  "Cannot split — the cut line missed the panel"; `logger.warning`; tool resets.
- **Panels not adjacent** (`merge_regions` → None): no change; status "Cannot merge —
  panels are not adjacent"; `logger.warning`.
- **Curved path** (`region_to_polygon` → None): same fail-safe path (status + log).
- **Delete last region / edit-region deleted:** allowed; if the deleted region was in
  edit mode, `geometry_editor.set_edit_region(None)` first so no stale handles.
- **Tool mode left active** when selection changes: `set_region` unchecks the tool
  toggles and `LayoutTab` resets the canvas to `"none"` (no dangling half-knife).
- **Never crash, never corrupt:** every op validates before mutating; an invalid op is
  a no-op + log.

## 6. Testing (headless, `QT_QPA_PLATFORM=offscreen`)

Pure (`tests/layout/test_region_ops.py`):
- `region_to_polygon`: rect→4 corners; polygon→points; straight path→anchors; curved path→None.
- `split_region`: a unit square cut by its vertical midline → two regions, each a
  valid polygon, x-extents partition the original; a cut entirely outside → None;
  ids `_a`/`_b`; kind/z/bleed copied.
- `merge_regions`: two edge-sharing squares → one region, single ring, bbox = union;
  two disjoint squares → None; curved input → None.

GUI (`tests/layout/test_region_ops_gui.py`):
- `_on_region_delete` removes the region and appends one snapshot.
- knife flow: drive `_on_region_knife_toggled(id, True)` then `canvas.knifeLine(...)`
  emit → `page.regions` goes 1→2 at the same index; one snapshot.
- merge flow: select base, `mergeTarget(other)` → 2→1; one snapshot.
- invalid op (cut miss / disjoint) → region count unchanged, no snapshot.
- Full layout suite stays green (baseline **293**; +N).

## 7. Out of scope (deferred, not gaps)

- Vertex insert/delete, line↔curve conversion, rect-corner resize.
- Splitting/merging **curved** path regions (would need curve subdivision).
- All overlay editing + export unification → **#5c**.

## 8. Self-review (author)

- **Placeholder scan:** none; every unit names a concrete file/interface and the
  existing primitive it reuses (`clip_halfplane`, `union_polygons`).
- **Consistency:** mutation lives only in `LayoutTab` (matches #5a); the pure module
  is Qt-free and deterministic; tool-mode additions don't change default canvas
  behavior (mode `"none"` is `super()`).
- **Scope:** core ops only; sized for one plan (~6 tasks: pure module split/merge,
  region_to_polygon, canvas tool mode, inspector buttons, controller wiring, integration).
- **Ambiguity:** "two-click free line" = clip both half-planes by the same segment
  reversed; results are `polygon`; curved paths explicitly rejected.
