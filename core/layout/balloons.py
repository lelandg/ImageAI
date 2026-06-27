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
        body = speech_body(inner, radius=style.radius_px)
        if tail_target is None:
            return body
        base_width = max(8.0, min(inner[2], inner[3]) * 0.35)
        return _splice_speech_tail(body, inner, tail_target, base_width, style.radius_px)
    if kind == "thought":
        # Implemented in Task 4; until then fall back to a plain body so callers
        # never crash. Replaced by thought_body + trail in Task 4.
        return speech_body(inner, radius=style.radius_px)
    logger.warning("Overlay has unknown kind %r; no body", kind)
    return []
