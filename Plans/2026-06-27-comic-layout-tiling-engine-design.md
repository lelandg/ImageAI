# Comic Layout — Sub-project #2: Page-Partition / Tiling Engine (Design) ⏳
**Last Updated:** 2026-06-27 13:59
**Author:** Leland Green + Claude (Opus 4.8)
**Status:** Design — awaiting user review before implementation plan
**Branch:** `feat/comic-layout-geometry-core` (shared by all 5 comic-layout sub-projects; one PR after #5)
**Design source:** Brainstorming session 2026-06-27 (this doc)
**Builds on:** `Plans/2026-06-27-comic-layout-geometry-core-design.md` (#1 — geometry & render core)

---

## 0. Why this exists

#1 gave a region a path-based shape and made the renderer clip an image to that
shape, honor a stroke, and bleed. But panels are still authored as independent
boxes; nothing divides the page into a coherent, gap-free set of panels. The
user's core complaint — **"lots of whitespace between" panels** — comes from
placing rectangles with fixed gaps on a grid.

#2 fixes that with **partition-then-inset**: divide the whole page into a gap-free
tiling whose panels share edges, then create every gutter by **insetting** each
panel. The output is a list of `Region`s with `shape="path"` that #1 renders
unchanged. This is the piece that eliminates the whitespace and unlocks angled
gutters and concave panels.

## 1. Scope (decisions from brainstorming)

**In scope**
- **Recursive slice-tree model** with any-angle straight cuts (horizontal,
  vertical, or skewed/angled).
- **Cell-merge → concave panels** (L-shapes, wrap-around) — the original
  "frames with concave sides" ask.
- **Partition → merge → per-edge inset** pipeline producing the gutters.
- **Hand-rolled, dependency-free** straight-edge polygon math (clip, union,
  inset) in a pure module — no new third-party dependency.
- **Per-edge inset** unifying outer **margin**, inter-panel **gutter**, and
  **bleed** (a `bleed` panel skips inset on its page-border edges).
- **Floating + bleed layering** — floating panels layer on top of the tiled base
  via z-order.
- **Preset templates** + **`apply_tiling`** that seeds `page.regions` (the usable,
  testable surface). No GUI, no LLM.

**Out of scope (later sub-projects)**
- GUI authoring / knife tool / vertex dragging (#5).
- AI designer emitting tilings (#4).
- Curved-edge **tiling** (curves remain available for free-floating/bleed panels
  and balloons via #1; tiling cuts are straight-edge only — a research-grade
  problem, explicitly excluded).
- Migrating GUI PNG/PDF export off the PIL engine onto the Qt renderer (a known
  follow-up recorded in #1's plan; not required for #2).

## 2. Data model (`core/layout/tiling.py`, pure, no Qt)

```python
@dataclass
class Split:
    axis: Literal["x", "y"]        # "x" = vertical cut → left/right; "y" = horizontal → top/bottom
    at: float                      # cut position, fraction (0,1) of the cell bbox along the axis
    a: "Node"                      # first child  (left / top)
    b: "Node"                      # second child (right / bottom)
    skew: float = 0.0              # [-1,1]; ≠0 shifts the cut's two endpoints in opposite
                                   # directions on the spanning edges → an angled gutter

@dataclass
class Leaf:
    id: str
    kind: Literal["image", "text"] = "image"
    bleed: bool = False
    merge: Optional[str] = None    # leaves sharing a merge key fuse into one (concave) panel

Node = Union[Split, Leaf]
```

Cut parameters are **relative to the current cell's bounding box**, so they remain
well-defined on the non-rectangular cells produced by earlier angled cuts.

## 3. Pipeline — `tile(tree, page_rect, *, gutter, margin) -> List[Region]`

1. **Partition.** Recursively clip the cell polygon by each `Split`'s cut line
   (Sutherland–Hodgman half-plane clip). Each `Leaf` gets an exact convex polygon;
   the leaves tile `page_rect` with no gaps or overlaps. A `Split.at` is clamped to
   a small `[ε, 1-ε]`; `skew` offsets the two cut endpoints on the spanning bbox
   edges.
2. **Merge.** Group leaf polygons by `merge` key; union each group by
   **boundary-edge cancellation**: split colinear opposing edges at their overlap,
   then cancel exactly-opposing shared edges; the survivors trace the panel ring
   (concave allowed). A disconnected merge group is logged and left unmerged.
3. **Per-edge inset.** For each final panel, classify each edge as **boundary**
   (lies on `page_rect`, within ε) or **interior**, and offset it inward by:
   - interior edge → `gutter / 2` (adjacent panels sum to a full `gutter`),
   - boundary edge → `margin`,
   - boundary edge of a `bleed` panel → `0` (panel runs to the trim/bleed edge).
   Offset = intersect consecutive offset lines; miter with a miter-limit
   (bevel fallback); reflex-aware. If a panel is too thin for its gutter and the
   inset inverts/self-intersects, log a warning and **drop** that panel.
4. **Emit.** Each inset panel polygon → `Region(shape="path",
   segments=polygon_to_segments(poly), kind=leaf.kind, bleed=leaf.bleed,
   id=leaf.id, z=<base>)`.

Margin, inter-panel gutter, angled gutters, and bleed all derive from the single
per-edge inset over an exact partition.

## 4. Module layout

- **`core/layout/polygon.py`** *(NEW, pure, no Qt)* — reusable straight-edge
  polygon math: `clip_halfplane(poly, line)`; `union_polygons(polys)`
  (boundary-edge cancellation + colinear-overlap splitting); `inset_polygon(poly,
  dist_per_edge)`; `polygon_to_segments(poly) -> List[PathSegment]`. Reusable by
  #5's editor.
- **`core/layout/tiling.py`** *(NEW, pure, no Qt)* — `Split`/`Leaf` model, `tile`,
  preset builders, `apply_tiling`.

## 5. Presets + apply-to-page

- Preset library (in `tiling.py`): `grid(rows, cols)` plus named trees exercising
  the range — `three_tiers()`, `splash_with_strip()` (one big panel + a row of
  small), `diagonal_action()` (angled cuts), `feature_L()` (a `merge` group → a
  concave hero panel).
- `apply_tiling(page, tree, *, gutter, margin, floating=()) -> PageSpec` — sets
  `page.regions = tiled_base + list(floating)`, assigning ids and z so **floating
  panels layer on top** of the tiled base. This is the usable feature surface.

## 6. Integration with #1 (no renderer changes)

Output `Region`s use `shape="path"`/`segments`, which #1's `region_to_painter_path`
+ clip + stroke render as-is. A `bleed` leaf skips inset on its page-border edges,
so #1's bleed canvas-growth and this no-inset combine into true full-bleed panels.
**#2 produces regions; #1 renders them — no renderer edits.**

## 7. Error handling (repo rule: all errors logged, platform-independent)

- Malformed tree (bad `at`, missing child, unknown `axis`) → `ValueError` with
  context.
- Disconnected `merge` group → log error, leave those cells unmerged (no crash).
- Panel too thin for its gutter (inset inverts) → log warning + drop the panel.
- Degenerate cut (`at` at/near 0 or 1) → clamp to `[ε, 1-ε]` + log debug.
- All via the layout file logger.

## 8. Testing

- **`tests/layout/test_polygon.py`** *(pure)* — half-plane clip of a square;
  per-edge inset of a square (boundary=`margin` vs interior=`gutter/2`); concave
  **L-shape inset** (reflex vertex) produces the expected ring; `union_polygons`
  of two adjacent cells → expected ring (incl. a partial-shared-edge case);
  thin-panel collapse → dropped + logged; `polygon_to_segments` round-trips.
- **`tests/layout/test_tiling.py`** *(pure)* — `grid(2,2)` → 4 panels; measured
  inter-panel gap == `gutter` and outer == `margin` (assert on coordinates);
  angled (`skew`) cut → a non-axis-aligned gutter edge; `merge` group → one
  concave panel (expected vertex count); `bleed` leaf → its boundary edges reach
  `page_rect`; `apply_tiling` seeds `shape="path"` regions with floating on top
  (higher z); every emitted region passes #1's `validate_segments` and a schema
  round-trip.
- **`tests/layout/test_tiling_render.py`** *(one offscreen Qt smoke test)* —
  render a tiled page via #1's `render_page_to_image` and assert the gutter
  between two panels is the page background (the whitespace is now intentional,
  uniform, and the two sub-projects compose).

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q`.

## 9. Cross-cutting compliance
- All errors logged (file + console), platform-independent.
- No size/ratio tokens in prompts (N/A — geometry only).
- Images scaled-not-cropped at generation; tiling only defines panel shapes.
- No new third-party dependency (hand-rolled polygon math).

## 10. Acceptance criteria (definition of done for #2)
1. `grid(rows, cols)` produces gap-free panels whose inter-panel gutters measure
   `gutter` and whose outer margin measures `margin`.
2. An angled (`skew`) cut yields a non-axis-aligned gutter between panels.
3. A `merge` group yields a single concave panel (correct reflex ring).
4. A `bleed` leaf's page-border edges reach `page_rect` (no inset there); interior
   edges still inset by `gutter/2`.
5. `apply_tiling` seeds `page.regions` with `shape="path"` regions and layers
   `floating` panels on top (higher z).
6. Every emitted region passes #1's `validate_segments` and serializes/round-trips
   via `schema.py`; a tiled page renders through #1 with background-colored gutters.
7. Malformed trees raise with context; thin/collapsed panels and disconnected
   merges are logged, never crash. Full `tests/layout/` suite stays green.
