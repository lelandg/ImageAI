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
    # over-inset detection: if an edge flipped direction the cell collapsed
    for i in range(n):
        o0, o1 = poly[i], poly[(i + 1) % n]
        n0, n1 = out[i], out[(i + 1) % n]
        odx, ody = o1[0] - o0[0], o1[1] - o0[1]
        ndx, ndy = n1[0] - n0[0], n1[1] - n0[1]
        if odx * ndx + ody * ndy < 0:  # edge direction reversed
            return None
    # collapse guards
    if len(out) < 3 or signed_area(out) <= EPS:
        return None
    return out


def _q(p: Point) -> Point:
    return (round(p[0], 3), round(p[1], 3))


def _colinear_between(a: Point, b: Point, p: Point) -> bool:
    """True if p is colinear with a-b and strictly between a and b."""
    cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    # 1e-6 (looser than module EPS) is intentional: union_polygons quantizes
    # all vertices to 3 decimals first, so colinear points land exactly on the
    # line and this generous threshold never mis-classifies. Do NOT feed raw
    # (un-quantized) floats here — the tolerance assumes quantized input.
    if abs(cross) > 1e-6:
        return False
    dot = (p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])
    if dot <= EPS:
        return False
    l2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
    return dot < l2 - EPS


def _subdivide(edges: List[Tuple[Point, Point]]) -> List[Tuple[Point, Point]]:
    """Split each edge at any other edge's endpoint that lies on it (colinear)."""
    pts: set = set()
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


def _remove_colinear(ring: Poly) -> Poly:
    """Remove vertices that lie exactly on the segment between their neighbors."""
    if len(ring) < 3:
        return ring
    result = list(ring)
    changed = True
    while changed:
        changed = False
        n = len(result)
        if n < 3:
            break
        keep = []
        for i in range(n):
            prev_pt = result[(i - 1) % n]
            cur_pt = result[i]
            next_pt = result[(i + 1) % n]
            cross = ((cur_pt[0] - prev_pt[0]) * (next_pt[1] - prev_pt[1])
                     - (cur_pt[1] - prev_pt[1]) * (next_pt[0] - prev_pt[0]))
            if abs(cross) > 1e-9:
                keep.append(cur_pt)
            else:
                changed = True
        result = keep
    return result


def union_polygons(polys: List[Poly]) -> List[Poly]:
    """Union edge-sharing polygons via directed-edge cancellation.

    Returns one positively-oriented ring per connected component. Vertices are
    quantized to 3 decimals so shared edges match exactly. Only valid for
    exact-partition, edge-sharing inputs (as produced by the tiler) — not a
    general boolean-union library.
    """
    from collections import Counter, defaultdict

    # Build directed edge list with quantized vertices
    edges: List[Tuple[Point, Point]] = []
    for poly in polys:
        ring = [_q(p) for p in ensure_orientation(poly)]
        n = len(ring)
        for i in range(n):
            edges.append((ring[i], ring[(i + 1) % n]))

    # Subdivide edges at colinear partial-overlap points
    edges = _subdivide(edges)

    # Cancel exact opposite pairs — interior shared edges cancel out
    counts: Counter = Counter(edges)
    survivors: List[Tuple[Point, Point]] = []
    for e, cnt in counts.items():
        a, b = e
        opp = (b, a)
        net = cnt - counts.get(opp, 0)
        for _ in range(max(0, net)):
            survivors.append(e)

    if not survivors:
        logger.warning("union_polygons: no survivor edges after cancellation")
        return []

    # Build adjacency: start_vertex -> list of edge indices
    starts: dict = defaultdict(list)
    for idx, e in enumerate(survivors):
        starts[e[0]].append(idx)

    # Chain survivors into closed rings using index-based tracking
    # (id()-based tracking is unreliable: Python may reuse tuple object ids)
    rings: List[Poly] = []
    used: set = set()  # set of survivor indices already consumed

    for start_idx, e0 in enumerate(survivors):
        if start_idx in used:
            continue

        ring: Poly = []
        cur_idx = start_idx
        guard = 0

        while True:
            guard += 1
            if guard > len(survivors) + 5:
                logger.warning("union_polygons: ring-chaining guard triggered; breaking")
                break

            used.add(cur_idx)
            cur = survivors[cur_idx]
            ring.append(cur[0])

            # Find the next unused edge whose start == cur's end
            next_vertex = cur[1]
            candidates = [i for i in starts[next_vertex] if i not in used]

            if not candidates:
                break

            # Pick the next edge; if it closes back to ring[0] we're done
            next_idx = candidates[0]
            next_edge = survivors[next_idx]

            if next_edge[0] == e0[0]:
                # Ring would close here — mark it used and stop
                used.add(next_idx)
                break

            cur_idx = next_idx

        if len(ring) >= 3:
            ring = _remove_colinear(ring)
            if len(ring) >= 3:
                rings.append(ensure_orientation(ring))

    return rings
