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
