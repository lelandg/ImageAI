# Comic Layout — Text Overlays Design (sub-project #3 of 5)

**Status:** Approved — ready for implementation plan
**Last Updated:** 2026-06-27 15:37
**Branch:** `feat/comic-layout-geometry-core` (all 5 comic-layout sub-projects share one branch)
**PR gate:** Do **NOT** open a PR — the single PR comes only after sub-project #5.

## 1. Overview

Sub-project #3 adds **comic text overlays** — tailed speech balloons, thought
bubbles, caption boxes, and SFX (sound-effect) lettering — that float above the
panels produced by #1 (geometry/render core) and #2 (tiling engine).

It is built as a **pure, testable core plus a thin Qt render layer**, exactly
like #1 and #2. Authoring (AI generation, manual drag-editing) is **out of
scope** and deferred to #4 (AI designer) and #5 (manual editor). #3 delivers the
data model, the pure balloon-geometry module, the rendering pass, serialization,
and tests.

### Goals
- A declarative `Overlay` data model (Qt-free, serializable) for the four
  overlay kinds: `speech`, `thought`, `caption`, `sfx`.
- A pure, Qt-free `core/layout/balloons.py` that compiles an overlay's inner
  content rectangle (+ optional tail target) into `PathSegment` geometry that
  the existing renderer draws unchanged.
- A renderer overlay pass that auto-fits each balloon to its wrapped text
  (measuring with Qt font metrics), draws the body fill + stroke + tail, and
  draws the wrapped text clipped to the body.
- Serialization round-trip and comprehensive tests (pure + headless Qt).

### Non-goals (deferred)
- **AI authoring (#4)** and **manual drag-editing UI (#5).**
- **Tail-to-region/character snapping** — the tail points at a free target
  point; snapping is #5.
- **Contour-aware text wrapping** — text wraps within the inner *rectangle*
  inside the body (the standard for the overwhelming majority of comic
  balloons), not following the oval/cloud contour.
- **SFX rotation / warping** — SFX is styled display text at its anchor; rotated
  and path-warped SFX is #5.
- **PIL export parity** — overlays render through the Qt renderer
  (`qt_renderer.py`). The legacy PIL export path (`gui/layout/export_dialog.py`
  → `core/layout/engine.py`) will **not** show overlays. This is the same
  known PIL/Qt divergence carried from #1 and #2; #3 does not fix it (a future
  export-migration task does).

## 2. Architecture

Three layers, mirroring #1/#2's pure-core + render split:

| Layer | File | Qt? | Responsibility |
|---|---|---|---|
| **Model** | `core/layout/models.py` | No | `Overlay` + `OverlayStyle` dataclasses; `PageSpec.overlays: List[Overlay]` |
| **Geometry** | `core/layout/balloons.py` *(new)* | No (pure) | Build body + tail `PathSegment`s from an explicit inner rect + tail target |
| **Render** | `core/layout/qt_renderer.py` | Yes | Overlay pass: measure wrapped text → inner rect → `balloons` → draw fill/stroke/tail + wrapped text |
| **Serialize** | `core/layout/schema.py` | No | `overlay_to_dict`/`overlay_from_dict`; `overlays` in PageSpec round-trip + JSON schema entry |

### Data flow
```
Overlay (declarative)                          [Qt-free authoring artifact, on PageSpec.overlays]
   │
   ├─ renderer overlay pass (qt_renderer, has Qt):
   │     1. resolve text style (effective_text_style: role / text_style)
   │     2. MEASURE wrapped text at style.max_width_px  → (text_w, text_h)   [QFontMetrics/QTextLayout]
   │     3. inner_rect = (text block + style.padding_px) placed at anchor (center|topleft)
   │     4. segs = balloons.overlay_to_segments(kind, inner_rect, tail_target, style)   [PURE]
   │     5. QPainterPath(segs) → fill style.fill, stroke stroke_px/stroke_color
   │     6. draw wrapped text (QGraphicsTextItem, setTextWidth = inner width) clipped to body
   │     7. z-order: overlays drawn after all regions, sorted by Overlay.z
   ▼
rendered page (overlays above panels)
```

The **pure/Qt boundary** is the central design decision (user-approved): font
measurement (which needs Qt or PIL) lives in the renderer where Qt already
exists; `balloons.py` takes an already-computed inner rectangle and stays
Qt-free and unit-testable headless — exactly as `polygon.py`/`tiling.py` are.

