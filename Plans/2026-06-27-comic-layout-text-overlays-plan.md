# Comic Layout — Text Overlays Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add comic text overlays — tailed speech balloons, thought bubbles, caption boxes, and SFX lettering — as a pure data model + Qt-free geometry module + a Qt renderer pass, floating above the panels from sub-projects #1 and #2.

**Architecture:** A declarative `Overlay`/`OverlayStyle` model lives on `PageSpec.overlays`. A new pure module `core/layout/balloons.py` compiles an overlay's inner bounding rectangle (+ optional tail target) into `PathSegment` geometry (rounded-rect cubics, scalloped-cloud quads, spliced tail). The renderer (`qt_renderer.py`) measures the wrapped text with Qt font metrics to size the balloon, then draws body fill + stroke + tail and the wrapped text clipped to the body. Authoring is deferred to #4/#5.

**Tech Stack:** Python 3.12, pytest, PySide6 (renderer only). Reuses `PathSegment`/`Region`/`PageSpec`/`TextStyle` (`core/layout/models.py`), `validate_segments`/`segments_bbox` (`core/layout/geometry.py`), `polygon_to_segments` (`core/layout/polygon.py`), `region_to_painter_path`/`_add_text_region` patterns (`core/layout/qt_renderer.py`), `effective_text_style` (`core/layout/styles.py`), and `region_to_dict`/`region_from_dict` (`core/layout/schema.py`).

## Global Constraints

- Test interpreter: `.venv_linux/bin/python`. Run tests with `QT_QPA_PLATFORM=offscreen` prefixed (required for the Qt render tests; harmless for pure tests).
- Full layout suite must stay green: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` (currently **222 passed** on branch `feat/comic-layout-geometry-core`).
- **No new third-party dependency** — all balloon geometry is hand-rolled in `core/layout/balloons.py`.
- `core/layout/balloons.py`, `core/layout/models.py`, and `core/layout/schema.py` must be **Qt-free** (importable headless). Only `qt_renderer.py` and the render tests touch Qt.
- **All errors logged** (platform-independent `logging.getLogger(__name__)`): degenerate overlay rects (non-positive size) are logged and produce an empty segment list, never crash.
- Every emitted overlay-body segment list must pass `validate_segments` (returns `[]`). No edits to how *regions* render.
- `Overlay`/`OverlayStyle` serialize and round-trip through `core/layout/schema.py`; old page dicts without `overlays` load to an empty list.
- Coordinates are page pixels (floats). `KAPPA = 0.5522847498307936` for circular-arc cubic approximation.
- Conventional Commits (`feat(layout): …`). Commit after each task.
- **Branch:** continue on `feat/comic-layout-geometry-core` (all 5 comic-layout sub-projects share one branch). **Do NOT open a pull request** — the single PR comes only after sub-project #5.

### Naming convention used across tasks
- `inner: Rect` (a `Tuple[float, float, float, float]` = `(x, y, w, h)`) is the **body's inner bounding rectangle** = text box + padding. The body must contain `inner` (its bbox equals or exceeds `inner`). The renderer computes `inner` from measured text; `balloons.py` only consumes it.
- `Point = Tuple[float, float]`, `Rect = Tuple[float, float, float, float]`.

---

### Task 1: `Overlay` / `OverlayStyle` model + `PageSpec.overlays`

**Files:**
- Modify: `core/layout/models.py`
- Test: `tests/layout/test_overlay_model.py` (create)

**Interfaces:**
- Consumes: `TextStyle` (existing, `core/layout/models.py`).
- Produces:
  - `@dataclass OverlayStyle(fill="#FFFFFF", stroke_px=2.0, stroke_color="#000000", padding_px=10.0, radius_px=16.0, max_width_px=240.0)`
  - `@dataclass Overlay(id, kind: Literal["speech","thought","caption","sfx"], text, anchor: Tuple[float,float], anchor_mode: Literal["center","topleft"]="center", tail_target: Optional[Tuple[float,float]]=None, z=0, role="", text_style: Optional[TextStyle]=None, style: OverlayStyle=field(default_factory=OverlayStyle))`
  - `PageSpec.overlays: List[Overlay] = field(default_factory=list)`

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_overlay_model.py`:

```python
from core.layout.models import Overlay, OverlayStyle, PageSpec, TextStyle


def test_overlay_style_defaults():
    s = OverlayStyle()
    assert s.fill == "#FFFFFF"
    assert s.stroke_px == 2.0
    assert s.stroke_color == "#000000"
    assert s.padding_px == 10.0
    assert s.radius_px == 16.0
    assert s.max_width_px == 240.0


def test_overlay_defaults_and_fields():
    ov = Overlay(id="o1", kind="speech", text="Hi!", anchor=(50.0, 40.0))
    assert ov.kind == "speech"
    assert ov.anchor == (50.0, 40.0)
    assert ov.anchor_mode == "center"
    assert ov.tail_target is None
    assert ov.z == 0
    assert ov.role == ""
    assert ov.text_style is None
    assert isinstance(ov.style, OverlayStyle)


def test_overlay_independent_style_instances():
    a = Overlay(id="a", kind="caption", text="x", anchor=(0.0, 0.0))
    b = Overlay(id="b", kind="caption", text="y", anchor=(0.0, 0.0))
    a.style.fill = "#FFEE00"
    assert b.style.fill == "#FFFFFF"  # default_factory -> no shared mutable default


def test_overlay_with_tail_and_text_style():
    ts = TextStyle()
    ov = Overlay(id="o2", kind="thought", text="hmm", anchor=(10.0, 10.0),
                 tail_target=(5.0, 30.0), z=3, role="dialogue", text_style=ts)
    assert ov.tail_target == (5.0, 30.0)
    assert ov.z == 3
    assert ov.role == "dialogue"
    assert ov.text_style is ts


def test_pagespec_overlays_default_empty():
    page = PageSpec(page_size_px=(100, 100))
    assert page.overlays == []
    page.overlays.append(Overlay(id="o", kind="sfx", text="BOOM", anchor=(20.0, 20.0)))
    assert len(page.overlays) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_model.py -q`
Expected: FAIL — `ImportError: cannot import name 'Overlay'`.

- [ ] **Step 3: Implement the model**

