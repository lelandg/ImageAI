from core.layout.models import Region, PathSegment
from core.layout import qt_renderer


def test_rect_region_path_matches_bbox(qapp):
    r = Region(id="r", kind="image", shape="rect", bbox=(10, 20, 30, 40))
    p = qt_renderer.region_to_painter_path(r)
    b = p.boundingRect()
    assert (round(b.x()), round(b.y()), round(b.width()), round(b.height())) == (10, 20, 30, 40)


def test_polygon_region_path_matches_points(qapp):
    r = Region(id="r", kind="image", shape="polygon", points=[(0, 0), (50, 0), (25, 40)])
    b = qt_renderer.region_to_painter_path(r).boundingRect()
    assert (round(b.x()), round(b.y()), round(b.width()), round(b.height())) == (0, 0, 50, 40)


def test_path_region_builds_from_segments(qapp):
    segs = [PathSegment(type="move", pts=[(0.0, 0.0)]),
            PathSegment(type="line", pts=[(60.0, 0.0)]),
            PathSegment(type="line", pts=[(30.0, 50.0)]),
            PathSegment(type="close", pts=[])]
    b = qt_renderer.region_to_painter_path(
        Region(id="r", kind="image", shape="path", segments=segs)).boundingRect()
    assert (round(b.x()), round(b.y()), round(b.width()), round(b.height())) == (0, 0, 60, 50)


def test_invalid_segments_fall_back_to_bbox(qapp):
    # cubic with too few points -> invalid -> bbox rect
    segs = [PathSegment(type="move", pts=[(0.0, 0.0)]),
            PathSegment(type="cubic", pts=[(1.0, 1.0)])]
    r = Region(id="r", kind="image", shape="path", segments=segs, bbox=(5, 5, 20, 20))
    b = qt_renderer.region_to_painter_path(r).boundingRect()
    assert (round(b.x()), round(b.y()), round(b.width()), round(b.height())) == (5, 5, 20, 20)
