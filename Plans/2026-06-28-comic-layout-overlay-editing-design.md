# Comic Layout — Manual Editor: Overlay Editing + Export (sub-project #5c of 5, FINAL)

**Status:** Design 2026-06-28. Scope user-approved (full overlay authoring + fold-in export unification).
**Branch:** `feat/comic-layout-geometry-core` (all comic-layout sub-projects share one branch).
**PR gate:** #5c is the LAST sub-project — open the single comic-layout PR after #5c is complete (when asked).

## 1. Goal

Complete the manual editor with **comic text-overlay authoring** and make **exports
render the comic layout**:

- **Place / move / delete** overlays (speech, thought, caption, SFX).
- **Tail → region snap** — drag a balloon's tail; it snaps to the nearest panel.
- **SFX rotation** — a new `Overlay.rotation` field, rendered, editable.
- **Stranded-overlay reposition** — when a regions-only redesign leaves pixel-anchored
  overlays floating over new panels, move them back onto a panel (#4 review #3 carry-forward).
- **Export fold-in** — the Layout tab gets a Qt-path PNG export, and the stale PIL
  export path is redirected to the Qt renderer, so PNG/PDF reflect geometry + overlays.

## 2. Scope decisions (user-approved)

| Decision | Choice |
|----------|--------|
| #5c overlay depth | **Full authoring** — place, move, tail-snap, delete, SFX rotation, stranded reposition |
| Export | **Fold in** — exports must render comic geometry + overlays |
| Rotation UX | **Inspector spin** (0–359°), not a drag handle — simpler, fully testable |
| Overlay selection | **Overlay inspector list** (not canvas hit-testing) — avoids a second canvas selection path, keeps it testable; consistent with the inspector/controller split |
| Stranded test | **bbox-based** — an overlay is "stranded" if its `anchor` lies outside every region's bbox; reposition = move `anchor` to the nearest region's bbox center |

## 3. Current architecture (verified, with anchors)

- **Overlay model** (`core/layout/models.py:141`): `id, kind ∈ {speech,thought,caption,sfx}, text, anchor:(float,float), anchor_mode ∈ {center,topleft}, tail_target:Optional[(float,float)], z, role, text_style, style:OverlayStyle`. No `rotation` yet.
- **Serialization** (`core/layout/schema.py`): `overlay_to_dict:118` / `overlay_from_dict:132` (uses `_filtered(OverlayStyle, d)`); page round-trip at `to_dict:189` / `from_dict:213`. Back-compat: missing keys default.
- **Rendering** (`core/layout/qt_renderer.py`): `_add_overlay:286` measures wrapped text → sizes `inner` rect → `balloons.overlay_to_segments(kind, inner, tail_target, style)` → `_OverlayPathItem` body (fill/stroke, clips text child) + `QGraphicsTextItem`; SFX has no body (text added directly). `build_scene:362` overlay pass sorts by `z`. Overlays are **not selectable** (no `setData`, no flags) — editing is via the controller, not canvas selection.
- **Editor foundation (#5a/#5b):** `GeometryEditor` (handle regen after full-scene rebuild), `LayoutTab._refresh` rebuilds the scene + `rebuild_handles`, `snapshot_and_refresh`, `set_refresh_suspended`, `_current_page`. `CanvasWidget` has tool modes (#5b). `History.append` for undo.
- **Export:** `qt_renderer.save_page_png:418` (`render_page_to_image:385` → includes overlays), `export_document_pdf:421`. Layout-tab "Export PDF…" → `export_pdf_to:442` → `qt_renderer.export_document_pdf` (already Qt). The PIL `gui/layout/export_dialog.py` (`LayoutExportWorker` → `core.layout.LayoutEngine`) is **unwired** (no callers) and bypasses overlays/geometry.
- **Designer apply:** `LayoutTab.apply_designer_result:584` — overlays path at :598-599 (`if result.overlays: pages[0].overlays = list(result.overlays)`); the regions-only branch leaves prior overlays untouched (the stranding case).

## 4. Architecture

### 4.1 `Overlay.rotation` (model + serialization + render)

- Add `rotation: float = 0.0` to `Overlay` (degrees clockwise about the body center / anchor). Back-compat: default 0.
- `overlay_to_dict` writes `"rotation": ov.rotation`; `overlay_from_dict` reads `float(d.get("rotation", 0.0) or 0.0)` (degrade-safe).
- `_add_overlay`: after building `body_item`/`text_item`, if `rotation` ≠ 0 apply a rotation transform about the anchor. For a body overlay, set the body's transform origin to the anchor and `setRotation(rotation)` (text is a child → rotates with it). For SFX (no body) rotate the text item about the anchor. Use `QGraphicsItem.setTransformOriginPoint` + `setRotation`.

### 4.2 Pure stranded-overlay reposition (`core/layout/overlay_ops.py`, Qt-free)

- `overlay_anchor_stranded(ov, regions) -> bool`: True if `ov.anchor` is outside every region's bbox.
- `nearest_region_center(point, regions) -> Optional[(float,float)]`: bbox center of the region whose bbox center is nearest `point` (None if no regions).
- `reposition_stranded_overlays(page) -> int`: for each stranded overlay, set `anchor` to `nearest_region_center`; return the count moved. No-op (0) if no regions. Pure, deterministic.

### 4.3 `OverlayInspector` widget (`gui/layout/overlay_inspector.py`, emit-signals-only)

A panel listing the page's overlays with authoring controls. Emits intent signals;
`LayoutTab` owns all mutation (same split as Geometry/Content inspectors).
- **Overlay list** (`QListWidget`) — selecting a row emits `overlaySelected(str)` (overlay id).
- **Add row**: four buttons (Speech / Thought / Caption / SFX) → `addRequested(str kind)`.
- **Delete** button → `deleteRequested(str id)`.
- **Rotation** spin (`QSpinBox` 0–359, suffix °) → `rotationChanged(str id, int deg)`; enabled when an overlay is selected.
- **"Edit on canvas"** toggle → `editToggled(str id, bool)` (drives `OverlayEditor`).
- `set_page(page)` refreshes the list; `set_selected(overlay_id)` reflects selection + rotation without re-emitting (blockSignals).

### 4.4 `OverlayEditor` controller (`gui/layout/overlay_editor.py`)

Mirrors `GeometryEditor`: owns drag handles for ONE selected overlay; handles are
**regenerated from the model after every scene rebuild** (`rebuild_handles`, called from
`LayoutTab._refresh`). Handles (move-only, like #5a):
- **Body handle** at `anchor` → drag writes `ov.anchor`; live-updates by reposition (a mid-drag `setPos` on the body group, or a lightweight refresh-suspend + re-add). Simplest consistent approach: suspend refresh on drag-start, mutate `ov.anchor` on move, commit = snapshot + refresh (re-lays handle). (No in-place body redraw needed — overlays are cheap to rebuild on commit; mid-drag we move only the handle + optionally the body item via `setPos`.)
- **Tail handle** at `tail_target` (only if `tail_target` is not None) → drag writes `ov.tail_target`; **commit snaps** to `nearest_region_center` if within a snap radius (else keeps the dragged point).
- Commit: `snapshot_and_refresh("edit overlay: <id>")`. Invalid/missing overlay → no-op + log.
- `set_edit_overlay(id|None)`, `rebuild_handles()`, `begin_edit()`, `move_handle(kind, x, y)`, `commit()`. `_find_overlay(id)` via `page.overlays`.

### 4.5 LayoutTab wiring

`LayoutTab` owns all mutation:
- `_add_overlay(kind)`: append a default `Overlay` (id `ov{N}`, default text per kind, `anchor` = page center, `tail_target` = None except speech/thought get a default below-center point) to `page.overlays`; `snapshot_and_refresh`; select it.
- `_delete_overlay(id)`, `_set_overlay_rotation(id, deg)`, `_on_overlay_selected(id)` (drive inspector + editor), `_on_overlay_edit_toggled(id, on)`.
- In `apply_designer_result` **regions-only** path (no `result.overlays`), call `overlay_ops.reposition_stranded_overlays(page)` so a redesign tidies orphaned overlays (logged: "repositioned N stranded overlays").
- The overlay inspector + editor are created in `_build`; `_refresh` also calls `overlay_editor.rebuild_handles()` and `overlay_inspector.set_page(page)`.

### 4.6 Export fold-in

- **Layout tab PNG export:** add an "Export PNG…" toolbar action → `export_png_to(path)` → `qt_renderer.save_page_png(page, path, style=doc.style)` (Qt → overlays + geometry included).
- **Retire the PIL bypass:** switch `gui/layout/export_dialog.py` `LayoutExportWorker._export_png`/`_export_pdf` to render via the Qt renderer (`qt_renderer.render_page_to_image(page).save(...)` and `qt_renderer.export_document_pdf(doc, ...)`) instead of `core.layout.LayoutEngine`, so any future use of that dialog renders the comic layout. `dpi` becomes advisory (Qt renders at `page_size_px`); document this in the dialog.

## 5. Error handling / edge cases

- **No regions** when repositioning / tail-snapping: `reposition_stranded_overlays` returns 0; tail-snap keeps the dragged point. Never crash.
- **Malformed rotation** on load: `overlay_from_dict` coerces via `float(... or 0.0)`; non-numeric → 0.
- **Edit overlay deleted** after a rebuild: `OverlayEditor.rebuild_handles` finds no overlay → clears edit mode + handles (mirror #5a).
- **SFX rotation with no body:** rotate the text item directly about the anchor.
- **All errors logged** via `logging.getLogger(__name__)`; a failed/again-degenerate op is a no-op + log, never a crash or corrupt model.

## 6. Testing (headless, `QT_QPA_PLATFORM=offscreen`)

Pure:
- `Overlay.rotation` round-trips through `overlay_to_dict`/`overlay_from_dict` (incl. missing-key → 0.0, non-numeric → 0.0).
- `overlay_ops`: stranded detection (anchor inside vs outside all bboxes); `nearest_region_center`; `reposition_stranded_overlays` moves only stranded ones + returns count; 0 with no regions.

GUI:
- `_add_overlay(kind)` appends one overlay + snapshot + selects it; `_delete_overlay` removes + snapshot; `_set_overlay_rotation` writes `ov.rotation` + snapshot.
- `OverlayEditor` handle generation: body handle at anchor; tail handle present iff `tail_target`; move + commit writes `ov.anchor`/`ov.tail_target` + one snapshot; tail commit snaps to nearest region center within radius.
- `OverlayInspector` signals (`addRequested`/`deleteRequested`/`rotationChanged`/`overlaySelected`/`editToggled`).
- Renderer: an overlay with `rotation=30` yields a body (or sfx text) item whose `rotation()==30`.
- `apply_designer_result` regions-only path repositions stranded overlays.
- Export: `export_png_to` writes a non-empty PNG via the Qt path; the PIL worker now calls the Qt renderer (no `LayoutEngine` import for rendering).
- Full layout suite stays green (baseline **316**; +N).

## 7. Out of scope (deferred, not gaps)

- **Contour-aware text wrapping** (text following a non-rect balloon's interior) — future polish.
- **Rotation drag handle** (rotation is via the inspector spin in #5c).
- **Overlay z-order UI** beyond existing `z` (no reorder widget) and **multi-overlay select**.
- The #5b cleanup Minors (split id-uniqueness, mid-file test imports) — fold opportunistically if touched.

## 8. Self-review (author)

- **Placeholder scan:** none; every unit names a concrete file/interface and the existing helper it reuses (`overlay_to_segments`, `save_page_png`, `region` bbox).
- **Consistency:** mutation only in `LayoutTab`; `overlay_ops.py` Qt-free + deterministic; `OverlayEditor` mirrors `GeometryEditor`'s regenerate-after-rebuild contract; rotation via spin keeps it testable.
- **Scope:** full overlay authoring + export fold-in; sized for one plan (~7 tasks). Contour-wrapping + rotation-handle explicitly deferred.
- **Ambiguity:** "stranded" = anchor outside all region bboxes; reposition target = nearest bbox center; rotation = degrees CW about anchor; tail-snap = nearest region center within a radius, else keep dragged point.