In `core/layout/models.py`, add the two dataclasses near `TextStyle`/`Region` (reuse the existing `from typing import ...` and `from dataclasses import dataclass, field` imports; add any missing names — `Literal`, `Optional`, `Tuple`, `List`, `field` — to the existing import lines, do not duplicate imports):

```python
@dataclass
class OverlayStyle:
    """Visual style for a comic text overlay's body (balloon/caption shell)."""
    fill: str = "#FFFFFF"
    stroke_px: float = 2.0
    stroke_color: str = "#000000"
    padding_px: float = 10.0        # inset between the text box and the body edge
    radius_px: float = 16.0         # corner roundness (speech) / scallop radius (thought)
    max_width_px: float = 240.0     # wrap-width cap used by the renderer's auto-fit


@dataclass
class Overlay:
    """A declarative comic text overlay (speech/thought/caption/sfx).

    Qt-free and serializable. The renderer measures the wrapped text to size the
    body; balloons.py builds the body/tail geometry. `anchor` places the body
    (center or top-left per `anchor_mode`); `tail_target` is a free page-pixel
    point the tail points at (None = no tail).
    """
    id: str
    kind: Literal["speech", "thought", "caption", "sfx"]
    text: str
    anchor: Tuple[float, float]
    anchor_mode: Literal["center", "topleft"] = "center"
    tail_target: Optional[Tuple[float, float]] = None
    z: int = 0
    role: str = ""
    text_style: Optional[TextStyle] = None
    style: OverlayStyle = field(default_factory=OverlayStyle)
```

In the `PageSpec` dataclass, add the field (place it after `regions`):

```python
    overlays: List[Overlay] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_model.py -q`
Expected: PASS (5 passed). Then full suite stays green: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` (expect 227).

- [ ] **Step 5: Commit**

```bash
git add core/layout/models.py tests/layout/test_overlay_model.py
git commit -m "feat(layout): Overlay/OverlayStyle model + PageSpec.overlays"
```

---

### Task 2: `balloons.py` — caption + speech body (rounded rect) + dispatch skeleton

**Files:**
- Create: `core/layout/balloons.py`
- Test: `tests/layout/test_balloons.py` (create)

**Interfaces:**
- Consumes: `PathSegment` (`core.layout.models`); `validate_segments`/`segments_bbox` (`core.layout.geometry`); `OverlayStyle` (`core.layout.models`).
- Produces:
  - `Point`, `Rect` aliases; `KAPPA` constant.
  - `caption_body(inner: Rect) -> List[PathSegment]`
  - `speech_body(inner: Rect, *, radius: float) -> List[PathSegment]`
  - `overlay_to_segments(kind: str, inner: Rect, tail_target: Optional[Point], style: OverlayStyle) -> List[PathSegment]` — this task implements `caption`, `speech` (no-tail), and `sfx` (`[]`); degenerate `inner` → `[]` + log. `thought` and the speech tail are added in Tasks 3–4.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_balloons.py`:

```python
from core.layout.balloons import caption_body, speech_body, overlay_to_segments
from core.layout.models import OverlayStyle
from core.layout.geometry import validate_segments, segments_bbox


INNER = (10.0, 20.0, 80.0, 40.0)  # x, y, w, h


def _contains(bbox, inner, tol=1e-6):
    bx, by, bw, bh = bbox
    ix, iy, iw, ih = inner
    return (bx <= ix + tol and by <= iy + tol
            and bx + bw >= ix + iw - tol and by + bh >= iy + ih - tol)


def test_caption_body_is_rectangle():
    segs = caption_body(INNER)
    assert validate_segments(segs) == []
    assert [s.type for s in segs] == ["move", "line", "line", "line", "close"]
    assert _contains(segments_bbox(segs), INNER)


def test_speech_body_valid_rounded_and_contains_inner():
    segs = speech_body(INNER, radius=12.0)
    assert validate_segments(segs) == []
    assert any(s.type == "cubic" for s in segs)        # rounded corners
    bbox = segments_bbox(segs)
    assert _contains(bbox, INNER)
    # rounded rect bbox equals inner bounds (corner controls stay inside)
    assert abs(bbox[2] - INNER[2]) < 1e-6 and abs(bbox[3] - INNER[3]) < 1e-6


def test_speech_radius_clamped_to_half_extent():
    # radius larger than half the smaller side must not invert the body
    segs = speech_body((0.0, 0.0, 20.0, 10.0), radius=999.0)
    assert validate_segments(segs) == []
    assert segments_bbox(segs)[2:] == (20.0, 10.0)


def test_overlay_to_segments_caption_and_speech_and_sfx():
    style = OverlayStyle(radius_px=10.0)
    assert overlay_to_segments("caption", INNER, None, style) == caption_body(INNER)
    speech = overlay_to_segments("speech", INNER, None, style)
    assert validate_segments(speech) == []
    assert any(s.type == "cubic" for s in speech)      # speech uses rounded body
    assert overlay_to_segments("sfx", INNER, None, style) == []  # sfx has no body


def test_overlay_to_segments_degenerate_logs_and_empty(caplog):
    import logging
    style = OverlayStyle()
    with caplog.at_level(logging.WARNING):
        assert overlay_to_segments("speech", (0.0, 0.0, 0.0, 30.0), None, style) == []
    assert any("degenerate" in r.message.lower() or "non-positive" in r.message.lower()
               for r in caplog.records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_balloons.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.layout.balloons'`.

- [ ] **Step 3: Implement `balloons.py` foundation**

Create `core/layout/balloons.py`:

```python
"""Pure (Qt-free) comic-overlay geometry: balloon/caption bodies + tails.

Compiles an overlay's inner bounding rectangle (text box + padding) into
PathSegment geometry that core.layout.qt_renderer draws unchanged. No Qt, no
font metrics here — the renderer measures text and passes us `inner`.

`inner` is (x, y, w, h); the produced body's bounding box contains `inner`.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from core.layout.models import OverlayStyle, PathSegment

logger = logging.getLogger(__name__)

Point = Tuple[float, float]
Rect = Tuple[float, float, float, float]

KAPPA = 0.5522847498307936  # control-point factor for a circular quarter-arc cubic


def _valid_rect(inner: Rect) -> bool:
    _, _, w, h = inner
    return w > 0.0 and h > 0.0


def caption_body(inner: Rect) -> List[PathSegment]:
    """A plain rectangle (caption box) around `inner`."""
    x, y, w, h = inner
    return [
        PathSegment(type="move", pts=[(x, y)]),
        PathSegment(type="line", pts=[(x + w, y)]),
        PathSegment(type="line", pts=[(x + w, y + h)]),
        PathSegment(type="line", pts=[(x, y + h)]),
        PathSegment(type="close", pts=[]),
    ]


def speech_body(inner: Rect, *, radius: float) -> List[PathSegment]:
    """A rounded rectangle around `inner`; corners are circular cubic arcs.

    Segment order (used by the tail splice in Task 3):
      0 move, 1 TOP line, 2 TR cubic, 3 RIGHT line, 4 BR cubic,
      5 BOTTOM line, 6 BL cubic, 7 LEFT line, 8 TL cubic, 9 close
    """
    x, y, w, h = inner
    r = max(0.0, min(radius, w / 2.0, h / 2.0))
    k = r * KAPPA
    x2, y2 = x + w, y + h
    return [
        PathSegment(type="move", pts=[(x + r, y)]),
        PathSegment(type="line", pts=[(x2 - r, y)]),
        PathSegment(type="cubic", pts=[(x2 - r + k, y), (x2, y + r - k), (x2, y + r)]),
        PathSegment(type="line", pts=[(x2, y2 - r)]),
        PathSegment(type="cubic", pts=[(x2, y2 - r + k), (x2 - r + k, y2), (x2 - r, y2)]),
        PathSegment(type="line", pts=[(x + r, y2)]),
        PathSegment(type="cubic", pts=[(x + r - k, y2), (x, y2 - r + k), (x, y2 - r)]),
        PathSegment(type="line", pts=[(x, y + r)]),
        PathSegment(type="cubic", pts=[(x, y + r - k), (x + r - k, y), (x + r, y)]),
        PathSegment(type="close", pts=[]),
    ]


def overlay_to_segments(kind: str, inner: Rect, tail_target: Optional[Point],
                        style: OverlayStyle) -> List[PathSegment]:
    """Compile an overlay body (+ tail) for `kind`.

    caption -> rectangle (tail ignored); speech -> rounded body (tail spliced in
    Task 3); thought -> cloud + trail (Task 4); sfx -> [] (text only).
    Degenerate `inner` (non-positive size) logs a warning and returns [].
    """
    if kind == "sfx":
        return []
    if not _valid_rect(inner):
        logger.warning("Overlay %r has a degenerate/non-positive inner rect %r; no body",
                       kind, inner)
        return []
    if kind == "caption":
        return caption_body(inner)
    if kind == "speech":
        return speech_body(inner, radius=style.radius_px)
    if kind == "thought":
        # Implemented in Task 4; until then fall back to a plain body so callers
        # never crash. Replaced by thought_body + trail in Task 4.
        return speech_body(inner, radius=style.radius_px)
    logger.warning("Overlay has unknown kind %r; no body", kind)
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_balloons.py -q`
Expected: PASS (5 passed). Then full suite green (expect 232).

- [ ] **Step 5: Commit**

```bash
git add core/layout/balloons.py tests/layout/test_balloons.py
git commit -m "feat(layout): balloons.py caption + speech body geometry + dispatch"
```

---

### Task 3: `balloons.py` — speech tail splice (single closed path)

**Files:**
- Modify: `core/layout/balloons.py`
- Test: `tests/layout/test_balloons.py` (extend)

**Interfaces:**
- Consumes: `speech_body`, `Point`, `Rect` (Task 2).
- Produces: `overlay_to_segments("speech", inner, tail_target, style)` now splices a triangular tail into the rounded body's nearest straight edge, yielding ONE closed path whose outline includes the tail tip at `tail_target`. Helper `_splice_speech_tail(segs, inner, target, base_width) -> List[PathSegment]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/layout/test_balloons.py`:

```python
def _all_points(segs):
    return [p for s in segs for p in s.pts]


def test_speech_tail_reaches_target_below():
    style = OverlayStyle(radius_px=10.0)
    target = (50.0, 120.0)  # well below INNER (which ends at y=60)
    segs = overlay_to_segments("speech", INNER, target, style)
    assert validate_segments(segs) == []
    # the tail tip is an exact vertex on the outline
    assert any(abs(px - target[0]) < 1e-6 and abs(py - target[1]) < 1e-6
               for px, py in _all_points(segs))
    # bbox now extends below the body to reach the target
    bbox = segments_bbox(segs)
    assert bbox[1] + bbox[3] >= target[1] - 1e-6


def test_speech_tail_target_above():
    style = OverlayStyle(radius_px=10.0)
    target = (50.0, -30.0)  # above the body
    segs = overlay_to_segments("speech", INNER, target, style)
    assert validate_segments(segs) == []
    assert any(abs(py - target[1]) < 1e-6 for _, py in _all_points(segs))
    assert segments_bbox(segs)[1] <= target[1] + 1e-6  # bbox reaches up to target


def test_speech_no_target_has_no_tail():
    style = OverlayStyle(radius_px=10.0)
    segs = overlay_to_segments("speech", INNER, None, style)
    # bbox stays within the inner bounds (no tail protrusion)
    bbox = segments_bbox(segs)
    assert bbox[1] >= INNER[1] - 1e-6
    assert bbox[1] + bbox[3] <= INNER[1] + INNER[3] + 1e-6


def test_speech_tail_single_closed_ring():
    style = OverlayStyle(radius_px=10.0)
    segs = overlay_to_segments("speech", INNER, (50.0, 120.0), style)
    assert sum(1 for s in segs if s.type == "move") == 1   # one subpath
    assert sum(1 for s in segs if s.type == "close") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_balloons.py -k "tail or no_target or single_closed" -q`
Expected: FAIL — speech currently ignores `tail_target`, so the tip vertex / extended bbox assertions fail.

- [ ] **Step 3: Implement the tail splice**

In `core/layout/balloons.py`, add the helpers and route speech through them. The four straight edges of `speech_body` are at segment indices TOP=1, RIGHT=3, BOTTOM=5, LEFT=7. Pick the edge whose outward direction faces the target (compare the target to the body center), compute two base points on that edge's straight span, and replace that edge's single `line` with `line(base_a) → line(tip) → line(base_b)` where `base_a` is the base point nearer the edge's start vertex (so the detour respects the outline's traversal direction). Append:

```python
def _edge_for_target(inner: Rect, target: Point) -> str:
    x, y, w, h = inner
    cx, cy = x + w / 2.0, y + h / 2.0
    dx, dy = target[0] - cx, target[1] - cy
    # choose the dominant direction; ties prefer vertical (bottom/top) — the
    # conventional comic tail direction
    if abs(dy) >= abs(dx):
        return "bottom" if dy >= 0 else "top"
    return "right" if dx >= 0 else "left"


def _edge_span(inner: Rect, r: float, edge: str) -> Tuple[Point, Point, int]:
    """Straight-edge start/end (in outline traversal order) + its segment index,
    for a rounded body of `inner` with corner radius r."""
    x, y, w, h = inner
    x2, y2 = x + w, y + h
    if edge == "top":     # left->right, segment index 1
        return (x + r, y), (x2 - r, y), 1
    if edge == "right":   # top->bottom, index 3
        return (x2, y + r), (x2, y2 - r), 3
    if edge == "bottom":  # right->left, index 5
        return (x2 - r, y2), (x + r, y2), 5
    return (x, y2 - r), (x, y + r), 7  # left: bottom->top, index 7


def _splice_speech_tail(segs: List[PathSegment], inner: Rect, target: Point,
                        base_width: float, radius: float) -> List[PathSegment]:
    x, y, w, h = inner
    r = max(0.0, min(radius, w / 2.0, h / 2.0))
    edge = _edge_for_target(inner, target)
    (sx, sy), (ex, ey), idx = _edge_span(inner, r, edge)
    tip = (float(target[0]), float(target[1]))
    if edge in ("top", "bottom"):
        lo, hi = sorted((sx, ex))
        mid = min(max(target[0], lo + 1e-6), hi - 1e-6)
        half = min(base_width / 2.0, (hi - lo) / 2.0 - 1e-6)
        p1, p2 = (mid - half, sy), (mid + half, sy)
    else:  # left / right edges (vertical span)
        lo, hi = sorted((sy, ey))
        mid = min(max(target[1], lo + 1e-6), hi - 1e-6)
        half = min(base_width / 2.0, (hi - lo) / 2.0 - 1e-6)
        p1, p2 = (sx, mid - half), (sx, mid + half)
    # order base points along the traversal start (sx,sy) -> end (ex,ey):
    # `a` is the base point nearer the start vertex.
    def _d2(p, q):
        return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2
    a, b = (p1, p2) if _d2(p1, (sx, sy)) <= _d2(p2, (sx, sy)) else (p2, p1)
    out: List[PathSegment] = []
    for i, seg in enumerate(segs):
        if i == idx and seg.type == "line":
            out.append(PathSegment(type="line", pts=[a]))
            out.append(PathSegment(type="line", pts=[tip]))
            out.append(PathSegment(type="line", pts=[b]))
            out.append(seg)  # original edge endpoint completes the edge
        else:
            out.append(seg)
    return out
```

Then update `overlay_to_segments`'s speech branch:

```python
    if kind == "speech":
        body = speech_body(inner, radius=style.radius_px)
        if tail_target is None:
            return body
        base_width = max(8.0, min(inner[2], inner[3]) * 0.35)
        return _splice_speech_tail(body, inner, tail_target, base_width, style.radius_px)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_balloons.py -q`
Expected: PASS (all balloon tests). Then full suite green (expect 236). If a tail test fails on the base-point ordering, confirm the inserted sequence `a → tip → b` matches the edge's traversal direction (start `sx,sy` → end `ex,ey`); the tip vertex must equal `tail_target` exactly.

- [ ] **Step 5: Commit**

```bash
git add core/layout/balloons.py tests/layout/test_balloons.py
git commit -m "feat(layout): speech-balloon tail splice (single closed outline)"
```

---

### Task 4: `balloons.py` — thought cloud body + bubble trail

**Files:**
- Modify: `core/layout/balloons.py`
- Test: `tests/layout/test_balloons.py` (extend)

**Interfaces:**
- Consumes: `Point`, `Rect`, `KAPPA` (Tasks 2–3).
- Produces:
  - `thought_body(inner: Rect, *, scallop: float) -> List[PathSegment]` — a closed scalloped cloud (quad bumps) on an ellipse circumscribing `inner`.
  - `thought_trail(body_center: Point, target: Point, *, count: int = 3) -> List[PathSegment]` — `count` shrinking circle subpaths marching toward `target`.
  - `overlay_to_segments("thought", …)` now returns `thought_body(...) + thought_trail(...)` (trail only when `tail_target` is set).

- [ ] **Step 1: Write the failing test**

Append to `tests/layout/test_balloons.py`:

```python
from core.layout.balloons import thought_body, thought_trail


def test_thought_body_is_valid_cloud_containing_inner():
    segs = thought_body(INNER, scallop=8.0)
    assert validate_segments(segs) == []
    assert any(s.type == "quad" for s in segs)         # scalloped bumps
    assert _contains(segments_bbox(segs), INNER)


def test_thought_trail_marches_toward_target_with_count_subpaths():
    trail = thought_trail((50.0, 40.0), (90.0, 90.0), count=3)
    assert validate_segments(trail) == []
    assert sum(1 for s in trail if s.type == "move") == 3   # 3 ellipse subpaths
    # last (smallest) bubble is nearest the target
    xs = [s.pts[0][0] for s in trail if s.type == "move"]
    assert xs[-1] > xs[0]  # progressing toward target.x = 90


def test_overlay_thought_has_body_plus_trail():
    style = OverlayStyle(radius_px=10.0)
    segs = overlay_to_segments("thought", INNER, (95.0, 95.0), style)
    assert validate_segments(segs) == []
    moves = sum(1 for s in segs if s.type == "move")
    assert moves == 1 + 3   # body + 3 trail bubbles


def test_overlay_thought_no_target_body_only():
    style = OverlayStyle(radius_px=10.0)
    segs = overlay_to_segments("thought", INNER, None, style)
    assert sum(1 for s in segs if s.type == "move") == 1   # body only, no trail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_balloons.py -k thought -q`
Expected: FAIL — `ImportError: cannot import name 'thought_body'` (and thought currently falls back to speech body, so the body+trail count assertions fail).

- [ ] **Step 3: Implement cloud + trail**

Append to `core/layout/balloons.py`:

```python
import math


def _circle_segments(cx: float, cy: float, r: float) -> List[PathSegment]:
    """A closed circle approximated by four cubic quarter-arcs (move..close)."""
    k = r * KAPPA
    return [
        PathSegment(type="move", pts=[(cx + r, cy)]),
        PathSegment(type="cubic", pts=[(cx + r, cy + k), (cx + k, cy + r), (cx, cy + r)]),
        PathSegment(type="cubic", pts=[(cx - k, cy + r), (cx - r, cy + k), (cx - r, cy)]),
        PathSegment(type="cubic", pts=[(cx - r, cy - k), (cx - k, cy - r), (cx, cy - r)]),
        PathSegment(type="cubic", pts=[(cx + k, cy - r), (cx + r, cy - k), (cx + r, cy)]),
        PathSegment(type="close", pts=[]),
    ]


def thought_body(inner: Rect, *, scallop: float) -> List[PathSegment]:
    """A scalloped 'cloud' on an ellipse circumscribing `inner`.

    N outward quad bumps around the ellipse. The circumscribing ellipse
    (semi-axes 1.42x the rect half-extents) contains `inner`'s corners; the
    bumps extend further, so bbox(cloud) contains `inner`.
    """
    x, y, w, h = inner
    cx, cy = x + w / 2.0, y + h / 2.0
    ax, ay = (w / 2.0) * 1.42, (h / 2.0) * 1.42  # circumscribe the corners
    bumps = max(8, int(((w + h) / 40.0)) * 2)    # even count, scales with size
    pts = [(cx + ax * math.cos(2 * math.pi * i / bumps),
            cy + ay * math.sin(2 * math.pi * i / bumps)) for i in range(bumps)]
    segs = [PathSegment(type="move", pts=[pts[0]])]
    for i in range(bumps):
        nxt = pts[(i + 1) % bumps]
        mid_ang = 2 * math.pi * (i + 0.5) / bumps
        ctrl = (cx + (ax + scallop) * math.cos(mid_ang),
                cy + (ay + scallop) * math.sin(mid_ang))
        segs.append(PathSegment(type="quad", pts=[ctrl, nxt]))
    segs.append(PathSegment(type="close", pts=[]))
    return segs


def thought_trail(body_center: Point, target: Point, *, count: int = 3) -> List[PathSegment]:
    """`count` shrinking circles from near `body_center` toward `target`."""
    out: List[PathSegment] = []
    for i in range(count):
        t = (i + 1) / (count + 1)
        cx = body_center[0] + (target[0] - body_center[0]) * t
        cy = body_center[1] + (target[1] - body_center[1]) * t
        r = max(1.0, 6.0 * (1.0 - t))   # shrink toward the target
        out.extend(_circle_segments(cx, cy, r))
    return out
```

Update the `thought` branch in `overlay_to_segments` (replace the Task-2 fallback):

```python
    if kind == "thought":
        body = thought_body(inner, scallop=max(4.0, style.radius_px * 0.5))
        if tail_target is None:
            return body
        cx, cy = inner[0] + inner[2] / 2.0, inner[1] + inner[3] / 2.0
        return body + thought_trail((cx, cy), tail_target, count=3)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_balloons.py -q`
Expected: PASS (all balloon tests). Full suite green (expect 240). If `_contains` fails for the cloud, confirm the circumscribing factor (1.42 ≈ √2) keeps the ellipse outside the rect corners.

- [ ] **Step 5: Commit**

```bash
git add core/layout/balloons.py tests/layout/test_balloons.py
git commit -m "feat(layout): thought-bubble cloud body + shrinking bubble trail"
```

---

### Task 5: Serialize `Overlay` through `schema.py`

**Files:**
- Modify: `core/layout/schema.py`
- Test: `tests/layout/test_overlay_schema.py` (create)

**Interfaces:**
- Consumes: `Overlay`, `OverlayStyle`, `TextStyle`, `PageSpec` (`core.layout.models`); existing `region_to_dict`/`region_from_dict` patterns and any `text_style` (de)serialization already in `schema.py`.
- Produces:
  - `overlay_to_dict(ov: Overlay) -> dict` and `overlay_from_dict(d: dict) -> Overlay` (incl. nested `OverlayStyle` and optional `TextStyle`).
  - `PageSpec` (de)serialization includes `overlays` (wire into the existing page-level functions — find how `regions` is serialized and mirror it for `overlays`). Old dicts without `overlays` → `[]`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_overlay_schema.py`:

```python
from core.layout.models import Overlay, OverlayStyle, TextStyle
from core.layout.schema import overlay_to_dict, overlay_from_dict


def _roundtrip(ov):
    return overlay_from_dict(overlay_to_dict(ov))


def test_speech_overlay_roundtrip_with_tail_and_style():
    ov = Overlay(id="o1", kind="speech", text="Hi!", anchor=(50.0, 40.0),
                 anchor_mode="center", tail_target=(50.0, 90.0), z=2, role="dialogue",
                 style=OverlayStyle(fill="#FFEE00", stroke_px=3.0, padding_px=12.0,
                                    radius_px=20.0, max_width_px=180.0))
    r = _roundtrip(ov)
    assert r.id == "o1" and r.kind == "speech" and r.text == "Hi!"
    assert r.anchor == (50.0, 40.0) and r.tail_target == (50.0, 90.0)
    assert r.z == 2 and r.role == "dialogue"
    assert r.style.fill == "#FFEE00" and r.style.stroke_px == 3.0
    assert r.style.padding_px == 12.0 and r.style.radius_px == 20.0
    assert r.style.max_width_px == 180.0


def test_overlay_roundtrip_each_kind():
    for kind in ("speech", "thought", "caption", "sfx"):
        ov = Overlay(id=kind, kind=kind, text="x", anchor=(1.0, 2.0))
        assert _roundtrip(ov).kind == kind


def test_overlay_roundtrip_with_text_style():
    ov = Overlay(id="t", kind="caption", text="cap", anchor=(0.0, 0.0),
                 text_style=TextStyle(size_px=30, color="#112233"))
    r = _roundtrip(ov)
    assert r.text_style is not None
    assert r.text_style.size_px == 30 and r.text_style.color == "#112233"


def test_overlay_from_dict_defaults_when_missing_optionals():
    r = overlay_from_dict({"id": "m", "kind": "sfx", "text": "BOOM", "anchor": [5.0, 6.0]})
    assert r.anchor == (5.0, 6.0)
    assert r.tail_target is None and r.role == ""
    assert isinstance(r.style, OverlayStyle) and r.style.fill == "#FFFFFF"
