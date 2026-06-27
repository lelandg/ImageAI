# Comic Layout — Tiling Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A pure, dependency-free page-partition engine that divides a page into a gap-free tiling of panels (any-angle slice tree, concave cell-merge) and creates every gutter by per-edge inset, emitting `shape="path"` `Region`s that sub-project #1's renderer draws unchanged.

**Architecture:** Two new pure modules. `core/layout/polygon.py` holds straight-edge polygon math (half-plane clip, per-edge inset, edge-cancellation union, polygon→segments). `core/layout/tiling.py` holds a `Split`/`Leaf` slice-tree model and `tile()` which runs partition→merge→inset, plus preset trees and `apply_tiling()`. No Qt in either module; no renderer changes.

**Tech Stack:** Python 3.12, pytest. Reuses `PathSegment`/`Region` (`core/layout/models.py`), `validate_segments`/`segments_bbox` (`core/layout/geometry.py`), and #1's `qt_renderer`/`schema` for the integration tests only. Renderer/serialization tests run headless under `QT_QPA_PLATFORM=offscreen`.

## Global Constraints

- Test interpreter: `.venv_linux/bin/python`. Run tests with `QT_QPA_PLATFORM=offscreen` (required for the Qt integration test; harmless for pure tests).
- Full layout suite must stay green: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` (currently **195 passed** on branch `feat/comic-layout-geometry-core`).
- **No new third-party dependency** — all polygon math is hand-rolled in `core/layout/polygon.py`.
- `core/layout/polygon.py` and `core/layout/tiling.py` must be **Qt-free** (importable headless).
- **All errors logged** (platform-independent `logging.getLogger(__name__)`): disconnected merge groups, collapsed/too-thin panels, and clamped degenerate cuts are logged, never crash.
- Output regions use `shape="path"` + `segments`; every emitted region must pass `validate_segments` and round-trip through `core/layout/schema.py`. No renderer edits.
- Coordinates are page pixels (floats). Use a shared `EPS = 1e-9` for geometric predicates and quantize to 3 decimals (`_q`) before edge cancellation.
- Conventional Commits (`feat(layout): …`). Commit after each task.
- **Branch:** continue on `feat/comic-layout-geometry-core` (all 5 comic-layout sub-projects share one branch). **Do NOT open a pull request** — the single PR comes only after sub-project #5.

---

### Task 1: `polygon.py` foundation — orientation, half-plane clip, segments

**Files:**
- Create: `core/layout/polygon.py`
- Test: `tests/layout/test_polygon.py` (create)

**Interfaces:**
- Consumes: `PathSegment` from `core.layout.models`.
- Produces:
  - `Point = Tuple[float, float]`, `Poly = List[Point]` (open ring — no repeated closing vertex).
  - `signed_area(poly: Poly) -> float`
  - `ensure_orientation(poly: Poly) -> Poly` (returns a copy with positive signed area)
  - `clip_halfplane(poly: Poly, a: Point, b: Point) -> Poly` (keeps the sub-polygon on the left of directed line a→b; may return `[]`)
  - `polygon_to_segments(poly: Poly) -> List[PathSegment]`

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_polygon.py`:

```python
from core.layout.polygon import (
    signed_area, ensure_orientation, clip_halfplane, polygon_to_segments,
)


SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]  # positive area in screen coords


def test_signed_area_positive_for_canonical_square():
    assert signed_area(SQUARE) == 100.0


def test_ensure_orientation_flips_negative():
    rev = list(reversed(SQUARE))
    assert signed_area(rev) == -100.0
    fixed = ensure_orientation(rev)
    assert signed_area(fixed) == 100.0


def test_ensure_orientation_keeps_positive():
    assert ensure_orientation(SQUARE) == SQUARE


def test_clip_halfplane_keeps_left_half():
    # vertical line downward through x=5: a=(5,0)->b=(5,10); left of downward is x<5
    clipped = clip_halfplane(SQUARE, (5.0, 0.0), (5.0, 10.0))
    xs = sorted({round(x, 3) for x, _ in clipped})
    assert xs == [0.0, 5.0]  # west half only
    assert abs(signed_area(clipped)) == 50.0


def test_clip_halfplane_other_side_by_reversing():
    clipped = clip_halfplane(SQUARE, (5.0, 10.0), (5.0, 0.0))  # reversed -> east half
    xs = sorted({round(x, 3) for x, _ in clipped})
    assert xs == [5.0, 10.0]


def test_polygon_to_segments_round_trip_shape():
    segs = polygon_to_segments([(1.0, 2.0), (3.0, 2.0), (2.0, 5.0)])
    assert [s.type for s in segs] == ["move", "line", "line", "close"]
    assert segs[0].pts == [(1.0, 2.0)]
    assert segs[1].pts == [(3.0, 2.0)]
    assert segs[2].pts == [(2.0, 5.0)]
    assert segs[3].pts == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_polygon.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.layout.polygon'`.

- [ ] **Step 3: Implement `polygon.py` foundation**

Create `core/layout/polygon.py`:

