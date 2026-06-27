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
    Poly, clip_halfplane, inset_polygon, polygon_to_segments, union_polygons, EPS,
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
        return ((maxx, y - dy), (minx, y + dy))  # leftward-directed: left of it is the 'a' (north/top) half


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
    """Partition page_rect, merge cells sharing a merge key, then inset each panel."""
    rx, ry, rw, rh = page_rect
    page_poly: Poly = [(rx, ry), (rx + rw, ry), (rx + rw, ry + rh), (rx, ry + rh)]
    leaves: List[Tuple[Leaf, Poly]] = []
    _collect_leaves(tree, page_poly, leaves)

    # Build the panel list: each entry is (representative_leaf, panel_polygon).
    panels: List[Tuple[Leaf, Poly]] = []
    # group polygons by merge key, preserving first-encounter order
    groups: dict = {}
    order: List[Optional[str]] = []
    for leaf, cell in leaves:
        key = leaf.merge
        if key is None:
            order.append(id(leaf))
            groups[id(leaf)] = (leaf, [(leaf, cell)])
        else:
            if key not in groups:
                groups[key] = (leaf, [])
                order.append(key)
            groups[key][1].append((leaf, cell))

    for key in order:
        rep_leaf, leaf_cells = groups[key]
        cells = [cell for _, cell in leaf_cells]
        if len(cells) == 1:
            panels.append((rep_leaf, cells[0]))
            continue
        rings = union_polygons(cells)
        if len(rings) == 1:
            panels.append((rep_leaf, rings[0]))
        else:
            logger.error("Tiling: merge group %r is disconnected (%d pieces); leaving unmerged",
                         key, len(rings))
            # fall back: emit each original cell with its own leaf identity
            for orig_leaf, orig_cell in leaf_cells:
                panels.append((orig_leaf, orig_cell))

    regions: List[Region] = []
    z = 0
    for leaf, panel in panels:
        r = _panel_to_region(panel, leaf, page_rect, gutter=gutter, margin=margin, z=z)
        if r is not None:
            regions.append(r)
            z += 1
    return regions