## 3. Data model (`core/layout/models.py`)

New dataclasses (Qt-free, defaults set so `schema._filtered` keeps
forward/backward compatibility):

```python
@dataclass
class OverlayStyle:
    fill: str = "#FFFFFF"          # body interior color
    stroke_px: float = 2.0         # body outline width (0 = no outline)
    stroke_color: str = "#000000"
    padding_px: float = 10.0       # text inset between inner text box and body edge
    radius_px: float = 16.0        # corner roundness (speech) / scallop radius (thought)
    max_width_px: float = 240.0    # wrap-width cap for auto-fit measurement

@dataclass
class Overlay:
    id: str
    kind: Literal["speech", "thought", "caption", "sfx"]
    text: str
    anchor: Tuple[float, float]                        # body placement (page px)
    anchor_mode: Literal["center", "topleft"] = "center"
    tail_target: Optional[Tuple[float, float]] = None  # free point the tail points at; None = no tail
    z: int = 0
    role: str = ""                                     # "dialogue"/"caption"/"sfx" → styles.py roles
    text_style: Optional[TextStyle] = None             # overrides role (reuse effective_text_style)
    style: OverlayStyle = field(default_factory=OverlayStyle)
```

`PageSpec` gains one field:
```python
    overlays: List[Overlay] = field(default_factory=list)
```

**Style resolution** reuses the existing `styles.effective_text_style` logic.
Because that resolver currently takes a `Region`, #3 adds a small overlay-aware
variant (or generalizes the lookup) so an `Overlay`'s `role`/`text_style`
resolve through the same precedence: `overlay.text_style` > role lookup >
`project_style.default_text_role`. The four comic roles
(`dialogue`, `sfx`, `caption`, `logo_title`) already exist in `styles.py`; a
`thought` role is **not** added — thought bubbles reuse `dialogue` (italic can
be set via `text_style` if desired).

### Default role per kind
When `overlay.role == ""`, the renderer applies a kind default:
`speech`/`thought` → `dialogue`, `caption` → `caption`, `sfx` → `sfx`.

## 4. `core/layout/balloons.py` — pure geometry

All functions are pure, Qt-free, and return `List[PathSegment]` whose every
element passes `geometry.validate_segments`. Coordinates are page pixels
(floats). Reuses `polygon_to_segments` from `polygon.py`; adds curve emitters
that produce `quad`/`cubic` segments (already supported by `PathSegment` and
`region_to_painter_path`).

```python
Point = Tuple[float, float]
Rect  = Tuple[float, float, float, float]   # (x, y, w, h)

def caption_body(inner: Rect) -> List[PathSegment]:
    """Plain rectangle (move + 3 lines + close) inset by nothing — caption box."""

def speech_body(inner: Rect, *, radius: float) -> List[PathSegment]:
    """Rounded rectangle around `inner`, corners as cubic beziers."""

def thought_body(inner: Rect, *, scallop: float) -> List[PathSegment]:
    """Scalloped 'cloud' around `inner`: a ring of outward quad-bezier bumps."""

def speech_tail(body: List[Point], target: Point, *, base_width: float) -> List[Point]:
    """Return body outline (as points) with a triangular tail spliced in at the
    edge nearest `target`, so body+tail is ONE closed ring."""

def thought_trail(body_center: Point, target: Point, *, count: int = 3) -> List[PathSegment]:
    """A trail of `count` shrinking ellipses from body toward `target`, each a
    closed subpath (move + cubics + close)."""

def overlay_to_segments(kind: str, inner: Rect, tail_target: Optional[Point],
                        style: "OverlayStyle") -> List[PathSegment]:
    """Top-level: build the body for `kind`, splice/append the tail when
    `tail_target` is set, and return the full PathSegment list.
      - speech : rounded body with triangular tail spliced into the outline
      - thought: cloud body + thought_trail ellipses appended as subpaths
      - caption: rectangle, tail ignored
      - sfx    : returns [] (no body; text-only)
    """
```