```python
"""Pure straight-edge polygon math for the tiling engine (no Qt).

Polygons are open rings: a list of (x, y) points with no repeated closing
vertex. "Positive signed area" is the canonical orientation; in screen
coordinates (y down) the interior then lies to the LEFT of each directed edge,
so the inward normal of edge direction (dx, dy) is (-dy, dx).
"""
from __future__ import annotations

import logging
import math
from typing import List, Optional, Tuple

from core.layout.models import PathSegment

logger = logging.getLogger(__name__)

Point = Tuple[float, float]
Poly = List[Point]

EPS = 1e-9


def signed_area(poly: Poly) -> float:
    n = len(poly)
    s = 0.0
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def ensure_orientation(poly: Poly) -> Poly:
    """Return a copy oriented to positive signed area (canonical)."""
    return list(reversed(poly)) if signed_area(poly) < 0 else list(poly)


def _cross(o: Point, a: Point, b: Point) -> float:
    """Cross product (a-o) x (b-o); >0 means b is left of ray o->a's... use as side test."""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _side(p: Point, a: Point, b: Point) -> float:
    """>0 if p is left of directed line a->b, <0 right, ~0 on the line."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def clip_halfplane(poly: Poly, a: Point, b: Point) -> Poly:
    """Sutherland-Hodgman clip: keep the part of poly on the LEFT of line a->b."""
    if not poly:
        return []
    out: Poly = []
    n = len(poly)
    for i in range(n):
        cur = poly[i]
        nxt = poly[(i + 1) % n]
        s_cur = _side(cur, a, b)
        s_nxt = _side(nxt, a, b)
        cur_in = s_cur >= -EPS
        nxt_in = s_nxt >= -EPS
        if cur_in:
            out.append(cur)
        if cur_in != nxt_in:
            denom = (s_cur - s_nxt)
            if abs(denom) > EPS:
                t = s_cur / denom
                out.append((cur[0] + t * (nxt[0] - cur[0]),
                            cur[1] + t * (nxt[1] - cur[1])))
    # drop consecutive duplicates introduced by clipping
    cleaned: Poly = []
    for p in out:
        if not cleaned or abs(p[0] - cleaned[-1][0]) > EPS or abs(p[1] - cleaned[-1][1]) > EPS:
            cleaned.append(p)
    if len(cleaned) >= 2 and abs(cleaned[0][0] - cleaned[-1][0]) <= EPS and abs(cleaned[0][1] - cleaned[-1][1]) <= EPS:
        cleaned.pop()
    return cleaned


def polygon_to_segments(poly: Poly) -> List[PathSegment]:
    """Convert an open-ring polygon to move/line.../close PathSegments."""
    if not poly:
        return []
    segs = [PathSegment(type="move", pts=[(float(poly[0][0]), float(poly[0][1]))])]
    for p in poly[1:]:
        segs.append(PathSegment(type="line", pts=[(float(p[0]), float(p[1]))]))
    segs.append(PathSegment(type="close", pts=[]))
    return segs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_polygon.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add core/layout/polygon.py tests/layout/test_polygon.py
git commit -m "feat(layout): polygon.py foundation — orientation, half-plane clip, segments"
```

---

### Task 2: `polygon.py` — per-edge inset

**Files:**
- Modify: `core/layout/polygon.py`
- Test: `tests/layout/test_polygon.py` (extend)

**Interfaces:**
- Consumes: `Poly`, `EPS`, `ensure_orientation`, `signed_area` (Task 1).
- Produces: `inset_polygon(poly: Poly, dists: List[float], *, miter_limit: float = 4.0) -> Optional[Poly]` — offsets edge `i` (from `poly[i]` to `poly[i+1]`) inward by `dists[i]`; returns the inset polygon, or `None` if it collapses (non-positive area / fewer than 3 vertices).

- [ ] **Step 1: Write the failing test**

Append to `tests/layout/test_polygon.py`:

```python
from core.layout.polygon import inset_polygon


def test_inset_square_uniform():
    sq = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    out = inset_polygon(sq, [1.0, 1.0, 1.0, 1.0])
    xs = sorted({round(x, 3) for x, _ in out})
    ys = sorted({round(y, 3) for _, y in out})
    assert xs == [1.0, 9.0]
    assert ys == [1.0, 9.0]


def test_inset_square_per_edge_distances():
    # edges: 0:(0,0)->(10,0) top, 1:(10,0)->(10,10) right, 2:(10,10)->(0,10) bottom, 3:(0,10)->(0,0) left
    sq = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    out = inset_polygon(sq, [2.0, 1.0, 2.0, 1.0])  # top/bottom in 2, left/right in 1
    xs = sorted({round(x, 3) for x, _ in out})
    ys = sorted({round(y, 3) for _, y in out})
    assert xs == [1.0, 9.0]   # left/right edges moved 1
    assert ys == [2.0, 8.0]   # top/bottom edges moved 2


def test_inset_concave_L_keeps_reflex():
    # L-shape (concave): 6 vertices, positive area
    L = [(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (4.0, 4.0), (4.0, 10.0), (0.0, 10.0)]
    out = inset_polygon(L, [1.0] * 6)
    assert out is not None
    assert len(out) == 6                      # still an L (one reflex vertex)
    assert signed_area(out) > 0
    assert signed_area(out) < signed_area(L)  # shrunk


def test_inset_collapse_returns_none():
    sq = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]
    assert inset_polygon(sq, [3.0, 3.0, 3.0, 3.0]) is None  # 3+3 > 4 each axis -> collapse
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_polygon.py -k inset -q`
Expected: FAIL — `ImportError: cannot import name 'inset_polygon'`.

- [ ] **Step 3: Implement `inset_polygon`**

Append to `core/layout/polygon.py`:

