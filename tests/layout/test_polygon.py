from core.layout.polygon import (
    signed_area, ensure_orientation, clip_halfplane, polygon_to_segments,
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
