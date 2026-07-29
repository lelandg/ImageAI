"""Pure helpers for text-on-a-curve overlays (no Qt).

The curve is a single open quadratic Bézier: segments == [move, quad].
Glyph layout math lives here so it is unit-testable without a QApplication;
the Qt renderer maps the resulting arc-length offsets onto the painter path.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from core.layout.geometry import validate_segments
from core.layout.models import PathSegment


def validate_text_path(segments: List[PathSegment]) -> List[str]:
    """Problems for an overlay text path; [] means valid.

    v1 contract: exactly one 'move' followed by one 'quad' (open path).
    """
    issues = validate_segments(segments or [])
    if issues:
        return issues
    if (len(segments) != 2 or segments[0].type != "move"
            or segments[1].type != "quad"):
        return ["text path must be exactly M + Q (one open quadratic Bézier)"]
    return []


def default_text_path(anchor: Tuple[float, float], chord_w: float,
                      peak_px: Optional[float] = None) -> List[PathSegment]:
    """Seed a gentle upward arch centred on ``anchor``.

    ``peak_px`` is the visual rise of the curve's midpoint above the chord
    (defaults to 12% of the chord). The quad control point sits at twice the
    peak because a quadratic Bézier's midpoint lies halfway to the control.
    """
    ax, ay = anchor
    w = max(40.0, float(chord_w))
    peak = w * 0.12 if peak_px is None else float(peak_px)
    return [
        PathSegment(type="move", pts=[(ax - w / 2.0, ay)]),
        PathSegment(type="quad", pts=[(ax, ay - 2.0 * peak), (ax + w / 2.0, ay)]),
    ]


def glyph_offsets(advances: List[float], path_len: float, align: str,
                  letter_spacing: float = 0.0) -> List[float]:
    """Arc-length distance of each glyph's advance midpoint along the path.

    ``advances`` are per-glyph advance widths (spaces included). Offsets may
    run past [0, path_len] when the text is longer than the curve; the caller
    extrapolates along the end tangents rather than truncating.
    """
    total = sum(advances) + letter_spacing * max(0, len(advances) - 1)
    if align == "left":
        start = 0.0
    elif align == "right":
        start = path_len - total
    else:  # center: default for curved text (incl. "justify", meaningless here)
        start = (path_len - total) / 2.0
    out: List[float] = []
    d = start
    for adv in advances:
        out.append(d + adv / 2.0)
        d += adv + letter_spacing
    return out