```python
def _unit(dx: float, dy: float) -> Tuple[float, float]:
    h = math.hypot(dx, dy)
    if h <= EPS:
        return (0.0, 0.0)
    return (dx / h, dy / h)


def _line_intersect(p1: Point, d1: Point, p2: Point, d2: Point) -> Optional[Point]:
    """Intersect line p1+t*d1 with p2+u*d2. None if (near-)parallel."""
    denom = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(denom) <= EPS:
        return None
    t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / denom
    return (p1[0] + t * d1[0], p1[1] + t * d1[1])


def inset_polygon(poly: Poly, dists: List[float], *, miter_limit: float = 4.0) -> Optional[Poly]:
    """Offset each edge inward by dists[i]; return inset polygon or None on collapse.

    Edge i runs poly[i] -> poly[i+1]. Inward normal (positive orientation,
    screen coords) is (-dy, dx). New vertex i is the intersection of the offset
    lines of edge i-1 and edge i (miter join); a near-parallel pair falls back to
    the offset point (bevel-equivalent). Returns None if the result is degenerate.
    """
    poly = ensure_orientation(poly)
    n = len(poly)
    if n < 3 or len(dists) != n:
        return None
    # offset line per edge: a point on it + its direction
    off_pt: List[Point] = []
    off_dir: List[Point] = []
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        dx, dy = q[0] - p[0], q[1] - p[1]
        ux, uy = _unit(dx, dy)
        nx, ny = -uy, ux  # inward normal for positive-area poly in screen coords
        d = dists[i]
        off_pt.append((p[0] + nx * d, p[1] + ny * d))
        off_dir.append((dx, dy))
    out: Poly = []
    for i in range(n):
        prev = (i - 1) % n
        pt = _line_intersect(off_pt[prev], off_dir[prev], off_pt[i], off_dir[i])
        if pt is None:
            pt = off_pt[i]  # parallel consecutive edges -> use offset point
        else:
            # crude miter clamp: if the join shot far from the original vertex, bevel to offset point
            ox, oy = poly[i]
            if math.hypot(pt[0] - ox, pt[1] - oy) > miter_limit * (max(dists) + EPS):
                pt = off_pt[i]
        out.append(pt)
    # collapse guards
    if len(out) < 3 or signed_area(out) <= EPS:
        return None
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_polygon.py -k inset -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add core/layout/polygon.py tests/layout/test_polygon.py
git commit -m "feat(layout): per-edge polygon inset (miter join, collapse guard)"
```

---

### Task 3: `polygon.py` — edge-cancellation union

**Files:**
- Modify: `core/layout/polygon.py`
- Test: `tests/layout/test_polygon.py` (extend)

**Interfaces:**
- Consumes: `Poly`, `EPS`, `ensure_orientation` (Task 1).
- Produces: `union_polygons(polys: List[Poly]) -> List[Poly]` — unions edge-sharing polygons by directed-edge cancellation (with colinear-overlap subdivision); returns one ring per connected component (positive orientation). Quantizes vertices to 3 decimals so shared vertices match.

- [ ] **Step 1: Write the failing test**

Append to `tests/layout/test_polygon.py`:

```python
from core.layout.polygon import union_polygons


def test_union_two_adjacent_squares_is_rectangle():
    left = [(0.0, 0.0), (5.0, 0.0), (5.0, 10.0), (0.0, 10.0)]
    right = [(5.0, 0.0), (10.0, 0.0), (10.0, 10.0), (5.0, 10.0)]
    rings = union_polygons([left, right])
    assert len(rings) == 1
    ring = rings[0]
    xs = sorted({round(x, 3) for x, _ in ring})
    ys = sorted({round(y, 3) for _, y in ring})
    assert xs == [0.0, 10.0] and ys == [0.0, 10.0]
    assert len(ring) == 4  # the shared interior edge is gone


def test_union_makes_concave_L():
    # bottom wide strip + top-left square -> L shape
    bottom = [(0.0, 6.0), (10.0, 6.0), (10.0, 10.0), (0.0, 10.0)]
    topleft = [(0.0, 0.0), (4.0, 0.0), (4.0, 6.0), (0.0, 6.0)]
    rings = union_polygons([bottom, topleft])
    assert len(rings) == 1
    assert len(rings[0]) == 6  # L-shape has 6 vertices (one reflex)


def test_union_partial_shared_edge():
    # right cell is shorter than left's full edge -> partial colinear overlap
    left = [(0.0, 0.0), (5.0, 0.0), (5.0, 10.0), (0.0, 10.0)]
    right = [(5.0, 0.0), (10.0, 0.0), (10.0, 5.0), (5.0, 5.0)]
    rings = union_polygons([left, right])
    assert len(rings) == 1
    assert abs(_area(rings[0]) - 75.0) < 1e-6  # 50 + 25


def test_union_disconnected_returns_two_rings():
    a = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    b = [(8.0, 8.0), (10.0, 8.0), (10.0, 10.0), (8.0, 10.0)]
    rings = union_polygons([a, b])
    assert len(rings) == 2


def _area(poly):
    from core.layout.polygon import signed_area
    return abs(signed_area(poly))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_polygon.py -k union -q`
Expected: FAIL — `ImportError: cannot import name 'union_polygons'`.

- [ ] **Step 3: Implement `union_polygons`**

Append to `core/layout/polygon.py`:

