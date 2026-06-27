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