```

Then add a `PageSpec` round-trip test using whatever page (de)serialization `schema.py`/`project_io.py` exposes (mirror the existing region round-trip test in the suite). At minimum:

```python
def test_pagespec_without_overlays_loads_empty():
    # an older page dict (no "overlays" key) must deserialize to overlays == []
    from core.layout.schema import page_from_dict  # use the actual page loader name
    page = page_from_dict({"page_size_px": [100, 100], "regions": []})
    assert page.overlays == []
```

> Note: if the page-level loader is named differently (e.g. in `project_io.py`), import and call that one instead; the requirement is "a page dict without `overlays` yields `overlays == []`".

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_schema.py -q`
Expected: FAIL — `ImportError: cannot import name 'overlay_to_dict'`.

- [ ] **Step 3: Implement serialization**

In `core/layout/schema.py`, add overlay (de)serializers modeled on `region_to_dict`/`region_from_dict`. Reuse the module's existing `TextStyle` (de)serialization helper if one exists; otherwise serialize `text_style` with `dataclasses.asdict` and reconstruct with `TextStyle(**d)`. Tuples serialize as lists and are restored as tuples:

```python
from core.layout.models import Overlay, OverlayStyle  # add to existing models import


def _overlay_style_to_dict(s: OverlayStyle) -> dict:
    return {"fill": s.fill, "stroke_px": s.stroke_px, "stroke_color": s.stroke_color,
            "padding_px": s.padding_px, "radius_px": s.radius_px,
            "max_width_px": s.max_width_px}


def _overlay_style_from_dict(d: dict) -> OverlayStyle:
    return OverlayStyle(**_filtered(d, OverlayStyle)) if d else OverlayStyle()


def overlay_to_dict(ov: Overlay) -> dict:
    d = {
        "id": ov.id, "kind": ov.kind, "text": ov.text,
        "anchor": [ov.anchor[0], ov.anchor[1]], "anchor_mode": ov.anchor_mode,
        "tail_target": (None if ov.tail_target is None
                        else [ov.tail_target[0], ov.tail_target[1]]),
        "z": ov.z, "role": ov.role,
        "style": _overlay_style_to_dict(ov.style),
    }
    if ov.text_style is not None:
        d["text_style"] = text_style_to_dict(ov.text_style)  # reuse existing helper
    return d


def overlay_from_dict(d: dict) -> Overlay:
    anchor = tuple(d["anchor"])
    tt = d.get("tail_target")
    text_style = None
    if d.get("text_style") is not None:
        text_style = text_style_from_dict(d["text_style"])  # reuse existing helper
    return Overlay(
        id=d["id"], kind=d["kind"], text=d.get("text", ""),
        anchor=(float(anchor[0]), float(anchor[1])),
        anchor_mode=d.get("anchor_mode", "center"),
        tail_target=(None if tt is None else (float(tt[0]), float(tt[1]))),
        z=int(d.get("z", 0)), role=d.get("role", ""),
        text_style=text_style,
        style=_overlay_style_from_dict(d.get("style", {})),
    )
```

> If `schema.py` has no `text_style_to_dict`/`text_style_from_dict` helpers, replace those two calls with `dataclasses.asdict(ov.text_style)` and `TextStyle(**_filtered(d["text_style"], TextStyle))` respectively. If there is no `_filtered` helper for dataclasses, construct directly with the known fields. Inspect the existing `region_*` (de)serializers first and match their idiom exactly.

Then wire `overlays` into the page-level (de)serialization: locate where `PageSpec.regions` is written/read (in `schema.py` or `project_io.py`) and add the parallel `overlays` handling:
- serialize: `d["overlays"] = [overlay_to_dict(o) for o in page.overlays]`
- deserialize: `overlays=[overlay_from_dict(o) for o in d.get("overlays", [])]`

Add an `OVERLAY_JSON_SCHEMA` fragment alongside `REGION_JSON_SCHEMA` describing the overlay object (kind enum, required `id`/`kind`/`text`/`anchor`), and reference it from the page schema's properties (`"overlays": {"type": "array", "items": OVERLAY_JSON_SCHEMA}`).

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_schema.py -q`
Expected: PASS. Full suite green (expect 244).

- [ ] **Step 5: Commit**

```bash
git add core/layout/schema.py tests/layout/test_overlay_schema.py
git commit -m "feat(layout): serialize Overlay/OverlayStyle + PageSpec.overlays round-trip"
```

---

### Task 6: Renderer overlay pass (measure → balloons → draw)

**Files:**
- Modify: `core/layout/qt_renderer.py`
- Test: `tests/layout/test_overlay_render.py` (create — basic render smoke; full pixel assertions in Task 7)

**Interfaces:**
- Consumes: `Overlay`/`OverlayStyle` (`core.layout.models`); `overlay_to_segments` (`core.layout.balloons`); `effective_text_style` (`core.layout.styles`); the existing `region_to_painter_path` segment-handling logic.
- Produces:
  - `segments_to_painter_path(segments) -> QPainterPath` — shared helper extracted from `region_to_painter_path` (the move/line/quad/cubic/close switch), reused by both regions and overlays.
  - `_add_overlay(scene, ov, project_style, base_z)` — measures wrapped text, sizes `inner`, builds the body via `overlay_to_segments`, draws body fill+stroke and the wrapped text clipped to the body. SFX → text only.
  - `render_page_to_image`/`build_scene` iterate `page.overlays` (sorted by `z`) after regions.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_overlay_render.py`:

```python
from core.layout.models import PageSpec, Overlay, OverlayStyle
from core.layout import qt_renderer


def test_speech_overlay_renders_body_and_text(qapp):
    page = PageSpec(page_size_px=(200, 160), background="#FFFFFF")
    page.overlays.append(Overlay(
        id="b1", kind="speech", text="Hello there friend",
        anchor=(100.0, 70.0), tail_target=(100.0, 150.0),
        style=OverlayStyle(fill="#FFFFFF", stroke_px=3.0, stroke_color="#000000")))
    img = qt_renderer.render_page_to_image(page)
    assert img.width() == 200 and img.height() == 160
    # a black stroked outline pixel exists somewhere on the body perimeter
    found_stroke = any(
        qt_renderer_pixel_is_dark(img, x, y)
        for x in range(40, 160) for y in range(40, 110)
    )
    assert found_stroke


def qt_renderer_pixel_is_dark(img, x, y):
    c = img.pixelColor(x, y)
    return c.red() < 80 and c.green() < 80 and c.blue() < 80


def test_overlays_render_count_and_kinds(qapp):
    page = PageSpec(page_size_px=(200, 200), background="#FFFFFF")
    page.overlays.append(Overlay(id="cap", kind="caption", text="Narration",
                                 anchor=(10.0, 10.0), anchor_mode="topleft"))
    page.overlays.append(Overlay(id="sfx", kind="sfx", text="BOOM", anchor=(120.0, 120.0)))
    img = qt_renderer.render_page_to_image(page)
    assert img.width() == 200 and img.height() == 200  # renders without error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_render.py -q`
Expected: FAIL — `render_page_to_image` ignores `page.overlays`, so no stroked body renders and `found_stroke` is False.

- [ ] **Step 3: Implement the overlay pass**

In `core/layout/qt_renderer.py`:

1. **Extract** the segment→path switch from `region_to_painter_path` into a module-level helper, and call it from `region_to_painter_path`:

```python
def segments_to_painter_path(segments) -> "QPainterPath":
    from PySide6.QtGui import QPainterPath
    path = QPainterPath()
    for seg in segments:
        if seg.type == "move":
            path.moveTo(*seg.pts[0])
        elif seg.type == "line":
            path.lineTo(*seg.pts[0])
        elif seg.type == "quad":
            (cx, cy), (ex, ey) = seg.pts
            path.quadTo(cx, cy, ex, ey)
        elif seg.type == "cubic":
            (c1x, c1y), (c2x, c2y), (ex, ey) = seg.pts
            path.cubicTo(c1x, c1y, c2x, c2y, ex, ey)
        elif seg.type == "close":
            path.closeSubpath()
    return path
```

2. **Add** the overlay renderer:

```python
def _add_overlay(scene, ov, project_style, base_z):
    from PySide6.QtCore import Qt, QRectF
    from PySide6.QtGui import QFont, QColor, QPen, QBrush, QFontMetricsF
    from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsTextItem
    from core.layout.balloons import overlay_to_segments
    from core.layout.styles import effective_text_style

    # resolve text style (kind default role when ov.role is empty)
    role = ov.role or {"speech": "dialogue", "thought": "dialogue",
                       "caption": "caption", "sfx": "sfx"}.get(ov.kind, "dialogue")
    ts = effective_text_style(_overlay_as_styleable(ov, role), project_style)

    font = QFont(ts.family[0] if ts and ts.family else "DejaVu Sans",
                 ts.size_px if ts else 16)
    if ts and ts.italic:
        font.setItalic(True)
    fm = QFontMetricsF(font)
    max_w = max(20.0, ov.style.max_width_px)
    rect = fm.boundingRect(QRectF(0, 0, max_w, 100000),
                           int(Qt.TextWordWrap), ov.text)
    text_w, text_h = rect.width(), rect.height()
    pad = ov.style.padding_px
    inner_w, inner_h = text_w + 2 * pad, text_h + 2 * pad

    ax, ay = ov.anchor
    if ov.anchor_mode == "center":
        ix, iy = ax - inner_w / 2.0, ay - inner_h / 2.0
    else:
        ix, iy = ax, ay
    inner = (ix, iy, inner_w, inner_h)

    z = base_z + ov.z
    segs = overlay_to_segments(ov.kind, inner, ov.tail_target, ov.style)
    body_item = None
    if segs:
        path = segments_to_painter_path(segs)
        body_item = QGraphicsPathItem(path)
        body_item.setBrush(QBrush(QColor(ov.style.fill)))
        if ov.style.stroke_px > 0:
            body_item.setPen(QPen(QColor(ov.style.stroke_color), ov.style.stroke_px))
        else:
            body_item.setPen(QPen(Qt.NoPen))
        body_item.setZValue(z)
        body_item.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)
        scene.addItem(body_item)

    text_item = QGraphicsTextItem(ov.text, parent=body_item)
    text_item.setFont(font)
    if ts:
        text_item.setDefaultTextColor(QColor(ts.color))
    text_item.setTextWidth(text_w)
    text_item.setPos(ix + pad, iy + pad)
    text_item.setZValue(z + 0.1)
    if body_item is None:           # sfx (no body): add text directly
        scene.addItem(text_item)
```

3. Add the small adapter `_overlay_as_styleable(ov, role)` so `effective_text_style` (which expects a region-like object with `.text_style` and `.role`) can resolve overlay styling. The simplest correct adapter returns a lightweight object exposing `text_style=ov.text_style` and `role=role`:

```python
class _OverlayStyleable:
    __slots__ = ("text_style", "role")
    def __init__(self, text_style, role):
        self.text_style = text_style
        self.role = role


def _overlay_as_styleable(ov, role):
    return _OverlayStyleable(ov.text_style, role)
```

> Verify `effective_text_style`'s exact attribute access (it reads `region.text_style` then `region.role`); the adapter must expose those two names. If it reads additional attributes, add them to `__slots__` with sensible values.

4. In `render_page_to_image`/`build_scene`, after the region loop, add:

```python
    base_z = (max((r.z for r in page.regions), default=0) + 1000)
    for ov in sorted(page.overlays, key=lambda o: o.z):
        _add_overlay(scene, ov, project_style, base_z)
```

