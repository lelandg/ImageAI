# Comic Layout — Sub-project #1: Geometry & Render Core (Design) ⏳
**Last Updated:** 2026-06-27 10:28
**Author:** Leland Green + Claude (Opus 4.8)
**Status:** Design — awaiting user review before implementation plan
**Branch:** `feat/comic-layout-geometry-core`
**Design source:** Brainstorming session 2026-06-27 (this doc)
**Related:** `Plans/2026-06-24-layout-ai-designer-design.md` (Layout AI Designer)

---

## 0. Why this exists

The Layout engine today represents a panel/frame as a **rectangle** (`Region.bbox`,
`core/layout/models.py:94`) placed on a **fixed-gutter grid**
(`compute_panel_grid`, `core/layout/layout_algorithms.py:187`), rendered with Qt
(`core/layout/qt_renderer.py:196`). A `shape="polygon"` exists but is shallow:

- **Images are not clipped to the shape** — a pixmap is scaled to the rectangular
  bbox and pasted at the bbox origin (`qt_renderer.py:104`), so a "triangle frame"
  shows a rectangular photo.
- **Borders are a hard-coded 1px pen** (`qt_renderer.py:104`); the `stroke_px` /
  `stroke_color` fields on `ImageStyle` (`models.py:54`) are **defined but ignored**.
- **There is no bleed / borderless concept** per region.

The user's goal is **arbitrary comic-style page layouts** (à la *Understanding
Comics*): non-rectangular and concave panels, angled gutters, curved edges, bleed
and borderless frames, with both AI-designed and manually-edited authoring, plus a
full comic text toolkit (balloons/captions/SFX).

That full goal is **several independent subsystems** and too large for one spec. It
is decomposed below; **this document specifies only sub-project #1**, the geometry
& render foundation every other piece depends on.

## 1. Decomposition (full comic-layout goal)

Build order, dependency-first. Each sub-project gets its own spec → plan → build
cycle.

1. **Geometry & render core** — *this spec.* Path-based region geometry (straight
   **and** curved); clip the image to the panel shape; per-region stroke incl.
   `stroke=0` borderless; page-bleed extension. Delivers shaped/borderless frames
   that actually render as shapes.
2. **Page-partition / tiling engine** — divide the page into a gap-free tiling with
   shared edges; gutters by **inset**, not grid gaps; free-floating + bleed panels
   layered on top. *Decision: tiling cuts are straight-edge only; curved edges stay
   available for floating/bleed panels and balloons. Curved-edge tiling with inset
   gutters is out of scope (research-grade).* Kills the whitespace problem.
3. **Comic text overlays** — shaped, tailed, styled text elements (speech balloons,
   thought bubbles, caption boxes, SFX) with tail-anchoring and text-fit-in-shape.
   Depends on #1; largely independent of #2.
4. **AI designer extension** — teach `core/layout/designer.py` to emit the new
   geometry (panels + gutters + bleed + balloons). Includes an `svg⇄segments`
   converter for LLM I/O.
5. **Manual editor UI** — knife/split tool, vertex & curve-handle dragging, edge
   dragging, bleed/borderless toggles, balloon + tail placement. Largest GUI piece.

*(Serialization/export — `Region`, schema, `.iaibundle`, PNG/PDF/multi-page —
evolves across all of them.)*

### Decisions captured from brainstorming
- **Authoring:** AI-first **+** manual refine (hybrid) — drives #4 and #5.
- **Panel model:** tiled grid **+** floating panels — drives #2.
- **Edge fidelity:** straight **+** curved — drives the path model here in #1.
- **Content scope:** full comic toolkit (overall) — drives #3.
- **Image fit in a shaped panel:** **cover + clip-to-shape** by default, per-panel
  **contain** toggle (reuses `ImageStyle.fit`).
- **No legacy projects exist** — no migration machinery, no golden-file
  round-trip tests. `rect`/`polygon` are retained only as compact shape kinds so we
  don't churn the existing designer prompt and tests inside #1.

## 2. Scope of sub-project #1