```python
def _q(p: Point) -> Point:
    return (round(p[0], 3), round(p[1], 3))


def _colinear_between(a: Point, b: Point, p: Point) -> bool:
    """True if p is colinear with a-b and strictly between a and b."""
    cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    if abs(cross) > 1e-6:
        return False
    dot = (p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])
    if dot <= EPS:
        return False
    l2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
    return dot < l2 - EPS


def _subdivide(edges: List[Tuple[Point, Point]]) -> List[Tuple[Point, Point]]:
    """Split each edge at any other edge's endpoint that lies on it (colinear)."""
    pts = set()
    for a, b in edges:
        pts.add(a)
        pts.add(b)
    out: List[Tuple[Point, Point]] = []
    for a, b in edges:
        cuts = [p for p in pts if _colinear_between(a, b, p)]
        cuts.sort(key=lambda p: (p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2)
        chain = [a] + cuts + [b]
        for i in range(len(chain) - 1):
            out.append((chain[i], chain[i + 1]))
    return out


def union_polygons(polys: List[Poly]) -> List[Poly]:
    """Union edge-sharing polygons via directed-edge cancellation.

    Returns one positively-oriented ring per connected component. Vertices are
    quantized to 3 decimals so shared edges match exactly.
    """
    edges: List[Tuple[Point, Point]] = []
    for poly in polys:
        ring = [_q(p) for p in ensure_orientation(poly)]
        n = len(ring)
        for i in range(n):
            edges.append((ring[i], ring[(i + 1) % n]))
    edges = _subdivide(edges)
    # cancel exact opposite duplicates
    from collections import Counter
    counts: Counter = Counter(edges)
    survivors: List[Tuple[Point, Point]] = []
    for e in counts:
        a, b = e
        opp = (b, a)
        net = counts[e] - counts.get(opp, 0)
        for _ in range(max(0, net)):
            survivors.append(e)
    # chain survivors into rings
    from collections import defaultdict
    starts = defaultdict(list)
    for e in survivors:
        starts[e[0]].append(e)
    rings: List[Poly] = []
    used = set()
    for e0 in survivors:
        if id(e0) in used:
            continue
        ring: Poly = []
        cur = e0
        guard = 0
        while True:
            guard += 1
            if guard > len(survivors) + 5:
                break
            used.add(id(cur))
            ring.append(cur[0])
            nexts = [e for e in starts[cur[1]] if id(e) not in used]
            if not nexts:
                break
            cur = nexts[0]
            if cur is e0 or cur[1] == e0[0] and id(cur) == id(e0):
                break
            if cur[0] == e0[0]:
                ring.append(cur[0])
                used.add(id(cur))
                break
        if len(ring) >= 3:
            rings.append(ensure_orientation(ring))
    return rings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_polygon.py -k union -q`
Expected: PASS (4 passed). If the chaining `guard`/termination misbehaves on a case, fix the loop so each connected component yields exactly one closed ring (the tests pin the expected ring counts and areas).

- [ ] **Step 5: Commit**

```bash
git add core/layout/polygon.py tests/layout/test_polygon.py
git commit -m "feat(layout): edge-cancellation polygon union (colinear subdivision)"
```

---

### Task 4: `tiling.py` — slice-tree model + `tile()` partition + per-edge inset

**Files:**
- Create: `core/layout/tiling.py`
- Test: `tests/layout/test_tiling.py` (create)

**Interfaces:**
- Consumes: `clip_halfplane`, `inset_polygon`, `polygon_to_segments`, `Poly` (`core/layout/polygon.py`); `Region` (`core/layout/models.py`); `segments_bbox` (`core/layout/geometry.py`).
- Produces:
  - `@dataclass Split(axis: Literal["x","y"], at: float, a: Node, b: Node, skew: float = 0.0)`
  - `@dataclass Leaf(id: str, kind: Literal["image","text"]="image", bleed: bool=False, merge: Optional[str]=None)`
  - `Node = Union[Split, Leaf]`
  - `tile(tree: Node, page_rect: Tuple[float,float,float,float], *, gutter: float, margin: float) -> List[Region]` (this task: no merge yet — every leaf is its own panel)

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_tiling.py`:

```python
from core.layout.tiling import Split, Leaf, tile


def _bbox(region):
    return tuple(round(v) for v in __import__("core.layout.geometry", fromlist=["segments_bbox"]).segments_bbox(region.segments))


def test_single_leaf_full_page_has_margin():
    tree = Leaf(id="only")
    regions = tile(tree, (0, 0, 100, 100), gutter=10, margin=8)
    assert len(regions) == 1
    x, y, w, h = _bbox(regions[0])
    # all four edges are page boundary -> inset by margin (8) on each side
    assert (x, y, w, h) == (8, 8, 84, 84)


def test_grid_2x2_gutters_and_margin():
    # vertical split into left/right, each split into top/bottom
    col = lambda pfx: Split(axis="y", at=0.5, a=Leaf(id=pfx + "t"), b=Leaf(id=pfx + "b"))
    tree = Split(axis="x", at=0.5, a=col("L"), b=col("R"))
    regions = {r.id: _bbox(r) for r in tile(tree, (0, 0, 100, 100), gutter=10, margin=10)}
    assert len(regions) == 4
    # left-top panel: left/top edges are page border (margin 10), right/bottom are interior (gutter/2 = 5)
    # page split at x=50, y=50 -> Lt cell is (0,0,50,50); inset L/T by 10, R/B by 5
    assert regions["Lt"] == (10, 10, 35, 35)   # x:10..45, y:10..45
    assert regions["Rb"] == (55, 55, 35, 35)   # mirror
    # gutter between Lt and Rt = (55 - 45) = 10 == gutter
    assert regions["Rt"][0] - (regions["Lt"][0] + regions["Lt"][2]) == 10


def test_angled_cut_produces_non_axis_aligned_edge():
    tree = Split(axis="x", at=0.5, a=Leaf(id="L"), b=Leaf(id="R"), skew=0.5)
    regions = {r.id: r for r in tile(tree, (0, 0, 100, 100), gutter=8, margin=8)}
    left = regions["L"]
    # the shared (interior) edge is slanted: its two endpoints differ in x
    xs = sorted({round(p.pts[0][0], 2) for p in left.segments if p.pts})
    assert max(xs) - min(xs) > 1.0  # not a single vertical line -> angled
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_tiling.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.layout.tiling'`.