(`project_style` is whatever the surrounding function already resolves for region text; reuse it. If the function signature doesn't have it, pass `None` — `effective_text_style` already handles `None`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_render.py -q`
Expected: PASS (2 passed). Full suite green (expect 246). If `region_to_painter_path` now delegates to `segments_to_painter_path`, re-run the existing renderer tests to confirm no regression: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q`.

- [ ] **Step 5: Commit**

```bash
git add core/layout/qt_renderer.py tests/layout/test_overlay_render.py
git commit -m "feat(layout): renderer overlay pass (measure, balloon body+tail, wrapped text)"
```

---

### Task 7: Integration — all four overlay kinds render with correct layering

**Files:**
- Test: `tests/layout/test_overlay_render.py` (extend)

**Interfaces:**
- Consumes: `render_page_to_image` (`core.layout.qt_renderer`); `PageSpec`/`Overlay`/`OverlayStyle` (`core.layout.models`).

- [ ] **Step 1: Write the failing test**

Append to `tests/layout/test_overlay_render.py`:

```python
def _is_white(img, x, y):
    c = img.pixelColor(x, y)
    return c.red() > 240 and c.green() > 240 and c.blue() > 240


def test_speech_body_fill_and_background(qapp):
    # blue page so the white balloon fill is unambiguous
    page = PageSpec(page_size_px=(220, 180), background="#1144CC")
    page.overlays.append(Overlay(
        id="b", kind="speech", text="Hello there friend, how are you",
        anchor=(110.0, 70.0), tail_target=(110.0, 165.0),
        style=OverlayStyle(fill="#FFFFFF", stroke_px=3.0)))
    img = qt_renderer.render_page_to_image(page)
    assert _is_white(img, 110, 70)              # inside the balloon body -> white fill
    assert not _is_white(img, 5, 5)             # page corner -> blue background
    # tail extends downward toward the target (a non-background pixel below the body)
    assert any(not (img.pixelColor(110, y).blue() > 200 and img.pixelColor(110, y).red() < 80)
               for y in range(110, 160))


def test_overlay_z_order_higher_on_top(qapp):
    page = PageSpec(page_size_px=(200, 200), background="#FFFFFF")
    page.overlays.append(Overlay(id="low", kind="caption", text="LOW",
                                 anchor=(60.0, 60.0), anchor_mode="topleft", z=0,
                                 style=OverlayStyle(fill="#FF0000")))
    page.overlays.append(Overlay(id="high", kind="caption", text="HIGH",
                                 anchor=(70.0, 70.0), anchor_mode="topleft", z=5,
                                 style=OverlayStyle(fill="#00AA00")))
    img = qt_renderer.render_page_to_image(page)
    # in the overlap region the higher-z (green) overlay wins
    c = img.pixelColor(95, 95)
    assert c.green() > c.red()


def test_caption_and_sfx_render(qapp):
    page = PageSpec(page_size_px=(200, 120), background="#FFFFFF")
    page.overlays.append(Overlay(id="cap", kind="caption", text="Meanwhile...",
                                 anchor=(8.0, 8.0), anchor_mode="topleft",
                                 style=OverlayStyle(fill="#FFFFAA")))
    page.overlays.append(Overlay(id="sfx", kind="sfx", text="KRAK", anchor=(150.0, 60.0)))
    img = qt_renderer.render_page_to_image(page)
    # caption box has its yellow fill
    c = img.pixelColor(20, 20)
    assert c.red() > 200 and c.green() > 200 and c.blue() < 200
```

- [ ] **Step 2: Run test to verify it fails / passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_render.py -q`
Per TDD this is an integration gate over already-built APIs; it should PASS if Tasks 1–6 are correct. If any assertion fails, it localizes a real defect (most likely the `inner` sizing/anchor math in `_add_overlay`, the fill brush, or the z-base). Fix the offending earlier code — do NOT weaken the assertions.

- [ ] **Step 3: (No new implementation expected)**

This task is the integration gate. If `test_speech_body_fill_and_background` fails on the tail check, verify the speech tail is spliced toward a *downward* target (Task 3) and that the body fill brush covers the interior. If `test_overlay_z_order_higher_on_top` fails, verify `base_z + ov.z` ordering and that overlays are iterated `sorted(by z)` after regions.

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_overlay_render.py -q`
Expected: PASS. Then the FULL suite: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` → all green (expect 249).

- [ ] **Step 5: Commit**

```bash
git add tests/layout/test_overlay_render.py
git commit -m "test(layout): overlay kinds render with fill, tail, and z-order"
```

---

## Notes / deliberately deferred (not gaps)
- **GUI export still uses the PIL engine** (carried from #1/#2): overlays render through `qt_renderer` (live editor + Qt export) but not through `gui/layout/export_dialog.py` (PIL). Migrating export onto the Qt renderer remains the biggest cross-cutting follow-up.
- **AI designer (#4)** will emit `Overlay`s (likely from a script/LLM step); **manual editor (#5)** authors/drag-edits them and adds: tail-to-region/character snapping, SFX rotation/path-warp, and contour-aware text wrapping (text currently wraps within the inner rectangle, not the oval/cloud contour).
- **Shape-aware wrapping** is out of scope: a rounded/oval balloon wraps text within its inscribed rectangle, which is correct for the vast majority of comic balloons.
- **`balloons.py` scope:** speech (rounded-rect + spliced triangular tail), thought (circumscribing-ellipse scalloped cloud + shrinking-circle trail), caption (rectangle), sfx (text-only). Not a general vector-shape library.

## Self-Review (completed by plan author)
- **Spec coverage:** model + `PageSpec.overlays` (T1); pure balloon geometry — caption/speech body (T2), speech tail splice (T3), thought cloud + trail (T4); serialization round-trip + back-compat (T5); renderer overlay pass with auto-fit measurement, fill/stroke/tail, wrapped text, z-order, SFX-text-only (T6); integration pixels for all four kinds + layering (T7). Every design §2–§9 item and acceptance criteria 1–7 map to a task.
- **Placeholder scan:** the only intentional "find the existing idiom" instructions are in T5 (schema/page-loader names: `text_style_to_dict`/`text_style_from_dict`/`_filtered`/`page_from_dict`) and T6 (`project_style`/`effective_text_style` attribute access) — each gives the exact requirement and a concrete fallback, not a TODO. No stub/placeholder code remains in any task.
- **Type/name consistency:** `Overlay(id,kind,text,anchor,anchor_mode,tail_target,z,role,text_style,style)`, `OverlayStyle(fill,stroke_px,stroke_color,padding_px,radius_px,max_width_px)`, `overlay_to_segments(kind,inner,tail_target,style)`, `caption_body(inner)`, `speech_body(inner,*,radius)`, `thought_body(inner,*,scallop)`, `thought_trail(body_center,target,*,count)`, `segments_to_painter_path(segments)`, `overlay_to_dict`/`overlay_from_dict` are used identically across tasks; `inner` is consistently (x,y,w,h) text-box+padding; `PathSegment(type=…, pts=…)` matches #1's model.
- **Test interpreter/baseline:** all tasks use `.venv_linux/bin/python` under `QT_QPA_PLATFORM=offscreen`; suite counts step 222 → 249 across tasks (5+5+4+4+4+2+3 new tests = 27).
```
