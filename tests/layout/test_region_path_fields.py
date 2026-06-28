from core.layout.models import Region, PathSegment


def test_region_defaults_have_empty_segments_and_no_bleed():
    r = Region(id="r", kind="image")
    assert r.shape == "rect"
    assert r.segments == []
    assert r.bleed is False


def test_region_accepts_path_shape_and_segments():
    segs = [
        PathSegment(type="move", pts=[(0.0, 0.0)]),
        PathSegment(type="line", pts=[(10.0, 0.0)]),
        PathSegment(type="cubic", pts=[(10.0, 5.0), (5.0, 10.0), (0.0, 10.0)]),
        PathSegment(type="close", pts=[]),
    ]
    r = Region(id="r", kind="image", shape="path", segments=segs, bleed=True)
    assert r.shape == "path"
    assert r.segments[2].type == "cubic"
    assert len(r.segments[2].pts) == 3
    assert r.bleed is True