- [ ] **Step 3: Implement the model + partition + inset (no merge)**

Create `core/layout/tiling.py`:

```python
"""Page-partition (tiling) engine: slice tree -> gap-free panels -> inset gutters.

Pure (no Qt). Emits shape="path" Regions rendered by the geometry/render core.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple, Union

from core.layout.geometry import segments_bbox
from core.layout.models import Region
from core.layout.polygon import (
    Poly, clip_halfplane, inset_polygon, polygon_to_segments, EPS,
)

logger = logging.getLogger(__name__)

Rect = Tuple[float, float, float, float]  # (x, y, w, h)
_CUT_EPS = 1e-3


@dataclass
class Split:
    axis: Literal["x", "y"]   # "x" = vertical cut (left/right); "y" = horizontal (top/bottom)
    at: float                 # fraction (0,1) of the cell bbox along the axis
    a: "Node"                 # left / top child
    b: "Node"                 # right / bottom child
    skew: float = 0.0         # [-1,1]; angled gutter


@dataclass
class Leaf:
    id: str
    kind: Literal["image", "text"] = "image"
    bleed: bool = False
    merge: Optional[str] = None


Node = Union[Split, Leaf]


def _cut_line(cell: Poly, split: Split) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    xs = [p[0] for p in cell]
    ys = [p[1] for p in cell]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    at = min(max(split.at, _CUT_EPS), 1 - _CUT_EPS)
    skew = max(-1.0, min(1.0, split.skew))
    if split.axis == "x":
        x = minx + at * (maxx - minx)
        dx = skew * (maxx - minx) * 0.5
        return ((x + dx, miny), (x - dx, maxy))  # downward-directed: left of it is the 'a' (west) half
    else:
        y = miny + at * (maxy - miny)
        dy = skew * (maxy - miny) * 0.5
        return ((minx, y + dy), (maxx, y - dy))  # rightward-directed: left of it is the 'a' (north) half


def _collect_leaves(node: Node, cell: Poly, out: List[Tuple[Leaf, Poly]]) -> None:
    if isinstance(node, Leaf):
        if len(cell) >= 3:
            out.append((node, cell))
        else:
            logger.warning("Tiling: leaf %s produced a degenerate cell; dropped", node.id)
        return
    if not isinstance(node, Split):
        raise ValueError(f"Tiling: unknown node type {type(node)!r}")
    if node.a is None or node.b is None:
        raise ValueError("Tiling: Split must have both children")
    a, b = _cut_line(cell, node)
    _collect_leaves(node.a, clip_halfplane(cell, a, b), out)
    _collect_leaves(node.b, clip_halfplane(cell, b, a), out)


def _edge_is_boundary(p: Tuple[float, float], q: Tuple[float, float], rect: Rect) -> bool:
    rx, ry, rw, rh = rect
    sides = ((0, rx), (0, rx + rw), (1, ry), (1, ry + rh))
    for coord, val in sides:
        if abs(p[coord] - val) <= _CUT_EPS and abs(q[coord] - val) <= _CUT_EPS:
            return True
    return False


def _inset_dists(panel: Poly, rect: Rect, *, gutter: float, margin: float, bleed: bool) -> List[float]:
    n = len(panel)
    dists: List[float] = []
    for i in range(n):
        p, q = panel[i], panel[(i + 1) % n]
        if _edge_is_boundary(p, q, rect):
            dists.append(0.0 if bleed else margin)
        else:
            dists.append(gutter / 2.0)
    return dists


def _panel_to_region(panel: Poly, leaf: Leaf, rect: Rect, *, gutter: float, margin: float, z: int) -> Optional[Region]:
    dists = _inset_dists(panel, rect, gutter=gutter, margin=margin, bleed=leaf.bleed)
    inset = inset_polygon(panel, dists)
    if inset is None:
        logger.warning("Tiling: panel %s too thin for gutter; dropped", leaf.id)
        return None
    segs = polygon_to_segments(inset)
    bx, by, bw, bh = (round(v) for v in segments_bbox(segs))
    return Region(id=leaf.id, kind=leaf.kind, shape="path", segments=segs,
                  bleed=leaf.bleed, bbox=(bx, by, bw, bh), z=z)


def tile(tree: Node, page_rect: Rect, *, gutter: float, margin: float) -> List[Region]:
    """Partition page_rect by the slice tree and inset each leaf into a Region."""
    rx, ry, rw, rh = page_rect
    page_poly: Poly = [(rx, ry), (rx + rw, ry), (rx + rw, ry + rh), (rx, ry + rh)]
    leaves: List[Tuple[Leaf, Poly]] = []
    _collect_leaves(tree, page_poly, leaves)
    regions: List[Region] = []
    z = 0
    for leaf, cell in leaves:
        r = _panel_to_region(cell, leaf, page_rect, gutter=gutter, margin=margin, z=z)
        if r is not None:
            regions.append(r)
            z += 1
    return regions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_tiling.py -q`
Expected: PASS (3 passed). If `test_grid_2x2` bbox numbers are off by rounding, confirm the cut is exactly at x=50/y=50 and the inset distances are margin=10 (boundary) / gutter/2=5 (interior) — the expected boxes follow directly.

- [ ] **Step 5: Commit**

```bash
git add core/layout/tiling.py tests/layout/test_tiling.py
git commit -m "feat(layout): tiling slice-tree model + tile() partition + per-edge inset"
```

