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