### Tail construction
- **Speech**: the tail is a triangle from two points on the body edge nearest
  the target out to the target tip. To keep a clean single outline (one stroke
  around the whole shape, no line across the join), the tail is **spliced into
  the body ring**: the body is approximated as a point ring (curved corners
  flattened only for the splice computation — the emitted body keeps its
  curves), the nearest straight edge is found, and the two base points + tip are
  inserted there. Because the speech body is a rounded rect, the tail attaches on
  one of the four straight edge spans between corner arcs. The result is emitted
  as a single closed path: straight/curved body spans + the tail detour.
- **Thought**: no spliced tail; instead `thought_trail` emits separate small
  closed ellipse subpaths marching toward the target (the classic "...oOo"
  thought trail). Each ellipse is its own `move…cubic…close` subpath in the same
  segment list (multiple subpaths are valid: each starts with `move`).

### Validity guarantees
- Every returned list starts with `move` and each subpath closes with `close`.
- `inner ⊆ bbox(body)` (the body strictly contains the text rect; padding makes
  this hold by construction).
- Degenerate inputs (zero/negative inner size) are logged via
  `logging.getLogger(__name__)` and produce an empty list rather than crashing.

## 5. Rendering (`core/layout/qt_renderer.py`)

A new `_add_overlay(scene, ov: Overlay, project_style, ...)` and an overlay loop
appended to the existing scene build:

1. Resolve `TextStyle` for the overlay (role/text_style precedence; kind default
   role).
2. **Measure** the wrapped text: lay `ov.text` into a `QTextLayout` (or
   `QFontMetrics.boundingRect` with word wrap) at width
   `min(style.max_width_px, …)`; obtain `(text_w, text_h)`.