---

### Task 5: `tiling.py` — concave cell-merge + bleed

**Files:**
- Modify: `core/layout/tiling.py` (route merged leaves through `union_polygons`)
- Test: `tests/layout/test_tiling.py` (extend)

**Interfaces:**
- Consumes: `union_polygons` (`core/layout/polygon.py`); everything from Task 4.
- Produces: `tile(...)` now merges leaves sharing a `merge` key into one concave panel (inheriting the first such leaf's `id`/`kind`/`bleed`); a disconnected merge group is logged and left unmerged. Signature unchanged.

- [ ] **Step 1: Write the failing test**

Append to `tests/layout/test_tiling.py`:

```python
from core.layout.geometry import segments_bbox


def test_merge_group_forms_one_concave_panel():
    # 3 cells; merge top-left + bottom (full width) into an L; top-right stays.
    # layout: top tier split L/R; bottom tier full width.
    top = Split(axis="x", at=0.5, a=Leaf(id="tl", merge="hero"), b=Leaf(id="tr"))
    tree = Split(axis="y", at=0.5, a=top, b=Leaf(id="bottom", merge="hero"))
    regions = {r.id: r for r in tile(tree, (0, 0, 100, 100), gutter=6, margin=6)}
    # merged panel takes the first-encountered merged leaf's id ("tl"); "bottom" is absorbed
    assert "tl" in regions and "bottom" not in regions and "tr" in regions
    assert len(regions) == 2
    hero = regions["tl"]
    # concave L panel has more than 4 vertices (move + N lines + close)
    line_pts = [s for s in hero.segments if s.type == "line"]
    assert len(line_pts) >= 5  # L-shape -> >=6 vertices total


def test_bleed_leaf_boundary_edges_reach_page_rect():
    tree = Split(axis="x", at=0.5, a=Leaf(id="L", bleed=True), b=Leaf(id="R"))
    regions = {r.id: r for r in tile(tree, (0, 0, 100, 100), gutter=10, margin=10)}
    lx, ly, lw, lh = (round(v) for v in segments_bbox(regions["L"].segments))
    # bleed: left/top/bottom boundary edges NOT inset (reach 0,0 and y=0..100); only the
    # interior right edge insets by gutter/2 (5).
    assert lx == 0 and ly == 0
    assert lh == 100
    assert lx + lw == 45  # 50 (cut) - 5 (interior gutter/2)


def test_disconnected_merge_is_logged_and_unmerged(caplog):
    import logging
    # two non-adjacent cells share a merge key -> cannot union -> stay separate
    top = Split(axis="x", at=0.5, a=Leaf(id="tl", merge="x"), b=Leaf(id="tr"))
    tree = Split(axis="y", at=0.5, a=top, b=Split(axis="x", at=0.5, a=Leaf(id="bl"), b=Leaf(id="br", merge="x")))
    with caplog.at_level(logging.ERROR):
        regions = {r.id: r for r in tile(tree, (0, 0, 100, 100), gutter=6, margin=6)}
    # tl and br are diagonal (not edge-adjacent) -> union yields 2 rings -> unmerged
    assert "tl" in regions and "br" in regions
    assert any("merge" in rec.message.lower() for rec in caplog.records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_tiling.py -k "merge or bleed" -q`
Expected: FAIL — current `tile()` ignores `merge` (emits `tl` and `bottom` separately; `test_merge_group_forms_one_concave_panel` fails).

- [ ] **Step 3: Implement merge in `tile()`**

In `core/layout/tiling.py`, add the import and replace the `tile` function body. Update the import line:

```python
from core.layout.polygon import (
    Poly, clip_halfplane, inset_polygon, polygon_to_segments, union_polygons, EPS,
)
```

Replace `tile` with:

```python
def tile(tree: Node, page_rect: Rect, *, gutter: float, margin: float) -> List[Region]:
    """Partition page_rect, merge cells sharing a merge key, then inset each panel."""
    rx, ry, rw, rh = page_rect
    page_poly: Poly = [(rx, ry), (rx + rw, ry), (rx + rw, ry + rh), (rx, ry + rh)]
    leaves: List[Tuple[Leaf, Poly]] = []
    _collect_leaves(tree, page_poly, leaves)

    # Build the panel list: each entry is (representative_leaf, panel_polygon).
    panels: List[Tuple[Leaf, Poly]] = []
    consumed_groups: set = set()
    # group polygons by merge key, preserving first-encounter order
    groups: dict = {}
    order: List[Optional[str]] = []
    for leaf, cell in leaves:
        key = leaf.merge
        if key is None:
            order.append(id(leaf))
            groups[id(leaf)] = (leaf, [cell])
        else:
            if key not in groups:
                groups[key] = (leaf, [])
                order.append(key)
            groups[key][1].append(cell)

    for key in order:
        rep_leaf, cells = groups[key]
        if len(cells) == 1:
            panels.append((rep_leaf, cells[0]))
            continue
        rings = union_polygons(cells)
        if len(rings) == 1:
            panels.append((rep_leaf, rings[0]))
        else:
            logger.error("Tiling: merge group %r is disconnected (%d pieces); leaving unmerged",
                         key, len(rings))
            for ring in rings:
                panels.append((rep_leaf, ring))

    regions: List[Region] = []
    z = 0
    for leaf, panel in panels:
        r = _panel_to_region(panel, leaf, page_rect, gutter=gutter, margin=margin, z=z)
        if r is not None:
            regions.append(r)
            z += 1
    return regions
```

Note: when a disconnected merge falls back to multiple rings they reuse `rep_leaf.id`; that is acceptable for the logged error path (the caller's tree was malformed). For the connected case each merge group yields exactly one region.

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_tiling.py -q`
Expected: PASS (all tiling tests). Then the full suite:
`QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` → green.

- [ ] **Step 5: Commit**

```bash
git add core/layout/tiling.py tests/layout/test_tiling.py
git commit -m "feat(layout): concave cell-merge + bleed in the tiling engine"
```

---

### Task 6: `tiling.py` — presets + `apply_tiling`

**Files:**
- Modify: `core/layout/tiling.py`
- Test: `tests/layout/test_tiling_apply.py` (create)

**Interfaces:**
- Consumes: `tile`, `Split`, `Leaf` (Tasks 4–5); `PageSpec`, `Region` (`core/layout/models.py`); `validate_segments` (`core/layout/geometry.py`); `region_to_dict`/`region_from_dict` (`core/layout/schema.py`).
- Produces:
  - `grid(rows: int, cols: int, *, kind="image", prefix="p") -> Node`
  - `three_tiers() -> Node`, `splash_with_strip() -> Node`, `diagonal_action() -> Node`, `feature_L() -> Node`
  - `apply_tiling(page: PageSpec, tree: Node, *, gutter: float, margin: float, floating: Tuple[Region, ...]=()) -> PageSpec` — sets `page.regions = tiled + list(floating)` with floating at higher z; returns `page`.

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_tiling_apply.py`:

```python
from core.layout.models import PageSpec, Region
from core.layout.tiling import grid, three_tiers, diagonal_action, feature_L, apply_tiling, tile
from core.layout.geometry import validate_segments
from core.layout.schema import region_to_dict, region_from_dict


def test_grid_preset_counts():
    assert len(tile(grid(2, 3), (0, 0, 120, 90), gutter=6, margin=6)) == 6


def test_named_presets_build_and_tile():
    for tree in (three_tiers(), diagonal_action(), feature_L()):
        regions = tile(tree, (0, 0, 200, 300), gutter=8, margin=10)
        assert regions  # non-empty
        for r in regions:
            assert r.shape == "path"
            assert validate_segments(r.segments) == []  # every emitted region is a valid path


def test_emitted_regions_round_trip_through_schema():
    regions = tile(grid(2, 2), (0, 0, 100, 100), gutter=6, margin=6)
    for r in regions:
        r2 = region_from_dict(region_to_dict(r))
        assert r2.shape == "path"
        assert [s.type for s in r2.segments] == [s.type for s in r.segments]


def test_apply_tiling_seeds_regions_and_layers_floating():
    page = PageSpec(page_size_px=(100, 100))
    floating = (Region(id="float1", kind="image", bbox=(20, 20, 30, 30)),)
    out = apply_tiling(page, grid(2, 2), gutter=6, margin=6, floating=floating)
    ids = [r.id for r in out.regions]
    assert "float1" in ids
    base = [r for r in out.regions if r.id != "float1"]
    fl = [r for r in out.regions if r.id == "float1"][0]
    # floating is layered on top: its z exceeds every base panel's z
    assert fl.z > max(r.z for r in base)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_tiling_apply.py -q`
Expected: FAIL — `ImportError: cannot import name 'grid'` (presets/apply not defined yet).

- [ ] **Step 3: Implement presets + `apply_tiling`**

Append to `core/layout/tiling.py` (add `PageSpec` to the models import: `from core.layout.models import Region, PageSpec`):

```python
def grid(rows: int, cols: int, *, kind: Literal["image", "text"] = "image", prefix: str = "p") -> Node:
    """A regular rows x cols grid (nested y-then-x splits)."""
    if rows < 1 or cols < 1:
        raise ValueError("grid requires rows >= 1 and cols >= 1")

    def row(r: int) -> Node:
        def col(c: int) -> Node:
            leaf = Leaf(id=f"{prefix}{r}_{c}", kind=kind)
            if c == cols - 1:
                return leaf
            return Split(axis="x", at=1.0 / (cols - c), a=leaf, b=col(c + 1))
        return col(0)

    def build(r: int) -> Node:
        if r == rows - 1:
            return row(r)
        return Split(axis="y", at=1.0 / (rows - r), a=row(r), b=build(r + 1))

    return build(0)


def three_tiers() -> Node:
    """Three full-width horizontal tiers."""
    return Split(axis="y", at=1 / 3, a=Leaf(id="t0"),
                 b=Split(axis="y", at=0.5, a=Leaf(id="t1"), b=Leaf(id="t2")))


def splash_with_strip() -> Node:
    """A large top splash panel and a bottom strip of two."""
    return Split(axis="y", at=0.66, a=Leaf(id="splash"),
                 b=Split(axis="x", at=0.5, a=Leaf(id="s0"), b=Leaf(id="s1")))


def diagonal_action() -> Node:
    """Two panels divided by a strongly angled gutter."""
    return Split(axis="x", at=0.5, a=Leaf(id="d0"), b=Leaf(id="d1"), skew=0.6)


def feature_L() -> Node:
    """A concave L hero (top-left + bottom strip merged) beside a tall right panel."""
    top = Split(axis="x", at=0.6, a=Leaf(id="hero", merge="L"), b=Leaf(id="side"))
    return Split(axis="y", at=0.6, a=top, b=Leaf(id="hero_b", merge="L"))


def apply_tiling(page: PageSpec, tree: Node, *, gutter: float, margin: float,
                 floating: Tuple[Region, ...] = ()) -> PageSpec:
    """Tile the page and layer floating panels on top (higher z). Mutates + returns page."""
    pw, ph = page.page_size_px
    base = tile(tree, (0, 0, pw, ph), gutter=gutter, margin=margin)
    next_z = (max((r.z for r in base), default=-1)) + 1
    layered: List[Region] = list(base)
    for r in floating:
        r.z = next_z
        next_z += 1
        layered.append(r)
    page.regions = layered
    return page
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_tiling_apply.py -q`
Expected: PASS (4 passed). Then full suite green.

- [ ] **Step 5: Commit**

```bash
git add core/layout/tiling.py tests/layout/test_tiling_apply.py
git commit -m "feat(layout): tiling presets + apply_tiling (floating layered on top)"
```

---

### Task 7: Integration — a tiled page renders through #1 with background gutters

**Files:**
- Test: `tests/layout/test_tiling_render.py` (create)

**Interfaces:**
- Consumes: `grid`, `apply_tiling` (`core/layout/tiling.py`); `PageSpec` (`core/layout/models.py`); `render_page_to_image` (`core/layout/qt_renderer.py`).

- [ ] **Step 1: Write the failing test**

Create `tests/layout/test_tiling_render.py`:

```python
from core.layout.models import PageSpec
from core.layout.tiling import grid, apply_tiling
from core.layout import qt_renderer


def test_tiled_page_renders_with_background_gutters(qapp):
    # 1x2 grid on a white page: the vertical gutter between the two panels must be background.
    page = PageSpec(page_size_px=(200, 100), background="#FFFFFF")
    apply_tiling(page, grid(1, 2), gutter=20, margin=10)
    img = qt_renderer.render_page_to_image(page)
    assert img.width() == 200 and img.height() == 100
    # center column (x=100) lies in the 20px gutter between the two panels -> background (white)
    gutter_px = img.pixelColor(100, 50)
    assert gutter_px.red() > 240 and gutter_px.green() > 240 and gutter_px.blue() > 240
    # a point inside the left panel (well left of the gutter) is within an (empty) image
    # placeholder frame, i.e. NOT the page background — the placeholder fill is grey.
    left_px = img.pixelColor(40, 50)
    assert not (left_px.red() > 240 and left_px.green() > 240 and left_px.blue() > 240)


def test_two_panels_present(qapp):
    page = PageSpec(page_size_px=(200, 100), background="#FFFFFF")
    apply_tiling(page, grid(1, 2), gutter=20, margin=10)
    assert len(page.regions) == 2
    for r in page.regions:
        assert r.shape == "path"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_tiling_render.py -q`
Expected: This test should actually **pass on first run if Tasks 1–6 are correct** (it uses only already-built APIs). Per TDD, first run it BEFORE writing it is impossible; instead, write it and confirm it passes, and if it fails, the failure localizes a real integration defect (e.g., emitted segments the renderer rejects, or panels overlapping the gutter). Treat any failure here as a bug in Tasks 1–6 to fix, not a reason to weaken the assertion.

- [ ] **Step 3: (No new implementation expected)**

This task is the integration gate: it wires `tiling` → `qt_renderer` with no new production code. If it fails, debug the offending earlier module (most likely `inset_polygon` distances or `polygon_to_segments` orientation) until the gutter is genuinely background and two valid path regions render.

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/test_tiling_render.py -q`
Expected: PASS (2 passed). Then the FULL suite:
`QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/layout/ -q` → all green (195 + the new tiling/polygon tests).

- [ ] **Step 5: Commit**

```bash
git add tests/layout/test_tiling_render.py
git commit -m "test(layout): tiled page renders through the geometry core with background gutters"
```

---

## Notes / deliberately deferred (not gaps)
- **GUI export still uses the PIL engine** (carried over from #1): a tiled page rendered via `qt_renderer` shows the new gutters, but `gui/layout/export_dialog.py` (PIL) does not. Migrating export onto the Qt renderer remains the biggest cross-cutting follow-up.
- **AI designer (#4)** will emit `Split`/`Leaf` trees (or an `svg⇄segments`-style serialization of them); **manual editor (#5)** will author/drag them and must handle segment writeback (`_writeback_move` in `qt_renderer.py` only persists bbox/points today).
- **Curved-edge tiling** is out of scope (research-grade); curves remain available for floating/bleed panels and balloons via #1.
- **`union_polygons` robustness:** targets the exact-partition inputs the tiler produces (edge-sharing cells), with 3-decimal quantization + colinear subdivision. It is not a general boolean-union library; arbitrary overlapping polygons are out of scope.

## Self-Review (completed by plan author)
- **Spec coverage:** slice-tree model + any-angle cuts (T4); cell-merge concave (T5); partition→merge→inset pipeline (T4+T5); hand-rolled pure polygon math — clip (T1), inset (T2), union (T3); per-edge inset unifying margin/gutter/bleed (T4 `_inset_dists`, bleed in T5); floating+bleed layering (T6 `apply_tiling`); presets + apply (T6); no-renderer-change integration + validate/round-trip (T6, T7). All §2–§8 spec items map to a task; acceptance criteria 1–7 each have a covering test.
- **Placeholder scan:** none — every code/test step is complete. (T7 intentionally has no new production code; its body explains the integration-gate semantics.)
- **Type/name consistency:** `Split(axis,at,a,b,skew)`, `Leaf(id,kind,bleed,merge)`, `tile(tree, page_rect, *, gutter, margin)`, `clip_halfplane`, `inset_polygon(poly, dists)`, `union_polygons`, `polygon_to_segments`, `apply_tiling(page, tree, *, gutter, margin, floating)` are used identically across tasks; `Region(shape="path", segments=…)` matches #1's model.
