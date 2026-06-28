"""Pure (Qt-free) overlay operations: stranded-anchor detection + reposition.

When a regions-only redesign replaces the panels, pixel-anchored overlays can be
left floating over empty space. These helpers detect that (anchor outside every
region's bbox) and move the anchor onto the nearest region's bbox center.
Deterministic; never mutates input regions.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from core.layout.models import Overlay, Region, PageSpec

logger = logging.getLogger(__name__)

Point = Tuple[float, float]


def _bbox_contains(bbox, x: float, y: float) -> bool:
    bx, by, bw, bh = bbox
    return bx <= x <= bx + bw and by <= y <= by + bh


def _bbox_center(bbox) -> Point:
    bx, by, bw, bh = bbox
    return (bx + bw / 2.0, by + bh / 2.0)


def overlay_anchor_stranded(ov: Overlay, regions: List[Region]) -> bool:
    """True if the overlay's anchor lies outside every region's bbox."""
    ax, ay = ov.anchor
    return not any(_bbox_contains(r.bbox, ax, ay) for r in regions)


def nearest_region_center(point: Point, regions: List[Region]) -> Optional[Point]:
    """bbox center of the region whose center is nearest ``point`` (None if empty)."""
    if not regions:
        return None
    px, py = point
    best = None
    best_d2 = None
    for r in regions:
        cx, cy = _bbox_center(r.bbox)
        d2 = (cx - px) ** 2 + (cy - py) ** 2
        if best_d2 is None or d2 <= best_d2:
            best_d2 = d2
            best = (cx, cy)
    return best


def reposition_stranded_overlays(page: PageSpec) -> int:
    """Move every stranded overlay's anchor to the nearest region center.

    Returns the number of overlays moved. No-op (0) when the page has no regions
    or no overlays. Logs a summary when it moves any.
    """
    regions = list(page.regions)
    if not regions or not page.overlays:
        return 0
    moved = 0
    for ov in page.overlays:
        if overlay_anchor_stranded(ov, regions):
            target = nearest_region_center(ov.anchor, regions)
            if target is not None:
                ov.anchor = target
                moved += 1
    if moved:
        logger.info("repositioned %d stranded overlay(s) onto nearest panels", moved)
    return moved
