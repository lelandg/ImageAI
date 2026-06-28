"""Pure (Qt-free) panel operations for the manual editor: split / merge / delete.

A region is reduced to an open-ring polygon, transformed with
``polygon.clip_halfplane`` / ``polygon.union_polygons``, and rebuilt as a
``polygon`` Region. Curved path regions (quad/cubic) are unsupported and yield
None so callers degrade gracefully — never crash, never corrupt the model.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from core.layout.models import Region
from core.layout.polygon import (
    Poly, Point, clip_halfplane, union_polygons, ensure_orientation, signed_area,
)

logger = logging.getLogger(__name__)

Rect = Tuple[int, int, int, int]
_AREA_EPS = 1.0  # sq-px tolerance for the merge area-conservation check


def region_to_polygon(region: Region) -> Optional[Poly]:
    """Open-ring polygon for a region, or None if unsupported/degenerate.

    rect -> 4 bbox corners; polygon -> its points; path with only move/line/close
    -> ordered anchor points; path with any quad/cubic -> None (curved).
    """
    if region.shape == "rect":
        x, y, w, h = region.bbox
        return [(float(x), float(y)), (float(x + w), float(y)),
                (float(x + w), float(y + h)), (float(x), float(y + h))]
    if region.shape == "polygon":
        if len(region.points) < 3:
            return None
        return [(float(px), float(py)) for px, py in region.points]
    if region.shape == "path":
        poly: Poly = []
        for seg in region.segments:
            if seg.type in ("quad", "cubic"):
                return None
            if seg.type in ("move", "line"):
                px, py = seg.pts[0]
                poly.append((float(px), float(py)))
            # close -> contributes no point
        return poly if len(poly) >= 3 else None
    return None


def _poly_bbox(poly: Poly) -> Rect:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x0, y0 = min(xs), min(ys)
    return (round(x0), round(y0), round(max(xs) - x0), round(max(ys) - y0))


def _region_from_polygon(template: Region, poly: Poly, *, id: str) -> Region:
    """Build a polygon Region from ``poly``, copying identity/style from template."""
    return Region(
        id=id,
        kind=template.kind,
        shape="polygon",
        bbox=_poly_bbox(poly),
        points=[(round(px), round(py)) for px, py in poly],
        bleed=template.bleed,
        z=template.z,
        name=template.name,
        role=template.role,
        text_style=template.text_style,
        image_style=template.image_style,
    )


def split_region(region: Region, a: Point, b: Point) -> Optional[Tuple[Region, Region]]:
    """Cut ``region`` by the line through a->b into two polygon regions.

    Returns ``(left, right)`` — ``left`` is the half on the LEFT of a->b, ``right``
    the other half (clip with the cut reversed). Returns None if the region is
    curved/unsupported or the cut misses (either side has < 3 vertices). The input
    region is never mutated. New ids are ``f"{region.id}_a"`` / ``f"{region.id}_b"``.
    """
    poly = region_to_polygon(region)
    if poly is None:
        return None
    poly = ensure_orientation(poly)
    left = clip_halfplane(poly, a, b)
    right = clip_halfplane(poly, b, a)
    if len(left) < 3 or len(right) < 3:
        return None
    return (
        _region_from_polygon(region, left, id=f"{region.id}_a"),
        _region_from_polygon(region, right, id=f"{region.id}_b"),
    )
