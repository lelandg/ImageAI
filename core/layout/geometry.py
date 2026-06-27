"""Pure geometry helpers for path-based regions (no Qt dependency)."""
from __future__ import annotations

import math
from typing import List, Tuple

from core.layout.models import PathSegment

_EXPECTED_PTS = {"move": 1, "line": 1, "quad": 2, "cubic": 3, "close": 0}


def validate_segments(segments: List[PathSegment]) -> List[str]:
    """Return a list of problem descriptions; empty list means valid."""
    if not segments:
        return ["empty segment list"]
    issues: List[str] = []
    if segments[0].type != "move":
        issues.append("path must start with a 'move' segment")
    for i, seg in enumerate(segments):
        expected = _EXPECTED_PTS.get(seg.type)
        if expected is None:
            issues.append(f"segment {i}: unknown type {seg.type!r}")
            continue
        if len(seg.pts) != expected:
            issues.append(
                f"segment {i}: {seg.type} expects {expected} point(s), got {len(seg.pts)}"
            )
        for (px, py) in seg.pts:
            if not (math.isfinite(px) and math.isfinite(py)):
                issues.append(f"segment {i}: non-finite coordinate")
                break
    return issues


def segments_bbox(segments: List[PathSegment]) -> Tuple[float, float, float, float]:
    """Bounding box (x, y, w, h) of all segment points.

    For curves this uses the control points, i.e. a safe superset of the visual
    extent. bbox is positioning-only, never used for clipping, so the superset is
    acceptable.
    """
    xs: List[float] = []
    ys: List[float] = []
    for seg in segments:
        for (px, py) in seg.pts:
            xs.append(px)
            ys.append(py)
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
