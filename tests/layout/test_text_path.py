from core.layout.models import PathSegment
from core.layout.text_path import validate_text_path, default_text_path, glyph_offsets


def _mq(x0=0.0, y0=0.0, cx=50.0, cy=-20.0, x1=100.0, y1=0.0):
    return [PathSegment(type="move", pts=[(x0, y0)]),
            PathSegment(type="quad", pts=[(cx, cy), (x1, y1)])]


def test_validate_accepts_move_quad():
    assert validate_text_path(_mq()) == []


def test_validate_rejects_wrong_shapes():
    assert validate_text_path([]) != []
    assert validate_text_path(_mq() + [PathSegment(type="close", pts=[])]) != []
    assert validate_text_path([PathSegment(type="move", pts=[(0, 0)]),
                               PathSegment(type="line", pts=[(10, 0)])]) != []
    assert validate_text_path([PathSegment(type="quad", pts=[(1, 1), (2, 2)])]) != []


def test_validate_rejects_non_finite():
    bad = _mq(cx=float("nan"))
    assert validate_text_path(bad) != []


def test_default_text_path_geometry():
    segs = default_text_path((500.0, 300.0), 400.0)
    assert validate_text_path(segs) == []
    (sx, sy) = segs[0].pts[0]
    (cx, cy), (ex, ey) = segs[1].pts
    assert (sx, sy) == (300.0, 300.0)
    assert (ex, ey) == (700.0, 300.0)
    assert cx == 500.0
    # peak defaults to 12% of chord; control sits at 2x the peak above the chord
    assert abs(cy - (300.0 - 2 * 0.12 * 400.0)) < 1e-9


def test_default_text_path_explicit_peak():
    segs = default_text_path((0.0, 0.0), 200.0, peak_px=10.0)
    assert segs[1].pts[0][1] == -20.0


def test_glyph_offsets_center_symmetric():
    # Three glyphs of width 10 on a path of length 100, centered:
    # total 30, start 35 -> midpoints at 40, 50, 60.
    offs = glyph_offsets([10.0, 10.0, 10.0], 100.0, "center")
    assert offs == [40.0, 50.0, 60.0]


def test_glyph_offsets_left_right():
    assert glyph_offsets([10.0, 10.0], 100.0, "left") == [5.0, 15.0]
    assert glyph_offsets([10.0, 10.0], 100.0, "right") == [85.0, 95.0]


def test_glyph_offsets_letter_spacing_monotonic():
    offs = glyph_offsets([10.0, 10.0, 10.0], 100.0, "left", letter_spacing=4.0)
    assert offs == [5.0, 19.0, 33.0]
    assert all(b > a for a, b in zip(offs, offs[1:]))


def test_glyph_offsets_overflow_not_truncated():
    # Text longer than the path: offsets run past the ends instead of clamping.
    offs = glyph_offsets([60.0, 60.0], 100.0, "center")
    assert offs[0] < 30.0 + 1e-9
    assert offs[-1] > 100.0 - 30.0 - 1e-9
    assert len(offs) == 2