3. Compute `inner_rect = (text_w + 2·padding, text_h + 2·padding)` placed at
   `ov.anchor` per `anchor_mode` (`center` centers the body on the anchor;
   `topleft` puts the body's top-left at the anchor).
4. `segs = balloons.overlay_to_segments(ov.kind, inner_rect, ov.tail_target, ov.style)`.
5. Build a `QPainterPath` from `segs` (reuse the segment→path logic already in
   `region_to_painter_path`; refactor a shared `segments_to_painter_path(segs)`
   helper if cleaner). Fill with `style.fill`; stroke with
   `QPen(style.stroke_color, style.stroke_px)` when `stroke_px > 0`.
6. Draw the wrapped text: a `QGraphicsTextItem` with `setTextWidth(inner_w)`,
   positioned inside the inner rect, clipped to the body path
   (`ItemClipsChildrenToShape` on a path item parent — same pattern the region
   text path already uses).
7. **SFX**: skip the body; draw the display text at `ov.anchor` using the `sfx`
   role style. An optional outline (common for SFX) is drawn with
   `QPainterPathStroker` around the glyph path; if that proves heavy, MVP draws
   filled text only and the outline is a Minor follow-up.
8. **Z-order**: overlays are drawn **after** all regions and sorted by `ov.z`,
   so they always sit above the panels.

`render_page_to_image` and the live `build_scene` both iterate
`page.overlays` after `page.regions`. No change to how regions render.

**No new production geometry in the renderer** beyond the measure step and the
overlay loop — the body/tail geometry all comes from the pure `balloons.py`.

## 6. Serialization (`core/layout/schema.py`)

- `overlay_to_dict(ov) -> dict` and `overlay_from_dict(d) -> Overlay`
  (and nested `OverlayStyle`), mirroring `region_to_dict`/`region_from_dict`.
- `PageSpec` serialization includes the `overlays` array.
- A `OVERLAY_JSON_SCHEMA` fragment is added and referenced from the page schema.
- `_filtered` keeps unknown-key tolerance; all new fields have defaults so older
  files (no `overlays`) load as an empty overlay list.

## 7. Testing

All tests run under `QT_QPA_PLATFORM=offscreen` with `.venv_linux/bin/python`.
The full layout suite must stay green (currently **222 passed** on the branch).

- **`tests/layout/test_balloons.py`** (pure, no Qt):
  - `caption_body` → exactly a rectangle (4 corners; `validate_segments == []`).
  - `speech_body` → valid; `inner ⊆ bbox`; contains cubic segments (rounded).
  - `thought_body` → valid; `inner ⊆ bbox`; contains quad segments (scallops).
  - `overlay_to_segments("speech", …, target)` → single closed ring whose bbox
    reaches toward the target (tail tip is the extreme point in the target's
    direction); without a target → no tail.
  - `overlay_to_segments("thought", …, target)` → body + N extra closed
    subpaths (trail), each valid; trail marches toward target.
  - `overlay_to_segments("sfx", …)` → `[]`.
  - Degenerate inner rect → `[]` + a logged warning (caplog).
- **`tests/layout/test_overlay_schema.py`**: `Overlay` (each kind, with/without
  tail, custom `OverlayStyle`) round-trips byte-stable through
  `overlay_to_dict`/`overlay_from_dict`; a `PageSpec` with overlays round-trips;
  an old dict without `overlays` loads to `[]`.
- **`tests/layout/test_overlay_render.py`** (Qt, offscreen, uses the existing
  `qapp` fixture):
  - A page with one speech overlay renders: a pixel inside the body is
    `style.fill` (white-ish), a pixel well outside is page background, text
    pixels are present (non-fill) inside the body.
  - The tail extends toward `tail_target` (a body pixel exists between body
    center and target).
  - Two overlays with different `z` paint in the right order (higher z on top
    where they overlap).
  - A caption overlay renders as a filled rect with text; an SFX overlay renders
    text with no body fill around it.

## 8. Module/interface summary (for the plan)

| Symbol | File | Signature |
|---|---|---|
| `OverlayStyle` | models.py | dataclass (fill, stroke_px, stroke_color, padding_px, radius_px, max_width_px) |
| `Overlay` | models.py | dataclass (id, kind, text, anchor, anchor_mode, tail_target, z, role, text_style, style) |
| `PageSpec.overlays` | models.py | `List[Overlay]` |
| `caption_body` | balloons.py | `(inner) -> List[PathSegment]` |
| `speech_body` | balloons.py | `(inner, *, radius) -> List[PathSegment]` |
| `thought_body` | balloons.py | `(inner, *, scallop) -> List[PathSegment]` |
| `thought_trail` | balloons.py | `(body_center, target, *, count) -> List[PathSegment]` |
| `overlay_to_segments` | balloons.py | `(kind, inner, tail_target, style) -> List[PathSegment]` |
| `_add_overlay` | qt_renderer.py | overlay render pass (measure → balloons → draw) |
| `segments_to_painter_path` | qt_renderer.py | shared `(segs) -> QPainterPath` (refactor) |
| `overlay_to_dict` / `overlay_from_dict` | schema.py | `Overlay ⇄ dict` |

## 9. Acceptance criteria
1. `Overlay`/`OverlayStyle` exist; `PageSpec.overlays` defaults to `[]`; all
   Qt-free and serializable.
2. `balloons.py` is Qt-free; each body/tail builder emits `validate_segments`-
   clean `PathSegment`s; `inner ⊆ body bbox`; degenerate input logs + returns
   `[]`.
3. The four kinds render through `qt_renderer` (speech body+tail, thought
   body+trail, caption rect, sfx text), with auto-fit to wrapped text.
4. Overlays paint above panels, ordered by `z`.
5. Overlays round-trip through `schema.py`; old files without `overlays` load
   cleanly.
6. No renderer change to how *regions* render; no new third-party dependency;
   `balloons.py` and `models.py`/`schema.py` stay Qt-free.
7. Full layout suite green (222 + new tests), pristine output.

## 10. Self-review
- **Placeholder scan:** none — every section is concrete; the only optional/MVP
  items (SFX outline pen) are explicitly marked as Minor follow-ups, not gaps.
- **Internal consistency:** the pure/Qt boundary is consistent throughout —
  measurement is always in the renderer, geometry always in `balloons.py`. The
  data model, geometry signatures, render steps, and serialization all reference
  the same field names (`kind`, `anchor`, `tail_target`, `style.*`).
- **Scope:** single sub-project, single implementation plan; authoring deferred
  to #4/#5; export divergence explicitly out of scope.
- **Ambiguity:** tail construction (spliced single path for speech; separate
  trail subpaths for thought), wrap-within-rect, default-role-per-kind, and
  z-order are each pinned to one interpretation.

## 11. Relationship to the feature
Builds on #1 (`Region`/`PathSegment`/`qt_renderer`/`schema`/`validate_segments`)
and #2 (`polygon_to_segments`). Produces the overlay substrate that #4 (AI
designer emits `Overlay`s) and #5 (manual editor authors/drag-edits `Overlay`s,
adds tail snapping + SFX rotation + contour wrap) build on. Per the feature PR
gate, no PR until all 5 sub-projects are done.
