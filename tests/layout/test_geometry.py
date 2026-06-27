from core.layout.models import PathSegment
from core.layout.geometry import validate_segments, segments_bbox


def _triangle():
    return [
        PathSegment(type="move", pts=[(0.0, 0.0)]),
        PathSegment(type="line", pts=[(10.0, 0.0)]),
        PathSegment(type="line", pts=[(5.0, 8.0)]),
        PathSegment(type="close", pts=[]),
    ]


def test_valid_path_has_no_issues():
    assert validate_segments(_triangle()) == []


def test_empty_is_invalid():
    assert validate_segments([]) == ["empty segment list"]


def test_must_start_with_move():
    segs = [PathSegment(type="line", pts=[(1.0, 1.0)])]
    assert any("must start with a 'move'" in m for m in validate_segments(segs))


def test_wrong_point_count_flagged():
    segs = [PathSegment(type="move", pts=[(0.0, 0.0)]),
            PathSegment(type="cubic", pts=[(1.0, 1.0)])]  # cubic needs 3
    assert any("cubic expects 3" in m for m in validate_segments(segs))


def test_non_finite_flagged():
    segs = [PathSegment(type="move", pts=[(0.0, float("nan"))])]
    assert any("non-finite" in m for m in validate_segments(segs))


def test_bbox_of_triangle():
    assert segments_bbox(_triangle()) == (0.0, 0.0, 10.0, 8.0)


def test_bbox_includes_cubic_control_points():
    segs = [PathSegment(type="move", pts=[(0.0, 0.0)]),
            PathSegment(type="cubic", pts=[(0.0, 20.0), (20.0, 20.0), (10.0, 0.0)])]
    # superset using control points: x in [0,20], y in [0,20]
    assert segments_bbox(segs) == (0.0, 0.0, 20.0, 20.0)