**In scope**
- A path-based geometry representation supporting straight and curved edges.
- Clipping a placed image to the exact panel shape (cover/contain).
- Per-region stroke control, including `stroke_px=0` ⇒ borderless.
- A per-region `bleed` flag honored by the renderer.
- Serialization of the new fields; JSON schema + `normalize_region` updates.
- Defensive validation + logging; tests.

**Out of scope (later sub-projects)**
- Page-partition/tiling and inset gutters (#2).
- Auto edge-snap of a bleed panel to the page edge (#2).
- Comic text overlays / balloons / tails / SFX (#3).
- `svg⇄segments` converter and designer prompt changes (#4).
- Manual editor / knife tool / vertex dragging (#5).
- Curved-edge **tiling** with inset gutters (explicitly not planned).
- The legacy rect-only `template_schema.json` export (unchanged).

## 3. Data model (`core/layout/models.py`)

- `Region.shape: Literal["rect","polygon","path"]` — add `"path"`.
- New `PathSegment` dataclass (kept in `models.py`, Qt-free):
  ```python
  @dataclass
  class PathSegment:
      type: Literal["move", "line", "quad", "cubic", "close"]
      pts: List[Tuple[float, float]] = field(default_factory=list)  # page px
  ```
  Point-count contract: `move` = 1, `line` = 1, `quad` = 2 (control, end),
  `cubic` = 3 (c1, c2, end), `close` = 0. Arcs are expressed as cubics — the type
  set stays minimal. A valid path starts with `move`.
- New fields on `Region`:
  - `segments: List[PathSegment] = field(default_factory=list)` — used when
    `shape="path"`.
  - `bleed: bool = False`.
- `bbox` is retained. For `shape="path"` it is **derived** (bounding box of segment
  points) and used only for positioning/hit-testing — **never** for clipping.
- **Stroke & fit reuse existing fields:** `ImageStyle.stroke_px` /
  `ImageStyle.stroke_color` become live (`stroke_px=0` ⇒ borderless); the
  cover/contain toggle is the existing `ImageStyle.fit`. No new style fields.

## 4. Geometry helpers (`core/layout/geometry.py` — NEW, pure, no Qt)

- `validate_segments(segments) -> list[str]` — returns a list of problem strings
  (empty = valid). Checks: starts with `move`; each segment's `pts` length matches
  its type; coordinates are finite (no NaN/inf).
- `segments_bbox(segments) -> tuple[float,float,float,float]` — `(x, y, w, h)`
  bounding box of all segment points. *Note: for curves this is the bounding box of
  control points, i.e. a safe superset of the visual extent; documented as such and
  acceptable because bbox is positioning-only.*

Pure so it unit-tests headless without a display.

## 5. Rendering (`core/layout/qt_renderer.py`)

- `region_to_painter_path(region) -> QPainterPath` — builds the path from whichever
  applies: `rect` → 4 lines from bbox; `polygon` → polyline from `points`; `path` →
  walk `segments` (`moveTo`/`lineTo`/`quadTo`/`cubicTo`/`closeSubpath`). Concave and
  curved paths are native to `QPainterPath`.
- **Image clip-to-shape:** scale the pixmap **cover** (or **contain** per
  `ImageStyle.fit`) to the path's bbox, paint it through `painter.setClipPath(path)`
  into an ARGB `QImage`, and place that QImage. Guarantees exact clipping for
  concave + curved panels (bbox corners outside the shape are transparent). Keeps
  the current two-item structure: a **shape path item** (stroke + selection +
  empty-placeholder fill) plus a **clipped pixmap item**, replacing today's
  `_RegionPolygonItem`/`_RegionPixmapItem` (`qt_renderer.py:86`).
- **Stroke:** outline pen = `QPen(stroke_color, stroke_px)`; `stroke_px=0` ⇒ no pen
  ⇒ borderless. Replaces the hard-coded 1px pen (`qt_renderer.py:104`).
- **Bleed:** when `region.bleed`, clip/extend rendering against the page **bleed
  box** (`PageSpec.bleed_px`, `models.py:138`) instead of the trim box. Bleed
  governs only the clip box; the border is governed independently by `stroke_px`,
  so a classic full-bleed borderless panel is `bleed=True` + `stroke_px=0` (no
  page-edge detection needed). (Auto edge-snap of a panel to the page edge is #2;
  #1 only honors the flag + bleed box.)
  - **Decision (canvas growth):** the **export canvas** grows to include the bleed
    margin whenever `PageSpec.bleed_px > 0` — standard print-bleed semantics, where
    the bleed area is a property of the *page*, not of any one panel. The per-region
    `bleed` flag then decides which regions may paint into that margin. (With no
    legacy projects this changes nothing observed; it is a deliberate print default,
    not incidental. Alternative considered: grow only when some region has
    `bleed=True` — rejected as less print-correct.)
- **Text regions** are clipped to the path too (text cannot spill past a shaped
  panel). Full text-reflow-inside-an-arbitrary-shape stays with #3.

## 6. Serialization (`core/layout/schema.py`)

- `region_to_dict` / `region_from_dict` gain `segments` (`[{type, pts}]`) and
  `bleed`. Confirm `image_style` round-trips `stroke_px` / `stroke_color`.
- `REGION_JSON_SCHEMA` (`schema.py:20`) — add `"path"` to the shape enum, a
  `segments` array schema, and `bleed`.
- `normalize_region` (`schema.py:160`) — for `shape="path"`, set
  `bbox = segments_bbox(segments)`.
- `.iaibundle` writes regions through `region_to_dict`, so it inherits the new
  fields automatically — no bundle-format work.
- The legacy rect-only `template_schema.json` is left unchanged.

## 7. Error handling (repo rule: all errors logged, platform-independent)

- `validate_segments` runs at **load** (`schema.py`) and at **path-build**
  (`qt_renderer.py`). A malformed segment is logged and the region **falls back to
  its `bbox` rectangle** so a panel never silently disappears.
- Unknown `shape` value → treat as `rect` + log.
- Image load/scale failure → draw the empty shaped placeholder clipped to shape +
  log.
- `bleed` with `PageSpec.bleed_px == 0` → no-op (debug log).
- Degenerate / duplicate curve control points → Qt renders tolerantly; no crash.
- All via the existing layout file logger.

## 8. Testing

- **`tests/layout/test_geometry.py`** *(NEW, pure)* — `validate_segments`
  accept/reject (bad point counts, missing leading `move`, NaN); `segments_bbox`
  for a straight polygon and for a cubic.
- **`tests/layout/test_qt_renderer.py`** *(offscreen, extend existing)* —
  - triangle path: bbox-corner pixels transparent/page-bg, interior = image;
  - concave L-shape: a pixel in the notch is background (clip is true-shape, not
    convex hull);
  - borderless (`stroke_px=0`) → no border pixels along an edge; stroked
    (`stroke_px=3` + color) → edge pixels match the stroke color;
  - `bleed=True` extends/clips to the bleed box (border independent, via stroke_px);
  - cover vs contain fit (contain shows panel bg in the letterbox area; cover fills);
  - cubic-edge smoke render (no exception; image pixels present).
- **Serialization round-trip** — `shape="path"` region with `bleed` → dict →
  region equal; `image_style` stroke fields round-trip.
- The existing **166 layout tests stay green** (rect/polygon paths unchanged).

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q`.

## 9. Cross-cutting compliance
- All errors logged (file + console), platform-independent (AGENTS.md §6, §8).
- Images **scaled, not cropped at generation/save**; layout placement still uses
  fit modes (cover crops overflow at placement — already the engine's behavior).
- No size/ratio tokens injected into prompts (N/A here; geometry-only).

## 10. Acceptance criteria (definition of done for #1)
1. A `shape="path"` region with straight, concave, and curved (`cubic`/`quad`)
   segments renders with the image clipped to the exact shape.
2. `stroke_px=0` produces a borderless panel; `stroke_px>0` draws a border in
   `stroke_color`.
3. A `bleed=True` region clips to the page bleed box; its border is controlled
   independently by `stroke_px` (full-bleed borderless = `bleed=True` + `stroke_px=0`).
4. `cover` (default) fills + clips; `contain` letterboxes inside the shape.
5. New fields round-trip through `schema.py` and `.iaibundle`.
6. Malformed segments fall back to the bbox rectangle and are logged; no crash.
7. All new tests pass and the existing 166 layout tests remain green.
