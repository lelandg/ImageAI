from core.layout.polygon import (
    signed_area, ensure_orientation, clip_halfplane, polygon_to_segments, inset_polygon,
)


SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]  # positive area in screen coords


def test_signed_area_positive_for_canonical_square():
    assert signed_area(SQUARE) == 100.0


def test_ensure_orientation_flips_negative():
    rev = list(reversed(SQUARE))
    assert signed_area(rev) == -100.0
    fixed = ensure_orientation(rev)
    assert signed_area(fixed) == 100.0


def test_ensure_orientation_keeps_positive():
    assert ensure_orientation(SQUARE) == SQUARE


def test_clip_halfplane_keeps_left_half():
    # vertical line downward through x=5: a=(5,0)->b=(5,10); left of downward is x<5
    clipped = clip_halfplane(SQUARE, (5.0, 0.0), (5.0, 10.0))
    xs = sorted({round(x, 3) for x, _ in clipped})
    assert xs == [0.0, 5.0]  # west half only
    assert abs(signed_area(clipped)) == 50.0


def test_clip_halfplane_other_side_by_reversing():
    clipped = clip_halfplane(SQUARE, (5.0, 10.0), (5.0, 0.0))  # reversed -> east half
    xs = sorted({round(x, 3) for x, _ in clipped})
    assert xs == [5.0, 10.0]


def test_polygon_to_segments_round_trip_shape():
    segs = polygon_to_segments([(1.0, 2.0), (3.0, 2.0), (2.0, 5.0)])
    assert [s.type for s in segs] == ["move", "line", "line", "close"]
    assert segs[0].pts == [(1.0, 2.0)]
    assert segs[1].pts == [(3.0, 2.0)]
    assert segs[2].pts == [(2.0, 5.0)]
    assert segs[3].pts == []


def test_inset_square_uniform():
    sq = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    out = inset_polygon(sq, [1.0, 1.0, 1.0, 1.0])
    xs = sorted({round(x, 3) for x, _ in out})
    ys = sorted({round(y, 3) for _, y in out})
    assert xs == [1.0, 9.0]
    assert ys == [1.0, 9.0]


def test_inset_square_per_edge_distances():
    # edges: 0:(0,0)->(10,0) top, 1:(10,0)->(10,10) right, 2:(10,10)->(0,10) bottom, 3:(0,10)->(0,0) left
    sq = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    out = inset_polygon(sq, [2.0, 1.0, 2.0, 1.0])  # top/bottom in 2, left/right in 1
    xs = sorted({round(x, 3) for x, _ in out})
    ys = sorted({round(y, 3) for _, y in out})
    assert xs == [1.0, 9.0]   # left/right edges moved 1
    assert ys == [2.0, 8.0]   # top/bottom edges moved 2


def test_inset_concave_L_keeps_reflex():
    # L-shape (concave): 6 vertices, positive area
    L = [(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (4.0, 4.0), (4.0, 10.0), (0.0, 10.0)]
    out = inset_polygon(L, [1.0] * 6)
    assert out is not None
    assert len(out) == 6                      # still an L (one reflex vertex)
    assert signed_area(out) > 0
    assert signed_area(out) < signed_area(L)  # shrunk


def test_inset_collapse_returns_none():
    sq = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]
    assert inset_polygon(sq, [3.0, 3.0, 3.0, 3.0]) is None  # 3+3 > 4 each axis -> collapse


def test_inset_large_dist_on_short_edge_not_falsely_collapsed():
    # 10x2 rectangle; a big inset (1.2) on a short (len-2) edge still leaves
    # plenty of width -> must NOT collapse (the old heuristic wrongly dropped this).
    rect = [(0.0, 0.0), (10.0, 0.0), (10.0, 2.0), (0.0, 2.0)]
    out = inset_polygon(rect, [0.5, 1.2, 0.5, 0.6])
    assert out is not None
    assert signed_area(out) > 0
